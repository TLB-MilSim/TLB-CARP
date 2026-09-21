/*
    USAFDC_fnc_steerBegin

    Hand a released load's steering job to whichever machine owns it.

    [_carrier, _cargo] call USAFDC_fnc_steerBegin

    Called by the AIRCRAFT'S OWNER when its package tracker latches RELEASED. That client
    is the only one holding all the inputs: the crew's DZ, and the pilot's own guided
    cargo settings. Every one of them goes into the job, because the machine that will
    actually fly the canopy has none of it -- USAFDC_setting_jpads* are CBA scope-0
    settings and read their defaults on a dedicated server, and USAFDC_state_dzPosASL is
    client-local. That is the third of the three reasons guided cargo did nothing on a
    server: even once the command reached the right machine, that machine had no idea
    where the drop zone was or that guided cargo was switched on at all.

    DELIVERED BY CBA_fnc_globalEventJIP, WHICH IS THE WHOLE MECHANISM

    Not a plain globalEvent, and not a hand-rolled object variable with a polling sweep
    to find it. globalEventJIP reaches every machine now AND every machine that joins
    later, which matters because a canopy takes the best part of a minute to come down.
    Keying it on a deterministic id derived from the load's netId means fn_steerTick can
    retire the entry when the job finishes without having been the publisher.

    THE JOB IS CREATED AT RELEASE, TWENTY SECONDS BEFORE THE PARACHUTE EXISTS

    USAF's fn_dropCargo waits on `getPos _obj select 2 < 300` before creating the chute,
    and CARP's own fn_releaseCargo does the same. That is fine and it is deliberate: the
    job names the LOAD, and fn_steerCargo resolves the canopy through attachedTo on every
    frame. There is nothing to wait for and nothing to race.
*/

params ["_carrier", "_cargo"];
if (isNull _cargo) exitWith {""};

// ONE JOB PER LOAD, NOT ONE PER DEPARTURE.
//
// fn_updatePackageTiming diffs the manifest and calls this for whatever left, which is
// right for a normal release and wrong for a vehicle-in-vehicle one: freeing a viv load
// takes it out of the manifest, fn_releaseCargo then attachTo`s it to the carrier for
// half a second -- putting it back in as an "attached" entry -- and the detach removes
// it again. One load, two departures, two jobs.
//
// The cost is not just a wasted publish. Each call consumes the next slot index, so the
// second load of a stick is handed slot 3 of 3 and flies to a pattern position nothing
// else is using, while the slot it should have had goes to no one.
//
// Stamped on the cargo rather than held in a list, because the object is the thing that
// can only be dropped once, and the stamp travels with it to whichever machine asks.
if (_cargo getVariable ["USAFDC_steerPublished", false]) exitWith {""};

// The crew's own switch, from the panel. With guided cargo off no job exists, so nothing
// anywhere steers -- which is what the switch means, even though the machine that would do
// the steering cannot read it. Read HERE for that reason, and shared between the seats so
// a loadmaster and a pilot cannot disagree about whether the load they drop is guided.
if !(missionNamespace getVariable ["USAFDC_state_jpadsEnabled", false]) exitWith {""};

private _dz = +(missionNamespace getVariable ["USAFDC_state_dzPosASL", []]);
if ((count _dz) < 3) exitWith {""};

// Derived from netId rather than generated, so any machine can name this job later --
// including one that has to retire it after the publisher has gone.
private _jipID = format ["USAFDC_steer_%1", netId _cargo];

// ---- where in the stick is this load, and therefore where does it aim ------------
//
// WITHOUT THIS A GUIDED STICK LANDS IN A PILE. Every load steers onto the DZ, and the
// only thing that kept them apart was jpadsScatterM -- a two-metre random jitter, sized
// for one load not fighting itself, not for four vehicles. Ballistically a stick is
// already strung out by sequenceIntervalS * groundspeed, about 82 m at 140 m/s; guiding
// them all to one point actively UNDOES that and converts a good stick into a heap.
//
// So each load gets a slot instead. Slots run ALONG the run-in, in release order, which
// is the direction the stick is already strung out in -- so each canopy flies the
// smallest correction that separates it, rather than crossing over its neighbours.
//
// HOW MANY LOADS ARE IN THIS STICK IS NOT A QUESTION THIS FUNCTION CAN ANSWER.
//
// v0.11.2 tried, by counting what was left in the hold and adding the load that had just
// gone. That is the size of the AIRCRAFT'S LOAD, not of the stick: dropping one pallet out
// of a hold of five made a stick of five, put the pallet in slot 1 of 5, and steered it
// 70 m short of the drop zone. Flown, and it is the whole reason a single guided load
// missed while the HUD said it was steering perfectly.
//
// The number belongs to whoever commanded the drop -- fn_triggerAutoDrop's _requested,
// which is the crew's own CARGO count -- and is stamped on the carrier there. Default 1,
// so a release this code did not see commanded (USAF's own action, a mission script) gets
// NO slot and aims at the drop zone. An unknown stick must cost accuracy nothing; a wrong
// offset is far worse than no offset.
private _spacing = missionNamespace getVariable ["USAFDC_setting_jpadsStickSpacingM", 35];
private _index = 0;
private _total = 1;
if (!isNull _carrier) then {
    _total = _carrier getVariable ["USAFDC_stickTotal", 1];
    // Within a stick the index advances. Ten seconds after the last release the stick is
    // over, whatever the stamp still says -- that covers a pass abandoned part-way.
    private _lastS = _carrier getVariable ["USAFDC_stickLastReleaseS", -1e9];
    if ((time - _lastS) > 10) then {
        _index = 0;
    } else {
        _index = (_carrier getVariable ["USAFDC_stickIndex", -1]) + 1;
    };
    if (_index >= _total) then {
        // More loads left than the stick was told to expect. Spreading past the end of the
        // pattern would put them progressively further downrange, so stop spreading.
        _total = 1;
    };
    _carrier setVariable ["USAFDC_stickIndex", _index, false];
    _carrier setVariable ["USAFDC_stickLastReleaseS", time, false];
};

// Centred on the DZ, so the drop zone stays the middle of the pattern rather than its
// leading edge. Along the LOCKED run-in; with no lock there is no axis to spread along
// and an empty offset lets fn_steerCargo fall back to its random scatter.
private _aimOffset = [];
if (_spacing > 0 && {_total > 1} && {USAFDC_state_runInLocked}) then {
    private _alongM = (_index - ((_total - 1) / 2)) * _spacing;
    _aimOffset = [_alongM * (sin USAFDC_state_runInDeg), _alongM * (cos USAFDC_state_runInDeg)];
};

private _job = [
    _cargo,
    _dz,
    missionNamespace getVariable ["USAFDC_setting_jpadsGlideMs", 12],
    missionNamespace getVariable ["USAFDC_setting_jpadsScatterM", 2],
    missionNamespace getVariable ["USAFDC_setting_jpadsReleaseAglM", 3],
    missionNamespace getVariable ["USAFDC_setting_jpadsEngageVzMs", 12],
    // Mission time, which is synchronised. diag_tickTime is this machine's own uptime
    // and would mean nothing to whichever machine ends up pruning the job.
    time,
    _jipID,
    // Computed here because this is the machine that knows the crew's run-in. The
    // machine that ends up flying the canopy may be a dedicated server, which has no
    // run-in and no panel.
    _aimOffset
];

_cargo setVariable ["USAFDC_steerPublished", true, true];
["USAFDC_steerBegin", [_job], _jipID] call CBA_fnc_globalEventJIP;

diag_log format [
    "[TLB CARP][JPADS] steer job published cargo=%1 carrier=%2 dz=%3 glide=%4 jip=%5 slot=%6/%7 aim=%8",
    typeOf _cargo, typeOf _carrier, _dz, _job # 2, _jipID, _index + 1, _total, _aimOffset
];
_jipID

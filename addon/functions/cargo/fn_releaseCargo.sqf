/*
    TLB_CARP_fnc_releaseCargo

    CARP's own release: ballistic fall from the ramp, canopy below 300 m AGL.

    [_carrier, _cargo, _source, _smoke] call TLB_CARP_fnc_releaseCargo

    MUST RUN WHERE THE CARGO IS LOCAL. detach, setVelocity and attachTo are all
    local-effect commands, and on a dedicated server a load that was placed in Eden,
    spawned by Zeus or driven aboard by another player is usually the server's. The
    caller remoteExecs to _cargo, exactly as USAF's own fn_canDrop does:

        [_carrier, _cargo] remoteExec ["USAF_CARGO_fnc_dropCargo", _cargo]

    That only works because fn_postInit now registers the compile table on every
    machine. Until v0.7.0 it sat behind a blanket hasInterface guard, so this function
    would have been nil on the server and the remoteExec would have resolved nothing
    at all.

    WHY THIS EXISTS AT ALL, GIVEN USAF'S RELEASE WORKS

    USAF's fn_dropCargo reads USAF_Cargo_DropPos off the carrier's config, which only
    USAF airframes have -- getArray returns [] elsewhere and `_dropPos select 0`
    throws. And its whole flow starts from the usaf_cargo array, so a load that arrived
    by ACE, by vanilla vehicle-in-vehicle or by a mission maker's attachTo is invisible
    to it. This is the same sequence, freed of both.

    IT IS THE DEFAULT AS OF v0.10.0. Through v0.9.1 a USAF airframe carrying USAF-loaded
    cargo went straight back to USAF's own canDrop, because that path is what the
    along-track calibration was measured against. That is now the fallback rather than
    the rule -- TLB_CARP_setting_useUsafRelease -- so CARP drops without the USAF mod
    present, and every behaviour the pilot sees on a drop is behaviour this project can
    fix.

    THE TIMING IS THE CALIBRATION, SO THE SEQUENCE IS COPIED RATHER THAN IMPROVED

    releaseDelayS = 0.5607 s is not physics. It is the measured script latency of
    USAF's path: the `sleep 0.5` below, plus the poll granularity around it. The attach,
    the sleep, the detach, the velocity inheritance and the 300 m canopy trigger are
    therefore reproduced in the same order with the same constants. Deviating to make
    the code nicer would move a number this project spent forty bench batches fitting.

    The two gaps left open in v0.8.0 are closed. The door wait now runs in
    fn_releaseSelected, on the commanding machine, exactly where USAF's canDrop does it
    and with USAF's own predicate. The smoke marker is reproduced below, switchable, and
    created ONCE rather than once per machine -- USAF dispatches its loop with
    `spawn BIS_fnc_MP` and no target, so every client runs a global-effect createVehicle
    and a full server stacks a shell per player.

    STILL NOT MEASURED, AND THIS IS THE ONE THING TO FLY

    releaseDelayS = 0.5607 s was measured on USAF's path. Every step that consumes time
    is reproduced here in the same order with the same constants, so it SHOULD carry --
    but reproducing a sequence is not measuring it, and this project's rule is that a
    calibration number is re-measured rather than inherited. TLB_CARP_releaseSimTime is
    stamped in mission time below and the flown record carries commandToReleaseS, so one
    drop settles it. If the two paths differ, the difference belongs in model.json as its
    own field, never folded into releaseDelayS.

    AND WHAT ACE DOES INSTEAD, FOR THE RECORD

    ace_cargo_fnc_paradropItem opens its canopy on a fixed 0.7 s timer after release,
    with no altitude test at all:

        [{ ... createVehicle "B_Parachute_02_F" ... }, _object, 0.7] call CBA_fnc_waitAndExecute

    That is the behaviour the developer guide warns about -- a canopy at aircraft
    altitude -- and
    it is why CARP runs its own release rather than delegating to ACE's.
*/

// _smoke is PASSED IN, never read from state here. This function runs where the CARGO
// is local, which on a dedicated server is the server -- a machine that has never had
// the panel open and whose TLB_CARP_state_smokeEnabled is therefore its power-on default,
// not the crew's choice. The commanding machine reads the crew's value and sends it.
// This is the same mistake guided cargo made with CBA settings in v0.8.0.
params ["_carrier", "_cargo", ["_source", ""], ["_smoke", true]];
if (isNull _carrier || {isNull _cargo}) exitWith {false};
if !(local _cargo) exitWith {
    diag_log format ["[TLB CARP][RELEASE] refused: cargo %1 is not local here", _cargo];
    false
};
if (_source isEqualTo "") then {_source = _cargo getVariable ["TLB_CARP_cargoSource", "attached"]};

// Spawned so the sleeps below are legal however this was invoked. remoteExec does not
// guarantee a scheduled environment, and the whole sequence is built on timing.
[_carrier, _cargo, _source, _smoke] spawn {
    params ["_carrier", "_cargo", "_source", "_smoke"];

    _carrier setVariable ["TLB_CARP_releaseInProgress", true, true];

    // Set by the "viv" branch below and swept after the attach. Declared here because a
    // switch case is its own scope and cannot hand a private back out of it.
    private _chutesBefore = [];

    // ---- take the load out of whatever is holding it ---------------------------
    switch (_source) do {
        case "usaf": {
            // NOTHING HERE, DELIBERATELY. USAF removes the load from usaf_cargo AFTER
            // the detach, and that is not bookkeeping pedantry: fn_sequenceCargo paces a
            // stick by waiting for the manifest to shrink, and the manifest reads
            // usaf_cargo. Clearing it up here would shrink the manifest before the load
            // had left, the next release would fire immediately, and a stick measured at
            // 0.588 s between loads would leave in one lump. See below the detach.
        };
        case "ace": {
            // ACE's own bookkeeping, in ACE's own order (fnc_paradropItem): drop it
            // from the loaded array first, then read the space left and give the
            // item's size back. Doing it the other way round double-counts.
            private _loaded = _carrier getVariable ["ace_cargo_loaded", []];
            if (_cargo in _loaded) then {
                private _size = if (isNil "ace_cargo_fnc_getSizeItem") then {0} else {_cargo call ace_cargo_fnc_getSizeItem};
                _loaded deleteAt (_loaded find _cargo);
                _carrier setVariable ["ace_cargo_loaded", _loaded, true];
                if !(isNil "ace_cargo_fnc_getCargoSpaceLeft") then {
                    _carrier setVariable ["ace_cargo_space", (_carrier call ace_cargo_fnc_getCargoSpaceLeft) + (_size max 0), true];
                };
            };
            detach _cargo;
            // ACE hides its loaded objects and attaches them 100 m below the carrier,
            // so the load is invisible and damage-blocked until this runs. Its own
            // server event does the unhide, the reposition and the damage unblock in
            // the order ACE requires -- worth using rather than reimplementing, since
            // it comments that hideObjectGlobal must precede setPos for light objects.
            ["ace_cargo_serverUnload", [_cargo, ASLToAGL (getPosASL _carrier)]] call CBA_fnc_serverEvent;
            sleep 0.1;
        };
        case "viv": {
            // THERE IS NO UNLOAD COMMAND. The engine ships canVehicleCargo,
            // enableVehicleCargo, getVehicleCargo, isVehicleCargo, setVehicleCargo and
            // vehicleCargoEnabled, and nothing else -- so a load is freed by setting its
            // TRANSPORTER to null, which is the idiom ACE's own dragging module uses:
            //
            //     if (!isNull isVehicleCargo _target && {!(objNull setVehicleCargo _target)})
            //
            // `_carrier setVehicleCargo [_cargo, false]` stood here from v0.8.0 and is
            // not a syntax the command has. It threw "Type Array, expected Object" on the
            // first drop that ever reached this branch -- which only happened in v0.13.0,
            // because until CARP could load a vehicle itself nothing ever arrived as
            // "viv" cargo. Three releases of dead code, correct-looking and untested.
            //
            // The result is checked rather than assumed: it returns false when the engine
            // refuses, and a silent false here would strand the load inside the aircraft
            // while the rest of the sequence ran as if it had left.
            // THE ENGINE GIVES AN IN-FLIGHT VIV UNLOAD ITS OWN PARACHUTE.
            //
            // That is vanilla behaviour and it is why a CARP-loaded vehicle dropped out of
            // a Blackfish appeared to open a canopy at the ramp, have it cut, fall
            // ballistic, then open a second one -- flown, v0.14.0. Only the second one was
            // ours. The first was the engine's, orphaned the moment the line below attaches
            // the load to the release offset, and left hanging in the air.
            //
            // Accuracy was never affected, which is exactly why this is easy to leave: all
            // four loads of a stick landed on target. It just looks broken.
            //
            // The chutes present BEFORE the unload are recorded so the sweep can only ever
            // delete one the engine just made. Deleting by proximity alone would take a
            // canopy belonging to a load dropped seconds earlier.
            _chutesBefore = nearestObjects [_cargo, ["ParachuteBase"], 40];
            if !(objNull setVehicleCargo _cargo) then {
                diag_log format ["[TLB CARP][RELEASE] viv unload refused for %1 -- load may be stuck aboard", typeOf _cargo];
            };
            // ---- kill the engine's canopy on the frame it appears -----------------
            //
            // Freeing a vehicle-in-vehicle load in flight makes vanilla give it a
            // parachute. The crew see it inflate at the ramp, get cut, and then our own
            // canopy open at 300 m -- three canopy events for one drop, two of them not
            // ours. Reported from the field.
            //
            // THE SWEEP EXISTED; IT WAS TOO LATE AND TOO SLOW. It was spawned AFTER the
            // whole attach / sleep 0.5 / detach sequence and polled on `sleep 0.1`, so the
            // engine's canopy was on screen for at least half a second. The comment that
            // used to sit down there said exactly that and accepted it.
            //
            // ARMED HERE, BEFORE THE TIMED SEQUENCE, AND THAT IS THE POINT. Registering it
            // between the attach and the sleep would put work inside the sequence
            // releaseDelayS was fitted against, which nothing is allowed to do. From here
            // the registration is outside it and the sequence is byte-identical.
            //
            // The handler decides for itself when deleting is SAFE: while the load is
            // still hanging from the engine's canopy, deleting that canopy leaves a state
            // nothing downstream can reason about. So it waits until the load is not
            // attached to a ParachuteBase -- which the release's own attachTo to the
            // carrier brings about a fraction of a second later -- and deletes on that
            // frame.
            //
            // PER FRAME, not a scheduled poll. Same lesson as TLB_CARP_fnc_canopyWatch: a
            // spawned loop shares three milliseconds of frame time with every other
            // script, so "check often" means "check whenever the scheduler reaches me".
            // Here that is the difference between a canopy nobody sees and one everybody
            // does.
            [{
                params ["_args", "_pfh"];
                _args params ["_cargo", "_before", "_deadline"];
                // Stop when OUR canopy is open. Deleting that one would drop the load.
                if (isNull _cargo || {time > _deadline} || {!(_cargo getVariable ["TLB_CARP_canopyPending", true])}) exitWith {
                    [_pfh] call CBA_fnc_removePerFrameHandler;
                };
                private _parent = attachedTo _cargo;
                if (!isNull _parent && {_parent isKindOf "ParachuteBase"}) exitWith {};
                {
                    if !(_x in _before) then {deleteVehicle _x};
                } forEach (nearestObjects [_cargo, ["ParachuteBase"], 40]);
            }, 0, [_cargo, _chutesBefore, time + 6]] call CBA_fnc_addPerFrameHandler;
        };
        default {
            detach _cargo;
        };
    };

    // ---- the release itself, step for step as USAF does it ---------------------
    _cargo disableCollisionWith _carrier;
    private _offset = [_carrier, _cargo] call TLB_CARP_fnc_releaseModelOffset;
    _cargo attachTo [_carrier, [_offset # 0, _offset # 1, _offset # 2]];

    sleep 0.5;
    detach _cargo;
    _cargo setVelocity (velocity _carrier);
    _cargo enableCollisionWith _carrier;


    // Stamped on the object and broadcast, in MISSION time. The existing command stamp
    // records diag_tickTime on the pilot's client, which is that machine's uptime and
    // means nothing on this one -- so a dedicated-server release could never be
    // measured end to end. Mission time is synchronised, so these two ends can be
    // subtracted.
    // USAF's order, and USAF's reason: the load is physically away, so the manifest may
    // now say so. fn_sequenceCargo is watching this.
    if (_source isEqualTo "usaf") then {
        private _list = _carrier getVariable ["usaf_cargo", []];
        _carrier setVariable ["usaf_cargo", _list - [_cargo], true];
        if ((count _list) <= 1) then {_carrier enableVehicleCargo true};
    };

    // USAF's own GetOut handler and back-pointer, left on a load it loaded. Clearing
    // them is what USAF's fn_dropCargo does last, and leaving them behind would have the
    // load still claiming a carrier it has left.
    private _getOutId = _cargo getVariable ["getoutevh", -1];
    if (_getOutId isEqualType 0 && {_getOutId >= 0}) then {
        _cargo removeEventHandler ["GetOut", _getOutId];
        _cargo setVariable ["getoutevh", nil, false];
    };
    _cargo setVariable ["carrier", nil, false];

    private _who = driver _carrier;
    if (!isNull _who) then {
        _who vehicleChat format ["%1 dropped from cargo",
            getText (configFile >> "CfgVehicles" >> typeOf _cargo >> "displayName")];
    };

    _cargo setVariable ["TLB_CARP_releaseSimTime", time, true];
    _cargo setVariable ["TLB_CARP_releasePath", "carp", true];
    _carrier setVariable ["TLB_CARP_releaseInProgress", false, true];
    diag_log format [
        "[TLB CARP][RELEASE] carp path sim=%1 cargo=%2 source=%3 offset=%4 (%5) carrierVel=%6",
        time, typeOf _cargo, _source, [_offset # 0, _offset # 1, _offset # 2], _offset # 3, velocity _carrier
    ];

    // ---- canopy -----------------------------------------------------------------
    //
    // Handed to TLB_CARP_fnc_canopyWatch, which tests the altitude on the FRAME LOOP and
    // creates the chute inline on the frame it crosses. It used to be a waitUntil right
    // here, and that is a scheduled poll: with a stick of three it slipped far enough
    // below 300 m that one load could not decelerate in time and was destroyed on
    // impact. See that function's header.
    //
    // The 0.5 s is USAF's and is kept -- it is part of the sequence releaseDelayS was
    // measured against, even though the trigger below it no longer is.
    sleep 0.5;
    [_cargo, _carrier, _smoke] call TLB_CARP_fnc_canopyWatch;
};

true

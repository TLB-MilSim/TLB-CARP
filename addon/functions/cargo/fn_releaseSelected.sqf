/*
    USAFDC_fnc_releaseSelected

    Release one load. CARP's own sequence, unless the mission asks for USAF's.

    [_carrier, _cargo] call USAFDC_fnc_releaseSelected  ->  "usaf" | "carp" | ""

    v0.10.0 FLIPPED THE DEFAULT. CARP NO LONGER DEPENDS ON THE USAF MOD TO DROP.

    Through v0.9.1 a USAF airframe carrying USAF-loaded cargo was handed straight back
    to USAF_CARGO_fnc_canDrop, because releaseDelayS = 0.5607 s was measured against
    that path and there was no reason to put a flown-validated number at risk. That
    bought safety at the price of a hard dependency: without the USAF mod loaded, the
    aircraft CARP was built for could not drop at all, and every behaviour the pilot
    sees on a drop belonged to somebody else's code.

    fn_releaseCargo now carries the whole sequence -- the doors, the attach, the
    sleep 0.5, the detach, the velocity inheritance, the canopy at 300 m AGL, the
    strobe and the smoke -- so USAF is optional rather than required.

    USAFDC_setting_useUsafRelease restores the old path. It is kept, and it is kept
    server-forced, for exactly one reason: it is the calibration reference. If a flown
    drop ever shows the two paths landing differently, that switch is how the
    difference gets measured rather than argued about.

    WHAT HAS TO MATCH, AND WHY IT IS COPIED RATHER THAN IMPROVED

    releaseDelayS is not physics. It is the measured script latency of this sequence,
    so every step that consumes time is reproduced in USAF's order with USAF's
    constants -- including the door wait, which USAF does in canDrop BEFORE handing
    off to dropCargo. On a normal drop run the ramp is already open and that wait costs
    one poll; with the ramp shut, both paths pay the same. Reproducing it is what keeps
    the two comparable.

    THE LAST-ELEMENT TEST IS NOT OPTIONAL

    USAF_CARGO_fnc_canDrop takes a CARRIER and then selects the cargo itself:

        _cargo = _cargos select (count (_cargos) - 1);

    It ignores anything it is handed. So with a mixed manifest -- say an ACE load and a
    USAF load aboard -- asking USAF to drop the USAF one is only safe while that one is
    genuinely last in usaf_cargo. When it is not, USAF would release a different object
    than the one the solver computed a release point for. Fall through to CARP's path
    in that case rather than hoping.
*/

// _dryRun answers "which path would run" without running it, so the panel can show the
// pilot what will happen without a second copy of the predicate drifting out of step
// with this one.
params ["_carrier", "_cargo", ["_dryRun", false]];
if (isNull _carrier || {isNull _cargo}) exitWith {""};

private _source = _cargo getVariable ["USAFDC_cargoSource", "attached"];
private _usafAboard = _carrier getVariable ["usaf_cargo", []];

private _useUsaf =
    (missionNamespace getVariable ["USAFDC_setting_useUsafRelease", false])
    && {!(isNil "USAF_CARGO_fnc_canDrop")}
    && {_source isEqualTo "usaf"}
    && {(count (getArray (configFile >> "CfgVehicles" >> typeOf _carrier >> "USAF_Cargo_DropPos"))) >= 3}
    && {(count _usafAboard) > 0}
    && {_cargo isEqualTo (_usafAboard select ((count _usafAboard) - 1))};

if (_useUsaf) exitWith {
    // canDrop opens the doors, waits for them, and then remoteExecs dropCargo to the
    // machine where the cargo is local. Spawned because it sleeps.
    if (!_dryRun) then {[_carrier] spawn USAF_CARGO_fnc_canDrop};
    "usaf"
};

if (_dryRun) exitWith {"carp"};

// The doors run HERE, on the machine that commanded the drop, and the cargo sequence
// runs one hop away where the cargo is local -- the same split USAF uses, so the
// latency between the command and the load leaving is the same latency that was
// measured. `animate` is global-effect, so opening them from this machine opens them
// for everyone.
// Read HERE, on the machine where a human chose it, and carried across. The far end
// cannot look it up: see the note at the top of fn_releaseCargo.
private _smoke = missionNamespace getVariable ["USAFDC_state_smokeEnabled", true];

[_carrier, _cargo, _source, _smoke] spawn {
    params ["_carrier", "_cargo", "_source", "_smoke"];

    private _doors = getArray (configFile >> "CfgVehicles" >> typeOf _carrier >> "USAF_Cargo_Doors");
    if ((count _doors) > 0) then {
        // usaf_cargo_loading is USAF's own "busy" flag and its load actions read it.
        // Setting it keeps USAF's UI honest on an airframe that has one, and costs
        // nothing on an airframe that does not.
        _carrier setVariable ["usaf_cargo_loading", true, true];
        {_carrier animate [_x, 1]} forEach _doors;
        // USAF's exact predicate, poll included. It passes on the first check when the
        // ramp is already open, which on a drop run it is.
        waitUntil {sleep 0.01; ({(_carrier animationPhase _x) isEqualTo 1} count _doors) > 0};
        _carrier setVariable ["usaf_cargo_loading", false, true];
    };

    // CARP's path runs where the CARGO is local, which on a dedicated server is usually
    // the server rather than the pilot. One hop out, the same shape as USAF's own
    // remoteExec, rather than splitting steps across machines and paying two.
    [_carrier, _cargo, _source, _smoke] remoteExec ["USAFDC_fnc_releaseCargo", _cargo];
};
"carp"

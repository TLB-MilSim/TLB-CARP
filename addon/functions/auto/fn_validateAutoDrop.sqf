params [["_requireReleaseStable", false]];

private _warnings = [];
private _fail = {
    params ["_reason", ["_warnings", []]];
    // LOGGED, not just returned. Flown 2026-09-20: a Blackfish crossed the release point
    // with the cue firing and perfect geometry, and nothing left. The RPT could show that
    // the cue fired and that fn_triggerAutoDrop never ran -- and could NOT show which of
    // the gates between them refused, because no gate said anything.
    //
    // A refusal a pilot sees as a hint and the log does not see at all is a refusal that
    // cannot be diagnosed after the flight, which is when it is always diagnosed.
    diag_log format ["[TLB CARP][AUTO] validate refused: %1 | warnings=%2 | armed=%3 latched=%4 guidance=%5 runIn=%6 mode=%7",
        _reason, _warnings,
        missionNamespace getVariable ["TLB_CARP_state_autoArmed", false],
        missionNamespace getVariable ["TLB_CARP_state_dropLatched", false],
        missionNamespace getVariable ["TLB_CARP_state_guidanceArmed", false],
        missionNamespace getVariable ["TLB_CARP_state_runInLocked", false],
        missionNamespace getVariable ["TLB_CARP_state_mode", "?"]];
    createHashMapFromArray [["valid", false], ["reason", _reason], ["warnings", +_warnings]]
};

if ((count TLB_CARP_state_dzPosASL) < 3) exitWith {["NO DZ"] call _fail};
if (!TLB_CARP_state_guidanceArmed) exitWith {["GUIDANCE NOT ARMED"] call _fail};
// A jump run releases people, not cargo, and they leave under their own power.
if (TLB_CARP_state_mode isEqualTo "JUMP") exitWith {["JUMP RUN - NO CARGO RELEASE"] call _fail};

private _carrier = objectParent player;
if (isNull _carrier) exitWith {["UNSUPPORTED AIRCRAFT"] call _fail};
private _air = [_carrier] call TLB_CARP_fnc_getAircraftState;
if !(_air getOrDefault ["valid", false]) exitWith {["UNSUPPORTED AIRCRAFT"] call _fail};
// "NO USAF CARGO" told a pilot with an ACE load aboard that he had no cargo, which is
// both wrong and unhelpful. cargoCount now comes from the manifest, which counts every
// carriage source.
if ((_air getOrDefault ["cargoCount", 0]) <= 0) exitWith {["NO CARGO ABOARD"] call _fail};
// Two busy flags, because only one of them is USAF's. The second is CARP's own, raised
// across its release so a second command cannot overlap the first.
if (_carrier getVariable ["usaf_cargo_loading", false]) exitWith {["CARGO LOADING BUSY"] call _fail};
if (_carrier getVariable ["TLB_CARP_releaseInProgress", false]) exitWith {["RELEASE IN PROGRESS"] call _fail};
if ((getPosATL _carrier # 2) <= 50) exitWith {["AIRCRAFT BELOW 50 M ATL"] call _fail};

private _solution = [_carrier] call TLB_CARP_fnc_buildWorldSolution;
if !(_solution getOrDefault ["valid", false]) exitWith {["INVALID SOLUTION"] call _fail};
private _confidence = _solution getOrDefault ["confidence", "INVALID"];
if (_confidence isEqualTo "INVALID") exitWith {["INVALID SOLUTION"] call _fail};
// INVALID above is the only confidence test left. The DEGRADED gate and its
// TLB_CARP_setting_allowDegradedAuto escape hatch are gone with the tier itself.
//
// The closed-ramp check went with them, and for its own reason rather than by
// association: since v0.10.0 the release OPENS the ramp and waits for it before the load
// moves, in fn_releaseSelected. This check runs at arm time, before any of that, so from
// v0.10.0 onward it could only ever fire on a ramp the release was about to open -- a
// false positive by construction.
if (_requireReleaseStable && {!(_solution getOrDefault ["releaseStable", false])}) exitWith {
    ["UNSTABLE RUN-IN", _warnings] call _fail
};

createHashMapFromArray [
    ["valid", true],
    ["reason", "READY"],
    ["warnings", _warnings],
    ["carrier", _carrier],
    ["aircraftState", _air],
    ["solution", _solution]
]

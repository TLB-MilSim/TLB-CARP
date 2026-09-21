/*
    USAFDC_fnc_armJumpRun

    Arm the jump run. Requires a DZ, a locked run-in, and an aircraft above the
    selected opening altitude.

    The aircraft is captured HERE and held for the life of the run. Every other CARP
    entry point resolves it as "objectParent player" on each call, which is right
    for a pilot in a seat and wrong for this: FFR's fnc_standUp calls moveOut before
    teleporting a jumper into its hidden dummy, so a standing jumper has no
    objectParent at all. Latching means the cue survives people standing up, which
    is precisely when they need it.
*/

if (USAFDC_state_jumpArmed) exitWith {hint "TLB CARP: jump run already armed"; false};

private _aircraft = objectParent player;
if (isNull _aircraft) exitWith {hint "TLB CARP: not aboard an aircraft"; false};

// ARMED-NESS BELONGS TO THE AIRFRAME, NOT TO THE CLIENT.
//
// USAFDC_state_jumpArmed above is a per-machine global, so it only ever stopped one
// person from arming twice. Two crew arming the same aircraft produced two independent
// per-frame handlers, each with its own roster snapshot, each evaluating the exit
// geometry against its own copy of the aircraft -- and a non-driver's copy is the
// extrapolated replica, so they reached GREEN at different instants. One client sent
// "green" once while the other went on sending "red" twenty times a second, leaving
// the light effectively red through the entire green window, and every jumper heard
// two overlapping countdowns.
private _armedBy = _aircraft getVariable ["USAFDC_jumpArmedBy", objNull];
if (!isNull _armedBy && {alive _armedBy} && {!(_armedBy isEqualTo player)}) exitWith {
    hint format ["TLB CARP: jump run already armed by %1", name _armedBy];
    false
};

// Stick size is snapshotted for the same reason the roster is: standing up removes a
// jumper from crew, so counting live would shrink the stick as people get up and the
// green light would creep later with each one. 0 in the setting means "count who is
// aboard", pilot excluded.
//
// Set BEFORE the probe below, which reads it. Computed after, the arm hint would
// report a stick of one on every jump.
// The crew's own number first: it is entered in the panel, it is shared, and it is the
// one a jumpmaster actually adjusts between serials. The Addon Option stays as a mission
// default, and counting the cabin stays as the answer when neither is set.
private _planned = missionNamespace getVariable ["USAFDC_state_jumpPlannedStick", 0];
private _setCount = missionNamespace getVariable ["USAFDC_setting_jumpStickCount", 0];
USAFDC_state_jumpStickCount = if (_planned >= 1) then {_planned} else {
    if (_setCount >= 1) then {_setCount} else {
        (count ((crew _aircraft) select {_x != (driver _aircraft)})) max 1
    }
};

private _probe = [_aircraft] call USAFDC_fnc_buildJumpSolution;
if !(_probe getOrDefault ["valid", false]) exitWith {
    hint format ["TLB CARP JUMP: %1", _probe getOrDefault ["reason", "unavailable"]];
    false
};

USAFDC_state_jumpAircraft = _aircraft;
// Snapshot who is aboard now, because standing up removes them from crew.
USAFDC_state_jumpRoster = crew _aircraft;
USAFDC_state_jumpArmed = true;
USAFDC_state_jumpPhase = "INBOUND";
USAFDC_state_jumpCountdownLatched = false;
USAFDC_state_jumpLastTickAnnounced = 1e9;
USAFDC_state_jumpGreenUntil = -1;
USAFDC_state_jumpGreenExitAglM = -1;
USAFDC_state_jumpGreenOffTrackM = 0;
USAFDC_state_jumpSolution = _probe;

// Claim the airframe. Global so every other client's arm attempt sees it, and so a
// jumper who boards mid-run can be told who is running the jump rather than starting
// a second one.
_aircraft setVariable ["USAFDC_jumpArmedBy", player, true];

[_aircraft, "red"] call USAFDC_fnc_setJumpLight;

if (USAFDC_state_jumpPfh >= 0) then {
    [USAFDC_state_jumpPfh] call CBA_fnc_removePerFrameHandler;
    USAFDC_state_jumpPfh = -1;
};
private _interval = missionNamespace getVariable ["USAFDC_setting_updateInterval", 0.05];
USAFDC_state_jumpPfh = [{[] call USAFDC_fnc_updateJumpCue}, _interval max 0.01, []] call CBA_fnc_addPerFrameHandler;

// Say out loud whether the physical light is available, because "no light" and
// "light stuck on red" look identical from the cargo compartment and the fix for
// the first one is FFR's Prep Ramp action.
private _hasLight = !(isNull (_aircraft getVariable ["ffr_jumplight", objNull]));
hint format [
    "TLB CARP JUMP ARMED\nexit %1 m upwind of DZ\nopen at %2 m AGL\n%4 jumpers over %5 m of track\ngreen called %6 m early to centre the stick\njumplight: %3",
    round (_probe get "exitRangeM"),
    round (_probe get "openAglM"),
    if (_hasLight) then {"FFR, driven"} else {"none -- use FFR Prep Ramp; HUD and audio only"},
    _probe get "stickCount",
    round (_probe get "stickLengthM"),
    round (_probe get "stickLeadM")
];
true

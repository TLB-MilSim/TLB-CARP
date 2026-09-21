/*
    USAFDC_fnc_disarmJumpRun

    End the jump run and put the light out.

    ["REASON"] call USAFDC_fnc_disarmJumpRun

    The light is set to "off" rather than "red", because red means "stand by, do not
    jump" to anyone on the ramp and an unarmed system should not be saying that. Off
    means the system is not running.
*/

params [["_reason", "PILOT DISARM"]];

if (USAFDC_state_jumpPfh >= 0) then {
    [USAFDC_state_jumpPfh] call CBA_fnc_removePerFrameHandler;
    USAFDC_state_jumpPfh = -1;
};

private _aircraft = USAFDC_state_jumpAircraft;
if (!isNull _aircraft) then {
    [_aircraft, "off"] call USAFDC_fnc_setJumpLight;
    // Release the airframe claim, but only if it is ours. A disarm on one client must
    // not hand the aircraft to a second armer while somebody else is still running a
    // jump on it.
    private _armedBy = _aircraft getVariable ["USAFDC_jumpArmedBy", objNull];
    if (_armedBy isEqualTo player) then {
        _aircraft setVariable ["USAFDC_jumpArmedBy", objNull, true];
    };
};

// Wipe the readout on every screen that was getting it, BEFORE the roster is cleared
// below -- after that there is nobody left to address. The readout lives on a title
// layer now (see the USAFDC_jumpHint receiver in fn_postInit), and a title layer holds
// its last frame forever, so without this the countdown's final state would sit on the
// jumpers' screens for the rest of the mission. Same audience and same mechanism as the
// readout itself, for the same reason: FFR's fnc_standUp calls moveOut, so `crew` alone
// would leave the text stuck on exactly the people standing on the ramp.
private _clearRoster = (USAFDC_state_jumpRoster select {alive _x}) + (crew _aircraft);
private _clearTargets = _clearRoster arrayIntersect _clearRoster;
if ((count _clearTargets) > 0) then {
    ["USAFDC_jumpHint", [""], _clearTargets] call CBA_fnc_targetEvent;
};

USAFDC_state_jumpArmed = false;
USAFDC_state_jumpPhase = "IDLE";
USAFDC_state_jumpCountdownLatched = false;
USAFDC_state_jumpLastTickAnnounced = 1e9;
USAFDC_state_jumpGreenUntil = -1;
USAFDC_state_jumpAircraft = objNull;
USAFDC_state_jumpRoster = [];
USAFDC_state_jumpSolution = createHashMap;
USAFDC_state_jumpDisarmReason = _reason;
true

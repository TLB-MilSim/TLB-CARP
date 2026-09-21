/*
    TLB_CARP_fnc_disarmJumpRun

    End the jump run and put the light out.

    ["REASON"] call TLB_CARP_fnc_disarmJumpRun

    The light is set to "off" rather than "red", because red means "stand by, do not
    jump" to anyone on the ramp and an unarmed system should not be saying that. Off
    means the system is not running.
*/

params [["_reason", "PILOT DISARM"]];

if (TLB_CARP_state_jumpPfh >= 0) then {
    [TLB_CARP_state_jumpPfh] call CBA_fnc_removePerFrameHandler;
    TLB_CARP_state_jumpPfh = -1;
};

private _aircraft = TLB_CARP_state_jumpAircraft;
if (!isNull _aircraft) then {
    [_aircraft, "off"] call TLB_CARP_fnc_setJumpLight;
    // Release the airframe claim, but only if it is ours. A disarm on one client must
    // not hand the aircraft to a second armer while somebody else is still running a
    // jump on it.
    private _armedBy = _aircraft getVariable ["TLB_CARP_jumpArmedBy", objNull];
    if (_armedBy isEqualTo player) then {
        _aircraft setVariable ["TLB_CARP_jumpArmedBy", objNull, true];
    };
};

// Wipe the readout on every screen that was getting it, BEFORE the roster is cleared
// below -- after that there is nobody left to address. The readout lives on a title
// layer now (see the TLB_CARP_jumpHint receiver in fn_postInit), and a title layer holds
// its last frame forever, so without this the countdown's final state would sit on the
// jumpers' screens for the rest of the mission. Same audience and same mechanism as the
// readout itself, for the same reason: FFR's fnc_standUp calls moveOut, so `crew` alone
// would leave the text stuck on exactly the people standing on the ramp.
private _clearRoster = (TLB_CARP_state_jumpRoster select {alive _x}) + (crew _aircraft);
private _clearTargets = _clearRoster arrayIntersect _clearRoster;
if ((count _clearTargets) > 0) then {
    ["TLB_CARP_jumpHint", [""], _clearTargets] call CBA_fnc_targetEvent;
};

TLB_CARP_state_jumpArmed = false;
TLB_CARP_state_jumpPhase = "IDLE";
TLB_CARP_state_jumpCountdownLatched = false;
TLB_CARP_state_jumpLastTickAnnounced = 1e9;
TLB_CARP_state_jumpGreenUntil = -1;
TLB_CARP_state_jumpAircraft = objNull;
TLB_CARP_state_jumpRoster = [];
TLB_CARP_state_jumpSolution = createHashMap;
TLB_CARP_state_jumpDisarmReason = _reason;
true

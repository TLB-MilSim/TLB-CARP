if !(isNil "USAFDC_fnc_disarmAutopilot") then {["GUIDANCE DISARMED", false] call USAFDC_fnc_disarmAutopilot};
if !(isNil "USAFDC_fnc_disarmAutoDrop") then {[] call USAFDC_fnc_disarmAutoDrop};
if (USAFDC_state_pfh >= 0) then {
    [USAFDC_state_pfh] call CBA_fnc_removePerFrameHandler;
    USAFDC_state_pfh = -1;
};
USAFDC_state_guidanceArmed = false;
USAFDC_state_solution = createHashMap;
USAFDC_state_pathSolution = createHashMap;
if !(isNil "USAFDC_fnc_resetPackageTiming") then {[] call USAFDC_fnc_resetPackageTiming};
USAFDC_state_lastSignedRpM = 1e9;
USAFDC_state_dropLatched = false;
USAFDC_state_standbyCueSent = false;
USAFDC_state_smoothedDesiredTrackDeg = nil;
USAFDC_state_guidanceLastTick = diag_tickTime;
USAFDC_state_passMissed = false;
USAFDC_state_displayRpM = nil;
USAFDC_state_displayXtkM = nil;
if !(isNil "USAFDC_state_hudLayer") then {USAFDC_state_hudLayer cutText ["", "PLAIN"]};
{
    deleteMarkerLocal _x;
} forEach ["USAFDC_LOCAL_RP", "USAFDC_LOCAL_PLANNED_RP", "USAFDC_LOCAL_CHUTE", "USAFDC_LOCAL_TOUCH", "USAFDC_LOCAL_RUNIN", "USAFDC_LOCAL_INTERCEPT", "USAFDC_LOCAL_CAPTURE"];
true

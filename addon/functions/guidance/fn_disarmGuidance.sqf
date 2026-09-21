if !(isNil "TLB_CARP_fnc_disarmAutopilot") then {["GUIDANCE DISARMED", false] call TLB_CARP_fnc_disarmAutopilot};
if !(isNil "TLB_CARP_fnc_disarmAutoDrop") then {[] call TLB_CARP_fnc_disarmAutoDrop};
if (TLB_CARP_state_pfh >= 0) then {
    [TLB_CARP_state_pfh] call CBA_fnc_removePerFrameHandler;
    TLB_CARP_state_pfh = -1;
};
TLB_CARP_state_guidanceArmed = false;
TLB_CARP_state_solution = createHashMap;
TLB_CARP_state_pathSolution = createHashMap;
if !(isNil "TLB_CARP_fnc_resetPackageTiming") then {[] call TLB_CARP_fnc_resetPackageTiming};
TLB_CARP_state_lastSignedRpM = 1e9;
TLB_CARP_state_dropLatched = false;
TLB_CARP_state_standbyCueSent = false;
TLB_CARP_state_smoothedDesiredTrackDeg = nil;
TLB_CARP_state_guidanceLastTick = diag_tickTime;
TLB_CARP_state_passMissed = false;
TLB_CARP_state_displayRpM = nil;
TLB_CARP_state_displayXtkM = nil;
if !(isNil "TLB_CARP_state_hudLayer") then {TLB_CARP_state_hudLayer cutText ["", "PLAIN"]};
{
    deleteMarkerLocal _x;
} forEach ["TLB_CARP_LOCAL_RP", "TLB_CARP_LOCAL_PLANNED_RP", "TLB_CARP_LOCAL_CHUTE", "TLB_CARP_LOCAL_TOUCH", "TLB_CARP_LOCAL_RUNIN", "TLB_CARP_LOCAL_INTERCEPT", "TLB_CARP_LOCAL_CAPTURE"];
true

if !(isNil "TLB_CARP_fnc_disarmAutoDrop") then {[] call TLB_CARP_fnc_disarmAutoDrop};
if !(isNil "TLB_CARP_fnc_disarmGuidance") then {[] call TLB_CARP_fnc_disarmGuidance};

if (TLB_CARP_state_mapClickEh >= 0) then {
    removeMissionEventHandler ["MapSingleClick", TLB_CARP_state_mapClickEh];
    TLB_CARP_state_mapClickEh = -1;
};

{
    deleteMarkerLocal _x;
} forEach ["TLB_CARP_LOCAL_DZ", "TLB_CARP_LOCAL_RP", "TLB_CARP_LOCAL_CHUTE", "TLB_CARP_LOCAL_TOUCH", "TLB_CARP_LOCAL_RUNIN", "TLB_CARP_LOCAL_INTERCEPT", "TLB_CARP_LOCAL_CAPTURE"];

TLB_CARP_state_dzPosASL = [];
TLB_CARP_state_dzName = "";
TLB_CARP_state_solution = createHashMap;
TLB_CARP_state_pathSolution = createHashMap;
if !(isNil "TLB_CARP_fnc_resetPackageTiming") then {[] call TLB_CARP_fnc_resetPackageTiming};
TLB_CARP_state_dropLatched = false;
// A missed pass belongs to the previous attempt, not this one.
TLB_CARP_state_passMissed = false;
TLB_CARP_state_lastSignedRpM = 1e9;
true

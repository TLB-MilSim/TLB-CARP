if !(isNil "USAFDC_fnc_disarmAutoDrop") then {[] call USAFDC_fnc_disarmAutoDrop};
if !(isNil "USAFDC_fnc_disarmGuidance") then {[] call USAFDC_fnc_disarmGuidance};

if (USAFDC_state_mapClickEh >= 0) then {
    removeMissionEventHandler ["MapSingleClick", USAFDC_state_mapClickEh];
    USAFDC_state_mapClickEh = -1;
};

{
    deleteMarkerLocal _x;
} forEach ["USAFDC_LOCAL_DZ", "USAFDC_LOCAL_RP", "USAFDC_LOCAL_CHUTE", "USAFDC_LOCAL_TOUCH", "USAFDC_LOCAL_RUNIN", "USAFDC_LOCAL_INTERCEPT", "USAFDC_LOCAL_CAPTURE"];

USAFDC_state_dzPosASL = [];
USAFDC_state_dzName = "";
USAFDC_state_solution = createHashMap;
USAFDC_state_pathSolution = createHashMap;
if !(isNil "USAFDC_fnc_resetPackageTiming") then {[] call USAFDC_fnc_resetPackageTiming};
USAFDC_state_dropLatched = false;
// A missed pass belongs to the previous attempt, not this one.
USAFDC_state_passMissed = false;
USAFDC_state_lastSignedRpM = 1e9;
true

if !(isNil "USAFDC_fnc_disarmAutopilot") then {["RUN-IN UNLOCKED", false] call USAFDC_fnc_disarmAutopilot};
if !(isNil "USAFDC_fnc_disarmAutoDrop") then {[] call USAFDC_fnc_disarmAutoDrop};
USAFDC_state_runInLocked = false;
USAFDC_state_dropLatched = false;
// A missed pass belongs to the previous attempt, not this one.
USAFDC_state_passMissed = false;
USAFDC_state_pathSolution = createHashMap;
USAFDC_state_smoothedDesiredTrackDeg = nil;
true

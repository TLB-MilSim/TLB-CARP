if !(isNil "TLB_CARP_fnc_disarmAutopilot") then {["RUN-IN UNLOCKED", false] call TLB_CARP_fnc_disarmAutopilot};
if !(isNil "TLB_CARP_fnc_disarmAutoDrop") then {[] call TLB_CARP_fnc_disarmAutoDrop};
TLB_CARP_state_runInLocked = false;
TLB_CARP_state_dropLatched = false;
// A missed pass belongs to the previous attempt, not this one.
TLB_CARP_state_passMissed = false;
TLB_CARP_state_pathSolution = createHashMap;
TLB_CARP_state_smoothedDesiredTrackDeg = nil;
true

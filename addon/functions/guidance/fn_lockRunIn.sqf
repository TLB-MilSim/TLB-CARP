private _vehicle = objectParent player;
private _state = [_vehicle] call TLB_CARP_fnc_getAircraftState;
if !(_state getOrDefault ["valid", false]) exitWith {false};
if !(isNil "TLB_CARP_fnc_disarmAutoDrop") then {[] call TLB_CARP_fnc_disarmAutoDrop};
TLB_CARP_state_runInDeg = _state get "trackDeg";
TLB_CARP_state_runInLocked = true;
TLB_CARP_state_dropLatched = false;
// A missed pass belongs to the previous attempt, not this one.
TLB_CARP_state_passMissed = false;
TLB_CARP_state_pathSolution = createHashMap;
TLB_CARP_state_smoothedDesiredTrackDeg = nil;
true

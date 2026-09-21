private _vehicle = objectParent player;
private _state = [_vehicle] call USAFDC_fnc_getAircraftState;
if !(_state getOrDefault ["valid", false]) exitWith {false};
if !(isNil "USAFDC_fnc_disarmAutoDrop") then {[] call USAFDC_fnc_disarmAutoDrop};
USAFDC_state_runInDeg = _state get "trackDeg";
USAFDC_state_runInLocked = true;
USAFDC_state_dropLatched = false;
// A missed pass belongs to the previous attempt, not this one.
USAFDC_state_passMissed = false;
USAFDC_state_pathSolution = createHashMap;
USAFDC_state_smoothedDesiredTrackDeg = nil;
true

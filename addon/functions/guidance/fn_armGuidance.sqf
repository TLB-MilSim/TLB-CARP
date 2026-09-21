private _vehicle = objectParent player;
private _solution = [_vehicle] call USAFDC_fnc_buildWorldSolution;
if !(_solution getOrDefault ["valid", false]) exitWith {
    hint format ["TLB CARP: %1", _solution getOrDefault ["reason", "solution unavailable"]];
    false
};

if (USAFDC_state_pfh >= 0) then {
    [USAFDC_state_pfh] call CBA_fnc_removePerFrameHandler;
    USAFDC_state_pfh = -1;
};
USAFDC_state_guidanceArmed = true;
USAFDC_state_smoothedDesiredTrackDeg = _solution getOrDefault ["rawDesiredTrackDeg", _solution get "runInDeg"];
USAFDC_state_guidanceLastTick = diag_tickTime;
USAFDC_state_passMissed = false;
_solution set ["desiredTrackDeg", USAFDC_state_smoothedDesiredTrackDeg];
private _currentTrack = (_solution get "aircraftState") get "trackDeg";
_solution set ["steeringErrorDeg", (((USAFDC_state_smoothedDesiredTrackDeg - _currentTrack + 540) mod 360) - 180)];
USAFDC_state_solution = _solution;
USAFDC_state_lastSignedRpM = _solution get "signedRpM";
USAFDC_state_dropLatched = false;
USAFDC_state_standbyCueSent = false;
USAFDC_state_displayRpM = nil;
USAFDC_state_displayXtkM = nil;
private _interval = missionNamespace getVariable ["USAFDC_setting_updateInterval", 0.05];
USAFDC_state_pfh = [{[] call USAFDC_fnc_updateGuidance}, _interval max 0.01, []] call CBA_fnc_addPerFrameHandler;
true

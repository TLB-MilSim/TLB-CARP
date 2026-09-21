private _vehicle = objectParent player;
private _solution = [_vehicle] call TLB_CARP_fnc_buildWorldSolution;
if !(_solution getOrDefault ["valid", false]) exitWith {
    hint format ["TLB CARP: %1", _solution getOrDefault ["reason", "solution unavailable"]];
    false
};

if (TLB_CARP_state_pfh >= 0) then {
    [TLB_CARP_state_pfh] call CBA_fnc_removePerFrameHandler;
    TLB_CARP_state_pfh = -1;
};
TLB_CARP_state_guidanceArmed = true;
TLB_CARP_state_smoothedDesiredTrackDeg = _solution getOrDefault ["rawDesiredTrackDeg", _solution get "runInDeg"];
TLB_CARP_state_guidanceLastTick = diag_tickTime;
TLB_CARP_state_passMissed = false;
_solution set ["desiredTrackDeg", TLB_CARP_state_smoothedDesiredTrackDeg];
private _currentTrack = (_solution get "aircraftState") get "trackDeg";
_solution set ["steeringErrorDeg", (((TLB_CARP_state_smoothedDesiredTrackDeg - _currentTrack + 540) mod 360) - 180)];
TLB_CARP_state_solution = _solution;
TLB_CARP_state_lastSignedRpM = _solution get "signedRpM";
TLB_CARP_state_dropLatched = false;
TLB_CARP_state_standbyCueSent = false;
TLB_CARP_state_displayRpM = nil;
TLB_CARP_state_displayXtkM = nil;
private _interval = missionNamespace getVariable ["TLB_CARP_setting_updateInterval", 0.05];
TLB_CARP_state_pfh = [{[] call TLB_CARP_fnc_updateGuidance}, _interval max 0.01, []] call CBA_fnc_addPerFrameHandler;
true

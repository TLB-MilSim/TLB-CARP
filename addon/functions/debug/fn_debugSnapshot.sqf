params [["_writeLog", false]];
private _vehicle = objectParent player;
private _air = if (isNull _vehicle) then {createHashMapFromArray [["valid", false]]} else {[_vehicle] call TLB_CARP_fnc_getAircraftState};
private _solution = TLB_CARP_state_solution;
if ((count _solution) isEqualTo 0 && {!isNull _vehicle} && {(count TLB_CARP_state_dzPosASL) >= 3}) then {
    _solution = [_vehicle] call TLB_CARP_fnc_buildWorldSolution;
};
private _relative = _solution getOrDefault ["relative", createHashMap];
private _model = [] call TLB_CARP_fnc_getModel;
private _profileId = _air getOrDefault ["profileId", ""];
private _profiles = _model getOrDefault ["aircraft", createHashMap];
private _profile = _profiles getOrDefault [_profileId, createHashMap];

private _snapshot = createHashMapFromArray [
    ["simTime", time],
    ["realTime", diag_tickTime],
    ["aircraftClass", _air getOrDefault ["class", ""]],
    ["profileId", _profileId],
    ["dropPos", _air getOrDefault ["dropPos", []]],
    ["groundSpeedMs", _air getOrDefault ["groundSpeedMs", 0]],
    ["verticalSpeedMs", _air getOrDefault ["verticalSpeedMs", 0]],
    ["trackDeg", _air getOrDefault ["trackDeg", 0]],
    ["aircraftPosASL", _air getOrDefault ["posASL", []]],
    ["dzPosASL", _solution getOrDefault ["dzPosASL", +TLB_CARP_state_dzPosASL]],
    ["openingTerrainAslM", _solution getOrDefault ["openingTerrainAslM", 0]],
    ["windVector", _solution getOrDefault ["windVector", wind]],
    ["windFromDeg", _solution getOrDefault ["windFromDeg", 0]],
    ["releaseDelayS", _profile getOrDefault ["releaseDelayS", 0]],
    ["actionToReleaseAlongM", _relative getOrDefault ["actionToReleaseAlongM", 0]],
    ["actionToReleaseRightM", _relative getOrDefault ["actionToReleaseRightM", 0]],
    ["freefallTimeS", _relative getOrDefault ["chuteAttachTimeS", 0]],
    ["triggerTimeS", _relative getOrDefault ["triggerTimeS", 0]],
    ["attachTimeS", _relative getOrDefault ["chuteAttachTimeS", 0]],
    ["predictedChuteAglM", _relative getOrDefault ["predictedChuteAglM", 0]],
    ["attachVerticalSpeedMs", _relative getOrDefault ["attachVerticalSpeedMs", 0]],
    ["canopyTimeS", _relative getOrDefault ["predictedCanopyTimeS", 0]],
    ["canopyAlongM", _relative getOrDefault ["canopyAlongM", 0]],
    ["canopyRightM", _relative getOrDefault ["canopyRightM", 0]],
    ["windAlongM", _relative getOrDefault ["windAlongM", 0]],
    ["windRightM", _relative getOrDefault ["windRightM", 0]],
    ["velocityAlongMs", _relative getOrDefault ["velocityAlongMs", 0]],
    ["velocityRightMs", _relative getOrDefault ["velocityRightMs", 0]],
    ["desiredTrackDeg", _solution getOrDefault ["desiredTrackDeg", _solution getOrDefault ["runInDeg", 0]]],
    ["interceptAngleDeg", _solution getOrDefault ["interceptAngleDeg", 0]],
    ["guidanceState", _solution getOrDefault ["guidanceState", ""]],
    ["finalRunLineOffsetM", _solution getOrDefault ["finalRunLineOffsetM", 0]],
    ["targetAglM", _solution getOrDefault ["targetAglM", TLB_CARP_state_targetAglM]],
    ["targetGroundSpeedKmh", _solution getOrDefault ["targetGroundSpeedKmh", TLB_CARP_state_targetGroundSpeedKmh]],
    ["actualAglM", _solution getOrDefault ["actualAglM", 0]],
    ["actualGroundSpeedKmh", _solution getOrDefault ["actualGroundSpeedKmh", 0]],
    ["plannedRpPosASL", _solution getOrDefault ["plannedRpPosASL", []]],
    ["liveRpPosASL", _solution getOrDefault ["liveRpPosASL", _solution getOrDefault ["rpPosASL", []]]],
    ["rpPosASL", _solution getOrDefault ["rpPosASL", []]],
    ["signedRpM", _solution getOrDefault ["signedRpM", 0]],
    ["crossTrackM", _solution getOrDefault ["crossTrackM", 0]],
    ["trackErrorDeg", _solution getOrDefault ["trackErrorDeg", 0]],
    ["confidence", _solution getOrDefault ["confidence", "INVALID"]],
    ["warnings", _solution getOrDefault ["warnings", []]],
    ["autoArmed", TLB_CARP_state_autoArmed],
    // Without these a refused pass cannot be attributed to the AP or the pilot.
    ["apArmed", missionNamespace getVariable ["TLB_CARP_state_apArmed", false]],
    ["apState", missionNamespace getVariable ["TLB_CARP_state_apState", "OFF"]],
    ["apDisconnectReason", missionNamespace getVariable ["TLB_CARP_state_apDisconnectReason", ""]],
    ["pathState", (missionNamespace getVariable ["TLB_CARP_state_pathSolution", createHashMap]) getOrDefault ["pathState", ""]],
    ["passMissed", missionNamespace getVariable ["TLB_CARP_state_passMissed", false]],
    ["cargoCount", _air getOrDefault ["cargoCount", 0]],
    ["selectedCargoCount", TLB_CARP_state_cargoCount],
    ["stickLengthM", _solution getOrDefault ["stickLengthM", 0]],
    ["firstReleaseLeadM", _solution getOrDefault ["firstReleaseLeadM", 0]]
];
if (_writeLog) then {diag_log format ["[TLB CARP] snapshot %1", _snapshot]};
_snapshot

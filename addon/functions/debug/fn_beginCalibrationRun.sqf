params ["_carrier", "_solution", ["_metadata", createHashMap]];
if (!TLB_CARP_setting_calibrationRecorder) exitWith {false};
if (isNull _carrier) exitWith {false};
if (TLB_CARP_state_calibrationActive) exitWith {
    diag_log "[TLB CARP][CAL] recorder already active; ignoring new cue";
    false
};
if !(_solution getOrDefault ["valid", false]) exitWith {false};

private _air = [_carrier] call TLB_CARP_fnc_getAircraftState;
if !(_air getOrDefault ["valid", false]) exitWith {false};
// THE MANIFEST, NOT usaf_cargo. Flown 2026-09-20: a vehicle-in-vehicle load dropped from
// a Blackfish logged "no cargo loaded at cue" while sitting in the hold, because this read
// USAF's array directly and a VIV load is not in it. The recorder was blind to three of
// the four carriage sources and to everything CARP loads itself.
//
// functions/debug/ is exempted from the test that enforces manifest discipline, which is
// why this survived v0.8.0's sweep. The exemption is for the harnesses that deliberately
// drive USAF's own path; it was never meant to cover the flown recorder.
private _initialCargo = +([_carrier] call TLB_CARP_fnc_getLoadedCargo);
if ((count _initialCargo) <= 0) exitWith {
    diag_log format ["[TLB CARP][CAL] no cargo aboard at cue, carrier=%1 -- nothing to record", typeOf _carrier];
    false
};

TLB_CARP_state_calibrationSerial = TLB_CARP_state_calibrationSerial + 1;
private _relative = _solution getOrDefault ["relative", createHashMap];
private _solutionAtCue = createHashMapFromArray [
    ["signedRpM", _solution getOrDefault ["signedRpM", 0]],
    ["crossTrackM", _solution getOrDefault ["crossTrackM", 0]],
    ["trackErrorDeg", _solution getOrDefault ["trackErrorDeg", 0]],
    ["confidence", _solution getOrDefault ["confidence", "INVALID"]],
    ["warnings", +(_solution getOrDefault ["warnings", []])],
    ["predictedChuteAglM", _relative getOrDefault ["predictedChuteAglM", 0]],
    ["predictedCanopyTimeS", _relative getOrDefault ["predictedCanopyTimeS", 0]],
    ["canopyModel", _relative getOrDefault ["canopyModel", ""]],
    ["canopyBaselineWorld", _relative getOrDefault ["canopyBaselineWorld", []]],
    ["canopyWindCorrectionWorld", _relative getOrDefault ["canopyWindCorrectionWorld", []]],
    ["canopyPredictedWorld", _relative getOrDefault ["canopyPredictedWorld", []]],
    ["canopyHeadingBracket", _relative getOrDefault ["canopyHeadingBracket", []]],
    ["canopyWindDirectionBracket", _relative getOrDefault ["canopyWindDirectionBracket", []]],
    ["canopyWindSpeedBracket", _relative getOrDefault ["canopyWindSpeedBracket", []]],
    ["canopyUsedOppositeDirectionSymmetry", _relative getOrDefault ["canopyUsedOppositeDirectionSymmetry", false]],
    ["totalAlongM", _relative getOrDefault ["totalAlongM", 0]],
    ["totalRightM", _relative getOrDefault ["totalRightM", 0]],
    ["velocityAlongMs", _relative getOrDefault ["velocityAlongMs", 0]],
    ["velocityRightMs", _relative getOrDefault ["velocityRightMs", 0]],
    ["desiredTrackDeg", _solution getOrDefault ["desiredTrackDeg", _solution get "runInDeg"]],
    ["interceptAngleDeg", _solution getOrDefault ["interceptAngleDeg", 0]],
    ["guidanceState", _solution getOrDefault ["guidanceState", ""]],
    ["finalRunLineOffsetM", _solution getOrDefault ["finalRunLineOffsetM", 0]],
    ["targetAglM", _solution getOrDefault ["targetAglM", TLB_CARP_state_targetAglM]],
    ["targetGroundSpeedKmh", _solution getOrDefault ["targetGroundSpeedKmh", TLB_CARP_state_targetGroundSpeedKmh]],
    ["actualAglM", _solution getOrDefault ["actualAglM", 0]],
    ["actualGroundSpeedKmh", _solution getOrDefault ["actualGroundSpeedKmh", 0]],
    ["plannedRpPosASL", +(_solution getOrDefault ["plannedRpPosASL", []])],
    ["liveRpPosASL", +(_solution getOrDefault ["liveRpPosASL", _solution getOrDefault ["rpPosASL", []]])]
];

private _cueAircraftPosASL = +(_air getOrDefault ["posASL", getPosASL _carrier]);
private _cueWindTelemetry = [_cueAircraftPosASL] call TLB_CARP_fnc_sampleWindTelemetry;

private _run = createHashMapFromArray [
    ["version", "TLB_CARP_CAL_V3"],
    ["runId", TLB_CARP_state_calibrationSerial],
    ["status", "WAITING_RELEASE"],
    ["cueSimTime", time],
    ["cueRealTime", diag_tickTime],
    ["aircraftClass", typeOf _carrier],
    ["profileId", _air getOrDefault ["profileId", ""]],
    ["mode", _solution getOrDefault ["mode", TLB_CARP_state_mode]],
    ["initialCargo", _initialCargo],
    ["initialCargoCount", count _initialCargo],
    ["solutionAtCue", _solutionAtCue],
    ["cueAircraftPosASL", _cueAircraftPosASL],
    ["cueWindTelemetry", _cueWindTelemetry],
    ["cueVelocity", +(_air getOrDefault ["velocity", velocity _carrier])],
    ["groundSpeedMs", _air getOrDefault ["groundSpeedMs", 0]],
    ["verticalSpeedMs", _air getOrDefault ["verticalSpeedMs", 0]],
    ["trackDeg", _air getOrDefault ["trackDeg", 0]],
    ["cueWind", +(_solution getOrDefault ["windVector", wind])],
    ["windFromDeg", _solution getOrDefault ["windFromDeg", 0]],
    ["runInDeg", _solution getOrDefault ["runInDeg", 0]],
    ["dzPosASL", +(_solution getOrDefault ["dzPosASL", TLB_CARP_state_dzPosASL])],
    ["rpPosASL", +(_solution getOrDefault ["rpPosASL", []])],
    ["chutePosASL", +(_solution getOrDefault ["chutePosASL", []])],
    ["testHarness", _metadata getOrDefault ["testHarness", false]],
    ["testRequestedHeadingDeg", _metadata getOrDefault ["testRequestedHeadingDeg", -1]]
];
{
    _run set [_x, _metadata get _x];
} forEach keys _metadata;

TLB_CARP_state_calibrationActive = true;
TLB_CARP_state_calibrationRun = _run;
diag_log format ["[TLB CARP][CAL] run=%1 armed cargo=%2 class=%3", TLB_CARP_state_calibrationSerial, count _initialCargo, typeOf _carrier];
[_carrier, _run] spawn TLB_CARP_fnc_pollCalibrationRun;
true

params [
    ["_headingDeg", 0, [0]],
    ["_aglM", 3000, [0]],
    ["_groundSpeedKmh", 500, [0]],
    ["_verticalSpeedMs", 0, [0]],
    ["_cargoClass", "rhsusf_mrzr4_d", [""]],
    ["_seriesId", 0, [0]],
    ["_seriesIndex", 0, [0]],
    ["_seriesOwnsHarness", false, [true]],
    ["_testWindMode", "LIVE", [""]],
    ["_testRequestedWindVector", [], [[]]]
];

if (isMultiplayer) exitWith {
    hint "TLB CARP DEBUG HARNESS\nEden / Single Player only";
    false
};
if (!_seriesOwnsHarness && {TLB_CARP_state_debugHarnessActive}) exitWith {
    hint "TLB CARP DEBUG HARNESS\nAnother test is already active";
    false
};
if (_seriesOwnsHarness && {!TLB_CARP_state_debugHarnessActive}) exitWith {
    diag_log "[TLB CARP][HARNESS] series-owned run rejected because series reservation is missing";
    false
};

if (!_seriesOwnsHarness) then {TLB_CARP_state_debugHarnessActive = true};
TLB_CARP_state_debugHarnessObjects = [];

private _cleanup = {
    {
        if (!isNull _x && {_x getVariable ["TLB_CARP_debugHarnessOwned", false]}) then {
            deleteVehicle _x;
        };
    } forEach +TLB_CARP_state_debugHarnessObjects;
    TLB_CARP_state_debugHarnessObjects = [];
    if (!_seriesOwnsHarness) then {TLB_CARP_state_debugHarnessActive = false};
};
private _fail = {
    params ["_reason", "_cleanup"];
    diag_log format ["[TLB CARP][HARNESS] failed: %1", _reason];
    hint format ["TLB CARP DEBUG HARNESS FAILED\n%1", _reason];
    call _cleanup;
    false
};

if ((count TLB_CARP_state_dzPosASL) < 3) exitWith {["Select a CARP DZ first", _cleanup] call _fail};
if !(isClass (configFile >> "CfgVehicles" >> _cargoClass)) exitWith {[format ["Cargo class missing: %1", _cargoClass], _cleanup] call _fail};

private _cargo = createVehicle [_cargoClass, [0, 0, 100], [], 0, "NONE"];
if (isNull _cargo) exitWith {[format ["Could not create cargo: %1", _cargoClass], _cleanup] call _fail};
_cargo setVariable ["TLB_CARP_debugHarnessOwned", true, false];
TLB_CARP_state_debugHarnessObjects pushBack _cargo;

private _build = [_headingDeg, _aglM, _groundSpeedKmh, _verticalSpeedMs, _cargoClass, _cargo] call TLB_CARP_fnc_buildDebugDropSolution;
if !(_build getOrDefault ["valid", false]) exitWith {[_build getOrDefault ["reason", "Invalid debug solution"], _cleanup] call _fail};

private _spawnPosASL = +(_build get "spawnPosASL");
private _carrier = createVehicle ["USAF_C17", [_spawnPosASL # 0, _spawnPosASL # 1, 0], [], 0, "FLY"];
if (isNull _carrier) exitWith {["Could not create USAF_C17", _cleanup] call _fail};
_carrier setVariable ["TLB_CARP_debugHarnessOwned", true, false];
TLB_CARP_state_debugHarnessObjects pushBack _carrier;

private _exactHeading = _build get "headingDeg";
private _forward = +(_build get "forward");
private _velocity = +(_build get "velocity");
_carrier setPosASL _spawnPosASL;
_carrier setDir _exactHeading;
_carrier setVectorDirAndUp [_forward, [0, 0, 1]];
_carrier setVelocity _velocity;

// Pre-open USAF cargo doors instantly so canDrop does not add an unmodelled door-animation delay.
{
    if (_x isEqualType "") then {
        _carrier animate [_x, 1, true];
    };
} forEach (_build getOrDefault ["doors", []]);

// Enter the same USAF Cargo state used by a legitimate force-loaded object.
// This establishes USAF's attachment/orientation plus the carrier and getoutevh
// variables consumed later by USAF_CARGO_fnc_dropCargo.
[_carrier, _cargo, 0, false] call USAF_CARGO_fnc_forceLoadCargo;

private _cargoRegistered = _cargo in (_carrier getVariable ["usaf_cargo", []]);
private _carrierValid = (_cargo getVariable ["carrier", objNull]) isEqualTo _carrier;
private _hasGetOutEH = !(isNil {_cargo getVariable "getoutevh"});
private _attachedCorrectly = (attachedTo _cargo) isEqualTo _carrier;

if (!_cargoRegistered || {!_carrierValid} || {!_hasGetOutEH} || {!_attachedCorrectly}) exitWith {
    private _reason = format [
        "USAF cargo initialization failed (registered=%1 carrier=%2 getOutEH=%3 attached=%4)",
        _cargoRegistered,
        _carrierValid,
        _hasGetOutEH,
        _attachedCorrectly
    ];
    [_reason, _cleanup] call _fail
};

private _solution = _build get "solution";
private _metadata = createHashMapFromArray [
    ["testHarness", true],
    ["testSeriesId", _seriesId],
    ["testSeriesIndex", _seriesIndex],
    ["testRequestedHeadingDeg", _exactHeading],
    ["testRequestedAglM", _aglM],
    ["testRequestedGroundSpeedKmh", _groundSpeedKmh],
    ["testRequestedVerticalSpeedMs", _verticalSpeedMs],
    ["testCargoClass", _cargoClass],
    ["testSpawnPosASL", +_spawnPosASL],
    ["testActionRpPosASL", +(_build get "actionRpPosASL")],
    ["testActualHeadingDeg", getDir _carrier],
    ["testActualVelocity", velocity _carrier],
    ["testWindMode", _testWindMode],
    ["testRequestedWindVector", +_testRequestedWindVector],
    ["testEngineWindAtHarnessStart", +(wind)],
    ["testGustsAtHarnessStart", gusts]
];

private _oldRecorderSetting = TLB_CARP_setting_calibrationRecorder;
TLB_CARP_setting_calibrationRecorder = true;
private _recorderStarted = [_carrier, _solution, _metadata] call TLB_CARP_fnc_beginCalibrationRun;
TLB_CARP_setting_calibrationRecorder = _oldRecorderSetting;
if (!_recorderStarted) exitWith {["Calibration recorder did not start", _cleanup] call _fail};

private _runId = TLB_CARP_state_calibrationRun getOrDefault ["runId", -1];
diag_log format ["[TLB CARP][HARNESS] run=%1 heading=%2 agl=%3 speed=%4 vz=%5 spawn=%6", _runId, _exactHeading, _aglM, _groundSpeedKmh, _verticalSpeedMs, _spawnPosASL];
hint format ["TLB CARP DEBUG DROP\nHDG %1 | %2 m | %3 km/h", round _exactHeading, round _aglM, round _groundSpeedKmh];

// An uncrewed C-17 immediately loses substantial speed to its flight model even
// when setVelocity is reasserted from scheduled SQF. During the short real USAF
// action-to-detach window, pin the carrier to the exact requested kinematic path
// from the recorder cue. The cargo remains attached through USAF's own loader and
// USAF_CARGO_fnc_dropCargo still owns the actual 0.5 s detach timing.
private _pinOriginPosASL = +(TLB_CARP_state_calibrationRun getOrDefault ["cueAircraftPosASL", getPosASL _carrier]);
private _pinOriginSimTime = TLB_CARP_state_calibrationRun getOrDefault ["cueSimTime", time];

[_carrier] spawn USAF_CARGO_fnc_canDrop;

private _releaseObserved = false;
private _pinDeadline = diag_tickTime + 10;
waitUntil {
    private _pinElapsedS = (time - _pinOriginSimTime) max 0;
    private _pinPosASL = [
        (_pinOriginPosASL # 0) + ((_velocity # 0) * _pinElapsedS),
        (_pinOriginPosASL # 1) + ((_velocity # 1) * _pinElapsedS),
        (_pinOriginPosASL # 2) + ((_velocity # 2) * _pinElapsedS)
    ];
    _carrier setPosASL _pinPosASL;
    _carrier setVectorDirAndUp [_forward, [0, 0, 1]];
    _carrier setVelocity _velocity;
    uiSleep 0.01;
    private _currentCargo = +(_carrier getVariable ["usaf_cargo", []]);
    _releaseObserved = !(_cargo in _currentCargo);
    _releaseObserved || {diag_tickTime >= _pinDeadline} || {isNull _carrier}
};

// USAF_CARGO owns its native side-selected smoke effect. The CARP harness does not add or override smoke.

// Give the recorder a chance to snapshot carrier position/velocity before cleanup.
private _trackingDeadline = diag_tickTime + 2;
waitUntil {
    uiSleep 0.01;
    private _activeRun = TLB_CARP_state_calibrationRun;
    ((_activeRun getOrDefault ["runId", -2]) isEqualTo _runId && {!((_activeRun getOrDefault ["status", ""]) isEqualTo "WAITING_RELEASE")})
        || {diag_tickTime >= _trackingDeadline}
};
if (!isNull _carrier && {_carrier getVariable ["TLB_CARP_debugHarnessOwned", false]}) then {
    deleteVehicle _carrier;
};

private _runDeadline = diag_tickTime + 220;
waitUntil {
    uiSleep 0.1;
    private _lastRun = TLB_CARP_state_lastCalibrationRun;
    private _done = ((_lastRun getOrDefault ["runId", -2]) isEqualTo _runId) && {(_lastRun getOrDefault ["status", ""]) in ["COMPLETE", "FAILED"]};
    _done || {diag_tickTime >= _runDeadline}
};

private _lastRun = TLB_CARP_state_lastCalibrationRun;
private _completed = ((_lastRun getOrDefault ["runId", -2]) isEqualTo _runId) && {(_lastRun getOrDefault ["status", ""]) in ["COMPLETE", "FAILED"]};
if (!_completed) exitWith {["Recorder did not finish within harness timeout", _cleanup] call _fail};

// Keep the actual cargo visible briefly at the settled position.
uiSleep 3;

// Cleanup only objects created by this harness after the recorder has retained its deep-enough data/text.
call _cleanup;
true

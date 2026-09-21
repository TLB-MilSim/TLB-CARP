params [
    ["_headings", [], [[]]],
    ["_aglM", 3000, [0]],
    ["_groundSpeedKmh", 500, [0]],
    ["_verticalSpeedMs", 0, [0]],
    ["_cargoClass", "rhsusf_mrzr4_d", [""]],
    ["_windMode", "LIVE", [""]],
    ["_controlledWindVector", [0, 0], [[]]]
];

_windMode = toUpper _windMode;

if (isMultiplayer) exitWith {
    hint "TLB CARP DEBUG SERIES\nEden / Single Player only";
    false
};
if ((count _headings) isEqualTo 0) exitWith {
    hint "TLB CARP DEBUG SERIES\nNo headings supplied";
    false
};
if !(_windMode in ["LIVE", "ZERO", "FIXED"]) exitWith {
    hint format ["TLB CARP DEBUG SERIES\nInvalid wind mode: %1\nUse LIVE, ZERO, or FIXED", _windMode];
    false
};
if (_windMode isEqualTo "FIXED" && {(count _controlledWindVector) < 2}) exitWith {
    hint "TLB CARP DEBUG SERIES\nFIXED mode requires [eastMs, northMs] wind vector";
    false
};
if (USAFDC_state_debugHarnessActive) exitWith {
    hint "TLB CARP DEBUG SERIES\nAnother harness run is active";
    false
};
if ((count USAFDC_state_dzPosASL) < 3) exitWith {
    hint "TLB CARP DEBUG SERIES\nSelect a CARP DZ first";
    false
};

private _requestedWindVector = switch (_windMode) do {
    case "ZERO": {[0, 0, 0]};
    case "FIXED": {[_controlledWindVector # 0, _controlledWindVector # 1, 0]};
    default {[]};
};
private _windBeforeSeries = +(wind);
private _gustsBeforeSeries = gusts;
private _aceWindSimulationWasDefined = !(isNil "ace_weather_disableWindSimulation");
private _aceWindSimulationBeforeSeries = missionNamespace getVariable ["ace_weather_disableWindSimulation", false];
private _controlledWindActive = !(_windMode isEqualTo "LIVE");
private _windControlToleranceMs = 0.05;

private _restoreEnvironment = {
    if (_controlledWindActive) then {
        setWind [_windBeforeSeries # 0, _windBeforeSeries # 1, false];
        0 setGusts _gustsBeforeSeries;
        if (_aceWindSimulationWasDefined) then {
            missionNamespace setVariable ["ace_weather_disableWindSimulation", _aceWindSimulationBeforeSeries];
        } else {
            missionNamespace setVariable ["ace_weather_disableWindSimulation", nil];
        };
        diag_log format [
            "[TLB CARP][HARNESS] wind control restored wind=%1 gusts=%2",
            _windBeforeSeries,
            _gustsBeforeSeries
        ];
    };
};

private _windControlReady = true;
private _windControlErrorMs = 0;
if (_controlledWindActive) then {
    ace_weather_disableWindSimulation = true;
    0 setGusts 0;

    // ACE Weather can complete one more scheduled wind update immediately after the
    // disable flag changes. Give it a full second to observe the flag while
    // continuously reasserting the requested controlled environment.
    private _aceDisableSettleDeadline = diag_tickTime + 1;
    waitUntil {
        setWind [_requestedWindVector # 0, _requestedWindVector # 1, true];
        0 setGusts 0;
        uiSleep 0.05;
        diag_tickTime >= _aceDisableSettleDeadline
    };
    setWind [_requestedWindVector # 0, _requestedWindVector # 1, true];

    // Give the final setWind/setGusts a few frames to propagate before verifying.
    private _settleFrame = diag_frameNo + 3;
    waitUntil {
        uiSleep 0.01;
        diag_frameNo >= _settleFrame
    };

    private _actualWind = wind;
    private _dx = (_actualWind # 0) - (_requestedWindVector # 0);
    private _dy = (_actualWind # 1) - (_requestedWindVector # 1);
    _windControlErrorMs = sqrt ((_dx * _dx) + (_dy * _dy));
    _windControlReady = _windControlErrorMs <= _windControlToleranceMs;

    diag_log format [
        "[TLB CARP][HARNESS] wind control mode=%1 requested=%2 actual=%3 error=%4 gusts=%5",
        _windMode,
        _requestedWindVector,
        _actualWind,
        _windControlErrorMs,
        gusts
    ];
};

if (!_windControlReady) exitWith {
    call _restoreEnvironment;
    hint format [
        "TLB CARP DEBUG SERIES\nControlled wind did not lock\nRequested %1\nError %2 m/s",
        _requestedWindVector,
        _windControlErrorMs toFixed 3
    ];
    false
};

USAFDC_state_debugHarnessActive = true;
USAFDC_state_debugHarnessObjects = [];
USAFDC_state_debugSeriesSerial = USAFDC_state_debugSeriesSerial + 1;
private _seriesId = USAFDC_state_debugSeriesSerial;
USAFDC_state_debugSeriesResults = [];
USAFDC_state_lastDebugSeriesText = "";

private _seriesIndex = 0;
{
    _seriesIndex = _seriesIndex + 1;
    private _headingDeg = ((_x % 360) + 360) % 360;
    diag_log format [
        "[TLB CARP][HARNESS] series=%1 index=%2/%3 heading=%4 windMode=%5 wind=%6 begin",
        _seriesId,
        _seriesIndex,
        count _headings,
        _headingDeg,
        _windMode,
        _requestedWindVector
    ];
    hint format [
        "TLB CARP DEBUG SERIES\n%1/%2 | HDG %3\nWIND %4 %5",
        _seriesIndex,
        count _headings,
        round _headingDeg,
        _windMode,
        if (_controlledWindActive) then {str _requestedWindVector} else {""}
    ];

    private _handle = [
        _headingDeg,
        _aglM,
        _groundSpeedKmh,
        _verticalSpeedMs,
        _cargoClass,
        _seriesId,
        _seriesIndex,
        true,
        _windMode,
        +_requestedWindVector
    ] spawn USAFDC_fnc_debugDropTest;

    waitUntil {
        uiSleep 0.1;
        scriptDone _handle
    };

    private _lastRun = USAFDC_state_lastCalibrationRun;
    private _status = _lastRun getOrDefault ["status", ""];
    private _sameSeries = (_lastRun getOrDefault ["testHarness", false])
        && {(_lastRun getOrDefault ["testSeriesId", -1]) isEqualTo _seriesId}
        && {(_lastRun getOrDefault ["testSeriesIndex", -1]) isEqualTo _seriesIndex};
    private _text = "";
    if (_sameSeries && {_status in ["COMPLETE", "FAILED"]}) then {
        _text = USAFDC_state_lastCalibrationText;
    } else {
        _text = format [
            "USAFDC_CAL_V3\nrunId=-1\nstatus=FAILED\nfailureReason=HARNESS RUN DID NOT PRODUCE CAL RECORD\ntestHarness=true\ntestSeriesId=%1\ntestSeriesIndex=%2\ntestRequestedHeadingDeg=%3\ntestWindMode=%4\ntestRequestedWindVector=%5",
            _seriesId,
            _seriesIndex,
            _headingDeg,
            _windMode,
            _requestedWindVector
        ];
    };
    USAFDC_state_debugSeriesResults pushBack _text;

    // The single-run function cleans its tagged carrier/cargo before returning.
    waitUntil {
        uiSleep 0.05;
        (count USAFDC_state_debugHarnessObjects) isEqualTo 0
    };

    diag_log format ["[TLB CARP][HARNESS] series=%1 index=%2 status=%3 complete", _seriesId, _seriesIndex, if (_sameSeries) then {_status} else {"FAILED"}];
} forEach _headings;

USAFDC_state_lastDebugSeriesText = USAFDC_state_debugSeriesResults joinString "\n\n";
USAFDC_state_debugHarnessObjects = [];
USAFDC_state_debugHarnessActive = false;
call _restoreEnvironment;

private _completeCount = 0;
private _failedCount = 0;
{
    if ((_x find "status=COMPLETE") >= 0) then {_completeCount = _completeCount + 1};
    if ((_x find "status=FAILED") >= 0) then {_failedCount = _failedCount + 1};
} forEach USAFDC_state_debugSeriesResults;

diag_log format [
    "[TLB CARP][HARNESS] series=%1 finished complete=%2 failed=%3 windMode=%4 wind=%5",
    _seriesId,
    _completeCount,
    _failedCount,
    _windMode,
    _requestedWindVector
];
hint format [
    "TLB CARP DEBUG SERIES COMPLETE\n%1 complete | %2 failed\nWIND %3\nRun [] call USAFDC_fnc_copyLastDebugSeries",
    _completeCount,
    _failedCount,
    _windMode
];
true

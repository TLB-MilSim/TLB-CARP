params ["_input", "_model"];

private _aircraftId = _input get "aircraft";
private _aircraftMap = _model get "aircraft";
private _aircraft = _aircraftMap getOrDefault [_aircraftId, createHashMap];
if ((count _aircraft) isEqualTo 0) exitWith {
    createHashMapFromArray [["confidence", "INVALID"], ["warnings", ["UNSUPPORTED AIRCRAFT PROFILE"]]]
};
// "ready" is fully calibrated. "provisional-borrowed" means the profile runs but its
// canopy table is borrowed from another airframe and has never been measured for this
// one -- it must solve, so it can BE measured, while never presenting as trustworthy.
// Anything else refuses outright.
// "ready"              fully calibrated.
// "provisional-borrowed" runs, but the whole canopy table is another airframe's.
// "zero-wind-measured"  the zero-wind baseline IS measured for this airframe; only
//                       the wind deltas are still borrowed, so the warning below is
//                       raised only when there is actually wind.
private _calState = _aircraft get "calibrationState";
private _borrowedProfile = _calState isEqualTo "provisional-borrowed";
private _windTablesBorrowed = _calState isEqualTo "zero-wind-measured";
// One explicit list, so it is greppable and cannot drift from the harness's copy.
if !(_calState in ["ready", "zero-wind-measured", "provisional-borrowed"]) exitWith {
    createHashMapFromArray [["confidence", "INVALID"], ["warnings", ["AIRCRAFT PROFILE NOT CALIBRATED"]]]
};

private _physics = _model get "physics";
private _usaf = _model get "usaf";
private _canopyRoot = _model get "canopy";
private _canopy = _canopyRoot get "highEnergy";
private _confidenceCfg = _model get "confidence";

private _speed = _input get "groundSpeedMs";
private _verticalSpeed = _input get "verticalSpeedMs";
private _releaseDelay = _aircraft get "releaseDelayS";
private _releaseVerticalOffsetM = _input getOrDefault ["releaseVerticalOffsetM", 0];
private _openingTerrainAslM = _input get "openingTerrainAslM";
private _dzTerrainAslM = _input get "dzTerrainAslM";
private _releaseAslM = (_input get "actionAltitudeAslM") + (_verticalSpeed * _releaseDelay) + _releaseVerticalOffsetM;
private _releaseAglM = _releaseAslM - _openingTerrainAslM;

private _ballistic = [
    _releaseAglM,
    _verticalSpeed,
    _usaf get "triggerAglM",
    _usaf get "attachLagS",
    _physics get "gravityMs2"
] call TLB_CARP_fnc_ballisticToTrigger;
if !(_ballistic get "valid") exitWith {
    createHashMapFromArray [["confidence", "INVALID"], ["warnings", [_ballistic get "reason"]]]
};

private _chuteAttachAslM = _openingTerrainAslM + (_ballistic get "attachAglM");
private _verticalPathM = _chuteAttachAslM - _dzTerrainAslM;
private _canopyResult = [_verticalPathM, _ballistic get "attachVerticalSpeedMs", _canopy] call TLB_CARP_fnc_canopyTime;

private _runInDeg = _input get "runInDeg";
private _basis = [_runInDeg] call TLB_CARP_fnc_basisFromHeading;
private _forward = _basis get "forward";
private _right = _basis get "right";
private _windSpeed = _input get "windSpeedMs";
private _windFromDeg = _input get "windFromDeg";
private _toDeg = (_windFromDeg + 180) mod 360;
private _wx = _windSpeed * sin _toDeg;
private _wy = _windSpeed * cos _toDeg;
private _windWorld = [_wx, _wy, 0];
private _windAlongMs = (_wx * (_forward # 0)) + (_wy * (_forward # 1));
private _windRightMs = (_wx * (_right # 0)) + (_wy * (_right # 1));

private _dropPos = _aircraft get "dropPos";
private _velocityAlongMs = _input getOrDefault ["velocityAlongMs", _speed];
private _velocityRightMs = _input getOrDefault ["velocityRightMs", 0];
private _releaseOffsetAlongM = _input getOrDefault ["releaseOffsetAlongM", _dropPos # 1];
private _releaseOffsetRightM = _input getOrDefault ["releaseOffsetRightM", _dropPos # 0];
private _actionToReleaseAlongM = (_velocityAlongMs * _releaseDelay) + _releaseOffsetAlongM;
private _actionToReleaseRightM = (_velocityRightMs * _releaseDelay) + _releaseOffsetRightM;
private _freefallAlongM = _velocityAlongMs * (_ballistic get "attachTimeS");
private _freefallRightM = _velocityRightMs * (_ballistic get "attachTimeS");
private _chuteMode = (_input get "mode") isEqualTo "CHUTE";

// Which empirical canopy table this airframe uses. Was hardcoded to c17, so any other
// aircraft would have silently borrowed the C-17 table by accident. The borrowing is
// now a declared property of the profile and visible in the model file.
private _canopyRef = _aircraft getOrDefault ["canopyRef", ""];
if (!_chuteMode && {!(_canopyRef in (keys _canopyRoot))}) exitWith {
    createHashMapFromArray [["confidence", "INVALID"], ["warnings", ["EMPIRICAL CANOPY MODEL NOT AVAILABLE FOR AIRCRAFT"]]]
};

private _canopyAlongM = 0;
private _canopyRightM = 0;
private _windAlongM = 0;
private _windRightM = 0;
private _predictedCanopyTimeS = 0;
private _canopyModel = "";
private _canopyBaselineWorld = [0, 0];
private _canopyWindCorrectionWorld = [0, 0];
private _canopyPredictedWorld = [0, 0];
private _canopyHeadingBracket = [];
private _canopyWindDirectionBracket = [];
private _canopyWindSpeedBracket = [];
private _canopyUsedOppositeDirectionSymmetry = false;
private _empiricalWarnings = [];
private _empiricalInvalid = false;

if (!_chuteMode) then {
    if (isNil "TLB_CARP_fnc_empiricalCanopyC17") then {
        TLB_CARP_fnc_empiricalCanopyC17 = compile preprocessFileLineNumbers "\x\tlbcarp\addons\drop_computer\functions\solver\fn_empiricalCanopyC17.sqf";
    };
    // The load enters the canopy phase at essentially its release ground speed: freefall
    // barely touches the horizontal component, and the flown records agree -- a release at
    // 97.27 m/s along reached the canopy at 97.3. That speed sets the forward throw.
    // Freefall time as well: the canopy's duration depends on how fast the load is
    // falling when the chute opens, which is set by the drop altitude.
    private _empirical = [_runInDeg, _windWorld, _canopyRoot get _canopyRef, _velocityAlongMs, _ballistic get "attachTimeS"] call TLB_CARP_fnc_empiricalCanopyC17;
    if !(_empirical getOrDefault ["valid", false]) then {
        _empiricalInvalid = true;
        _empiricalWarnings = +(_empirical getOrDefault ["warnings", ["EMPIRICAL C17 CANOPY SOLVE FAILED"]]);
    } else {
        private _canopyWorld = +(_empirical get "canopyWorld");
        private _windCorrectionWorld = +(_empirical get "windCorrectionWorld");
        _canopyAlongM = ((_canopyWorld # 0) * (_forward # 0)) + ((_canopyWorld # 1) * (_forward # 1));
        _canopyRightM = ((_canopyWorld # 0) * (_right # 0)) + ((_canopyWorld # 1) * (_right # 1));
        _windAlongM = ((_windCorrectionWorld # 0) * (_forward # 0)) + ((_windCorrectionWorld # 1) * (_forward # 1));
        _windRightM = ((_windCorrectionWorld # 0) * (_right # 0)) + ((_windCorrectionWorld # 1) * (_right # 1));
        _predictedCanopyTimeS = _empirical getOrDefault ["predictedCanopyTimeS", 0];
        _canopyModel = _empirical getOrDefault ["modelId", "EMPIRICAL_C17_V2"];
        _canopyBaselineWorld = +(_empirical getOrDefault ["baselineWorld", [0, 0]]);
        _canopyWindCorrectionWorld = +_windCorrectionWorld;
        _canopyPredictedWorld = +_canopyWorld;
        _canopyHeadingBracket = +(_empirical getOrDefault ["headingBracket", []]);
        _canopyWindDirectionBracket = +(_empirical getOrDefault ["windDirectionBracket", []]);
        _canopyWindSpeedBracket = +(_empirical getOrDefault ["windSpeedBracket", []]);
        _canopyUsedOppositeDirectionSymmetry = _empirical getOrDefault ["usedOppositeDirectionSymmetry", false];
        _empiricalWarnings = +(_empirical getOrDefault ["warnings", []]);
    };
};

if (_empiricalInvalid) exitWith {
    createHashMapFromArray [["confidence", "INVALID"], ["warnings", _empiricalWarnings]]
};

private _totalRightM = _actionToReleaseRightM + _freefallRightM + _canopyRightM;
private _totalAlongM = _actionToReleaseAlongM + _freefallAlongM + _canopyAlongM;

// ---- confidence -------------------------------------------------------------------
//
// THERE IS NO DEGRADED TIER ANY MORE. A solution is GOOD or it does not exist.
//
// Five warnings used to live here -- low-energy canopy, speed outside the calibrated
// range, wind above the empirical range, borrowed canopy table, borrowed wind tables --
// and any one of them forced DEGRADED, which in turn gated Auto Drop and put a block of
// amber text over the HUD.
//
// They were honest while the C-17 tables were the only measured thing and every other
// airframe was an open question. That question is now closed by flying it: the C-17
// model has been flown across the C-17, the C-130 and the V-44 Blackfish, and guided
// cargo carries whatever residual the tables leave. A warning that fires on every drop
// of every airframe is not information, it is furniture -- and the one drop where it
// would have mattered is the one where the pilot has already learned to read past it.
//
// What did NOT go is the distinction between a rough answer and no answer. Every
// genuine failure above this point still exits with INVALID: an unsupported profile, an
// uncalibrated airframe, a failed ballistic solve, a missing canopy model, a failed
// empirical canopy solve. Those are the checks that stop a drop, and they are untouched.
//
// So by the time execution reaches here the solve has succeeded, and the answer is GOOD.
private _warnings = [];
private _confidence = "GOOD";

createHashMapFromArray [
    ["mode", _input get "mode"],
    ["velocityAlongMs", _velocityAlongMs],
    ["velocityRightMs", _velocityRightMs],
    ["releaseOffsetAlongM", _releaseOffsetAlongM],
    ["releaseOffsetRightM", _releaseOffsetRightM],
    ["actionToReleaseAlongM", _actionToReleaseAlongM],
    ["actionToReleaseRightM", _actionToReleaseRightM],
    ["freefallAlongM", _freefallAlongM],
    ["freefallRightM", _freefallRightM],
    ["canopyAlongM", _canopyAlongM],
    ["canopyRightM", _canopyRightM],
    ["windAlongM", if (_chuteMode) then {0} else {_windAlongM}],
    ["windRightM", if (_chuteMode) then {0} else {_windRightM}],
    ["windAlongMs", _windAlongMs],
    ["windRightMs", _windRightMs],
    ["totalAlongM", _totalAlongM],
    ["totalRightM", _totalRightM],
    ["releaseDistanceM", _totalAlongM],
    ["runInOffsetM", -_totalRightM],
    ["triggerTimeS", _ballistic get "triggerTimeS"],
    ["chuteAttachTimeS", _ballistic get "attachTimeS"],
    ["predictedChuteAglM", _ballistic get "attachAglM"],
    ["attachVerticalSpeedMs", _ballistic get "attachVerticalSpeedMs"],
    ["predictedCanopyTimeS", if (_chuteMode) then {0} else {_predictedCanopyTimeS}],
    ["canopyModel", _canopyModel],
    ["canopyBaselineWorld", _canopyBaselineWorld],
    ["canopyWindCorrectionWorld", _canopyWindCorrectionWorld],
    ["canopyPredictedWorld", _canopyPredictedWorld],
    ["canopyHeadingBracket", _canopyHeadingBracket],
    ["canopyWindDirectionBracket", _canopyWindDirectionBracket],
    ["canopyWindSpeedBracket", _canopyWindSpeedBracket],
    ["canopyUsedOppositeDirectionSymmetry", _canopyUsedOppositeDirectionSymmetry],
    ["confidence", _confidence],
    ["warnings", _warnings]
]

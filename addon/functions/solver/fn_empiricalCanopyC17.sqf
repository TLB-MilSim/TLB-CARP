params ["_headingDeg", "_windVectorWorld", "_model", ["_entrySpeedMs", -1], ["_freefallS", -1]];

private _invalid = {
    params ["_reason"];
    createHashMapFromArray [
        ["valid", false],
        ["modelId", ""],
        ["baselineWorld", [0, 0]],
        ["windCorrectionWorld", [0, 0]],
        ["canopyWorld", [0, 0]],
        ["predictedCanopyTimeS", 0],
        ["headingBracket", []],
        ["windDirectionBracket", []],
        ["windSpeedBracket", []],
        ["usedOppositeDirectionSymmetry", false],
        ["warnings", [_reason]]
    ]
};

if ((count _model) isEqualTo 0) exitWith {["EMPIRICAL C17 MODEL MISSING"] call _invalid};

private _headingAnchors = _model getOrDefault ["headingAnchorsDeg", []];
private _cardinalHeadingAnchors = _model getOrDefault ["cardinalHeadingAnchorsDeg", []];
private _zeroWorld = _model getOrDefault ["zeroWorldM", []];
private _zeroTime = _model getOrDefault ["zeroTimeS", []];
if ((count _headingAnchors) < 2 || {(count _zeroWorld) != (count _headingAnchors)} || {(count _zeroTime) != (count _headingAnchors)} || {(count _cardinalHeadingAnchors) < 2}) exitWith {
    ["EMPIRICAL C17 MODEL INVALID"] call _invalid
};

private _normalizeHeading = {
    params ["_value"];
    ((_value % 360) + 360) % 360
};
private _lerpScalar = {
    params ["_a", "_b", "_t"];
    _a + ((_b - _a) * _t)
};
private _lerpVector = {
    params ["_a", "_b", "_t"];
    [
        (_a # 0) + (((_b # 0) - (_a # 0)) * _t),
        (_a # 1) + (((_b # 1) - (_a # 1)) * _t)
    ]
};
private _interpScalar = {
    params ["_heading", "_anchors", "_values"];
    private _h = [_heading] call _normalizeHeading;
    private _exactIndex = _anchors findIf {abs (_h - _x) < 0.0001};
    if (_exactIndex >= 0) exitWith {
        private _anchor = _anchors # _exactIndex;
        [_values # _exactIndex, [_anchor, _anchor]]
    };
    private _loIndex = 0;
    {
        if (_h >= _x) then {_loIndex = _forEachIndex};
    } forEach _anchors;
    private _hiIndex = (_loIndex + 1) % (count _anchors);
    private _lo = _anchors # _loIndex;
    private _hi = if (_hiIndex isEqualTo 0) then {360} else {_anchors # _hiIndex};
    private _factor = (_h - _lo) / (_hi - _lo);
    private _value = [_values # _loIndex, _values # _hiIndex, _factor] call _lerpScalar;
    [_value, [_lo, _hi]]
};
private _interpVector = {
    params ["_heading", "_anchors", "_values"];
    private _h = [_heading] call _normalizeHeading;
    private _exactIndex = _anchors findIf {abs (_h - _x) < 0.0001};
    if (_exactIndex >= 0) exitWith {
        private _anchor = _anchors # _exactIndex;
        [+(_values # _exactIndex), [_anchor, _anchor]]
    };
    private _loIndex = 0;
    {
        if (_h >= _x) then {_loIndex = _forEachIndex};
    } forEach _anchors;
    private _hiIndex = (_loIndex + 1) % (count _anchors);
    private _lo = _anchors # _loIndex;
    private _hi = if (_hiIndex isEqualTo 0) then {360} else {_anchors # _hiIndex};
    private _factor = (_h - _lo) / (_hi - _lo);
    private _value = [_values # _loIndex, _values # _hiIndex, _factor] call _lerpVector;
    [_value, [_lo, _hi]]
};

private _heading = [_headingDeg] call _normalizeHeading;
private _baselineResult = [_heading, _headingAnchors, _zeroWorld] call _interpVector;
private _baselineWorld = +(_baselineResult # 0);
private _headingBracket = +(_baselineResult # 1);

// FORWARD THROW SCALES WITH THE SPEED THE LOAD ENTERS THE CANOPY PHASE AT.
//
// zeroWorldM is a measured displacement at ONE airspeed -- every one of the original 140
// bench runs flew at ~500 km/h -- and until v0.16.7 it was applied at every airspeed.
// Measured 2026-09-21, 8 headings x 4 speeds at 3000 m, verified zero wind, 0 degraded:
//
//     350 km/h   along bias -40.03 m      500 km/h   along bias  +4.08 m
//     425 km/h   along bias -18.04 m      600 km/h   along bias +24.08 m
//
// Pure along-track -- cross-track bias stayed under 2.2 m at every speed -- which is the
// signature of a throw term. Halving the drop altitude to 1500 m moved it by 1.5 m, so
// altitude is NOT an axis. Airspeed alone.
//
// THE FORM IS DERIVED, NOT FITTED. A body decelerating under quadratic drag covers a
// distance proportional to ln(v0/vt), and that beat both a power law and a straight line on
// the same four points: RMS 0.96 m against 2.13 and 2.33, chi 0.45 -- inside the
// measurement error. Only the two constants are fitted.
//
// It MULTIPLIES the baseline so each heading scales by its own measured throw, and it
// touches the BASELINE only: the wind correction is drift, which scales with canopy
// duration rather than with entry speed.
//
// Missing constants or a non-positive speed leave the baseline exactly as measured, so a
// model without them behaves as it did before this existed.
private _throwRefMs = _model getOrDefault ["throwRefSpeedMs", -1];
private _throwTerminalMs = _model getOrDefault ["throwTerminalMs", -1];
private _throwScale = 1;
if (_throwRefMs > 0 && {_throwTerminalMs > 0} && {_entrySpeedMs > _throwTerminalMs} && {_throwRefMs > _throwTerminalMs}) then {
    _throwScale = (log (_entrySpeedMs / _throwTerminalMs)) / (log (_throwRefMs / _throwTerminalMs));
    _baselineWorld = [(_baselineWorld # 0) * _throwScale, (_baselineWorld # 1) * _throwScale];
};
private _baseTimeResult = [_heading, _headingAnchors, _zeroTime] call _interpScalar;
private _baseTimeS = _baseTimeResult # 0;

// CANOPY DURATION DEPENDS ON THE DROP ALTITUDE, AND zeroTimeS WAS MEASURED AT ONE.
//
// Every original run had a freefall of 23.26 +/- 0.41 s -- about 3000 m -- and that one
// duration was applied at every altitude. From 3000 m the load reaches the chute at about
// -230 m/s and PLUNGES during inflation, spending most of the 300 m fast. From 1500 m it
// arrives at -153 m/s, does not plunge as far, and has far more altitude left to spend at
// the canopy's ~4.3 m/s terminal. Flown transients show it directly: 300 m to 182 m in
// three seconds, then 182 m at 4.3 m/s for another forty-two.
//
// Measured 2026-09-21: 8 headings x 4 drop altitudes, verified zero wind, 32 runs, 0
// degraded. Mean duration error 4.43 -> 2.08 s.
//
// PER-HEADING because every other axis here is, and because a single global slope made
// three of the eight headings worse.
//
// THIS REACHES THE TOT COUNTDOWN AND THE CALIBRATION RECORD ONLY. It does not touch the
// release point -- the canopy DISPLACEMENT is a stored vector, not time multiplied by
// anything -- so no drop geometry moves. Scaling the wind correction by this corrected
// duration is the obvious next step, it is physically the right idea, and it made two of
// three flown drops WORSE. It is deliberately not done here.
private _timeRefS = _model getOrDefault ["canopyTimeRefFreefallS", -1];
private _timeSlopes = _model getOrDefault ["canopyTimeSlopeS", []];
if (_timeRefS > 0 && {(count _timeSlopes) isEqualTo (count _headingAnchors)} && {_freefallS > 0}) then {
    private _slope = ([_heading, _headingAnchors, _timeSlopes] call _interpScalar) # 0;
    _baseTimeS = (_baseTimeS + (_slope * (_freefallS - _timeRefS))) max 1;
};

private _evalAxis = {
    params ["_speed", "_prefix"];
    private _corr5 = _model getOrDefault [_prefix + "5CorrectionWorldM", []];
    private _time5 = _model getOrDefault [_prefix + "5TimeDeltaS", []];
    private _corr10 = _model getOrDefault [_prefix + "10CorrectionWorldM", []];
    private _time10 = _model getOrDefault [_prefix + "10TimeDeltaS", []];
    if ((count _corr5) != (count _headingAnchors) || {(count _time5) != (count _headingAnchors)} || {(count _corr10) != (count _cardinalHeadingAnchors)} || {(count _time10) != (count _cardinalHeadingAnchors)}) exitWith {
        [[0, 0], 0, [0, 0], false, false]
    };

    private _v5 = ([_heading, _headingAnchors, _corr5] call _interpVector) # 0;
    private _t5 = ([_heading, _headingAnchors, _time5] call _interpScalar) # 0;
    private _v10 = ([_heading, _cardinalHeadingAnchors, _corr10] call _interpVector) # 0;
    private _t10 = ([_heading, _cardinalHeadingAnchors, _time10] call _interpScalar) # 0;

    if (_speed <= 0.0001) exitWith {[[0, 0], 0, [0, 0], false, true]};
    if (abs (_speed - 5) < 0.0001) exitWith {[+_v5, _t5, [5, 5], false, true]};
    if (_speed < 5) exitWith {
        private _factor = _speed / 5;
        [[(_v5 # 0) * _factor, (_v5 # 1) * _factor], _t5 * _factor, [0, 5], false, true]
    };
    if (abs (_speed - 10) < 0.0001) exitWith {[+_v10, _t10, [10, 10], false, true]};

    private _factor = (_speed - 5) / 5;
    private _correction = [_v5, _v10, _factor] call _lerpVector;
    private _timeDelta = [_t5, _t10, _factor] call _lerpScalar;
    [_correction, _timeDelta, [5, 10], _speed > 10, true]
};

private _wx = _windVectorWorld param [0, 0];
private _wy = _windVectorWorld param [1, 0];
private _windSpeed = sqrt ((_wx * _wx) + (_wy * _wy));
private _windCorrectionWorld = [0, 0];
private _timeDeltaS = 0;
private _windDirectionBracket = [0, 0];
private _windSpeedBracket = [0, 0];
private _activeDirections = [];
private _speedBrackets = [];
private _warnings = [];
private _axisInvalid = false;

if (abs _wx > 0.0001) then {
    private _prefix = if (_wx > 0) then {"east"} else {"west"};
    private _direction = if (_wx > 0) then {90} else {270};
    private _axis = [abs _wx, _prefix] call _evalAxis;
    if !(_axis # 4) then {
        _axisInvalid = true;
    } else {
        private _corr = _axis # 0;
        _windCorrectionWorld set [0, (_windCorrectionWorld # 0) + (_corr # 0)];
        _windCorrectionWorld set [1, (_windCorrectionWorld # 1) + (_corr # 1)];
        _timeDeltaS = _timeDeltaS + (_axis # 1);
        _speedBrackets pushBack +(_axis # 2);
        _activeDirections pushBack _direction;
        if (_axis # 3) then {_warnings pushBackUnique "WIND ABOVE EMPIRICAL RANGE"};
    };
};

if (abs _wy > 0.0001) then {
    private _prefix = if (_wy > 0) then {"north"} else {"south"};
    private _direction = if (_wy > 0) then {0} else {180};
    private _axis = [abs _wy, _prefix] call _evalAxis;
    if !(_axis # 4) then {
        _axisInvalid = true;
    } else {
        private _corr = _axis # 0;
        _windCorrectionWorld set [0, (_windCorrectionWorld # 0) + (_corr # 0)];
        _windCorrectionWorld set [1, (_windCorrectionWorld # 1) + (_corr # 1)];
        _timeDeltaS = _timeDeltaS + (_axis # 1);
        _speedBrackets pushBack +(_axis # 2);
        _activeDirections pushBack _direction;
        if (_axis # 3) then {_warnings pushBackUnique "WIND ABOVE EMPIRICAL RANGE"};
    };
};

if (_axisInvalid) exitWith {["EMPIRICAL C17 MODEL INVALID"] call _invalid};
if (_windSpeed > 10) then {_warnings pushBackUnique "WIND ABOVE EMPIRICAL RANGE"};

if ((count _activeDirections) > 1) then {
    _warnings pushBackUnique "DIAGONAL WIND COMPONENT COMBINATION PROVISIONAL";
    private _dirs = +_activeDirections;
    _dirs sort true;
    _windDirectionBracket = if (_dirs isEqualTo [0, 270]) then {[270, 360]} else {_dirs};
} else {
    if ((count _activeDirections) isEqualTo 1) then {
        private _dir = _activeDirections # 0;
        _windDirectionBracket = [_dir, _dir];
    };
};

if ((count _speedBrackets) isEqualTo 1) then {
    _windSpeedBracket = +(_speedBrackets # 0);
};
if ((count _speedBrackets) > 1) then {
    private _first = _speedBrackets # 0;
    private _same = _speedBrackets findIf {!(_x isEqualTo _first)};
    if (_same < 0) then {
        _windSpeedBracket = +_first;
    } else {
        private _lo = 999;
        private _hi = -999;
        {
            if ((_x # 0) < _lo) then {_lo = _x # 0};
            if ((_x # 1) > _hi) then {_hi = _x # 1};
        } forEach _speedBrackets;
        _windSpeedBracket = [_lo, _hi];
    };
};

private _canopyWorld = [
    (_baselineWorld # 0) + (_windCorrectionWorld # 0),
    (_baselineWorld # 1) + (_windCorrectionWorld # 1)
];
private _predictedCanopyTimeS = 0 max (_baseTimeS + _timeDeltaS);

createHashMapFromArray [
    ["valid", true],
    ["modelId", _model getOrDefault ["modelId", "EMPIRICAL_C17_V2"]],
    ["baselineWorld", _baselineWorld],
    ["throwScale", _throwScale],
    ["windCorrectionWorld", _windCorrectionWorld],
    ["canopyWorld", _canopyWorld],
    ["predictedCanopyTimeS", _predictedCanopyTimeS],
    ["headingBracket", _headingBracket],
    ["windDirectionBracket", _windDirectionBracket],
    ["windSpeedBracket", _windSpeedBracket],
    ["usedOppositeDirectionSymmetry", false],
    ["warnings", _warnings]
]

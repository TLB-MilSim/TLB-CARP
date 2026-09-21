params ["_cargo", "_parachute", ["_elapsedS", 0], ["_targetS", -1]];
if (isNull _cargo || {isNull _parachute}) exitWith {[]};

private _cargoPosASL = getPosASL _cargo;
private _parachutePosASL = getPosASL _parachute;
private _windTelemetry = [_cargoPosASL] call USAFDC_fnc_sampleWindTelemetry;
[
    // Keep the first eight elements compatible with USAFDC_CAL_V3 v0.1.7/v0.1.8 samples.
    _targetS,
    _elapsedS,
    _parachutePosASL,
    (getPosATL _parachute) # 2,
    getDir _parachute,
    velocity _parachute,
    _windTelemetry getOrDefault ["engineWind", []],
    _windTelemetry getOrDefault ["aceEffectiveSpeedMs", -1],
    // v0.1.9 additive transient detail.
    _cargoPosASL,
    (getPosATL _cargo) # 2,
    velocity _cargo,
    vectorDir _parachute,
    vectorUp _parachute,
    _windTelemetry getOrDefault ["aceEffectiveVector", []]
]

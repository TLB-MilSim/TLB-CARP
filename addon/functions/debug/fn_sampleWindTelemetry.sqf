params [["_positionASL", [0, 0, 0], [[]]]];

private _engineWind = +wind;
private _engineSpeedMs = vectorMagnitude _engineWind;
private _aceAvailable = !(isNil "ace_weather_fnc_calculateWindSpeed");
private _aceWeatherEnabled = missionNamespace getVariable ["ace_weather_enabled", false];
private _aceWindSimulation = missionNamespace getVariable ["ace_weather_windSimulation", false];
private _aceAdvancedBallistics = missionNamespace getVariable ["ace_advanced_ballistics_enabled", false];
private _aceEffectiveSpeedMs = -1;
private _aceEffectiveVector = [0, 0, 0];

if (_aceAvailable) then {
    private _aceWindFunction = missionNamespace getVariable ["ace_weather_fnc_calculateWindSpeed", {}];
    _aceEffectiveSpeedMs = [_positionASL, _aceAdvancedBallistics, true, true] call _aceWindFunction;
    if (_engineSpeedMs > 0.001) then {
        _aceEffectiveVector = _engineWind vectorMultiply (_aceEffectiveSpeedMs / _engineSpeedMs);
    };
};

createHashMapFromArray [
    ["engineWind", _engineWind],
    ["engineSpeedMs", _engineSpeedMs],
    ["aceAvailable", _aceAvailable],
    ["aceWeatherEnabled", _aceWeatherEnabled],
    ["aceWindSimulation", _aceWindSimulation],
    ["aceAdvancedBallistics", _aceAdvancedBallistics],
    ["aceEffectiveSpeedMs", _aceEffectiveSpeedMs],
    ["aceEffectiveVector", _aceEffectiveVector]
]

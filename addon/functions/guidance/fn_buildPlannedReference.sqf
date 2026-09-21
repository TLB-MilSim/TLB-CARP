params ["_baseInput", "_model", "_dz", "_targetAglM", "_targetGroundSpeedKmh"];

private _targetGroundSpeedMs = (0 max _targetGroundSpeedKmh) / 3.6;
private _input = createHashMap;
{_input set [_x, _baseInput get _x]} forEach keys _baseInput;
_input set ["groundSpeedMs", _targetGroundSpeedMs];
_input set ["velocityAlongMs", _targetGroundSpeedMs];
_input set ["velocityRightMs", 0];
_input set ["verticalSpeedMs", 0];

private _terrainGuess = _dz # 2;
private _reference = createHashMapFromArray [["valid", false]];
for "_i" from 0 to 1 do {
    _input set ["actionAltitudeAslM", _terrainGuess + _targetAglM];
    _input set ["openingTerrainAslM", _terrainGuess];
    _reference = [_input, _model, _dz] call USAFDC_fnc_solveWorldReference;
    if (_reference getOrDefault ["valid", false]) then {
        _terrainGuess = getTerrainHeightASL (_reference get "rpPosASL");
    };
};
_reference set ["targetAglM", _targetAglM];
_reference set ["targetGroundSpeedKmh", _targetGroundSpeedKmh];
_reference

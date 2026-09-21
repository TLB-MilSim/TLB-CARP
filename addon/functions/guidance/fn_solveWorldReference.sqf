params ["_input", "_model", "_dz"];

private _runInDeg = _input get "runInDeg";
private _basis = [_runInDeg] call TLB_CARP_fnc_basisFromHeading;
private _forward = _basis get "forward";
private _right = _basis get "right";

private _first = [_input, _model] call TLB_CARP_fnc_solveRelative;
if ((_first getOrDefault ["confidence", "INVALID"]) isEqualTo "INVALID") exitWith {
    createHashMapFromArray [["valid", false], ["relative", _first]]
};

private _provisionalChute = [
    (_dz # 0) - ((_forward # 0) * (_first get "canopyAlongM")) - ((_right # 0) * (_first get "canopyRightM")),
    (_dz # 1) - ((_forward # 1) * (_first get "canopyAlongM")) - ((_right # 1) * (_first get "canopyRightM")),
    0
];
private _openingTerrain = getTerrainHeightASL _provisionalChute;
private _secondInput = createHashMap;
{_secondInput set [_x, _input get _x]} forEach keys _input;
_secondInput set ["openingTerrainAslM", _openingTerrain];

private _relative = [_secondInput, _model] call TLB_CARP_fnc_solveRelative;
if ((_relative getOrDefault ["confidence", "INVALID"]) isEqualTo "INVALID") exitWith {
    createHashMapFromArray [["valid", false], ["relative", _relative]]
};

private _rpX = (_dz # 0) - ((_forward # 0) * (_relative get "totalAlongM")) - ((_right # 0) * (_relative get "totalRightM"));
private _rpY = (_dz # 1) - ((_forward # 1) * (_relative get "totalAlongM")) - ((_right # 1) * (_relative get "totalRightM"));
private _rp = [_rpX, _rpY, getTerrainHeightASL [_rpX, _rpY]];

private _chuteAlongM = (_relative get "actionToReleaseAlongM") + (_relative get "freefallAlongM");
private _chuteRightM = (_relative get "actionToReleaseRightM") + (_relative getOrDefault ["freefallRightM", 0]);
private _chute = [
    (_rp # 0) + ((_forward # 0) * _chuteAlongM) + ((_right # 0) * _chuteRightM),
    (_rp # 1) + ((_forward # 1) * _chuteAlongM) + ((_right # 1) * _chuteRightM),
    _openingTerrain + (_relative get "predictedChuteAglM")
];

createHashMapFromArray [
    ["valid", true],
    ["relative", _relative],
    ["rpPosASL", _rp],
    ["chutePosASL", _chute],
    ["openingTerrainAslM", _openingTerrain],
    ["forward", _forward],
    ["right", _right]
]

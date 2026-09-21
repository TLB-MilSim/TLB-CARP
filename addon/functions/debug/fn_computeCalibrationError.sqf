params ["_posASL", "_dzPosASL", "_runInDeg"];
if ((count _posASL) < 2 || {(count _dzPosASL) < 2}) exitWith {
    createHashMapFromArray [["valid", false], ["alongM", 0], ["rightM", 0], ["radialM", 0]]
};

private _basis = [_runInDeg] call TLB_CARP_fnc_basisFromHeading;
private _forward = _basis get "forward";
private _right = _basis get "right";
private _dx = (_posASL # 0) - (_dzPosASL # 0);
private _dy = (_posASL # 1) - (_dzPosASL # 1);
private _alongM = (_dx * (_forward # 0)) + (_dy * (_forward # 1));
private _rightM = (_dx * (_right # 0)) + (_dy * (_right # 1));
private _radialM = sqrt ((_dx * _dx) + (_dy * _dy));

createHashMapFromArray [
    ["valid", true],
    ["alongM", _alongM],
    ["rightM", _rightM],
    ["radialM", _radialM]
]

params ["_vehicle", "_airState", "_runInDeg"];

private _basis = [_runInDeg] call USAFDC_fnc_basisFromHeading;
private _forward = _basis get "forward";
private _right = _basis get "right";
private _velocity = _airState getOrDefault ["velocity", velocity _vehicle];
private _vx = _velocity # 0;
private _vy = _velocity # 1;
private _velocityAlongMs = (_vx * (_forward # 0)) + (_vy * (_forward # 1));
private _velocityRightMs = (_vx * (_right # 0)) + (_vy * (_right # 1));

private _airPos = _airState getOrDefault ["posASL", getPosASL _vehicle];
private _releaseModelOffset = _airState getOrDefault ["releaseModelOffset", [0, 0, 0]];
private _releaseWorld = _vehicle modelToWorldWorld _releaseModelOffset;
private _releaseDx = (_releaseWorld # 0) - (_airPos # 0);
private _releaseDy = (_releaseWorld # 1) - (_airPos # 1);

createHashMapFromArray [
    ["forward", _forward],
    ["right", _right],
    ["velocityAlongMs", _velocityAlongMs],
    ["velocityRightMs", _velocityRightMs],
    ["releaseOffsetAlongM", (_releaseDx * (_forward # 0)) + (_releaseDy * (_forward # 1))],
    ["releaseOffsetRightM", (_releaseDx * (_right # 0)) + (_releaseDy * (_right # 1))],
    ["releaseVerticalOffsetM", (_releaseWorld # 2) - (_airPos # 2)],
    ["releaseOffsetWorld", _releaseWorld]
]

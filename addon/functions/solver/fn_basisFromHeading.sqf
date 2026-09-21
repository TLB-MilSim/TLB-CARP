params ["_headingDeg"];
private _h = _headingDeg mod 360;
if (_h < 0) then {_h = _h + 360};
private _s = sin _h;
private _c = cos _h;
createHashMapFromArray [
    ["forward", [_s, _c]],
    ["right", [_c, -_s]]
]

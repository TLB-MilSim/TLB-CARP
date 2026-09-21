params ["_releaseAglM", "_verticalSpeedMs", "_triggerAglM", "_attachLagS", "_gravityMs2"];
if (_releaseAglM <= _triggerAglM) exitWith {
    createHashMapFromArray [["valid", false], ["reason", "RELEASE BELOW TRIGGER"]]
};
private _disc = (_verticalSpeedMs * _verticalSpeedMs) + (2 * _gravityMs2 * (_releaseAglM - _triggerAglM));
private _triggerTimeS = (_verticalSpeedMs + sqrt _disc) / _gravityMs2;
private _attachTimeS = _triggerTimeS + _attachLagS;
private _attachAglM = _releaseAglM + (_verticalSpeedMs * _attachTimeS) - (0.5 * _gravityMs2 * _attachTimeS * _attachTimeS);
private _attachVz = _verticalSpeedMs - (_gravityMs2 * _attachTimeS);
createHashMapFromArray [
    ["valid", true],
    ["triggerTimeS", _triggerTimeS],
    ["attachTimeS", _attachTimeS],
    ["attachAglM", _attachAglM],
    ["attachVerticalSpeedMs", _attachVz]
]

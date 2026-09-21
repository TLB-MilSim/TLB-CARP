params ["_windComponentMs", "_canopyTimeS", "_tauS"];
if (_canopyTimeS <= 0) exitWith {0};
_windComponentMs * (_canopyTimeS - _tauS * (1 - exp (-_canopyTimeS / _tauS)))

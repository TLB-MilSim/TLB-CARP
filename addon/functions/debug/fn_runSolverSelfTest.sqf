private _model = [] call TLB_CARP_fnc_getModel;
private _fixtureRoot = [] call TLB_CARP_fnc_getTestVectors;
private _fixtures = _fixtureRoot get "vectors";
private _allPass = true;

{
    private _fixture = _x;
    private _result = [_fixture, _model] call TLB_CARP_fnc_solveRelative;
    private _expected = _fixture get "expected";
    private _alongError = abs ((_result get "totalAlongM") - (_expected get "totalAlongM"));
    private _rightError = abs ((_result get "totalRightM") - (_expected get "totalRightM"));
    private _canopyError = abs ((_result get "predictedCanopyTimeS") - (_expected get "predictedCanopyTimeS"));
    private _chuteExpected = _expected getOrDefault ["predictedChuteAglM", -1e9];
    private _chuteError = if (_chuteExpected < -1e8) then {0} else {abs ((_result get "predictedChuteAglM") - _chuteExpected)};
    private _pass = _alongError < 0.08 && {_rightError < 0.08} && {_canopyError < 0.08} && {_chuteError < 0.08};
    if (!_pass) then {_allPass = false};
    diag_log format [
        "[TLB CARP][SELFTEST] %1 pass=%2 alongErr=%3 rightErr=%4 canopyErr=%5 chuteErr=%6",
        _fixture get "id", _pass, _alongError, _rightError, _canopyError, _chuteError
    ];
} forEach _fixtures;

_allPass

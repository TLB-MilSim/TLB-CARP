params ["_vehicle", "_solution"];

private _invalid = createHashMapFromArray [
    ["dropEtaS", -1], ["chuteEtaS", -1], ["touchdownEtaS", -1],
    ["dropClockText", "--:--:--"], ["chuteClockText", "--:--:--"], ["totClockText", "--:--:--"],
    ["dropTMinusText", "T---:--"], ["chuteTMinusText", "T---:--"], ["totTMinusText", "T---:--"],
    ["timingState", "EST"]
];
if (isNull _vehicle || {!(_solution getOrDefault ["valid", false])}) exitWith {_invalid};

private _model = [] call TLB_CARP_fnc_getModel;
private _profileId = _solution getOrDefault ["profileId", ""];
private _profile = (_model get "aircraft") getOrDefault [_profileId, createHashMap];
if ((count _profile) isEqualTo 0) exitWith {_invalid};
private _releaseDelayS = _profile get "releaseDelayS";
private _relative = _solution getOrDefault ["relative", createHashMap];
private _chuteAttachTimeS = _relative getOrDefault ["chuteAttachTimeS", 0];
private _predictedCanopyTimeS = _relative getOrDefault ["predictedCanopyTimeS", 0];

private _airState = _solution getOrDefault ["aircraftState", createHashMap];
private _actualGs = _airState getOrDefault ["groundSpeedMs", 0];
private _targetGs = (TLB_CARP_state_targetGroundSpeedKmh max 100) / 3.6;
private _speedMs = if (missionNamespace getVariable ["TLB_CARP_state_apArmed", false]) then {_targetGs} else {_actualGs max 1};
private _signedRpM = _solution getOrDefault ["signedRpM", -1];

private _distance2d = {
    params ["_a", "_b"];
    private _dx = (_b # 0) - (_a # 0);
    private _dy = (_b # 1) - (_a # 1);
    sqrt ((_dx * _dx) + (_dy * _dy))
};

private _dropEtaS = 0;
private _usePathEta = (missionNamespace getVariable ["TLB_CARP_state_apArmed", false]) && {_solution getOrDefault ["pathValid", false]} && {(_solution getOrDefault ["routeEtaS", -1]) >= 0};
if (_signedRpM > 0) then {
    if (_usePathEta) then {
        _dropEtaS = _solution getOrDefault ["routeEtaS", 0];
    } else {
        if (_signedRpM <= 1500) then {
            _dropEtaS = _signedRpM / (_speedMs max 1);
        } else {
            private _airPos = getPosASL _vehicle;
            private _capturePosASL = _solution getOrDefault ["capturePosASL", _solution get "liveRpPosASL"];
            private _liveRp = _solution get "liveRpPosASL";
            private _routeM = ([_airPos, _capturePosASL] call _distance2d) + ([_capturePosASL, _liveRp] call _distance2d);
            _dropEtaS = _routeM / (_speedMs max 1);
        };
    };
};

private _chuteEtaS = _dropEtaS + _releaseDelayS + _chuteAttachTimeS;
private _touchdownEtaS = if ((_solution getOrDefault ["mode", "TOUCHDOWN"]) isEqualTo "TOUCHDOWN") then {
    _chuteEtaS + _predictedCanopyTimeS
} else {
    -1
};

private _two = {
    params ["_value"];
    if (_value < 10) then {format ["0%1", _value]} else {str _value}
};
private _fmtDuration = {
    params ["_seconds"];
    if (_seconds < 0) exitWith {"T---:--"};
    private _whole = floor (_seconds + 0.5);
    private _hours = floor (_whole / 3600);
    private _minutes = floor ((_whole mod 3600) / 60);
    private _secs = _whole mod 60;
    if (_hours > 0) then {
        format ["T-%1:%2:%3", [_hours] call _two, [_minutes] call _two, [_secs] call _two]
    } else {
        format ["T-%1:%2", [_minutes] call _two, [_secs] call _two]
    }
};
private _fmtClock = {
    params ["_etaS"];
    if (_etaS < 0) exitWith {"--:--:--"};
    private _missionSeconds = floor (((daytime * 3600) + _etaS) mod 86400);
    private _hours = floor (_missionSeconds / 3600);
    private _minutes = floor ((_missionSeconds mod 3600) / 60);
    private _secs = _missionSeconds mod 60;
    format ["%1:%2:%3", [_hours] call _two, [_minutes] call _two, [_secs] call _two]
};

private _timingState = if (missionNamespace getVariable ["TLB_CARP_state_apArmed", false]) then {
    if ((_signedRpM <= 800) && {_solution getOrDefault ["releaseStable", false]}) then {"AP STABLE"} else {"AP CONTROLLED"}
} else {
    "EST"
};

createHashMapFromArray [
    ["dropEtaS", _dropEtaS],
    ["chuteEtaS", _chuteEtaS],
    ["touchdownEtaS", _touchdownEtaS],
    ["dropClockText", [_dropEtaS] call _fmtClock],
    ["chuteClockText", [_chuteEtaS] call _fmtClock],
    ["totClockText", [_touchdownEtaS] call _fmtClock],
    ["dropTMinusText", [_dropEtaS] call _fmtDuration],
    ["chuteTMinusText", [_chuteEtaS] call _fmtDuration],
    ["totTMinusText", [_touchdownEtaS] call _fmtDuration],
    ["timingState", _timingState]
]

params ["_vehicle", "_solution"];

private _invalid = createHashMapFromArray [
    ["pathValid", false],
    ["pathState", "OFF"],
    ["pathDesiredTrackDeg", 0],
    ["captureGateASL", []],
    ["captureDistanceM", -1],
    ["routeDistanceM", -1],
    ["routeEtaS", -1],
    ["targetDropAslM", -1],
    ["altitudeErrorM", 0],
    ["requiredVerticalSpeedMs", 0],
    ["commandVerticalSpeedMs", 0],
    ["altitudePathState", "ALT UNAVAILABLE"],
    ["altitudeReachable", false]
];
if (isNull _vehicle || {!(_solution getOrDefault ["valid", false])} || {!TLB_CARP_state_runInLocked}) exitWith {_invalid};

private _plannedRp = +(_solution getOrDefault ["plannedRpPosASL", []]);
private _liveRp = +(_solution getOrDefault ["liveRpPosASL", _solution getOrDefault ["rpPosASL", []]]);
private _dz = +(_solution getOrDefault ["dzPosASL", TLB_CARP_state_dzPosASL]);
if ((count _plannedRp) < 3 || {(count _liveRp) < 3} || {(count _dz) < 3}) exitWith {_invalid};

private _runInDeg = _solution getOrDefault ["runInDeg", TLB_CARP_state_runInDeg];
private _basis = [_runInDeg] call TLB_CARP_fnc_basisFromHeading;
private _forward = _basis get "forward";
private _right = _basis get "right";
private _airPos = getPosASL _vehicle;
private _airState = _solution getOrDefault ["aircraftState", createHashMap];
private _trackDeg = _airState getOrDefault ["trackDeg", getDir _vehicle];

private _dx = (_airPos # 0) - (_plannedRp # 0);
private _dy = (_airPos # 1) - (_plannedRp # 1);
private _alongM = (_dx * (_forward # 0)) + (_dy * (_forward # 1));
private _crossTrackM = (_dx * (_right # 0)) + (_dy * (_right # 1));
private _trackErrorDeg = (((_trackDeg - _runInDeg + 540) mod 360) - 180);
private _signedRpM = _solution getOrDefault ["signedRpM", 1e9];
private _remainingUpstreamM = 0 max (-_alongM);

private _dzTerrainAsl = getTerrainHeightASL [_dz # 0, _dz # 1];
private _targetDropAslM = _dzTerrainAsl + TLB_CARP_state_targetAglM;
private _finalAnchor = +_plannedRp;
_finalAnchor set [2, _targetDropAslM];

private _bearingTo = {
    params ["_from", "_to"];
    private _bdx = (_to # 0) - (_from # 0);
    private _bdy = (_to # 1) - (_from # 1);
    ((_bdx atan2 _bdy) + 360) mod 360
};
private _distance2D = {
    params ["_a", "_b"];
    private _ddx = (_b # 0) - (_a # 0);
    private _ddy = (_b # 1) - (_a # 1);
    sqrt ((_ddx * _ddx) + (_ddy * _ddy))
};

private _leadM = ((1500 max (3 * abs _crossTrackM)) min 5000);
private _canUseRemoteGate = (_remainingUpstreamM > 2000) && {((abs _crossTrackM) > 100) || {(abs _trackErrorDeg) > 10}};
private _gateLeadM = _leadM;
if (_canUseRemoteGate) then {
    _gateLeadM = _gateLeadM min (_remainingUpstreamM - 500);
    _gateLeadM = _gateLeadM max 1500;
};
private _captureGate = [
    (_plannedRp # 0) - ((_forward # 0) * _gateLeadM),
    (_plannedRp # 1) - ((_forward # 1) * _gateLeadM),
    _targetDropAslM
];

private _nearestOnLine = [
    (_plannedRp # 0) + ((_forward # 0) * _alongM),
    (_plannedRp # 1) + ((_forward # 1) * _alongM),
    _targetDropAslM
];
private _lookAheadM = ((500 max ((abs _crossTrackM) * 5)) min 1500);
private _maxLookAheadM = ((_remainingUpstreamM - 250) max 100);
_lookAheadM = _lookAheadM min _maxLookAheadM;
private _finalLookAhead = [
    (_nearestOnLine # 0) + ((_forward # 0) * _lookAheadM),
    (_nearestOnLine # 1) + ((_forward # 1) * _lookAheadM),
    _targetDropAslM
];

private _pathState = "CAPTURE FINAL";
if (_signedRpM <= 0) then {
    _pathState = "POST DROP";
} else {
    if ((_signedRpM <= 800) && {_solution getOrDefault ["releaseStable", false]}) then {
        _pathState = "RELEASE STABLE";
    } else {
        if ((_signedRpM <= 1500) && {(abs _crossTrackM) <= 25} && {(abs _trackErrorDeg) <= 3}) then {
            _pathState = "FINAL RUN";
        } else {
            if (_canUseRemoteGate) then {_pathState = "INTERCEPT"} else {_pathState = "CAPTURE FINAL"};
        };
    };
};

private _pathDesiredTrackDeg = _runInDeg;
private _captureTarget = +_finalLookAhead;
switch (_pathState) do {
    case "INTERCEPT": {
        _captureTarget = +_captureGate;
        _pathDesiredTrackDeg = [_airPos, _captureGate] call _bearingTo;
    };
    case "CAPTURE FINAL": {
        _captureTarget = +_finalLookAhead;
        _pathDesiredTrackDeg = [_airPos, _finalLookAhead] call _bearingTo;
    };
    default {
        _captureTarget = +_finalLookAhead;
        _pathDesiredTrackDeg = _runInDeg;
    };
};

private _captureDistanceM = [_airPos, _captureTarget] call _distance2D;
private _routeDistanceM = 0 max _signedRpM;
if (_pathState isEqualTo "INTERCEPT") then {
    _routeDistanceM = ([_airPos, _captureGate] call _distance2D) + ([_captureGate, _liveRp] call _distance2D);
};
if (_pathState isEqualTo "CAPTURE FINAL") then {
    _routeDistanceM = ([_airPos, _finalLookAhead] call _distance2D) + ([_finalLookAhead, _liveRp] call _distance2D);
};
if (_pathState isEqualTo "POST DROP") then {_routeDistanceM = 0};

private _targetGroundSpeedMs = (TLB_CARP_state_targetGroundSpeedKmh max 100) / 3.6;
private _routeEtaS = if (_routeDistanceM > 0) then {_routeDistanceM / (_targetGroundSpeedMs max 1)} else {0};
private _altitudeErrorM = _targetDropAslM - (_airPos # 2);
// Capture altitude early instead of spreading the correction all the way to the RP.
// The ballistic solver remains authoritative if AP cannot reach the requested profile.
private _verticalCaptureTimeS = (((_routeEtaS * 0.60) - 8) max 8);
private _requiredVerticalSpeedMs = _altitudeErrorM / _verticalCaptureTimeS;
private _commandVerticalSpeedMs = (_requiredVerticalSpeedMs max -20) min 12;
private _altitudeReachable = (_requiredVerticalSpeedMs >= -20) && {_requiredVerticalSpeedMs <= 12};
private _altitudePathState = "ALT CAPTURED";
if ((abs _altitudeErrorM) > 30) then {
    if (!_altitudeReachable) then {
        _altitudePathState = "ALT UNABLE";
    } else {
        _altitudePathState = if (_altitudeErrorM < 0) then {"ALT HIGH"} else {"ALT LOW"};
    };
};

createHashMapFromArray [
    ["pathValid", true],
    ["pathState", _pathState],
    ["finalLineAnchorASL", _finalAnchor],
    ["finalLineHeadingDeg", _runInDeg],
    ["pathAlongM", _alongM],
    ["pathCrossTrackM", _crossTrackM],
    ["captureGateASL", _captureGate],
    ["captureDistanceM", _captureDistanceM],
    ["pathDesiredTrackDeg", _pathDesiredTrackDeg],
    ["routeDistanceM", _routeDistanceM],
    ["routeEtaS", _routeEtaS],
    ["targetDropAslM", _targetDropAslM],
    ["altitudeErrorM", _altitudeErrorM],
    ["requiredVerticalSpeedMs", _requiredVerticalSpeedMs],
    ["commandVerticalSpeedMs", _commandVerticalSpeedMs],
    ["altitudePathState", _altitudePathState],
    ["altitudeReachable", _altitudeReachable],
    ["pathLookAheadASL", _finalLookAhead],
    ["pathLookAheadM", _lookAheadM]
]

params ["_airPos", "_stableAnchor", "_liveRp", "_runInDeg", "_currentTrackDeg"];

private _basis = [_runInDeg] call TLB_CARP_fnc_basisFromHeading;
private _forward = _basis get "forward";
private _right = _basis get "right";

private _toLiveRp = [(_liveRp # 0) - (_airPos # 0), (_liveRp # 1) - (_airPos # 1)];
private _signedRpM = ((_toLiveRp # 0) * (_forward # 0)) + ((_toLiveRp # 1) * (_forward # 1));
private _fromStable = [(_airPos # 0) - (_stableAnchor # 0), (_airPos # 1) - (_stableAnchor # 1)];
private _crossTrackM = ((_fromStable # 0) * (_right # 0)) + ((_fromStable # 1) * (_right # 1));
private _trackErrorDeg = (((_currentTrackDeg - _runInDeg + 540) mod 360) - 180);

private _lookAheadM = ((_signedRpM * 0.5) max 500) min 2000;
private _limitDeg = [_signedRpM] call TLB_CARP_fnc_interceptLimitDeg;
private _rawInterceptDeg = if ((abs _crossTrackM) <= 15 || {_limitDeg <= 0}) then {0} else {((-_crossTrackM) atan2 _lookAheadM)};
private _interceptAngleDeg = (_rawInterceptDeg max (-_limitDeg)) min _limitDeg;
private _rawDesiredTrackDeg = (_runInDeg + _interceptAngleDeg + 360) mod 360;

private _nearest = [
    (_airPos # 0) - ((_right # 0) * _crossTrackM),
    (_airPos # 1) - ((_right # 1) * _crossTrackM),
    0
];
private _capture = [
    (_nearest # 0) + ((_forward # 0) * _lookAheadM),
    (_nearest # 1) + ((_forward # 1) * _lookAheadM),
    0
];
_capture set [2, getTerrainHeightASL _capture];

private _insideFinal = _signedRpM <= 800;
private _releaseStable = (!_insideFinal) || {((abs _crossTrackM) <= 50) && {(abs _trackErrorDeg) <= 5}};
private _onRunIn = ((abs _crossTrackM) <= 25) && {(abs _trackErrorDeg) <= 3};
private _guidanceState = if (_signedRpM <= 0) then {
    "PASSED RP"
} else {
    if (_insideFinal && {!_releaseStable}) then {
        "UNSTABLE RUN-IN"
    } else {
        if (_onRunIn) then {
            "ON RUN-IN"
        } else {
            if ((abs _crossTrackM) <= 75) then {"CAPTURE RUN-IN"} else {"INTERCEPT"}
        }
    }
};

createHashMapFromArray [
    ["signedRpM", _signedRpM],
    ["crossTrackM", _crossTrackM],
    ["trackErrorDeg", _trackErrorDeg],
    ["capturePosASL", _capture],
    ["rawDesiredTrackDeg", _rawDesiredTrackDeg],
    ["interceptAngleDeg", _interceptAngleDeg],
    ["interceptLimitDeg", _limitDeg],
    ["lookAheadM", _lookAheadM],
    ["releaseStable", _releaseStable],
    ["onRunIn", _onRunIn],
    ["guidanceState", _guidanceState]
]

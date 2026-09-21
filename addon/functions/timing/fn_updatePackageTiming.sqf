params ["_vehicle", "_solution"];

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
private _fmtClockSeconds = {
    params ["_seconds"];
    if (_seconds < 0) exitWith {"--:--:--"};
    private _missionSeconds = floor (_seconds mod 86400);
    private _hours = floor (_missionSeconds / 3600);
    private _minutes = floor ((_missionSeconds mod 3600) / 60);
    private _secs = _missionSeconds mod 60;
    format ["%1:%2:%3", [_hours] call _two, [_minutes] call _two, [_secs] call _two]
};
private _empty = {
    params ["_state"];
    createHashMapFromArray [
        ["dropEtaS", -1], ["chuteEtaS", -1], ["touchdownEtaS", -1],
        ["dropClockText", "--:--:--"], ["chuteClockText", "--:--:--"], ["totClockText", "--:--:--"],
        ["dropTMinusText", "T---:--"], ["chuteTMinusText", "T---:--"], ["totTMinusText", "T---:--"],
        ["timingState", _state], ["packageState", _state]
    ]
};

private _state = missionNamespace getVariable ["TLB_CARP_state_packageTimingState", "IDLE"];
private _solutionValid = _solution getOrDefault ["valid", false];
// The manifest, not usaf_cargo. Release is detected by an object leaving this list, so
// reading only USAF's array meant an ACE or vehicle-in-vehicle load left the aircraft
// without the tracker ever noticing -- no RELEASED transition, and a frozen TOT.
private _currentCargo = if (isNull _vehicle) then {[]} else {[_vehicle] call TLB_CARP_fnc_getLoadedCargo};

// ---- guided cargo: one steer job per load that leaves, however it leaves ------------
//
// NOT tied to the RELEASED transition. That fires once and names one object, so a stick
// of four produced one guided canopy and three ballistic ones while the HUD reported
// STEERING for the lot. Diffing the manifest on every tick catches each load in a
// sequence, and catches a drop the pilot made through USAF's own action instead of
// through CARP.
//
// The carrier identity check is what stops "the player changed aircraft" being read as
// "four loads just departed" -- the same trap the RELEASED latch guards against below.
if (!(isNil "TLB_CARP_fnc_steerBegin")) then {
    private _steerCarrier = missionNamespace getVariable ["TLB_CARP_state_steerSeenCarrier", objNull];
    if (!isNull _vehicle && {_vehicle isEqualTo _steerCarrier}) then {
        private _departed = (missionNamespace getVariable ["TLB_CARP_state_steerSeenCargo", []]) select {!(_x in _currentCargo)};
        if ((count _departed) > 0 && {[_vehicle] call TLB_CARP_fnc_steerPublisher}) then {
            {[_vehicle, _x] call TLB_CARP_fnc_steerBegin} forEach _departed;
        };
    };
    TLB_CARP_state_steerSeenCarrier = _vehicle;
    TLB_CARP_state_steerSeenCargo = +_currentCargo;
};

if (_state in ["IDLE", "ARRIVED", "LOST"] && {_solutionValid} && {(count _currentCargo) > 0} && {(_solution getOrDefault ["signedRpM", -1]) > 0}) then {
    if (_state in ["ARRIVED", "LOST"]) then {
        [] call TLB_CARP_fnc_resetPackageTiming;
    };
    TLB_CARP_state_packageTimingState = "ESTIMATE";
    TLB_CARP_state_packageCargoSnapshot = +_currentCargo;
    TLB_CARP_state_packageCarrier = _vehicle;
    _state = "ESTIMATE";
};

if (_state isEqualTo "IDLE") exitWith {
    private _result = ["IDLE"] call _empty;
    TLB_CARP_state_packageTiming = _result;
    _result
};

if (_state isEqualTo "ESTIMATE") then {
    // Release detection must run BEFORE any invalid-solution bail-out. Dropping
    // the last cargo empties usaf_cargo, which makes the live solution invalid
    // on the same tick the cargo leaves; gating this on validity left the state
    // machine stuck in ESTIMATE, so RELEASED/CHUTE/ARRIVED never happened and
    // the visible TOT froze on the final package.
    private _previousCargo = +(missionNamespace getVariable ["TLB_CARP_state_packageCargoSnapshot", []]);
    private _removed = _previousCargo select {!(_x in _currentCargo)};
    // Solver validity used to gate this block, which also implicitly rejected
    // "cargo vanished because the player left the aircraft (or changed seats to
    // another vehicle)". With the gate gone, the carrier identity check is what
    // keeps that from latching a release that never happened.
    private _snapshotCarrier = missionNamespace getVariable ["TLB_CARP_state_packageCarrier", objNull];
    private _sameCarrier = !isNull _vehicle && {_vehicle isEqualTo _snapshotCarrier};
    if ((count _removed) > 0 && {_sameCarrier}) then {
        private _primaryCargo = _removed # 0;
        // The solution may already be invalid, so fall back to the predictions
        // cached on the last valid ESTIMATE tick.
        private _chuteAttachTimeS = 0;
        private _predictedCanopyTimeS = 0;
        if (_solutionValid) then {
            private _relative = _solution getOrDefault ["relative", createHashMap];
            _chuteAttachTimeS = _relative getOrDefault ["chuteAttachTimeS", 0];
            _predictedCanopyTimeS = _relative getOrDefault ["predictedCanopyTimeS", 0];
        };
        if (_chuteAttachTimeS <= 0) then {
            _chuteAttachTimeS = missionNamespace getVariable ["TLB_CARP_state_packageEstimatedChuteAttachTimeS", 0];
        };
        if (_predictedCanopyTimeS <= 0) then {
            _predictedCanopyTimeS = missionNamespace getVariable ["TLB_CARP_state_packageEstimatedCanopyTimeS", 0];
        };
        TLB_CARP_state_packagePrimaryCargo = _primaryCargo;
        TLB_CARP_state_packageReleaseSimTime = time;
        TLB_CARP_state_packageReleaseClockSeconds = (daytime * 3600) mod 86400;
        TLB_CARP_state_packagePredictedCanopyTimeS = _predictedCanopyTimeS;
        TLB_CARP_state_packagePredictedChuteSimTime = time + _chuteAttachTimeS;
        TLB_CARP_state_packagePredictedTouchdownSimTime = TLB_CARP_state_packagePredictedChuteSimTime + _predictedCanopyTimeS;
        TLB_CARP_state_packagePredictedTouchdownClockSeconds = ((daytime * 3600) + (TLB_CARP_state_packagePredictedTouchdownSimTime - time)) mod 86400;
        TLB_CARP_state_packageActualChuteSimTime = -1;
        TLB_CARP_state_packageActualTouchdownSimTime = -1;
        TLB_CARP_state_packageActualTouchdownClockSeconds = -1;
        TLB_CARP_state_packageAirborneConfirmed = false;
        TLB_CARP_state_packageGroundCandidateSince = -1;
        TLB_CARP_state_packageTimingState = "RELEASED";
        _state = "RELEASED";
        diag_log format ["[TLB CARP][TOT] release tracked cargo=%1 chuteT=%2 touchdownT=%3", typeOf _primaryCargo, TLB_CARP_state_packagePredictedChuteSimTime, TLB_CARP_state_packagePredictedTouchdownSimTime];

    } else {
        if (!_solutionValid) exitWith {
            private _result = ["ESTIMATE"] call _empty;
            TLB_CARP_state_packageTiming = _result;
            _result
        };
        TLB_CARP_state_packageCargoSnapshot = +_currentCargo;
        TLB_CARP_state_packageCarrier = _vehicle;
        // Cache the predictions so a release detected on an invalid tick can
        // still latch real chute/touchdown times.
        private _relativeNow = _solution getOrDefault ["relative", createHashMap];
        TLB_CARP_state_packageEstimatedChuteAttachTimeS = _relativeNow getOrDefault ["chuteAttachTimeS", 0];
        TLB_CARP_state_packageEstimatedCanopyTimeS = _relativeNow getOrDefault ["predictedCanopyTimeS", 0];
        private _estimate = [_vehicle, _solution] call TLB_CARP_fnc_estimatePackageTiming;
        _estimate set ["packageState", "ESTIMATE"];
        TLB_CARP_state_packageTiming = _estimate;
        _estimate
    };
};

if (_state in ["RELEASED", "CHUTE"]) then {
    private _primaryCargo = missionNamespace getVariable ["TLB_CARP_state_packagePrimaryCargo", objNull];
    if (isNull _primaryCargo) then {
        TLB_CARP_state_packageTimingState = "LOST";
        _state = "LOST";
    } else {
        private _aglM = (getPosATL _primaryCargo) # 2;
        if (_aglM >= 10) then {TLB_CARP_state_packageAirborneConfirmed = true};

        if (_state isEqualTo "RELEASED") then {
            private _attached = attachedTo _primaryCargo;
            // A CANOPY ABOVE THE TRIGGER ALTITUDE IS NOT THIS DROP'S CANOPY.
            //
            // Vanilla gives an in-flight vehicle-in-vehicle unload its own parachute, which
            // fn_releaseCargo sweeps away within three seconds. Until it does, the load is
            // briefly attached to a ParachuteBase AT RELEASE ALTITUDE, and this test latched
            // it. Flown 2026-09-20: a viv drop recorded its chute event at 1005 m against a
            // 300 m trigger and called TOT twelve seconds early, and the calibration run
            // failed outright with TOUCHDOWN NOT DETECTED.
            //
            // The same rule this project keeps relearning: when a measurement implies
            // something physically impossible -- a canopy seven hundred metres above the
            // altitude that creates canopies -- suspect the instrument. The margin is
            // generous because the trigger is tested per frame at about 230 m/s, so the
            // real event can legitimately land a few metres high, never hundreds.
            private _chuteCeilingM = (missionNamespace getVariable ["TLB_CARP_setting_canopyTriggerAglM", 300]) + 100;
            if (!isNull _attached && {_attached isKindOf "ParachuteBase"} && {_aglM <= _chuteCeilingM}) then {
                TLB_CARP_state_packageActualChuteSimTime = time;
                TLB_CARP_state_packagePredictedTouchdownSimTime = time + TLB_CARP_state_packagePredictedCanopyTimeS;
                TLB_CARP_state_packagePredictedTouchdownClockSeconds = ((daytime * 3600) + TLB_CARP_state_packagePredictedCanopyTimeS) mod 86400;
                TLB_CARP_state_packageTimingState = "CHUTE";
                _state = "CHUTE";
                diag_log format ["[TLB CARP][TOT] chute tracked cargo=%1 touchdownT=%2", typeOf _primaryCargo, TLB_CARP_state_packagePredictedTouchdownSimTime];
            };
        };

        private _groundCandidate = TLB_CARP_state_packageAirborneConfirmed && {isTouchingGround _primaryCargo} && {_aglM <= 2};
        if (_groundCandidate) then {
            if (TLB_CARP_state_packageGroundCandidateSince < 0) then {
                TLB_CARP_state_packageGroundCandidateSince = time;
            };
            if ((time - TLB_CARP_state_packageGroundCandidateSince) >= 0.5) then {
                TLB_CARP_state_packageActualTouchdownSimTime = time;
                TLB_CARP_state_packageActualTouchdownClockSeconds = (daytime * 3600) mod 86400;
                TLB_CARP_state_packageTimingState = "ARRIVED";
                _state = "ARRIVED";
                diag_log format ["[TLB CARP][TOT] arrived cargo=%1 clock=%2", typeOf _primaryCargo, TLB_CARP_state_packageActualTouchdownClockSeconds];
            };
        } else {
            TLB_CARP_state_packageGroundCandidateSince = -1;
        };
    };
};

private _result = ["IDLE"] call _empty;
switch (_state) do {
    case "RELEASED": {
        private _predictedChuteSimTime = missionNamespace getVariable ["TLB_CARP_state_packagePredictedChuteSimTime", -1];
        private _predictedTouchdownSimTime = missionNamespace getVariable ["TLB_CARP_state_packagePredictedTouchdownSimTime", -1];
        private _chuteRemaining = (_predictedChuteSimTime - time) max 0;
        private _touchdownRemaining = (_predictedTouchdownSimTime - time) max 0;
        _result = createHashMapFromArray [
            ["dropEtaS", 0], ["chuteEtaS", _chuteRemaining], ["touchdownEtaS", _touchdownRemaining],
            ["dropClockText", [TLB_CARP_state_packageReleaseClockSeconds] call _fmtClockSeconds],
            ["chuteClockText", [((daytime * 3600) + _chuteRemaining) mod 86400] call _fmtClockSeconds],
            ["totClockText", [TLB_CARP_state_packagePredictedTouchdownClockSeconds] call _fmtClockSeconds],
            ["dropTMinusText", "RELEASED"], ["chuteTMinusText", [_chuteRemaining] call _fmtDuration],
            ["totTMinusText", [_touchdownRemaining] call _fmtDuration],
            ["timingState", "TRACKING"], ["packageState", "RELEASED"]
        ];
    };
    case "CHUTE": {
        private _predictedTouchdownSimTime = missionNamespace getVariable ["TLB_CARP_state_packagePredictedTouchdownSimTime", -1];
        private _touchdownRemaining = (_predictedTouchdownSimTime - time) max 0;
        _result = createHashMapFromArray [
            ["dropEtaS", 0], ["chuteEtaS", 0], ["touchdownEtaS", _touchdownRemaining],
            ["dropClockText", [TLB_CARP_state_packageReleaseClockSeconds] call _fmtClockSeconds],
            ["chuteClockText", [((daytime * 3600) - (time - TLB_CARP_state_packageActualChuteSimTime)) mod 86400] call _fmtClockSeconds],
            ["totClockText", [TLB_CARP_state_packagePredictedTouchdownClockSeconds] call _fmtClockSeconds],
            ["dropTMinusText", "RELEASED"], ["chuteTMinusText", "CHUTE"],
            ["totTMinusText", [_touchdownRemaining] call _fmtDuration],
            ["timingState", "TRACKING"], ["packageState", "CHUTE"]
        ];
    };
    case "ARRIVED": {
        _result = createHashMapFromArray [
            ["dropEtaS", 0], ["chuteEtaS", 0], ["touchdownEtaS", 0],
            ["dropClockText", [TLB_CARP_state_packageReleaseClockSeconds] call _fmtClockSeconds],
            ["chuteClockText", "DONE"],
            ["totClockText", [TLB_CARP_state_packageActualTouchdownClockSeconds] call _fmtClockSeconds],
            ["dropTMinusText", "RELEASED"], ["chuteTMinusText", "CHUTE"], ["totTMinusText", "ARRIVED"],
            ["timingState", "ARRIVED"], ["packageState", "ARRIVED"]
        ];
    };
    case "LOST": {
        _result = ["LOST"] call _empty;
        _result set ["totTMinusText", "LOST"];
        _result set ["packageState", "LOST"];
    };
    case "ESTIMATE": {
        _result = if (_solutionValid) then {[_vehicle, _solution] call TLB_CARP_fnc_estimatePackageTiming} else {["ESTIMATE"] call _empty};
        _result set ["packageState", "ESTIMATE"];
    };
};

TLB_CARP_state_packageTimingState = _state;
TLB_CARP_state_packageCargoSnapshot = +_currentCargo;
TLB_CARP_state_packageCarrier = _vehicle;
TLB_CARP_state_packageTiming = _result;
_result

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

private _state = missionNamespace getVariable ["USAFDC_state_packageTimingState", "IDLE"];
private _solutionValid = _solution getOrDefault ["valid", false];
// The manifest, not usaf_cargo. Release is detected by an object leaving this list, so
// reading only USAF's array meant an ACE or vehicle-in-vehicle load left the aircraft
// without the tracker ever noticing -- no RELEASED transition, and a frozen TOT.
private _currentCargo = if (isNull _vehicle) then {[]} else {[_vehicle] call USAFDC_fnc_getLoadedCargo};

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
if (!(isNil "USAFDC_fnc_steerBegin")) then {
    private _steerCarrier = missionNamespace getVariable ["USAFDC_state_steerSeenCarrier", objNull];
    if (!isNull _vehicle && {_vehicle isEqualTo _steerCarrier}) then {
        private _departed = (missionNamespace getVariable ["USAFDC_state_steerSeenCargo", []]) select {!(_x in _currentCargo)};
        if ((count _departed) > 0 && {[_vehicle] call USAFDC_fnc_steerPublisher}) then {
            {[_vehicle, _x] call USAFDC_fnc_steerBegin} forEach _departed;
        };
    };
    USAFDC_state_steerSeenCarrier = _vehicle;
    USAFDC_state_steerSeenCargo = +_currentCargo;
};

if (_state in ["IDLE", "ARRIVED", "LOST"] && {_solutionValid} && {(count _currentCargo) > 0} && {(_solution getOrDefault ["signedRpM", -1]) > 0}) then {
    if (_state in ["ARRIVED", "LOST"]) then {
        [] call USAFDC_fnc_resetPackageTiming;
    };
    USAFDC_state_packageTimingState = "ESTIMATE";
    USAFDC_state_packageCargoSnapshot = +_currentCargo;
    USAFDC_state_packageCarrier = _vehicle;
    _state = "ESTIMATE";
};

if (_state isEqualTo "IDLE") exitWith {
    private _result = ["IDLE"] call _empty;
    USAFDC_state_packageTiming = _result;
    _result
};

if (_state isEqualTo "ESTIMATE") then {
    // Release detection must run BEFORE any invalid-solution bail-out. Dropping
    // the last cargo empties usaf_cargo, which makes the live solution invalid
    // on the same tick the cargo leaves; gating this on validity left the state
    // machine stuck in ESTIMATE, so RELEASED/CHUTE/ARRIVED never happened and
    // the visible TOT froze on the final package.
    private _previousCargo = +(missionNamespace getVariable ["USAFDC_state_packageCargoSnapshot", []]);
    private _removed = _previousCargo select {!(_x in _currentCargo)};
    // Solver validity used to gate this block, which also implicitly rejected
    // "cargo vanished because the player left the aircraft (or changed seats to
    // another vehicle)". With the gate gone, the carrier identity check is what
    // keeps that from latching a release that never happened.
    private _snapshotCarrier = missionNamespace getVariable ["USAFDC_state_packageCarrier", objNull];
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
            _chuteAttachTimeS = missionNamespace getVariable ["USAFDC_state_packageEstimatedChuteAttachTimeS", 0];
        };
        if (_predictedCanopyTimeS <= 0) then {
            _predictedCanopyTimeS = missionNamespace getVariable ["USAFDC_state_packageEstimatedCanopyTimeS", 0];
        };
        USAFDC_state_packagePrimaryCargo = _primaryCargo;
        USAFDC_state_packageReleaseSimTime = time;
        USAFDC_state_packageReleaseClockSeconds = (daytime * 3600) mod 86400;
        USAFDC_state_packagePredictedCanopyTimeS = _predictedCanopyTimeS;
        USAFDC_state_packagePredictedChuteSimTime = time + _chuteAttachTimeS;
        USAFDC_state_packagePredictedTouchdownSimTime = USAFDC_state_packagePredictedChuteSimTime + _predictedCanopyTimeS;
        USAFDC_state_packagePredictedTouchdownClockSeconds = ((daytime * 3600) + (USAFDC_state_packagePredictedTouchdownSimTime - time)) mod 86400;
        USAFDC_state_packageActualChuteSimTime = -1;
        USAFDC_state_packageActualTouchdownSimTime = -1;
        USAFDC_state_packageActualTouchdownClockSeconds = -1;
        USAFDC_state_packageAirborneConfirmed = false;
        USAFDC_state_packageGroundCandidateSince = -1;
        USAFDC_state_packageTimingState = "RELEASED";
        _state = "RELEASED";
        diag_log format ["[TLB CARP][TOT] release tracked cargo=%1 chuteT=%2 touchdownT=%3", typeOf _primaryCargo, USAFDC_state_packagePredictedChuteSimTime, USAFDC_state_packagePredictedTouchdownSimTime];

    } else {
        if (!_solutionValid) exitWith {
            private _result = ["ESTIMATE"] call _empty;
            USAFDC_state_packageTiming = _result;
            _result
        };
        USAFDC_state_packageCargoSnapshot = +_currentCargo;
        USAFDC_state_packageCarrier = _vehicle;
        // Cache the predictions so a release detected on an invalid tick can
        // still latch real chute/touchdown times.
        private _relativeNow = _solution getOrDefault ["relative", createHashMap];
        USAFDC_state_packageEstimatedChuteAttachTimeS = _relativeNow getOrDefault ["chuteAttachTimeS", 0];
        USAFDC_state_packageEstimatedCanopyTimeS = _relativeNow getOrDefault ["predictedCanopyTimeS", 0];
        private _estimate = [_vehicle, _solution] call USAFDC_fnc_estimatePackageTiming;
        _estimate set ["packageState", "ESTIMATE"];
        USAFDC_state_packageTiming = _estimate;
        _estimate
    };
};

if (_state in ["RELEASED", "CHUTE"]) then {
    private _primaryCargo = missionNamespace getVariable ["USAFDC_state_packagePrimaryCargo", objNull];
    if (isNull _primaryCargo) then {
        USAFDC_state_packageTimingState = "LOST";
        _state = "LOST";
    } else {
        private _aglM = (getPosATL _primaryCargo) # 2;
        if (_aglM >= 10) then {USAFDC_state_packageAirborneConfirmed = true};

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
            private _chuteCeilingM = (missionNamespace getVariable ["USAFDC_setting_canopyTriggerAglM", 300]) + 100;
            if (!isNull _attached && {_attached isKindOf "ParachuteBase"} && {_aglM <= _chuteCeilingM}) then {
                USAFDC_state_packageActualChuteSimTime = time;
                USAFDC_state_packagePredictedTouchdownSimTime = time + USAFDC_state_packagePredictedCanopyTimeS;
                USAFDC_state_packagePredictedTouchdownClockSeconds = ((daytime * 3600) + USAFDC_state_packagePredictedCanopyTimeS) mod 86400;
                USAFDC_state_packageTimingState = "CHUTE";
                _state = "CHUTE";
                diag_log format ["[TLB CARP][TOT] chute tracked cargo=%1 touchdownT=%2", typeOf _primaryCargo, USAFDC_state_packagePredictedTouchdownSimTime];
            };
        };

        private _groundCandidate = USAFDC_state_packageAirborneConfirmed && {isTouchingGround _primaryCargo} && {_aglM <= 2};
        if (_groundCandidate) then {
            if (USAFDC_state_packageGroundCandidateSince < 0) then {
                USAFDC_state_packageGroundCandidateSince = time;
            };
            if ((time - USAFDC_state_packageGroundCandidateSince) >= 0.5) then {
                USAFDC_state_packageActualTouchdownSimTime = time;
                USAFDC_state_packageActualTouchdownClockSeconds = (daytime * 3600) mod 86400;
                USAFDC_state_packageTimingState = "ARRIVED";
                _state = "ARRIVED";
                diag_log format ["[TLB CARP][TOT] arrived cargo=%1 clock=%2", typeOf _primaryCargo, USAFDC_state_packageActualTouchdownClockSeconds];
            };
        } else {
            USAFDC_state_packageGroundCandidateSince = -1;
        };
    };
};

private _result = ["IDLE"] call _empty;
switch (_state) do {
    case "RELEASED": {
        private _predictedChuteSimTime = missionNamespace getVariable ["USAFDC_state_packagePredictedChuteSimTime", -1];
        private _predictedTouchdownSimTime = missionNamespace getVariable ["USAFDC_state_packagePredictedTouchdownSimTime", -1];
        private _chuteRemaining = (_predictedChuteSimTime - time) max 0;
        private _touchdownRemaining = (_predictedTouchdownSimTime - time) max 0;
        _result = createHashMapFromArray [
            ["dropEtaS", 0], ["chuteEtaS", _chuteRemaining], ["touchdownEtaS", _touchdownRemaining],
            ["dropClockText", [USAFDC_state_packageReleaseClockSeconds] call _fmtClockSeconds],
            ["chuteClockText", [((daytime * 3600) + _chuteRemaining) mod 86400] call _fmtClockSeconds],
            ["totClockText", [USAFDC_state_packagePredictedTouchdownClockSeconds] call _fmtClockSeconds],
            ["dropTMinusText", "RELEASED"], ["chuteTMinusText", [_chuteRemaining] call _fmtDuration],
            ["totTMinusText", [_touchdownRemaining] call _fmtDuration],
            ["timingState", "TRACKING"], ["packageState", "RELEASED"]
        ];
    };
    case "CHUTE": {
        private _predictedTouchdownSimTime = missionNamespace getVariable ["USAFDC_state_packagePredictedTouchdownSimTime", -1];
        private _touchdownRemaining = (_predictedTouchdownSimTime - time) max 0;
        _result = createHashMapFromArray [
            ["dropEtaS", 0], ["chuteEtaS", 0], ["touchdownEtaS", _touchdownRemaining],
            ["dropClockText", [USAFDC_state_packageReleaseClockSeconds] call _fmtClockSeconds],
            ["chuteClockText", [((daytime * 3600) - (time - USAFDC_state_packageActualChuteSimTime)) mod 86400] call _fmtClockSeconds],
            ["totClockText", [USAFDC_state_packagePredictedTouchdownClockSeconds] call _fmtClockSeconds],
            ["dropTMinusText", "RELEASED"], ["chuteTMinusText", "CHUTE"],
            ["totTMinusText", [_touchdownRemaining] call _fmtDuration],
            ["timingState", "TRACKING"], ["packageState", "CHUTE"]
        ];
    };
    case "ARRIVED": {
        _result = createHashMapFromArray [
            ["dropEtaS", 0], ["chuteEtaS", 0], ["touchdownEtaS", 0],
            ["dropClockText", [USAFDC_state_packageReleaseClockSeconds] call _fmtClockSeconds],
            ["chuteClockText", "DONE"],
            ["totClockText", [USAFDC_state_packageActualTouchdownClockSeconds] call _fmtClockSeconds],
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
        _result = if (_solutionValid) then {[_vehicle, _solution] call USAFDC_fnc_estimatePackageTiming} else {["ESTIMATE"] call _empty};
        _result set ["packageState", "ESTIMATE"];
    };
};

USAFDC_state_packageTimingState = _state;
USAFDC_state_packageCargoSnapshot = +_currentCargo;
USAFDC_state_packageCarrier = _vehicle;
USAFDC_state_packageTiming = _result;
_result

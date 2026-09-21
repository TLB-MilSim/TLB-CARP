params ["_carrier", "_run"];
// Stop the per-frame canopy watcher. Called on every exit path -- a leaked EachFrame
// handler would keep stamping the next run's cargo.
private _stopChuteWatch = {
    if ((missionNamespace getVariable ["TLB_CARP_state_calChuteWatchEh", -1]) >= 0) then {
        removeMissionEventHandler ["EachFrame", TLB_CARP_state_calChuteWatchEh];
        TLB_CARP_state_calChuteWatchEh = -1;
    };
    TLB_CARP_state_calChuteWatchCargo = objNull;
    TLB_CARP_state_calChuteWatchCarrier = objNull;
};

private _abort = {
    [] call _stopChuteWatch;
    params ["_run", "_reason"];
    _run set ["status", "FAILED"];
    _run set ["failureReason", _reason];
    TLB_CARP_state_calibrationRun = _run;
    TLB_CARP_state_calibrationActive = false;

    private _text = [_run] call TLB_CARP_fnc_formatCalibrationRun;
    TLB_CARP_state_lastCalibrationRun = _run;
    TLB_CARP_state_lastCalibrationText = _text;
    diag_log format ["[TLB CARP][CAL] run=%1 failed reason=%2", _run getOrDefault ["runId", -1], _reason];
    // Chunked: Arma silently truncates a diag_log string at about a kilobyte, and every
    // record this addon has ever written was being cut off mid-field.
    ["CAL", _text] call TLB_CARP_fnc_logLong;
    // THE HINT OMITTED `call`, AND THE PILOT TYPED WHAT IT SAID. The flown RPT carries
    // the result four times: Error in expression <[] TLB_CARP_fnc_copyLastCalibrationRun;>.
    // A bare function name is a variable reference, not a call.
    hint format ["CAL RUN FAILED\n%1\nRun: [] call TLB_CARP_fnc_copyLastCalibrationRun", _reason];
};

private _initialCargo = +(_run getOrDefault ["initialCargo", []]);
private _releaseDeadline = diag_tickTime + 15;
private _releasedCargo = objNull;
waitUntil {
    uiSleep 0.05;
    if (isNull _carrier) exitWith {true};
    // THE MANIFEST, NOT usaf_cargo -- the same fix fn_beginCalibrationRun got and this
    // sibling did not, which made the recorder lie for two of the four cargo sources.
    // _initialCargo is built from TLB_CARP_fnc_getLoadedCargo, so a viv, ace or attached
    // load is in it but is NEVER in usaf_cargo. findIf therefore matched on the FIRST
    // poll, at the cue, and the run recorded the cue position as the release.
    //
    // Flown 2026-09-20: one sortie logged signedRp -36.30 for a usaf-source load and
    // -4.62 / -4.05 for a viv and an attached one. The flattering pair were the bug.
    private _currentCargo = [_carrier] call TLB_CARP_fnc_getLoadedCargo;
    private _releasedIndex = _initialCargo findIf {!(_x in _currentCargo)};
    if (_releasedIndex >= 0) then {_releasedCargo = _initialCargo # _releasedIndex};
    (!isNull _releasedCargo) || {diag_tickTime >= _releaseDeadline}
};

if (isNull _releasedCargo) exitWith {[_run, "RELEASE NOT DETECTED WITHIN 15S"] call _abort};

// Per-frame canopy-attach watcher. Stamps the instant on the cargo itself so the
// scheduled loop below can read it rather than race for it.
// The command instant, recorded by fn_triggerAutoDrop itself. Inferring it from the
// cue was not good enough: three v0.5.2 drops showed 34-57 m of travel between cue
// and detected release, i.e. 0.24-0.41 s, which cannot be reconciled with the
// hardcoded `sleep 0.5` in USAF's fn_dropCargo.sqf. Rather than infer again, record
// what actually happened at both ends.
private _cmd = missionNamespace getVariable ["TLB_CARP_state_autoDropCommand", []];
if ((count _cmd) >= 3) then {
    _run set ["autoDropCommandSimTimeS", (_cmd # 0) - (_run getOrDefault ["releaseSimTime", _cmd # 0])];
    _run set ["autoDropCommandPosASL", _cmd # 2];
    _run set ["cueToCommandM", ((_run getOrDefault ["cueAircraftPosASL", _cmd # 2]) distance2D (_cmd # 2))];
    // NOT _releaseAircraftPosASL -- that is computed further down this file, so it
    // was nil here and the field came back blank in v0.5.3. Sample the carrier now;
    // this block runs immediately after release detection.
    _run set ["commandToReleaseM", ((_cmd # 2) distance2D (getPosASL _carrier))];
    _run set ["commandToReleaseS", (time - (_cmd # 0)) max -1];
};

TLB_CARP_state_calChuteWatchCargo = _releasedCargo;
TLB_CARP_state_calChuteWatchCarrier = _carrier;
if ((missionNamespace getVariable ["TLB_CARP_state_calChuteWatchEh", -1]) >= 0) then {
    removeMissionEventHandler ["EachFrame", TLB_CARP_state_calChuteWatchEh];
};
TLB_CARP_state_calChuteWatchEh = addMissionEventHandler ["EachFrame", {
    private _c = missionNamespace getVariable ["TLB_CARP_state_calChuteWatchCargo", objNull];
    if (isNull _c) exitWith {};
    if !(isNil {_c getVariable "TLB_CARP_calChuteStamp"}) exitWith {};
    private _att = attachedTo _c;
    private _carr = missionNamespace getVariable ["TLB_CARP_state_calChuteWatchCarrier", objNull];
    if (isNull _att || {_att isEqualTo _carr} || {!(_att isKindOf "ParachuteBase")}) exitWith {};
    _c setVariable ["TLB_CARP_calChuteStamp", [
        _att,                       // 0 parachute
        time,                       // 1 sim time
        diag_tickTime,              // 2 real time
        getPosASL _c,               // 3 cargo pos at attach
        (getPosATL _c) # 2,         // 4 cargo AGL at attach
        getPosASL _att,             // 5 parachute pos
        getDir _att,                // 6
        vectorDir _att,             // 7
        vectorUp _att,              // 8
        velocity _att               // 9
    ], false];
}];
_run set ["status", "TRACKING"];
_run set ["releasedCargo", _releasedCargo];
_run set ["cargoClass", typeOf _releasedCargo];
_run set ["releaseSimTime", time];
_run set ["releaseRealTime", diag_tickTime];
_run set ["releaseAircraftPosASL", getPosASL _carrier];
private _releaseVel = velocity _carrier;
_run set ["releaseVelocity", _releaseVel];
private _releaseWindTelemetry = [getPosASL _releasedCargo] call TLB_CARP_fnc_sampleWindTelemetry;
_run set ["releaseWindTelemetry", _releaseWindTelemetry];
_run set ["releaseWind", +(_releaseWindTelemetry getOrDefault ["engineWind", wind])];
_run set ["cargoReleasePosASL", getPosASL _releasedCargo];
_run set ["cargoReleaseAglM", (getPosATL _releasedCargo) # 2];

private _rp = _run getOrDefault ["rpPosASL", []];
private _runInDeg = _run getOrDefault ["runInDeg", 0];
private _basis = [_runInDeg] call TLB_CARP_fnc_basisFromHeading;
private _forward = _basis get "forward";
private _right = _basis get "right";
private _rvx = _releaseVel # 0;
private _rvy = _releaseVel # 1;
_run set ["releaseVelocityAlongMs", (_rvx * (_forward # 0)) + (_rvy * (_forward # 1))];
_run set ["releaseVelocityRightMs", (_rvx * (_right # 0)) + (_rvy * (_right # 1))];
private _releaseAircraftPosASL = _run get "releaseAircraftPosASL";
private _signedRpAtReleaseM = 0;
if ((count _rp) >= 2) then {
    private _rdx = (_rp # 0) - (_releaseAircraftPosASL # 0);
    private _rdy = (_rp # 1) - (_releaseAircraftPosASL # 1);
    _signedRpAtReleaseM = (_rdx * (_forward # 0)) + (_rdy * (_forward # 1));
};
_run set ["signedRpAtReleaseM", _signedRpAtReleaseM];
diag_log format ["[TLB CARP][CAL] run=%1 release cargo=%2 signedRp=%3 aircraftPos=%4 velocity=%5 wind=%6", _run getOrDefault ["runId", -1], typeOf _releasedCargo, _signedRpAtReleaseM, _releaseAircraftPosASL, _run get "releaseVelocity", _run get "releaseWind"];

/*
 * Track the actual USAF-created parachute. The cargo is temporarily attached to
 * the carrier during release, so ignore the carrier and only accept ParachuteBase.
 *
 * Canopy attach MUST be stamped per frame, not by the scheduled loop below.
 *
 * Detecting it in a uiSleep 0.05 loop under flight load produced readings that
 * looked like a physical fault and were not: flown drops recorded attach altitudes
 * of 229.8, 236.7 and 253.7 m against USAF's fixed ~300 m trigger, and that was read
 * as "the chute attaches late". The vertical speed at the recorded instant disproves
 * it -- those three read -180, -145 and -124 m/s while every promptly-detected drop
 * read -230 to -251 m/s. Freefall terminal is about -230, so the low readings had
 * ALREADY begun decelerating under an open canopy. The chute was on time; the poll
 * was late by 0.3-0.5 s. The parallel bench, whose detection is per frame, reads
 * 293-300 m every run on the same engine and the same USAF code.
 *
 * A contaminated attach point also corrupts everything derived from it:
 * chuteOpeningError*, canopyDuration* and every canopy sample.
 */
private _parachute = objNull;
private _chuteAttachSimTime = -1;
private _chuteAttachRealTime = -1;
private _canopySamples = [];
private _sampleTargets = [0, 0.5, 1, 2, 3, 4, 5, 6, 10, 20];
private _nextSampleIndex = 0;
private _nextWindSampleRealTime = -1;
private _engineWindSum = [0, 0, 0];
private _engineWindSampleCount = 0;
private _aceEffectiveWindSum = 0;
private _aceEffectiveVectorSum = [0, 0, 0];
private _aceEffectiveWindSampleCount = 0;

/*
 * isTouchingGround can be true for cargo while it is still airborne and attached
 * to another object (notably a parachute). Require confirmed airborne travel plus
 * terrain proximity before accepting the command as a real touchdown.
 */
private _airborneConfirmed = false;
private _touchdownConfirmed = false;
private _firstContactAglM = -1;
private _groundDeadline = diag_tickTime + 180;
waitUntil {
    uiSleep 0.05;
    if (isNull _releasedCargo) exitWith {true};

    private _cargoATL = getPosATL _releasedCargo;
    private _aglM = _cargoATL # 2;
    if (_aglM >= 10) then {_airborneConfirmed = true};

    // Latch on _chuteAttachSimTime, NOT on isNull _parachute. The parachute
    // reference goes null again when USAF deletes the canopy, so the isNull guard
    // let this block re-run and overwrite the attach fields every iteration until
    // touchdown: v0.5.2 reported chuteAttachDetectionLagS of 26.9 s (exactly the
    // canopy duration), an empty actualChuteClass and an empty canopySample00,
    // because the last overwrite happened with an already-deleted canopy.
    // The stamped position, altitude and velocity were unaffected -- they come from
    // the stamp -- but everything sampled live at read time was wrong.
    if (_chuteAttachSimTime < 0) then {
        // Read the per-frame stamp. Do NOT re-detect here: that is what produced
        // 0.3-0.5 s of latency and attach altitudes 46-70 m below the real trigger.
        private _stamp = _releasedCargo getVariable ["TLB_CARP_calChuteStamp", []];
        if ((count _stamp) >= 10) then {
            _parachute = _stamp # 0;
            _chuteAttachSimTime = _stamp # 1;
            _chuteAttachRealTime = _stamp # 2;
            private _cargoAttachPosASL = _stamp # 3;
            private _parachuteAttachPosASL = _stamp # 5;
            private _chuteWindTelemetry = [_cargoAttachPosASL] call TLB_CARP_fnc_sampleWindTelemetry;
            private _attachElapsedSimS = _chuteAttachSimTime - (_run getOrDefault ["releaseSimTime", _chuteAttachSimTime]);
            private _attachElapsedRealS = _chuteAttachRealTime - (_run getOrDefault ["releaseRealTime", _chuteAttachRealTime]);

            _run set ["chuteDetectionStatus", "DETECTED"];
            _run set ["actualChuteClass", typeOf _parachute];
            _run set ["actualChuteAttachPosASL", _cargoAttachPosASL];
            _run set ["actualParachuteAttachPosASL", _parachuteAttachPosASL];
            _run set ["actualChuteAttachAglM", _stamp # 4];
            _run set ["actualChuteAttachTimeS", _attachElapsedSimS];
            _run set ["actualChuteAttachSimTimeS", _attachElapsedSimS];
            _run set ["actualChuteAttachRealTimeS", _attachElapsedRealS];
            _run set ["actualChuteDirDeg", _stamp # 6];
            _run set ["actualChuteVectorDir", _stamp # 7];
            _run set ["actualChuteVectorUp", _stamp # 8];
            _run set ["actualChuteVelocity", _stamp # 9];
            // How long the scheduled loop took to notice the per-frame stamp. This is
            // the latency that used to corrupt the attach point; it should now be one
            // loop tick (<= ~0.05 s) and it no longer affects any recorded value,
            // because every attach field above comes from the stamp.
            _run set ["chuteAttachDetectionLagS", (diag_tickTime - (_stamp # 2)) max 0];
            _run set ["chuteWindTelemetry", _chuteWindTelemetry];

            private _predictedChutePosASL = _run getOrDefault ["chutePosASL", []];
            if ((count _predictedChutePosASL) >= 3) then {
                private _chuteErrorWorld = [
                    (_cargoAttachPosASL # 0) - (_predictedChutePosASL # 0),
                    (_cargoAttachPosASL # 1) - (_predictedChutePosASL # 1),
                    (_cargoAttachPosASL # 2) - (_predictedChutePosASL # 2)
                ];
                private _chuteDx = _chuteErrorWorld # 0;
                private _chuteDy = _chuteErrorWorld # 1;
                _run set ["chuteOpeningErrorWorld", _chuteErrorWorld];
                _run set ["chuteOpeningErrorM", sqrt ((_chuteDx * _chuteDx) + (_chuteDy * _chuteDy))];
                _run set ["chuteOpeningErrorAlongM", (_chuteDx * (_forward # 0)) + (_chuteDy * (_forward # 1))];
                _run set ["chuteOpeningErrorRightM", (_chuteDx * (_right # 0)) + (_chuteDy * (_right # 1))];
            };

            private _sample00 = [_releasedCargo, _parachute, 0, 0] call TLB_CARP_fnc_sampleParachuteTelemetry;
            _run set ["canopySample00", _sample00];
            _canopySamples pushBack _sample00;
            _nextSampleIndex = 1;
            _nextWindSampleRealTime = diag_tickTime;
            diag_log format ["[TLB CARP][CAL] run=%1 chute=%2 attachSim=%3 attachReal=%4 cargoPos=%5 parachutePos=%6 dir=%7", _run getOrDefault ["runId", -1], typeOf _parachute, _attachElapsedSimS, _attachElapsedRealS, _cargoAttachPosASL, _parachuteAttachPosASL, getDir _parachute];
        };
    };

    if (!isNull _parachute && {_chuteAttachSimTime >= 0} && {_chuteAttachRealTime >= 0}) then {
        private _canopyElapsedS = time - _chuteAttachSimTime;
        private _canopyElapsedRealS = diag_tickTime - _chuteAttachRealTime;

        _run set ["canopyElapsedRealTimeLastS", _canopyElapsedRealS];

        if (_nextWindSampleRealTime >= 0 && {diag_tickTime >= _nextWindSampleRealTime}) then {
            private _windTelemetry = [getPosASL _releasedCargo] call TLB_CARP_fnc_sampleWindTelemetry;
            _engineWindSum = _engineWindSum vectorAdd (_windTelemetry getOrDefault ["engineWind", [0, 0, 0]]);
            _engineWindSampleCount = _engineWindSampleCount + 1;
            private _aceSpeed = _windTelemetry getOrDefault ["aceEffectiveSpeedMs", -1];
            if (_aceSpeed >= 0) then {
                _aceEffectiveWindSum = _aceEffectiveWindSum + _aceSpeed;
                _aceEffectiveVectorSum = _aceEffectiveVectorSum vectorAdd (_windTelemetry getOrDefault ["aceEffectiveVector", [0, 0, 0]]);
                _aceEffectiveWindSampleCount = _aceEffectiveWindSampleCount + 1;
            };
            _nextWindSampleRealTime = diag_tickTime + 1;
        };

        if (_nextSampleIndex < (count _sampleTargets)) then {
            private _sampleTargetS = _sampleTargets # _nextSampleIndex;
            if (_canopyElapsedS >= _sampleTargetS) then {
                private _sample = [_releasedCargo, _parachute, _canopyElapsedS, _sampleTargetS] call TLB_CARP_fnc_sampleParachuteTelemetry;
                _canopySamples pushBack _sample;
                if (_sampleTargetS isEqualTo 5) then {_run set ["canopySample05", _sample]};
                if (_sampleTargetS isEqualTo 10) then {_run set ["canopySample10", _sample]};
                if (_sampleTargetS isEqualTo 20) then {_run set ["canopySample20", _sample]};
                _nextSampleIndex = _nextSampleIndex + 1;
            };
        };
    };

    private _cargoVel = velocity _releasedCargo;
    private _verticalNearGround = (abs (_cargoVel # 2)) <= 2.5;

    if (_airborneConfirmed && {_aglM <= 5} && {_verticalNearGround} && {isTouchingGround _releasedCargo}) then {
        _touchdownConfirmed = true;
        _firstContactAglM = _aglM;
    };

    _touchdownConfirmed || {diag_tickTime >= _groundDeadline}
};
if (isNull _releasedCargo) exitWith {[_run, "CARGO DELETED BEFORE TOUCHDOWN"] call _abort};
if (!_touchdownConfirmed) exitWith {[_run, "TOUCHDOWN NOT DETECTED WITHIN 180S"] call _abort};
if (!_airborneConfirmed || {_firstContactAglM > 5}) exitWith {[_run, "FALSE TOUCHDOWN / CARGO STILL AIRBORNE"] call _abort};

private _firstContactPosASL = getPosASL _releasedCargo;
private _firstContactSimTime = time;
private _firstContactRealTime = diag_tickTime;
private _releaseToContactSimTimeS = _firstContactSimTime - (_run getOrDefault ["releaseSimTime", _firstContactSimTime]);
private _releaseToContactRealTimeS = _firstContactRealTime - (_run getOrDefault ["releaseRealTime", _firstContactRealTime]);
_run set ["firstContactSimTime", _firstContactSimTime];
_run set ["firstContactRealTime", _firstContactRealTime];
_run set ["firstContactPosASL", _firstContactPosASL];
_run set ["firstContactAglM", _firstContactAglM];
_run set ["releaseToContactS", _releaseToContactSimTimeS];
_run set ["releaseToContactSimTimeS", _releaseToContactSimTimeS];
_run set ["releaseToContactRealTimeS", _releaseToContactRealTimeS];
private _dz = _run getOrDefault ["dzPosASL", []];
private _firstError = [_firstContactPosASL, _dz, _runInDeg] call TLB_CARP_fnc_computeCalibrationError;
_run set ["firstContactError", _firstError];

if (_chuteAttachSimTime >= 0 && {_chuteAttachRealTime >= 0}) then {
    private _actualChuteAttachPosASL = _run getOrDefault ["actualChuteAttachPosASL", []];
    private _canopyDurationSimTimeS = _firstContactSimTime - _chuteAttachSimTime;
    private _canopyDurationRealTimeS = _firstContactRealTime - _chuteAttachRealTime;
    private _canopyDurationActualS = _canopyDurationSimTimeS;
    _run set ["canopyDurationActualS", _canopyDurationActualS];
    _run set ["canopyDurationSimTimeS", _canopyDurationSimTimeS];
    _run set ["canopyDurationRealTimeS", _canopyDurationRealTimeS];
    if ((count _actualChuteAttachPosASL) >= 3) then {
        private _canopyDisplacementWorld = [
            (_firstContactPosASL # 0) - (_actualChuteAttachPosASL # 0),
            (_firstContactPosASL # 1) - (_actualChuteAttachPosASL # 1),
            (_firstContactPosASL # 2) - (_actualChuteAttachPosASL # 2)
        ];
        private _canopyDx = _canopyDisplacementWorld # 0;
        private _canopyDy = _canopyDisplacementWorld # 1;
        _run set ["canopyDisplacementWorld", _canopyDisplacementWorld];
        _run set ["canopyDisplacementAlongM", (_canopyDx * (_forward # 0)) + (_canopyDy * (_forward # 1))];
        _run set ["canopyDisplacementRightM", (_canopyDx * (_right # 0)) + (_canopyDy * (_right # 1))];
    };

    if (!isNull _parachute) then {
        _run set ["canopySampleTouchdown", [_releasedCargo, _parachute, _canopyDurationActualS, -2] call TLB_CARP_fnc_sampleParachuteTelemetry];
    };
};

if (_engineWindSampleCount > 0) then {
    _run set ["engineWindAverageCanopy", _engineWindSum vectorMultiply (1 / _engineWindSampleCount)];
};
if (_aceEffectiveWindSampleCount > 0) then {
    _run set ["aceEffectiveWindAverageCanopyMs", _aceEffectiveWindSum / _aceEffectiveWindSampleCount];
    _run set ["aceEffectiveWindVectorAverageCanopy", _aceEffectiveVectorSum vectorMultiply (1 / _aceEffectiveWindSampleCount)];
};
_run set ["canopyWindSampleCount", _engineWindSampleCount];
_run set ["canopySamples", _canopySamples];
_run set ["canopyTransientSamples", _canopySamples];
if (isNull _parachute && {_chuteAttachRealTime < 0}) then {
    _run set ["chuteDetectionStatus", "NOT_DETECTED"];
};

private _stableSince = -1;
private _settledConfirmed = false;
private _settleDeadline = diag_tickTime + 15;
waitUntil {
    uiSleep 0.05;
    if (isNull _releasedCargo) exitWith {true};

    private _settleAglM = (getPosATL _releasedCargo) # 2;
    private _stable = _settleAglM <= 5 && {isTouchingGround _releasedCargo} && {(vectorMagnitude (velocity _releasedCargo)) <= 1.5};
    if (_stable) then {
        if (_stableSince < 0) then {_stableSince = diag_tickTime};
        if ((diag_tickTime - _stableSince) >= 1.25) then {_settledConfirmed = true};
    } else {
        _stableSince = -1;
    };

    _settledConfirmed || {diag_tickTime >= _settleDeadline}
};
if (isNull _releasedCargo) exitWith {[_run, "CARGO DELETED AFTER TOUCHDOWN"] call _abort};

private _settledPosASL = getPosASL _releasedCargo;
private _settledAglM = (getPosATL _releasedCargo) # 2;
_run set ["settledSimTime", time];
_run set ["settledRealTime", diag_tickTime];
_run set ["settledPosASL", _settledPosASL];
_run set ["settledAglM", _settledAglM];
_run set ["settleTimedOut", !_settledConfirmed];

if (!_settledConfirmed) exitWith {[_run, "CARGO DID NOT SETTLE WITHIN 15S"] call _abort};
if (_settledAglM > 5) exitWith {[_run, "FALSE TOUCHDOWN / CARGO STILL AIRBORNE"] call _abort};

private _settledError = [_settledPosASL, _dz, _runInDeg] call TLB_CARP_fnc_computeCalibrationError;
_run set ["settledError", _settledError];
_run set ["status", "COMPLETE"];

private _text = [_run] call TLB_CARP_fnc_formatCalibrationRun;
TLB_CARP_state_lastCalibrationRun = _run;
TLB_CARP_state_lastCalibrationText = _text;
TLB_CARP_state_calibrationRun = _run;
TLB_CARP_state_calibrationActive = false;
[] call _stopChuteWatch;
["CAL", _text] call TLB_CARP_fnc_logLong;

private _along = _settledError getOrDefault ["alongM", 0];
private _rightM = _settledError getOrDefault ["rightM", 0];
private _alongLabel = if (_along >= 0) then {"LONG"} else {"SHORT"};
private _sideLabel = if (_rightM >= 0) then {"RIGHT"} else {"LEFT"};
hint format ["CAL RUN RECORDED\n%1 %2 m | %3 %4 m\nRun: [] call TLB_CARP_fnc_copyLastCalibrationRun", _alongLabel, round (abs _along), _sideLabel, round (abs _rightM)];
true

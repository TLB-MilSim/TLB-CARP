params [["_vehicle", objectParent player]];

if ((count USAFDC_state_dzPosASL) < 3) exitWith {
    createHashMapFromArray [["valid", false], ["reason", "NO DZ"], ["confidence", "INVALID"], ["warnings", ["NO DZ"]]]
};
if (isNull _vehicle) exitWith {
    createHashMapFromArray [["valid", false], ["reason", "NO AIRCRAFT"], ["confidence", "INVALID"], ["warnings", ["NO AIRCRAFT"]]]
};

private _airState = [_vehicle] call USAFDC_fnc_getAircraftState;
if !(_airState get "valid") exitWith {
    createHashMapFromArray [
        ["valid", false],
        ["reason", _airState getOrDefault ["reason", "INVALID AIRCRAFT"]],
        ["confidence", "INVALID"],
        ["warnings", [_airState getOrDefault ["reason", "INVALID AIRCRAFT"]]]
    ]
};
// A HALO run carries no cargo, and requiring some is what stopped guidance, and
// therefore the autopilot, from arming for a jump. The mode says which kind of pass this
// is; it is not inferred from an empty hold, so a jump run still works with cargo aboard
// for a later pass.
private _jumpRun = USAFDC_state_mode isEqualTo "JUMP";
if (!_jumpRun && {(_airState get "cargoCount") <= 0}) exitWith {
    createHashMapFromArray [["valid", false], ["reason", "NO CARGO ABOARD"], ["confidence", "INVALID"], ["warnings", ["NO CARGO ABOARD"]]]
};

private _runInDeg = if (USAFDC_state_runInLocked) then {USAFDC_state_runInDeg} else {_airState get "trackDeg"};
private _basis = [_runInDeg] call USAFDC_fnc_basisFromHeading;
private _forward = _basis get "forward";
private _right = _basis get "right";
private _dz = +USAFDC_state_dzPosASL;
private _dzTerrain = _dz # 2;

private _windSpeed = 0;
private _windFromDeg = 0;
private _windVector = [0, 0, 0];
if (USAFDC_state_manualWind) then {
    _windSpeed = 0 max USAFDC_state_manualWindMs;
    _windFromDeg = USAFDC_state_manualWindFromDeg mod 360;
    if (_windFromDeg < 0) then {_windFromDeg = _windFromDeg + 360};
    private _to = (_windFromDeg + 180) mod 360;
    _windVector = [_windSpeed * sin _to, _windSpeed * cos _to, 0];
} else {
    _windVector = wind;
    private _wx = _windVector # 0;
    private _wy = _windVector # 1;
    _windSpeed = sqrt ((_wx * _wx) + (_wy * _wy));
    if (_windSpeed > 0.01) then {
        private _windToDeg = ((_wx atan2 _wy) + 360) mod 360;
        _windFromDeg = (_windToDeg + 180) mod 360;
    };
};

private _model = [] call USAFDC_fnc_getModel;
private _profileId = _airState get "profileId";
private _aircraftProfiles = _model get "aircraft";
private _profile = _aircraftProfiles getOrDefault [_profileId, createHashMap];
if ((count _profile) isEqualTo 0) exitWith {
    createHashMapFromArray [["valid", false], ["reason", "PROFILE MISSING"], ["confidence", "INVALID"], ["warnings", ["PROFILE MISSING"]]]
};
_profile set ["dropPos", +(_airState get "dropPos")];

private _airPos = _airState get "posASL";
private _kinematics = [_vehicle, _airState, _runInDeg] call USAFDC_fnc_projectAircraftKinematics;
private _input = createHashMapFromArray [
    ["aircraft", _profileId],
    ["mode", USAFDC_state_mode],
    ["actionAltitudeAslM", _airPos # 2],
    ["openingTerrainAslM", _dzTerrain],
    ["dzTerrainAslM", _dzTerrain],
    ["groundSpeedMs", _airState get "groundSpeedMs"],
    ["velocityAlongMs", _kinematics get "velocityAlongMs"],
    ["velocityRightMs", _kinematics get "velocityRightMs"],
    ["verticalSpeedMs", _airState get "verticalSpeedMs"],
    ["releaseOffsetAlongM", _kinematics get "releaseOffsetAlongM"],
    ["releaseOffsetRightM", _kinematics get "releaseOffsetRightM"],
    ["releaseVerticalOffsetM", _kinematics get "releaseVerticalOffsetM"],
    ["runInDeg", _runInDeg],
    ["windSpeedMs", _windSpeed],
    ["windFromDeg", _windFromDeg]
];

// ---- HALO jump run ------------------------------------------------------------
//
// Everything above -- the locked run-in, the basis, the wind, the aircraft state -- is
// what a jump run needs. Everything below it is cargo ballistics, which a jump run has
// none of: no release delay, no forward throw, no canopy table, no release gate.
//
// The aim point is the JUMP EXIT POINT, not the drop zone. fn_buildJumpSolution already
// computes where the aircraft has to be for a jumper to reach the DZ under canopy --
// upwind of it by the freefall drift, led by the stick length and the early bias -- so
// the path manager and the autopilot fly to that, and the exit cue fires when they get
// there. Aiming at the DZ itself would put the aircraft a kilometre or more downwind of
// where the jumpers actually need to leave.
//
// Auto drop and the release gate stay out of it entirely: fn_updateGuidance skips the
// drop cue on a jump run and fn_validateAutoDrop refuses one.
if (_jumpRun) exitWith {
    private _jump = if (isNil "USAFDC_fnc_buildJumpSolution") then {createHashMap} else {
        [_vehicle] call USAFDC_fnc_buildJumpSolution
    };
    private _jumpValid = _jump getOrDefault ["valid", false];
    // Without a usable exit point the run-in itself is still worth flying, so fall back
    // to the DZ rather than refusing to guide at all.
    private _aim = if (_jumpValid) then {_jump getOrDefault ["exitPointPosASL", _dz]} else {_dz};
    private _alongM = if (_jumpValid) then {_jump getOrDefault ["alongM", 0]} else {
        private _dx = (_aim # 0) - (_airPos # 0);
        private _dy = (_aim # 1) - (_airPos # 1);
        (_dx * (_forward # 0)) + (_dy * (_forward # 1))
    };
    private _crossM = if (_jumpValid) then {_jump getOrDefault ["offTrackM", 0]} else {
        private _dx = (_aim # 0) - (_airPos # 0);
        private _dy = (_aim # 1) - (_airPos # 1);
        -((_dx * (_right # 0)) + (_dy * (_right # 1)))
    };
    private _trackErrorDeg = (((_airState get "trackDeg") - _runInDeg + 540) mod 360) - 180;

    private _warnings = _jump getOrDefault ["warnings", []];
    if (!_jumpValid) then {_warnings = _warnings + [_jump getOrDefault ["reason", "JUMP SOLUTION UNAVAILABLE"]]};

    createHashMapFromArray [
        ["valid", true],
        ["jumpRun", true],
        ["jumpSolution", _jump],
        ["mode", "JUMP"],
        ["profileId", _profileId],
        ["aircraftClass", _airState get "class"],
        ["aircraftState", _airState],
        ["kinematics", _kinematics],
        ["runInDeg", _runInDeg],
        ["forward", _forward],
        ["right", _right],
        ["windVector", _windVector],
        ["windSpeedMs", _windSpeed],
        ["windFromDeg", _windFromDeg],
        ["dzPosASL", _dz],
        ["openingTerrainAslM", _dzTerrain],
        // The exit point stands in for the release point everywhere downstream, so the
        // path manager, the markers and the HUD countdown all aim at it without any of
        // them needing to know this is a jump.
        ["rpPosASL", _aim],
        ["liveRpPosASL", _aim],
        ["plannedRpPosASL", _aim],
        ["chutePosASL", _dz],
        ["touchdownPosASL", _dz],
        ["targetAglM", USAFDC_state_targetAglM],
        ["targetGroundSpeedKmh", USAFDC_state_targetGroundSpeedKmh],
        ["actualAglM", (_airPos # 2) - (getTerrainHeightASL _airPos)],
        ["actualGroundSpeedKmh", (_airState get "groundSpeedMs") * 3.6],
        ["signedRpM", _alongM],
        ["crossTrackM", _crossM],
        ["trackErrorDeg", _trackErrorDeg],
        ["velocityRightMs", _kinematics get "velocityRightMs"],
        // No cargo leaves the aircraft on a jump run, so there is nothing for the
        // release gate to be stable FOR. It reads true so the path manager will fly the
        // final run rather than treating every pass as a missed one; fn_updateGuidance
        // is what keeps the drop cue and auto drop out of it.
        ["releaseStable", true],
        ["guidanceState", if ((abs _crossM) <= 25 && {(abs _trackErrorDeg) <= 2}) then {"ON RUN-IN"} else {"INTERCEPT"}],
        // GOOD or nothing, like every other solution. An exit point this code could not
        // compute falls back to the drop zone and says so through the JUMP HOLD readout,
        // which reaches the jumpers rather than sitting on the pilot's HUD as a word.
        ["confidence", "GOOD"],
        ["warnings", _warnings]
    ]
};

private _liveReference = [_input, _model, _dz] call USAFDC_fnc_solveWorldReference;
if !(_liveReference getOrDefault ["valid", false]) exitWith {
    private _badRelative = _liveReference getOrDefault ["relative", createHashMapFromArray [["warnings", ["INVALID SOLUTION"]]]];
    createHashMapFromArray [
        ["valid", false],
        ["reason", (_badRelative getOrDefault ["warnings", ["INVALID SOLUTION"]]) # 0],
        ["confidence", "INVALID"],
        ["warnings", _badRelative getOrDefault ["warnings", ["INVALID SOLUTION"]]]
    ]
};
private _relative = _liveReference get "relative";
private _openingTerrain = _liveReference get "openingTerrainAslM";
private _airTerrainAsl = getTerrainHeightASL _airPos;
private _actualAglM = (_airPos # 2) - _airTerrainAsl;
private _actualGroundSpeedKmh = (_airState get "groundSpeedMs") * 3.6;
// USAFDC_fnc_confidenceReason turned a warning into one short line for the HUD. With the
// DEGRADED tier gone there is no warning to phrase, so it is no longer called. The file
// stays in the PBO for now rather than being cut from a pre-binarized CfgFunctions in the
// same release that changes solver behaviour.

private _plannedBaseInput = createHashMap;
{_plannedBaseInput set [_x, _input get _x]} forEach keys _input;
private _releaseModelOffset = _airState get "releaseModelOffset";
_plannedBaseInput set ["releaseOffsetAlongM", _releaseModelOffset # 1];
_plannedBaseInput set ["releaseOffsetRightM", _releaseModelOffset # 0];
_plannedBaseInput set ["releaseVerticalOffsetM", _releaseModelOffset # 2];
private _plannedReference = [
    _plannedBaseInput,
    _model,
    _dz,
    USAFDC_state_targetAglM,
    USAFDC_state_targetGroundSpeedKmh
] call USAFDC_fnc_buildPlannedReference;

private _cargoSequenceCount = 1;
private _stickLengthM = 0;
private _firstReleaseLeadM = 0;
private _predictedFootprintM = 0;
private _guidedSlots = false;
// Hoisted: the export below is outside the multi-cargo block, and a `private` declared
// inside it reads nil out here -- which would put nil into the solution hashmap and throw
// in the HUD rather than in this function.
private _stickWarningLengthM = ((_model getOrDefault ["multiCargo", createHashMap]) getOrDefault ["stickWarningLengthM", 50]);
private _warnings = +(_relative get "warnings");
if (USAFDC_state_autoArmed) then {
    private _availableCargo = _airState get "cargoCount";
    _cargoSequenceCount = if (USAFDC_state_cargoCount < 0) then {_availableCargo} else {(USAFDC_state_cargoCount min _availableCargo) max 1};
    if (_cargoSequenceCount > 1) then {
        private _multiCargo = _model getOrDefault ["multiCargo", createHashMap];
        private _sequenceIntervalS = _multiCargo getOrDefault ["sequenceIntervalS", 0.53];
        private _spacingM = (_airState get "groundSpeedMs") * _sequenceIntervalS;
        // BOTH OF THESE ARE RELEASE GEOMETRY AND NEITHER MAY MOVE.
        //
        // The obvious way to fix the warning below is to redefine _stickLengthM as the
        // guided span. That would silently halve _firstReleaseLeadM -- 32.5 m to 17.5 m on
        // the flown pass -- shifting the RP 15 m along-track on every guided stick, which
        // is 0.14 s of release timing at 110 m/s and would surface later as an
        // unexplained bias in a calibration batch. The ballistic stick IS 65 m whether or
        // not anything steers afterwards, so these two stay exactly as they were.
        _stickLengthM = _spacingM * (_cargoSequenceCount - 1);
        _firstReleaseLeadM = _stickLengthM * 0.5;

        // WHAT THE PILOT IS TOLD IS A DIFFERENT NUMBER, AND THAT WAS THE BUG.
        //
        // Flown report: two loads dropped with JPADS on, warned "PREDICTED STICK 65 m -
        // FULL STICK CANNOT FIT 50 m DZ", both landed inside a 50 m box about 20 m from
        // the DZ. The warning was right about the ballistic spread and wrong about the
        // pass: guided cargo REPLACES that spread with a slot pattern jpadsStickSpacingM
        // wide -- 35 m for two loads, where the ballistic figure was 65.
        //
        // It was not a borderline case either. For two loads the ballistic prediction
        // exceeds 50 m above 85 m/s, and the calibrated drop band is 480-525 km/h, so this
        // warning has fired on every multi-cargo pass the system has ever flown. A warning
        // that is always on is a warning nobody reads.
        //
        // The predicate MIRRORS fn_steerBegin.sqf:100 exactly -- jpads on, a positive
        // spacing, more than one load, and a locked run-in to spread along. Keep the two
        // in step; a test pins them. It is a prediction of intent rather than a guarantee,
        // because the stick total is only known at release, but a number describing the
        // pass that will happen beats a number describing one that cannot.
        private _slotSpacingM = missionNamespace getVariable ["USAFDC_setting_jpadsStickSpacingM", 35];
        _guidedSlots = USAFDC_state_jpadsEnabled && {_slotSpacingM > 0} && {USAFDC_state_runInLocked};
        _predictedFootprintM = if (_guidedSlots) then {_slotSpacingM * (_cargoSequenceCount - 1)} else {_stickLengthM};
        if (_predictedFootprintM > _stickWarningLengthM) then {
            // The threshold was hardcoded into the text while the test read the variable,
            // so a changed setting would have produced a message that lied about itself.
            _warnings pushBack format ["%1 CARGO - PREDICTED %2 %3 m - WILL NOT FIT %4 m DZ",
                _cargoSequenceCount,
                if (_guidedSlots) then {"PATTERN"} else {"STICK"},
                round _predictedFootprintM,
                round _stickWarningLengthM];
        };

        // Guidance on with no run-in lock is the one case that gets no slots at all: every
        // load steers onto the DZ centre with only the 2 m random scatter between them, so
        // guidance actively collapses the spread a stick would otherwise have had. That is
        // a pile, and it is silent -- the footprint above reads as the ballistic stick and
        // says nothing about the loads converging.
        if (USAFDC_state_jpadsEnabled && {!USAFDC_state_runInLocked}) then {
            _warnings pushBack format ["%1 CARGO GUIDED - NO RUN-IN LOCK - ALL LOADS WILL AIM AT ONE POINT", _cargoSequenceCount];
        };
    };
};

private _rp = +(_liveReference get "rpPosASL");
private _chutePos = +(_liveReference get "chutePosASL");
if (_firstReleaseLeadM > 0) then {
    _rp set [0, (_rp # 0) - ((_forward # 0) * _firstReleaseLeadM)];
    _rp set [1, (_rp # 1) - ((_forward # 1) * _firstReleaseLeadM)];
    _rp set [2, getTerrainHeightASL [_rp # 0, _rp # 1]];
    _chutePos set [0, (_chutePos # 0) - ((_forward # 0) * _firstReleaseLeadM)];
    _chutePos set [1, (_chutePos # 1) - ((_forward # 1) * _firstReleaseLeadM)];
};

private _plannedRp = if (_plannedReference getOrDefault ["valid", false]) then {+(_plannedReference get "rpPosASL")} else {+_rp};
private _guidance = [_airPos, _plannedRp, _rp, _runInDeg, _airState get "trackDeg"] call USAFDC_fnc_computeRunInGuidance;
private _signedRpM = _guidance get "signedRpM";
private _crossTrackM = _guidance get "crossTrackM";
private _trackErrorDeg = _guidance get "trackErrorDeg";
private _capturePos = _guidance get "capturePosASL";
private _rawDesiredTrackDeg = _guidance get "rawDesiredTrackDeg";
private _desiredTrackDeg = _rawDesiredTrackDeg;
private _currentTrackDeg = _airState get "trackDeg";
private _steeringErrorDeg = (((_desiredTrackDeg - _currentTrackDeg + 540) mod 360) - 180);
private _groundSpeedMs = _airState get "groundSpeedMs";
private _timeToRpS = if ((_signedRpM > 0) && {_groundSpeedMs > 1}) then {_signedRpM / _groundSpeedMs} else {-1};
private _guidanceState = _guidance get "guidanceState";
private _releaseStable = _guidance get "releaseStable";
private _velocityRightMs = _kinematics get "velocityRightMs";
private _chuteAttachTimeS = _relative getOrDefault ["chuteAttachTimeS", 0];
private _releaseDelayS = _profile get "releaseDelayS";
private _freefallLateralDriftM = _velocityRightMs * _chuteAttachTimeS;
private _preChuteLateralDriftM = _velocityRightMs * (_releaseDelayS + _chuteAttachTimeS);

// THE LIMIT WAS 15 m AND NOTHING COULD EVER VIOLATE IT UNTIL v0.16.8.
//
// The term is real: lateral velocity at release displaces the load, measured as
// +1.294 m/s -> ~+30 m and -2.904 m/s -> ~-68 m. What was not real was the threshold being
// tested. Until v0.16.8 the autopilot wrote the horizontal velocity with setVelocity,
// built from the commanded heading -- so velocityRightMs was IDENTICALLY ZERO by
// construction and this gate could not fail. 15 m was never exercised.
//
// The force autopilot flies the aircraft instead of moving it, so the lateral velocity is
// now genuine. Flown 2026-09-21: five passes, no drop. The best of them had crossTrack
// -1.19 m and trackError -0.57 deg -- the aircraft was ON the line -- and was refused for
// 16.6 m of predicted drift, which is 0.69 m/s of lateral velocity. No aircraft holds a
// ground track that exactly.
//
// 25 m, MATCHING THE CROSS-TRACK LIMIT, and that symmetry is the argument. The gate
// already accepts 25 m of cross-track POSITION error; accepting 25 m of predicted lateral
// DISPLACEMENT is the same tolerance applied to the same axis. It is not "widen it until
// it passes" -- 25 m is half the 50 m operational box, and the canopy wind term is
// currently mis-predicting by 150 m, so refusing a pass over 16 m is straining at a gnat.
//
// A setting, because this is the gate that stops a drop and the crew must be able to move
// it without waiting for a build.
private _driftLimitM = missionNamespace getVariable ["USAFDC_setting_releaseDriftLimitM", 25];
// Bounded at BOTH ends. Without the lower bound the gate kept judging the
// aircraft for the whole egress and go-around: cross-track necessarily grows
// once the pass is over, so the HUD stuck on NO DROP - GO AROUND indefinitely
// and the state never returned to a normal PASSED RP presentation.
private _insideFinal = (_signedRpM <= 800) && {_signedRpM > -250};
if (_insideFinal) then {
    _releaseStable = ((abs _crossTrackM) <= 25) && {((abs _trackErrorDeg) <= 2) && {(abs _preChuteLateralDriftM) <= _driftLimitM}};
    if (!_releaseStable) then {
        _guidanceState = "UNSTABLE RUN-IN";
        _warnings pushBackUnique "UNSTABLE RUN-IN";
        // Name the term that failed; "UNSTABLE RUN-IN" alone gives the pilot
        // nothing to correct.
        if ((abs _crossTrackM) > 25) then {
            _warnings pushBackUnique format ["CROSS TRACK %1 m", round _crossTrackM];
        };
        if ((abs _trackErrorDeg) > 2) then {
            _warnings pushBackUnique format ["TRACK ERROR %1 deg", _trackErrorDeg toFixed 1];
        };
        if ((abs _preChuteLateralDriftM) > _driftLimitM) then {
            _warnings pushBackUnique format ["PRE-CHUTE LATERAL DRIFT %1 m", round _preChuteLateralDriftM];
        };
    };
};
private _finalRunLineOffsetM = (((_plannedRp # 0) - (_dz # 0)) * (_right # 0)) + (((_plannedRp # 1) - (_dz # 1)) * (_right # 1));
if (_guidanceState isEqualTo "UNSTABLE RUN-IN") then {
    _warnings pushBackUnique "UNSTABLE RUN-IN";
};

createHashMapFromArray [
    ["valid", true],
    ["profileId", _profileId],
    ["aircraftClass", _airState get "class"],
    ["aircraftState", _airState],
    ["mode", USAFDC_state_mode],
    ["runInDeg", _runInDeg],
    ["forward", _forward],
    ["right", _right],
    ["windVector", _windVector],
    ["windSpeedMs", _windSpeed],
    ["windFromDeg", _windFromDeg],
    ["dzPosASL", _dz],
    ["openingTerrainAslM", _openingTerrain],
    ["rpPosASL", _rp],
    ["liveRpPosASL", _rp],
    ["plannedRpPosASL", _plannedRp],
    ["plannedReference", _plannedReference],
    ["targetAglM", USAFDC_state_targetAglM],
    ["targetGroundSpeedKmh", USAFDC_state_targetGroundSpeedKmh],
    ["actualAglM", _actualAglM],
    ["actualGroundSpeedKmh", _actualGroundSpeedKmh],
    ["chutePosASL", _chutePos],
    ["touchdownPosASL", _dz],
    ["signedRpM", _signedRpM],
    ["crossTrackM", _crossTrackM],
    ["trackErrorDeg", _trackErrorDeg],
    ["velocityRightMs", _velocityRightMs],
    ["freefallLateralDriftM", _freefallLateralDriftM],
    ["preChuteLateralDriftM", _preChuteLateralDriftM],
    ["preChuteDriftLimitM", _driftLimitM],
    ["capturePosASL", _capturePos],
    ["captureLeadM", _guidance getOrDefault ["lookAheadM", 0]],
    ["desiredTrackDeg", _desiredTrackDeg],
    ["rawDesiredTrackDeg", _rawDesiredTrackDeg],
    ["steeringErrorDeg", _steeringErrorDeg],
    ["timeToRpS", _timeToRpS],
    ["guidanceState", _guidanceState],
    ["releaseStable", _releaseStable],
    ["onRunIn", _guidance get "onRunIn"],
    ["interceptAngleDeg", _guidance get "interceptAngleDeg"],
    ["interceptLimitDeg", _guidance get "interceptLimitDeg"],
    ["finalRunLineAnchorASL", _plannedRp],
    ["finalRunLineOffsetM", _finalRunLineOffsetM],
    ["confidence", _relative get "confidence"],

    ["warnings", _warnings],
    ["cargoSequenceCount", _cargoSequenceCount],
    ["stickLengthM", _stickLengthM],
    ["firstReleaseLeadM", _firstReleaseLeadM],
    // What the pattern will actually be, and whether guidance is what makes it so. The HUD
    // reads these; stickLengthM stays exported unchanged because it is release geometry.
    ["predictedFootprintM", _predictedFootprintM],
    ["guidedSlots", _guidedSlots],
    ["stickWarningLengthM", _stickWarningLengthM],
    ["relative", _relative]
]

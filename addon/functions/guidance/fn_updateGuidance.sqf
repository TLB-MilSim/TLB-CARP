if (!USAFDC_state_guidanceArmed) exitWith {false};
private _vehicle = objectParent player;
if (isNull _vehicle) exitWith {[] call USAFDC_fnc_disarmGuidance; false};

// Once the cargo is away and the solver has already gone invalid, rebuilding the
// world solution 20 times a second serves no purpose: nothing downstream consumes
// it, and it cannot become valid again while usaf_cargo is empty. Skipping it during
// freefall frees the scheduler for USAF's own chute-attach check, which is the
// dominant flown error source -- 3 of 7 flown drops attached 37-70 m below its ~300 m
// trigger, and a late attach cost 52.1 m against 9.76 m for a prompt one.
//
// This is worth doing on its own merits (do not compute what nobody reads); the
// attach-altitude benefit is a hypothesis with one supporting flown drop behind it,
// not a settled result. Package timing, TOT and the HUD all keep updating below.
private _packageAirborne = (missionNamespace getVariable ["USAFDC_state_packageTimingState", "IDLE"]) in ["RELEASED", "CHUTE"];
private _lastWasInvalid = !((missionNamespace getVariable ["USAFDC_state_solution", createHashMap]) getOrDefault ["valid", false]);
private _skipSolve = _packageAirborne && _lastWasInvalid;

private _solution = if (_skipSolve) then {
    createHashMapFromArray [["valid", false], ["solveSkipped", true]]
} else {
    [_vehicle] call USAFDC_fnc_buildWorldSolution
};
if !(_solution getOrDefault ["valid", false]) exitWith {
    private _packageState = missionNamespace getVariable ["USAFDC_state_packageTimingState", "IDLE"];
    // ESTIMATE is included deliberately: releasing the last cargo empties
    // usaf_cargo and invalidates the solver on the same tick the cargo leaves,
    // so the ESTIMATE -> RELEASED transition has to be able to fire from here.
    // Without it the package tracker never starts and the TOT freezes.
    private _packageLive = _packageState in ["ESTIMATE", "RELEASED", "CHUTE", "ARRIVED"];
    if (_packageLive && {!(isNil "USAFDC_fnc_updatePackageTiming")}) then {
        private _timing = [_vehicle, _solution] call USAFDC_fnc_updatePackageTiming;
        {_solution set [_x, _timing get _x]} forEach keys _timing;

        // Keep the last valid flight presentation alive after cargo leaves the carrier.
        // The live solver may now be invalid because usaf_cargo is empty, but package
        // timing must continue to refresh independently of that solver validity.
        private _displaySolution = missionNamespace getVariable ["USAFDC_state_displaySolution", createHashMap];
        if ((count _displaySolution) > 0) then {
            {_displaySolution set [_x, _timing get _x]} forEach keys _timing;
            _displaySolution set ["packageTrackingOnly", true];
            USAFDC_state_displaySolution = _displaySolution;
        };
    };

    USAFDC_state_solution = _solution;
    if !(isNil "USAFDC_fnc_disarmAutoDrop") then {[] call USAFDC_fnc_disarmAutoDrop};

    // Re-read: the timing call above may have transitioned ESTIMATE -> RELEASED,
    // and the release tick is exactly the one that must refresh the display.
    private _trackingPackage = (missionNamespace getVariable ["USAFDC_state_packageTimingState", "IDLE"]) in ["RELEASED", "CHUTE", "ARRIVED"];
    if (_trackingPackage) then {
        if !(isNil "USAFDC_fnc_updatePanelTelemetry") then {
            if ((diag_tickTime - USAFDC_state_panelLastTelemetryTick) >= 0.20) then {
                USAFDC_state_panelLastTelemetryTick = diag_tickTime;
                [] call USAFDC_fnc_updatePanelTelemetry;
            };
        };
        if !(isNil "USAFDC_fnc_updateHud") then {[] call USAFDC_fnc_updateHud};
    };
    false
};

private _path = if !(isNil "USAFDC_fnc_buildPathSolution") then {[_vehicle, _solution] call USAFDC_fnc_buildPathSolution} else {createHashMapFromArray [["pathValid", false]]};
{_solution set [_x, _path get _x]} forEach keys _path;
USAFDC_state_pathSolution = _path;

private _rawDesired = _solution getOrDefault ["pathDesiredTrackDeg", _solution getOrDefault ["rawDesiredTrackDeg", _solution get "runInDeg"]];
private _nowTick = diag_tickTime;
private _dt = (_nowTick - USAFDC_state_guidanceLastTick) max 0;
USAFDC_state_guidanceLastTick = _nowTick;
if (isNil "USAFDC_state_smoothedDesiredTrackDeg") then {
    USAFDC_state_smoothedDesiredTrackDeg = _rawDesired;
};
private _currentDesired = USAFDC_state_smoothedDesiredTrackDeg;
private _delta = (((_rawDesired - _currentDesired + 540) mod 360) - 180);

// THE SMOOTHING RATE FOLLOWS THE AUTOPILOT'S OWN TURN-RATE SCHEDULE.
//
// It was a flat 4 deg/s, which was right while only the flight director read this value.
// The autopilot now reads it too (see below), and a flat 4 would BIND during INTERCEPT,
// where the AP is allowed 6 -- turning a display filter into a silent cap on how fast the
// aircraft may intercept.
//
// So the schedule is the AP's, not a second opinion about it. No new constant is
// introduced here and the AP remains the single authority on slew rate;
// test_v0160_one_steering_reference pins the two lists identical.
private _turnRateDegS = switch (_solution getOrDefault ["pathState", ""]) do {
    case "INTERCEPT": {6};
    case "CAPTURE FINAL": {4};
    case "FINAL RUN": {2.5};
    case "RELEASE STABLE": {2.0};
    case "POST DROP": {2.0};
    default {4};
};
private _maxStep = _turnRateDegS * _dt;
private _step = (_delta max (-_maxStep)) min _maxStep;
USAFDC_state_smoothedDesiredTrackDeg = (_currentDesired + _step + 360) mod 360;
_solution set ["desiredTrackDeg", USAFDC_state_smoothedDesiredTrackDeg];
// AND THE AUTOPILOT FLIES IT TOO. Until v0.16.0 fn_updateAutopilot read
// pathDesiredTrackDeg -- the RAW pure-pursuit bearing straight out of the path manager --
// while the flight director read the smoothed value written on the line above. The needle
// and the aircraft were following two different references, which is indefensible however
// small the difference happens to be, and is the literal reading of "the AP feels off".
//
// The raw bearing is recomputed from the aircraft's own live position every tick, so it
// carries the aircraft's own motion back into its own command. Rate-limiting the TARGET is
// a different thing from rate-limiting the NOSE, and the AP only ever did the second.
//
// Overwritten rather than read differently at the far end, so there is exactly one key any
// consumer can reach and no third reference can appear by accident.
_solution set ["pathDesiredTrackDeg", USAFDC_state_smoothedDesiredTrackDeg];
_solution set ["rawDesiredTrackDeg", _rawDesired];
private _currentTrack = (_solution get "aircraftState") get "trackDeg";
_solution set ["steeringErrorDeg", (((USAFDC_state_smoothedDesiredTrackDeg - _currentTrack + 540) mod 360) - 180)];

if (USAFDC_state_apArmed && {!(isNil "USAFDC_fnc_updateAutopilot")}) then {
    [_vehicle, _solution] call USAFDC_fnc_updateAutopilot;
};

if !(isNil "USAFDC_fnc_updatePackageTiming") then {
    private _timing = [_vehicle, _solution] call USAFDC_fnc_updatePackageTiming;
    {_solution set [_x, _timing get _x]} forEach keys _timing;
} else {
    if !(isNil "USAFDC_fnc_estimatePackageTiming") then {
        private _timing = [_vehicle, _solution] call USAFDC_fnc_estimatePackageTiming;
        {_solution set [_x, _timing get _x]} forEach keys _timing;
    };
};

// ONLY THE MACHINE THAT OWNS THE AIRCRAFT MAY JUDGE THE PASS.
//
// Every crew member now runs this loop -- that is what makes a co-pilot's HUD, markers
// and 3D cue live -- but only the pilot's client owns the aircraft. Everyone else
// solves against a replica updated at roughly 10 Hz and extrapolated in between, which
// at 140 m/s is metres of position error and a smoothed velocity vector, judged
// against a release gate of |crossTrack| <= 25 m and |trackError| <= 2 deg. Those
// tolerances are the same order as the disagreement, so a co-pilot would latch a miss
// and be told to go around on a pass the pilot's own client considers good, with
// nothing in the cockpit to say which reading is authoritative.
//
// The display stays live on every client. What is withheld from a non-owner is the
// LATCH, which persists and spoils subsequent passes, and the instruction.
private _authoritative = local _vehicle;
_solution set ["authoritative", _authoritative];

// A jump run reaches the same geometry but releases nothing. The exit cue is
// fn_updateJumpCue's job on its own handler, so the drop cue, the missed-pass latch and
// auto drop all stay out of the way -- otherwise crossing the exit point would sound a
// cargo drop cue and, worse, a latched miss would tell the pilot to go around.
private _jumpRun = _solution getOrDefault ["jumpRun", false];

private _current = _solution get "signedRpM";
private _previous = USAFDC_state_lastSignedRpM;
private _crossed = (_previous > 0) && {_current <= 0};
private _releaseStable = _solution getOrDefault ["releaseStable", true];
USAFDC_state_lastSignedRpM = _current;
USAFDC_state_releaseCrossed = _crossed;

// Going around is the instruction the HUD gives, so it has to be actionable
// without touching the panel: once the aircraft is back upstream of the final
// envelope this is a new attempt and the previous miss no longer applies.
if (USAFDC_state_passMissed && {_current > 800}) then {
    USAFDC_state_passMissed = false;
    USAFDC_state_standbyCueSent = false;
    diag_log format ["[TLB CARP][GO AROUND] repositioned upstream, pass reset signedRp=%1", _current];
};

if (USAFDC_state_passMissed && {_current <= 0}) then {
    _releaseStable = false;
    _solution set ["releaseStable", false];
    _solution set ["guidanceState", "UNSTABLE RUN-IN"];
};

if (!_jumpRun && {(_current > 0)} && {_current <= 250} && {_releaseStable} && {!USAFDC_state_standbyCueSent}) then {
    USAFDC_state_standbyCueSent = true;
    if (USAFDC_setting_sounds) then {playSound "FD_Timer_F"};
};

if (!_jumpRun && {_crossed} && {_releaseStable}) then {
    USAFDC_state_dropCueUntil = time + 1;
    if (USAFDC_setting_sounds) then {playSound "FD_Start_F"};
    // Chunked, because the solution hashmap alone runs past what diag_log will write:
    // every one of these lines in the flown RPTs is exactly 1031 bytes and stops inside
    // an array, so the half of the solution that matters never reached the file.
    ["DROP", format ["sim=%1 real=%2 posASL=%3 velocity=%4 wind=%5 signedRp=%6 crossTrack=%7 solution=%8", time, diag_tickTime, getPosASL _vehicle, velocity _vehicle, wind, _current, _solution get "crossTrackM", _solution]] call USAFDC_fnc_logLong;
    if (USAFDC_setting_debug && {USAFDC_setting_calibrationRecorder} && {!(isNil "USAFDC_fnc_beginCalibrationRun")}) then {
        [_vehicle, _solution] call USAFDC_fnc_beginCalibrationRun;
    };
};

if (!_jumpRun && {_crossed} && {!_releaseStable}) then {
    _solution set ["guidanceState", "UNSTABLE RUN-IN"];
    _solution set ["releaseStable", false];
};
if (_crossed && {!_releaseStable} && {_authoritative}) then {
    USAFDC_state_passMissed = true;
    USAFDC_state_dropCueUntil = -1;
    USAFDC_state_standbyCueSent = false;
    // A refusal used to leave no evidence at all -- only successful crossings
    // were logged -- so there was no way to tell which tolerance failed.
    diag_log format [
        "[TLB CARP][NO DROP] missed pass sim=%1 crossTrack=%2 trackError=%3 preChuteDrift=%4 signedRp=%5 lineOffset=%6 velRight=%7 warnings=%8",
        time,
        _solution getOrDefault ["crossTrackM", 0],
        _solution getOrDefault ["trackErrorDeg", 0],
        _solution getOrDefault ["preChuteLateralDriftM", 0],
        _current,
        _solution getOrDefault ["finalRunLineOffsetM", 0],
        // "kinematics" is exported ONLY by the jump-run exit, so on every cargo drop this
        // read an empty hashmap and printed its default. velRight was 0 in every NO DROP
        // line ever logged, which is exactly the tell that would have found this sooner.
        _solution getOrDefault ["velocityRightMs", 0],
        _solution getOrDefault ["warnings", []]
    ];
    if (USAFDC_state_autoArmed && {!(isNil "USAFDC_fnc_disarmAutoDrop")}) then {[] call USAFDC_fnc_disarmAutoDrop};
    hint "TLB CARP: UNSTABLE RUN-IN - NO DROP - GO AROUND";
};

_solution set ["packageTrackingOnly", false];
USAFDC_state_solution = _solution;
USAFDC_state_displaySolution = _solution;

if !(isNil "USAFDC_fnc_updatePanelTelemetry") then {
    if ((diag_tickTime - USAFDC_state_panelLastTelemetryTick) >= 0.20) then {
        USAFDC_state_panelLastTelemetryTick = diag_tickTime;
        [] call USAFDC_fnc_updatePanelTelemetry;
    };
};

if !(isNil "USAFDC_fnc_updateMarkers") then {[] call USAFDC_fnc_updateMarkers};
if !(isNil "USAFDC_fnc_updateHud") then {[] call USAFDC_fnc_updateHud};

if (!_jumpRun && {_crossed} && {_releaseStable} && {USAFDC_state_autoArmed} && {!USAFDC_state_dropLatched} && {!(isNil "USAFDC_fnc_triggerAutoDrop")}) then {
    USAFDC_state_dropLatched = true;
    [] call USAFDC_fnc_triggerAutoDrop;
};
true

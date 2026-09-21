params ["_vehicle", "_solution"];
if !(missionNamespace getVariable ["USAFDC_state_apArmed", false]) exitWith {false};

if (isNull _vehicle || {!((driver _vehicle) isEqualTo player)}) exitWith {
    ["PILOT SEAT LOST", true] call USAFDC_fnc_disarmAutopilot;
    false
};
// Ownership can move mid-flight -- a seat handover, a headless-client offload, a
// mission framework calling setOwner. Every actuation below except setDir is a
// local-effect command, so a silent loss of locality leaves the controller writing
// orientation into a vehicle it cannot move. Disconnect loudly instead.
if !(local _vehicle) exitWith {
    ["AIRCRAFT NOT LOCAL", true] call USAFDC_fnc_disarmAutopilot;
    false
};
if (!USAFDC_state_guidanceArmed) exitWith {
    ["GUIDANCE DISARMED", true] call USAFDC_fnc_disarmAutopilot;
    false
};
if (!USAFDC_state_runInLocked) exitWith {
    ["RUN-IN UNLOCKED", true] call USAFDC_fnc_disarmAutopilot;
    false
};
if !(_solution getOrDefault ["valid", false]) exitWith {
    ["INVALID SOLUTION", true] call USAFDC_fnc_disarmAutopilot;
    false
};
if !(_solution getOrDefault ["pathValid", false]) exitWith {
    ["INVALID PATH", true] call USAFDC_fnc_disarmAutopilot;
    false
};

private _manualInput = 0;
private _overrideTriggered = false;
private _uiHasFocus = if !(isNil "USAFDC_fnc_inputFocusActive") then {[] call USAFDC_fnc_inputFocusActive} else {!(isNull (findDisplay 9300)) || {!(isNull (findDisplay 312))}};
if (_uiHasFocus) then {
    USAFDC_state_apOverrideSince = -1;
    USAFDC_state_apOverrideInhibitUntil = diag_tickTime + 0.5;
} else {
    private _overrideInhibited = diag_tickTime < (missionNamespace getVariable ["USAFDC_state_apOverrideInhibitUntil", -1]);
    if (_overrideInhibited) then {
        USAFDC_state_apOverrideSince = -1;
    } else {
        private _threshold = missionNamespace getVariable ["USAFDC_setting_apOverrideThreshold", 0.25];
        {
            _manualInput = _manualInput max (inputAction _x);
        } forEach [
            "HeliForward", "HeliBack", "AirBankLeft", "AirBankRight",
            "HeliRudderLeft", "HeliRudderRight", "HeliUp", "HeliDown"
        ];
        private _throttleNow = inputAction "HeliThrottlePos";
        private _throttleBase = missionNamespace getVariable ["USAFDC_state_apThrottleBaseline", _throttleNow];
        _manualInput = _manualInput max (abs (_throttleNow - _throttleBase));

        if (_manualInput >= _threshold) then {
            if (USAFDC_state_apOverrideSince < 0) then {USAFDC_state_apOverrideSince = diag_tickTime};
            if ((diag_tickTime - USAFDC_state_apOverrideSince) >= 0.12) then {_overrideTriggered = true};
        } else {
            USAFDC_state_apOverrideSince = -1;
        };
    };
};
if (_overrideTriggered) exitWith {
    ["PILOT OVERRIDE", true] call USAFDC_fnc_disarmAutopilot;
    false
};
if !(missionNamespace getVariable ["USAFDC_state_apArmed", false]) exitWith {false};

// ---- actuation rate limit ----------------------------------------------------
// The AP must not actuate once per rendered frame, and the per-frame handler it runs
// on does NOT guarantee that.
//
// v0.6.3 measured the failure exactly: an EachFrame loop that wrote orientation
// immediately before setVelocity held an aircraft at 2.0 m/s of actual travel while
// velocity read the commanded 138.9 m/s on the correct bearing, the nose was correct
// and attachedTo was null. The same loop commanding velocity alone gave 130.8 m/s.
// Re-seating the transform every frame stops displacement accumulating.
//
// That was recorded at the time as a harness-only problem, on the grounds that this
// function runs on a 0.05 s CBA per-frame handler rather than on EachFrame. That
// reasoning was wrong. CBA's scheduler (cba_common, init_perFrameHandler.sqf) is:
//
//     if (diag_tickTime > _delta) then {_x set [2, _delta + _delay]; ... call _function};
//
// Two consequences. At any frame time above the interval -- below 20 fps for the
// 0.05 s default, ordinary on a populated dedicated server -- the condition holds
// every frame, so a 20 Hz handler IS an EachFrame handler. And _delta advances by
// exactly _delay per execution while real time advances by a whole frame, so once the
// handler falls behind it can never catch up: it fires every frame from then on even
// after the framerate recovers. One hitch latches it for the rest of the mission,
// which is why this appears mid-session rather than from the first engagement.
//
// Two guards, because they cover different cases. The wall-clock throttle restores
// the configured rate once CBA's schedule has slipped at a healthy framerate. It
// cannot help when frames are genuinely further apart than the interval, so the
// orientation write additionally requires a frame in which nothing re-seats the
// transform, which is what the engine needs to integrate position.
private _now = diag_tickTime;
private _interval = missionNamespace getVariable ["USAFDC_setting_updateInterval", 0.05];
if ((_now - (missionNamespace getVariable ["USAFDC_state_apLastActuateTick", -1])) < (_interval * 0.9)) exitWith {
    // Not a disconnect and not an error: the handler simply ran early. Returning
    // without stamping apLastTick keeps _dt equal to the real actuation interval, so
    // the bounded turn rate below stays in degrees per second rather than per call.
    true
};
USAFDC_state_apLastActuateTick = _now;

private _dt = ((_now - USAFDC_state_apLastTick) max 0.001) min 0.20;
USAFDC_state_apLastTick = _now;

private _pathState = _solution getOrDefault ["pathState", "INTERCEPT"];
private _runInDeg = _solution getOrDefault ["runInDeg", getDir _vehicle];
private _desiredTrackDeg = _solution getOrDefault ["pathDesiredTrackDeg", _runInDeg];
if (_pathState isEqualTo "POST DROP") then {_desiredTrackDeg = _runInDeg};
private _targetVz = _solution getOrDefault ["commandVerticalSpeedMs", 0];

private _targetGroundSpeedMs = (USAFDC_state_targetGroundSpeedKmh max 100) / 3.6;
private _currentDir = getDir _vehicle;
private _headingError = (((_desiredTrackDeg - _currentDir + 540) mod 360) - 180);
private _turnRateDegS = switch (_pathState) do {
    case "INTERCEPT": {6};
    case "CAPTURE FINAL": {4};
    case "FINAL RUN": {2.5};
    case "RELEASE STABLE": {2.0};
    case "POST DROP": {2.0};
    default {4};
};
private _maxHeadingStep = _turnRateDegS * _dt;
private _headingStep = (_headingError max (-_maxHeadingStep)) min _maxHeadingStep;
private _newHeading = (_currentDir + _headingStep + 360) mod 360;

private _vel = velocity _vehicle;
private _currentGroundSpeed = sqrt (((_vel # 0) ^ 2) + ((_vel # 1) ^ 2));

// THE AIRCRAFT NOW FLIES A COMMANDED STATE THAT MOVES AT A BOUNDED ACCELERATION.
//
// It used to blend from the MEASURED velocity every tick:
//
//     _alphaSpeed = (_dt * 1.6) min 0.18;
//     _newGroundSpeed = _current + ((_target - _current) * _alphaSpeed);
//
// Three things are wrong with that, and all three are what a pilot feels.
//
// 1. IT IS A FILTER ON A NOISY MEASUREMENT, NOT A COMMAND. Whatever the engine did to the
//    velocity since the last write is fed straight back into the next one. The aircraft is
//    therefore always correcting the engine rather than flying a trajectory, which is the
//    "forcing it instead of smoothing it" the crew reported.
//
// 2. THE TIME CONSTANT IS ABOUT 0.6 s, WHICH IS NOT AN AIRCRAFT. Engaging in a 20-degree
//    dive at 1000 km/h with 350 set took roughly two seconds to level out and wash off
//    180 m/s. A C-130 shedding that much speed is most of a minute, and no transport pulls
//    level from a dive in two seconds.
//
// 3. IT DOES NOT SCALE WITH dt THE WAY IT LOOKS LIKE IT DOES. The clamp at 0.18 means a
//    long tick applies a disproportionately large correction, so the irregular actuation
//    interval turns into an irregular lurch.
//
// The command is now integrated instead: held as AP state, moved toward the target by at
// most (rate * dt), and written. It is seeded from the ACTUAL velocity at arm time, so
// engaging is continuous with whatever the pilot was doing, and it converges on the target
// at a rate a transport can actually fly.
//
// The measured velocity is still read -- but only to decide the THROTTLE, below, which is
// the control surface that belongs in a speed loop.
private _accelMs2 = missionNamespace getVariable ["USAFDC_setting_apAccelMs2", 1.5];
private _vzRateMs2 = missionNamespace getVariable ["USAFDC_setting_apVzRateMs2", 2.5];

private _cmdSpeed = missionNamespace getVariable ["USAFDC_state_apCmdSpeedMs", -1];
private _cmdVz = missionNamespace getVariable ["USAFDC_state_apCmdVzMs", -1e9];
// Seeded on the first actuation rather than at arm, so it cannot be stale if the aircraft
// changed state between the arm and the first tick.
if (_cmdSpeed < 0) then {_cmdSpeed = _currentGroundSpeed};
if (_cmdVz < -1e8) then {_cmdVz = _vel # 2};

private _speedStep = _accelMs2 * _dt;
private _vzStep = _vzRateMs2 * _dt;
_cmdSpeed = _cmdSpeed + (((_targetGroundSpeedMs - _cmdSpeed) max (-_speedStep)) min _speedStep);
_cmdVz = _cmdVz + (((_targetVz - _cmdVz) max (-_vzStep)) min _vzStep);
USAFDC_state_apCmdSpeedMs = _cmdSpeed;
USAFDC_state_apCmdVzMs = _cmdVz;

private _newGroundSpeed = _cmdSpeed;
private _newVz = _cmdVz;
private _newVel = [
    _newGroundSpeed * sin _newHeading,
    _newGroundSpeed * cos _newHeading,
    _newVz
];

// setDir before setVelocity: setDir wipes velocity, which was the v0.3.0 bug. That
// ordering invariant is unchanged. What is new is that the write is skipped entirely
// unless the engine has had a frame to itself since the last one.
//
// Skipping it is safe for guidance because the commanded velocity is built from
// _newHeading, not from the nose: the aircraft keeps translating exactly where the
// path manager wants it, and only the nose lags by one actuation. _newHeading is
// recomputed from getDir every tick, so a skipped write is not a lost command -- the
// next tick takes another bounded step from wherever the nose actually is.
private _orientationWritten = false;
private _forceMode = missionNamespace getVariable ["USAFDC_setting_apForceMode", true];

if (_forceMode) then {
    // ---- FLY THE AIRCRAFT INSTEAD OF MOVING IT -------------------------------------
    //
    // THIS IS WHY IT JUDDERED. setVelocity and setDir OVERWRITE the engine's own
    // integration. Between two writes Arma flies the aeroplane properly; the next write
    // throws that away and replaces it with the commanded state. At the measured 15.8 Hz
    // that is sixteen discontinuities a second, and no amount of smoothing the COMMAND
    // removes them -- v0.16.6 smoothed the command and cured the snap on engage while the
    // judder stayed, which is exactly what this predicts.
    //
    // The reference is @Realistic Auto Pilots (HAL, by Blockdude, itself from ITC).
    // NOT ONE FILE IN THAT MOD CALLS setVelocity OR setDir. It applies forces and torques
    // and lets the flight model do the flying, which is why it is smooth. The same
    // approach is taken here; the numbers are ours and the structure is theirs.
    //
    //   pitch   a vertical force applied ahead of the centre of gravity, which is a
    //           pitching moment, driving the FLIGHT PATH ANGLE to the commanded one
    //   roll    bank-to-turn: heading error commands a bank angle, torque holds it
    //   yaw     torque proportional to sideslip, so the turn stays coordinated
    //
    // THE HONEST COST: a real aircraft turns at g*tan(bank)/V. At 30 degrees of bank and
    // 140 m/s that is about 2.3 deg/s, where the old code yawed the nose at up to 6. The
    // aircraft will take longer to come round onto an intercept, because that is what an
    // aircraft does. USAFDC_setting_apForceMode switches back if this is worse in flight.
    private _massMult = (getMass _vehicle) * 0.0001;
    private _vz = _vel # 2;

    // Flight path angle, commanded and actual. Driving the PATH rather than the pitch
    // attitude is what stops the aircraft mushing up or down at a constant attitude.
    private _targetFpa = if (_currentGroundSpeed > 1) then {(_cmdVz atan2 _currentGroundSpeed)} else {0};
    private _actualFpa = if (_currentGroundSpeed > 1) then {(_vz atan2 _currentGroundSpeed)} else {0};
    private _pitchForce = (_targetFpa - _actualFpa) * 1.0 * _massMult;

    // INTEGRAL TRIM, straight from HAL and the reason it holds altitude instead of
    // drifting. Every flight model has a standing force deficit at trim; a proportional
    // term alone answers it with a permanent small error. This accumulates the mean over
    // 100 samples and folds it into an offset, so the steady state is actually steady.
    if ((abs _pitchForce) < 20) then {
        USAFDC_state_apTrimCount = (missionNamespace getVariable ["USAFDC_state_apTrimCount", 0]) + 1;
        USAFDC_state_apTrimSum = (missionNamespace getVariable ["USAFDC_state_apTrimSum", 0]) + _pitchForce;
        if (USAFDC_state_apTrimCount >= 100) then {
            USAFDC_state_apTrimOffset = (missionNamespace getVariable ["USAFDC_state_apTrimOffset", 0]) + (USAFDC_state_apTrimSum / 100);
            USAFDC_state_apTrimCount = 0;
            USAFDC_state_apTrimSum = 0;
        };
        _pitchForce = _pitchForce + (missionNamespace getVariable ["USAFDC_state_apTrimOffset", 0]);
    };

    // addForce acts for ONE simulation step, so actuating at 20 Hz on a 60 fps machine
    // would deliver a third of the intended impulse. Scaled by the frames this actuation
    // stands in for, and clamped, because diag_fps is smoothed and a wild value here would
    // be indistinguishable from the judder this exists to remove.
    private _rateComp = ((_dt * (diag_fps max 1)) max 1) min 6;

    _vehicle addForce [_vehicle vectorModelToWorld [0, 0, _pitchForce * _rateComp], [0, 500, 0]];

    // BANK TO TURN. The heading error commands a bank; the torque holds the aircraft at
    // it. Capped per path state so a release run is flown wings-near-level and only an
    // intercept is allowed to use real bank.
    private _maxBank = switch (_pathState) do {
        case "INTERCEPT": {30};
        case "CAPTURE FINAL": {20};
        case "FINAL RUN": {8};
        case "RELEASE STABLE": {4};
        case "POST DROP": {20};
        default {20};
    };
    private _pitchBank = _vehicle call BIS_fnc_getPitchBank;
    private _bank = _pitchBank # 1;

    // ---- rates, which is what the loop was missing entirely ------------------------
    //
    // Flown report: "it banks left, but by the time the vector passes it starts to turn
    // back right, and by the time it's straight the vector is on the other side. So it's a
    // constant chase between XTRK left and right. We need AP to predict the turn and
    // arrest it."
    //
    // That is a textbook proportional-only oscillation and the diagnosis is in the
    // description. Commanded bank was k * headingError and nothing else, so when the error
    // reached zero the commanded bank reached zero -- while the aircraft was still TURNING
    // at up to three degrees a second. It sailed through, the error reversed, and it rolled
    // the other way. Nothing in the loop knew the aircraft had a turn rate.
    //
    // Both rates are measured here rather than inferred, because an inferred turn rate from
    // g*tan(bank)/V would be right only in a steady coordinated turn -- which is precisely
    // the condition the aircraft is NOT in while it is chasing.
    private _prevDir = missionNamespace getVariable ["USAFDC_state_apPrevDir", -1e9];
    private _prevBank = missionNamespace getVariable ["USAFDC_state_apPrevBank", -1e9];
    private _hdgRate = 0;
    private _rollRate = 0;
    if (_prevDir > -1e8) then {
        _hdgRate = ((((_currentDir - _prevDir) + 540) mod 360) - 180) / _dt;
        _rollRate = (_bank - _prevBank) / _dt;
    };
    USAFDC_state_apPrevDir = _currentDir;
    USAFDC_state_apPrevBank = _bank;

    // LEAD: steer to where the error WILL be, not where it is. A turn rate of w degrees a
    // second closes w*lead degrees of error over the lead time, so subtracting that is a
    // prediction rather than a damper -- the aircraft starts rolling out while the needle
    // is still off centre, which is what a pilot does and what was asked for.
    private _leadS = missionNamespace getVariable ["USAFDC_setting_apTurnLeadS", 4];
    private _errPredicted = _headingError - (_hdgRate * _leadS);
    private _targetBank = ((_errPredicted * 1.5) max (-_maxBank)) min _maxBank;

    // ROLL DAMPING. The bank loop was also proportional-only: torque proportional to bank
    // error, nothing opposing the roll RATE, so the aircraft overshot its own commanded
    // bank as well. Two undamped loops in series is why the chase never settled.
    private _rollDamp = missionNamespace getVariable ["USAFDC_setting_apRollDamping", 150];
    private _bankTorque = (((_targetBank - _bank) * 300) - (_rollRate * _rollDamp)) * _massMult;
    _vehicle addTorque (_vehicle vectorModelToWorld [0, -_bankTorque * _rateComp, 0]);

    // ---- yaw: coordination plus the turn it is actually flying ---------------------
    //
    // Flown report: "I don't see the AP using YAW at all... I don't see the tail moving at
    // all even in roll turns."
    //
    // Correct observation. The only yaw term was proportional to SIDESLIP, and in a turn
    // the flight model keeps sideslip near zero, so the rudder had nothing to answer and
    // never visibly moved. Aerodynamically that was defensible -- you turn with bank and
    // the rudder only coordinates -- but it left the rudder inert and the turn entry
    // sloppier than it needs to be.
    //
    // A real turn coordinator drives rudder with the TURN, not only with the slip: rudder
    // proportional to bank is the feedforward that holds the ball centred through the roll
    // in and roll out. The slip term stays as the feedback that catches whatever the
    // feedforward misses.
    //
    // Deliberately modest. Yaw is not a steering input here and must never become one:
    // rudder used to turn makes the aircraft SKID, and lateral velocity at release is the
    // thing the release gate punishes hardest -- +1.294 m/s measured as ~+30 m of miss.
    private _slip = (_vehicle vectorWorldToModel _vel) # 0;
    private _yawFF = missionNamespace getVariable ["USAFDC_setting_apYawCoordination", 40];
    private _yawTorque = ((_slip * 200) + (_bank * _yawFF)) * _massMult;
    _vehicle addTorque (_vehicle vectorModelToWorld [0, 0, _yawTorque * _rateComp]);
} else {
    // ---- LEGACY: WRITE THE TRANSFORM ----------------------------------------------
    // setDir before setVelocity: setDir wipes velocity, which was the v0.3.0 bug. That
    // ordering invariant is unchanged. The write is skipped unless the engine has had a
    // frame to itself since the last one.
    //
    // Skipping it is safe for guidance because the commanded velocity is built from
    // _newHeading, not from the nose: the aircraft keeps translating exactly where the
    // path manager wants it, and only the nose lags by one actuation.
    if ((diag_frameNo - (missionNamespace getVariable ["USAFDC_state_apLastDirFrame", -1])) >= 2) then {
        USAFDC_state_apLastDirFrame = diag_frameNo;
        _orientationWritten = true;
        _vehicle setDir _newHeading;
    };
    _vehicle setVelocity _newVel;
};

// THROTTLE IS NOW A REAL SPEED LOOP, DRIVEN BY THE ACTUAL ERROR.
//
// It used to read (_target - _newGroundSpeed), and _newGroundSpeed was itself pulled to
// within a few per cent of the target by the blend above -- so the error was almost always
// near zero and the throttle sat at its 0.58 baseline doing nothing. All the speed
// authority came from setVelocity, which is exactly the "forced" behaviour that was asked
// about. Reading the MEASURED speed makes this the term that actually holds the aircraft
// at its commanded speed, and leaves setVelocity correcting a much smaller residual.
private _speedErr = _targetGroundSpeedMs - _currentGroundSpeed;
// Gain raised from 0.015 to 1/15, which is HAL's. At 0.015 a 20 m/s error moved the
// throttle by 0.3 and the aircraft took half a minute to respond -- acceptable only
// because setVelocity was doing the real work. In force mode the throttle IS the
// speed authority, so it has to be able to answer.
private _throttleCmd = (0.58 + (_speedErr / 15)) max 0.20 min 1.0;
_vehicle setAirplaneThrottle _throttleCmd;

USAFDC_state_apState = _pathState;
_solution set ["apState", _pathState];
_solution set ["apDesiredTrackDeg", _desiredTrackDeg];

// THE JITTER IS STILL UNDIAGNOSED AND THIS IS THE INSTRUMENT FOR IT.
//
// Thirty-eight candidate mechanisms were raised against this file and the path manager and
// every one was refuted -- none offered a magnitude. What was never available was a
// MEASUREMENT: how noisy the commanded track actually is, whether the nose is slewing at
// its limit continuously, and what the frame time is doing while that happens.
//
// GATED BEHIND THE DEBUG SETTING AS OF v0.16.6, AND THAT IS ITSELF A JITTER CANDIDATE.
//
// The crew describe the aircraft nudging forward and back "every half second or so".
// This ran at exactly 0.5 s and diag_log is a synchronous write to the RPT on the
// render thread. A period that matches the symptom to the tick is worth removing from
// the normal flight path before anything subtler is blamed -- and it costs nothing to
// test, because turning the setting on brings it straight back.
//
// That is a candidate, not a finding. The measured actuation rate is 15.8 Hz against a
// configured 20, so there is a second irregularity here that this does not explain.
//
// Twice a second, so it costs nothing and a two-minute run-in gives ~240 samples. Read
// them with: grep "AP TRACK" in the RPT.
//   raw     the pure-pursuit bearing before smoothing
//   des     what the AP is actually chasing after v0.16.0
//   dir     the nose now
//   step    this actuation's slew, against lim -- equal means saturated
//   dt/fps  whether the actuation rate is what it is supposed to be
if ((missionNamespace getVariable ["USAFDC_setting_debug", false]) && {(diag_tickTime - (missionNamespace getVariable ["USAFDC_state_apTrackLogTick", -1e9])) >= 0.5}) then {
    USAFDC_state_apTrackLogTick = diag_tickTime;
    diag_log format ["[TLB CARP][AP TRACK] state=%1 raw=%2 des=%3 dir=%4 err=%5 step=%6 lim=%7 dt=%8 fps=%9 vz=%10 cmdVz=%11 cmdGs=%12",
        _pathState,
        (_solution getOrDefault ["rawDesiredTrackDeg", -1]) toFixed 2,
        _desiredTrackDeg toFixed 2,
        _currentDir toFixed 2,
        _headingError toFixed 2,
        _headingStep toFixed 3,
        _maxHeadingStep toFixed 3,
        _dt toFixed 4,
        round diag_fps,
        ((velocity _vehicle) # 2) toFixed 2,
        _targetVz toFixed 2,
        _cmdSpeed toFixed 2];
};
_solution set ["apTargetVzMs", _targetVz];
_solution set ["apManualInput", _manualInput];
_solution set ["apOrientationWritten", _orientationWritten];
true

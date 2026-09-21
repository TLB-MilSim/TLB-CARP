/*
    USAFDC_fnc_buildJumpSolution

    Where a jumper must leave the aircraft to reach the DZ, and whether the profile
    they have asked for can reach it at all.

    Separate from fn_buildWorldSolution on purpose, not for tidiness:

      1. fn_buildWorldSolution.sqf:19 hard-exits with NO USAF CARGO when the carrier
         is empty, and a jump aircraft is empty by definition.
      2. The cargo canopy model (EMPIRICAL_C17_V2, zeroWorldM, the wind delta tables)
         is measured for a USAF pallet at ~230 m/s freefall terminal under its own
         chute. A human falls at 64 m/s under a canopy with an air glide ratio of
         1.27. None of those numbers transfer, and calibration/model.json is a
         protected asset that unrelated work must not touch.
      3. USAFDC_state_solution is the live authoritative CARGO state. Writing jump
         geometry into it would make an invalid cargo solver look valid to
         operational logic, which is explicitly not how display problems get fixed
         in this codebase.

    Returns its own hashmap; the caller stores it in USAFDC_state_jumpSolution.

    ---------------------------------------------------------------------------
    THE MODEL, and the four flown runs behind it

    exitRange = windSpeed * freefallTime, positioned UPWIND of the DZ.
    freefallTime = (exitAgl - openAgl) / 66 + 3 s

    There is deliberately NO forward-throw term. FFR hands the jumper 0.9x the
    aircraft's velocity (fnc_standUp; measured exitHoriz 124.8 m/s against a
    predicted 125.0 at 500 km/h, so the 0.9 is confirmed to 0.2%), and it was
    tempting to correct for the resulting throw. The data says do not:

      run  exit speed  wind-subtracted freefall residual
      C     208.3 m/s   520 m
      D     124.8 m/s   604 m

    A throw with any fixed decay scales LINEARLY with exit speed, so C should have
    shown 1.67x D. It showed 0.86x. The residual is therefore independent of exit
    speed, which makes it the jumper TRACKING in freefall -- run D's freefall went
    401 m toward 181 while the wind pushed 443 m toward 090 -- and tracking is range
    the jumper spends, not an error to pre-empt. Adding a throw term would have
    displaced the exit by 300-600 m in the wrong direction.

    Validation, four runs, rule vs flown:

      run       rule    flown   excess   miss   recovery
      A  5 m/s   211 m   1758 m  +1547    1087 m   460 m
      B 10 m/s  1494 m   1685 m   +191       2 m     -
      C 10 m/s   443 m   1844 m  +1401     938 m   463 m
      D 10 m/s   443 m    463 m    +20      72 m     -

    Both exits near the rule landed inside a 200 m box. Both gross overshoots imply
    a recovery budget of 460 and 463 m -- two independent measurements agreeing to
    3 m, which is what JUMP_RECOVERY_M is.

    CAVEAT that belongs in the cockpit, not just here: the recovery budget IS the
    jumper's freefall tracking plus canopy glide. A stick that exits and simply
    falls has neither, and the 0.9x throw then carries them along the run-in
    uncorrected. USAFDC_setting_jumpTrackOffsetM exists for that case and defaults
    to 0.
*/

// ---- measured constants ------------------------------------------------------
// Freefall steady-state vertical speed: 63.15, 66.41, 63.41, 63.97 m/s across four
// runs (mean 64.2, sd 1.3). 66 is used in the time model rather than the mean
// because the model's constant term absorbs the acceleration phase; fitted against
// the two runs with the widest altitude spread it errs -0.7 s and +1.6 s, which is
// 16 m of drift at 10 m/s.
#define JUMP_FF_TERMINAL_MS 66
// Seconds of extra freefall time from the acceleration phase, over and above
// distance/terminal. Fitted, n=2.
#define JUMP_FF_ACCEL_S 3

// Canopy, air-relative. Ground-relative figures are wind-contaminated and worthless
// as constants: the same canopy read a ground glide of 1.440 flown crosswind and
// 2.298 downwind, while subtracting the wind gave 1.274 and 1.271.
#define JUMP_CANOPY_GLIDE 1.27
// Altitude lost in the first 4 s after the canopy opens, before it flies. 103, 106,
// 106, 106 m across four runs -- the tightest constant in the set, and a large one:
// at a 233 m opening it is 45% of the whole descent.
#define JUMP_CANOPY_TRANSIENT_M 105
// Horizontal travel during that transient, air-relative.
#define JUMP_CANOPY_TRANSIENT_TRAVEL_M 20
// Canopy airspeed at full glide: 11.29, 11.96, 10.86, 11.73, 11.37 m/s (n=5,
// mean 11.44, sd 0.38). This is the number that decides which exit errors can be
// recovered, because it is what the canopy can do AGAINST the wind.
#define JUMP_CANOPY_AIRSPEED_MS 11.4
// Descent rate at full glide: 8.86, 9.41, 9.25, 9.10, 8.86 m/s (n=5, mean 9.10,
// sd 0.22). Braked and spiralling runs read 5.10 and 7.79 and are excluded -- a
// different flight regime, not a different canopy.
#define JUMP_CANOPY_DESCENT_MS 9.1
// Freefall tracking plus canopy glide, ALONG track: 460, 463 and 553 m from three
// overshoots. Kept at the pessimistic end on purpose.
#define JUMP_RECOVERY_M 460
// Fraction of the canopy's theoretical reach treated as usable. The theoretical
// figure assumes a straight line at best glide from the instant of opening, with no
// time spent assessing, turning or setting up a landing.
#define JUMP_RECOVERY_MARGIN 0.7

params [["_aircraft", objNull]];

private _fail = {
    params ["_reason"];
    createHashMapFromArray [["valid", false], ["reason", _reason]]
};

if (isNull _aircraft) exitWith {["NO AIRCRAFT"] call _fail};
if ((count USAFDC_state_dzPosASL) < 3) exitWith {["NO DZ SET"] call _fail};
if (!USAFDC_state_runInLocked) exitWith {["RUN-IN UNLOCKED"] call _fail};

private _dz = USAFDC_state_dzPosASL;
private _acPos = getPosASL _aircraft;
private _vel = velocity _aircraft;
private _groundSpeedMs = sqrt (((_vel # 0) ^ 2) + ((_vel # 1) ^ 2));
private _exitAgl = (getPosATL _aircraft) # 2;
// Panel first, Addon Option as the mission default. 0 means the crew has not overridden
// it, not "open at ground level".
private _openAgl = missionNamespace getVariable ["USAFDC_state_jumpOpenAglM", 0];
if (_openAgl <= 0) then {_openAgl = missionNamespace getVariable ["USAFDC_setting_jumpOpenAglM", 600]};

if (_exitAgl <= (_openAgl + JUMP_CANOPY_TRANSIENT_M)) exitWith {
    ["BELOW OPENING ALTITUDE"] call _fail
};

// ---- freefall ----------------------------------------------------------------
private _fallM = _exitAgl - _openAgl;
private _freefallS = (_fallM / JUMP_FF_TERMINAL_MS) + JUMP_FF_ACCEL_S;

// ---- wind drift --------------------------------------------------------------
// Trig in DEGREES throughout; Arma's sin/cos take degrees.
private _w = wind;
private _windE = _w # 0;
private _windN = _w # 1;
private _windMs = sqrt ((_windE * _windE) + (_windN * _windN));
private _windDirDeg = if (_windMs > 0.01) then {((_windE atan2 _windN) + 360) mod 360} else {0};
private _driftM = _windMs * _freefallS;

// Ideal exit point: upwind of the DZ by exactly the drift, so a jumper who does
// nothing arrives over the DZ and every input they make is margin. That is the
// conservative case made the design case.
private _exitE = (_dz # 0) - (_windE * _freefallS);
private _exitN = (_dz # 1) - (_windN * _freefallS);

private _runInDeg = USAFDC_state_runInDeg;
private _tE = sin _runInDeg;
private _tN = cos _runInDeg;

// ---- the stick ---------------------------------------------------------------
// A stick does not exit at a point. Each jumper leaves later than the one ahead, and
// the aircraft has moved on: spacing is groundSpeed x interval, so the stick occupies
//     (N - 1) x interval x groundSpeed
// metres of track. At 500 km/h and one second between jumpers that is 139 m per gap
// -- 972 m for eight jumpers, which is longer than the entire recovery budget. Cueing
// the whole stick at the single ideal exit point therefore puts the tail of it
// somewhere no amount of tracking or canopy will bring back.
//
// So the green light is called EARLY by half the stick length, which straddles the
// ideal exit: the middle jumper gets the computed point, and the first and last are
// symmetric about it instead of the first being right and everyone after being late.
//
// This is the term the exit velocity actually contributes, and unlike the per-jumper
// forward throw it is exact -- pure geometry, no measurement in it. The throw stays
// out of the computation because three flown residuals (520 m at 208.3 m/s, 604 m and
// 529 m at ~125 m/s) show it is dominated by how the jumper flies, not by exit speed:
// two runs at the SAME exit speed differed by 75 m. USAFDC_setting_jumpTrackOffsetM
// is there for anyone who wants to bias for it by hand.
// ---- the asymmetry that decides everything -----------------------------------
// The exit point sits UPWIND of the DZ, so an exit error has a SIGN, and the two
// signs are not remotely equivalent:
//
//   exited EARLY (further upwind) -> opens upwind of the DZ -> flies DOWNWIND to it,
//                                    over the ground at airspeed PLUS wind
//   exited LATE  (nearer the DZ)  -> opens downwind         -> flies UPWIND to it,
//                                    over the ground at airspeed MINUS wind
//
// At 10 m/s with an 11.4 m/s canopy that is 21.4 m/s one way and 1.4 m/s the other:
// from a 600 m opening, 1167 m of recovery early against 78 m late. Above 11.4 m/s
// of wind the canopy cannot make ground upwind at all, and a late exit cannot then
// be recovered by any amount of skill.
//
// Flown confirmation: one run exited 1964 m EARLY, tracked 596 m past the wind's
// share in freefall, covered 1273 m downwind under canopy at 21.0 m/s, and still
// landed 179 m out. No late exit has been recovered like that, and the arithmetic
// says none could be.
//
// So every bias below pushes the exit EARLY. Being early costs seconds of downwind
// glide; being late costs the DZ.
private _canopyTimeS = ((_openAgl - JUMP_CANOPY_TRANSIENT_M) max 0) / JUMP_CANOPY_DESCENT_MS;
private _downwindRecoveryM = (JUMP_CANOPY_AIRSPEED_MS + _windMs) * _canopyTimeS;
private _upwindRecoveryM = ((JUMP_CANOPY_AIRSPEED_MS - _windMs) max 0) * _canopyTimeS;

private _stickCount = missionNamespace getVariable ["USAFDC_state_jumpStickCount", 0];
if (_stickCount < 1) then {
    _stickCount = (missionNamespace getVariable ["USAFDC_setting_jumpStickCount", 1]) max 1;
};
private _stickIntervalS = missionNamespace getVariable ["USAFDC_setting_jumpStickIntervalS", 1];
private _stickDurationS = (_stickCount - 1) * _stickIntervalS;
private _stickLengthM = _stickDurationS * _groundSpeedMs;

// The FULL stick length, not half. Centring the stick on the ideal exit puts its
// back half LATE, which is the unrecoverable side. Leading by the whole length puts
// the last jumper on the ideal point and everyone ahead of them early.
//
// The early bias covers human exit timing, now the largest single error in the
// system: against a cue calling ~394 m, one run exited 18 m late and another 274 m
// early -- they went on the count rather than the light. The two err in opposite
// directions so there is no lead to compute, but there is every reason to put the
// spread on the recoverable side.
private _trackOffsetM = missionNamespace getVariable ["USAFDC_setting_jumpTrackOffsetM", 0];
private _earlyBiasM = missionNamespace getVariable ["USAFDC_setting_jumpEarlyBiasM", 250];
private _leadM = _trackOffsetM + _stickLengthM + _earlyBiasM;
_exitE = _exitE - (_tE * _leadM);
_exitN = _exitN - (_tN * _leadM);

// ---- where that sits relative to the flown line ------------------------------
// The ideal exit is a POINT; the aircraft flies a LINE on the locked run-in. Unless
// the wind happens to lie along the track the two do not coincide, so the cue fires
// at the point on the line closest to the ideal exit, and the leftover cross-track
// offset is reported rather than hidden -- it is the first call on the jumper's
// recovery budget and the pilot should be able to see it before the light goes green.
private _dE = _exitE - (_acPos # 0);
private _dN = _exitN - (_acPos # 1);
private _alongM = (_dE * _tE) + (_dN * _tN);          // + ahead, - passed
private _offTrackM = (_dE * _tN) - (_dN * _tE);       // + ideal exit is right of track

// ---- can the jumper actually get there ---------------------------------------
// Canopy range is air-relative and starts only after the opening transient, which
// buys almost no forward travel.
private _canopyRangeM = (JUMP_CANOPY_GLIDE * ((_openAgl - JUMP_CANOPY_TRANSIENT_M) max 0))
                        + JUMP_CANOPY_TRANSIENT_TRAVEL_M;
// Cross-track is corrected roughly ACROSS the wind, so its budget is the canopy's
// own airspeed over the available canopy time -- not the along-track JUMP_RECOVERY_M,
// which was measured from upwind/downwind overshoots and had no business being
// applied to a perpendicular error. Deriving it this way also makes the budget scale
// with opening altitude, which is the point: 136 m of cross-track reach from a 259 m
// opening, 432 m from a 600 m one.
private _crossRecoveryM = JUMP_CANOPY_AIRSPEED_MS * _canopyTimeS * JUMP_RECOVERY_MARGIN;
private _requiredM = abs _offTrackM;
// With the whole stick led, the last jumper is on the aim point and the first is a
// stick length early -- the recoverable side -- so the stick no longer worsens the
// worst case the way a centred one did.
private _worstJumperM = _requiredM;
private _achievable = _requiredM <= _crossRecoveryM;

private _warnings = [];
if (!_achievable) then {
    _warnings pushBack format ["EXIT %1 M OFF TRACK", round _requiredM];
};
if (_upwindRecoveryM < 100) then {
    // Any late exit is unrecoverable here, which makes the early bias load-bearing
    // rather than a nicety. Say so where the pilot can see it.
    _warnings pushBack format ["WIND %1 M/S: NO UPWIND RECOVERY", round _windMs];
};
if (_stickLengthM > _downwindRecoveryM) then {
    // Not a refusal -- the middle of the stick is fine and the pilot may well accept
    // a spread. It has to be visible, though, because the cure is a slower run-in or
    // a shorter interval, and neither is guessable from a miss report afterwards.
    _warnings pushBack format ["STICK %1 M > %2 M REACH", round _stickLengthM, round _downwindRecoveryM];
};
if (_openAgl < (JUMP_CANOPY_TRANSIENT_M + 50)) then {
    // Below this the transient has eaten the canopy phase and there is no glide left
    // to correct with. The 233 m opening left only 184 m of range.
    _warnings pushBack format ["OPEN %1 M LEAVES NO GLIDE", round _openAgl];
};
if (_windMs > 15) then {
    _warnings pushBack format ["WIND %1 M/S ABOVE MEASURED RANGE", round _windMs];
};

createHashMapFromArray [
    ["valid", true],
    ["mode", "JUMP"],
    ["exitRangeM", _driftM],
    ["alongM", _alongM],
    ["offTrackM", _offTrackM],
    ["exitPointPosASL", [_exitE, _exitN, _dz # 2]],
    ["freefallTimeS", _freefallS],
    ["exitAglM", _exitAgl],
    ["openAglM", _openAgl],
    ["fallM", _fallM],
    ["canopyRangeM", _canopyRangeM],
    ["stickCount", _stickCount],
    ["stickIntervalS", _stickIntervalS],
    ["stickDurationS", _stickDurationS],
    ["stickLengthM", _stickLengthM],
    ["stickLeadM", _stickLengthM],
    ["earlyBiasM", _earlyBiasM],
    ["canopyTimeS", _canopyTimeS],
    ["downwindRecoveryM", _downwindRecoveryM],
    ["upwindRecoveryM", _upwindRecoveryM],
    ["crossRecoveryM", _crossRecoveryM],
    ["worstJumperM", _worstJumperM],
    ["recoveryM", JUMP_RECOVERY_M],
    ["requiredCorrectionM", _requiredM],
    ["achievable", _achievable],
    ["groundSpeedMs", _groundSpeedMs],
    ["runInDeg", _runInDeg],
    ["windMs", _windMs],
    ["windDirDeg", _windDirDeg],
    ["trackOffsetM", _trackOffsetM],
    ["warnings", _warnings]
]

"""Jump run (HALO/HAHO exit cue) -- v0.6.0.

Two kinds of test here. Most are the project's usual static assertions over SQF
source, pinning decisions that were expensive to establish. A few are plain
arithmetic: they reproduce the exit-range model in Python and check it against the
four flown runs, which is a stronger guarantee than asserting the text of a formula.
"""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from strip_sqf_comments import strip_comments  # noqa: E402


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def code(rel: str) -> str:
    """Source with comments removed, string literals intact.

    Every "must not contain" assertion below reads THIS, not read(). These files
    explain at length why they do not use objectParent player, playSound, or the
    cargo canopy model, so asserting absence against the raw text fails on the
    prose that documents the decision -- which is how the first version of this
    module failed five tests while the code was correct. Comments only: string
    bodies stay, or an absence assertion would pass vacuously.
    """
    return strip_comments(read(rel))


JUMP = "addon/functions/jump/"
SOLUTION = JUMP + "fn_buildJumpSolution.sqf"
CUE = JUMP + "fn_updateJumpCue.sqf"
ARM = JUMP + "fn_armJumpRun.sqf"
DISARM = JUMP + "fn_disarmJumpRun.sqf"
LIGHT = JUMP + "fn_setJumpLight.sqf"
POSTINIT = "addon/functions/fn_postInit.sqf"


# Flown runs: (label, exitAgl, exitDzRange, freefallS, openAgl, windMs, dzMiss)
#
# F is the first run flown on the cue rather than by eye: the light called the exit
# at ~394 m upwind, the jumper left at 376 m, and it landed 7 m from the DZ.
FLOWN = [
    ("A", 3007, 1758, 41.10, 541, 5.14, 1087),
    ("B", 9999, 1685, 149.40, 233, 10.00, 2),
    ("C", 3006, 1844, 44.27, 351, 10.00, 938),
    ("D", 3010, 463, 44.30, 306, 10.00, 72),
    ("E", 3005, 1569, 41.97, 507, 10.00, 596),
    ("F", 3001, 376, 45.39, 259, 10.00, 7),
    ("G", 3003, 668, 40.56, 589, 10.00, 12),
]

FF_TERMINAL = 66
FF_ACCEL = 3
CANOPY_GLIDE = 1.27
TRANSIENT_M = 105
TRANSIENT_TRAVEL_M = 20
RECOVERY_M = 460


class ExitRangeModelTests(unittest.TestCase):
    """The arithmetic, checked against what was actually flown."""

    def test_freefall_time_model_matches_the_flown_durations(self):
        """(exitAgl - openAgl)/66 + 3. Fitted on the two runs with the widest
        altitude spread; the check here is that it holds across all four."""
        for label, exit_agl, _r, ff_s, open_agl, _w, _m in FLOWN:
            predicted = (exit_agl - open_agl) / FF_TERMINAL + FF_ACCEL
            self.assertLess(
                abs(predicted - ff_s), 2.5,
                f"run {label}: predicted {predicted:.2f} s vs flown {ff_s} s",
            )

    def test_freefall_time_error_is_small_against_the_drift_it_feeds(self):
        """The time model only matters through wind drift, so its error should be
        judged in metres, not seconds."""
        for label, exit_agl, _r, ff_s, open_agl, wind, _m in FLOWN:
            predicted = (exit_agl - open_agl) / FF_TERMINAL + FF_ACCEL
            drift_error_m = abs(predicted - ff_s) * wind
            self.assertLess(
                drift_error_m, 25,
                f"run {label}: time error is {drift_error_m:.0f} m of drift",
            )

    def test_the_cue_flown_runs_landed_inside_the_box(self):
        """F and G are the acceptance cases: flown on the light rather than by eye,
        7 m and 12 m from the DZ.

        They also bracket the human term. Against a cue calling ~394 m, F exited 18 m
        late and G 274 m early -- G went on the count rather than the light, which is
        about 2 s at 139 m/s. That +/-275 m of exit timing is now the largest single
        error in the system and it is a person, not a constant. It fits inside the
        +/-549 m tolerance a 600 m opening gives and would NOT fit inside the +/-84 m
        of a 233 m opening, which is what the default opening altitude is for."""
        for label in ("F", "G"):
            run = [r for r in FLOWN if r[0] == label][0]
            _l, _exit_agl, _exit_range, _ff_s, _open_agl, _wind, miss = run
            self.assertLess(miss, 100, f"cue-flown run {label} must land inside a 200 m box")

    def test_exit_timing_variance_fits_the_default_opening_tolerance(self):
        """The reason F and G both worked is the 600 m default, not luck."""
        def tolerance(open_agl):
            return CANOPY_GLIDE * max(0.0, open_agl - TRANSIENT_M) + TRANSIENT_TRAVEL_M - 100

        observed_timing_spread_m = 275
        self.assertGreater(tolerance(600), observed_timing_spread_m)
        self.assertLess(tolerance(233), observed_timing_spread_m)

    def test_the_rule_explains_both_hits_and_both_misses(self):
        """exitRange = wind x freefallTime, with a 460 m recovery budget.

        Near-rule exits must land inside a 200 m box; gross overshoots must miss by
        roughly the excess less the recovery budget. This is the whole model, and it
        is the reason there is no forward-throw term."""
        for label, _a, exit_range, ff_s, _o, wind, miss in FLOWN:
            rule = wind * ff_s
            excess = exit_range - rule
            predicted_miss = max(0.0, excess - RECOVERY_M)
            if excess <= RECOVERY_M:
                self.assertLess(
                    miss, 100,
                    f"run {label}: within budget but missed {miss} m",
                )
            else:
                self.assertLess(
                    abs(predicted_miss - miss), 120,
                    f"run {label}: predicted {predicted_miss:.0f} m, actual {miss} m",
                )

    def test_recovery_budget_is_the_pessimistic_end_of_what_was_measured(self):
        """Three runs overshot far enough for the budget to be read off directly:
        460, 463 and 553 m.

        At n=2 that looked like agreement to 3 m, and the earlier version of this
        test asserted +/-15 m -- which was overfitting two samples. The third run
        widened it to a 93 m spread, which is what a jumper's technique is worth.

        460 stays as the constant deliberately: a BUDGET wants the pessimistic end,
        because using the mean would promise recovery a bad run cannot deliver. So
        the assertion is that the constant is at or below every measurement, not that
        it matches them."""
        implied = [
            (exit_range - wind * ff_s) - miss
            for _l, _a, exit_range, ff_s, _o, wind, miss in FLOWN
            if (exit_range - wind * ff_s) > RECOVERY_M
        ]
        self.assertGreaterEqual(len(implied), 3)
        for value in implied:
            self.assertLessEqual(
                RECOVERY_M, value + 5,
                f"constant {RECOVERY_M} promises more recovery than a run delivered: {value:.0f}",
            )
        # Sanity: not so pessimistic it is useless.
        self.assertGreater(RECOVERY_M, 0.75 * min(implied))

    def test_canopy_range_sets_the_tolerance_not_the_exit_range(self):
        """1.27 x (opening - 105) + 20. The point of pinning this is the conclusion
        it forces: at a 233 m opening there is only +/-84 m of tolerance against a
        200 m box, so the OPENING ALTITUDE decides whether a jump is forgiving."""
        def tolerance(open_agl):
            return CANOPY_GLIDE * max(0.0, open_agl - TRANSIENT_M) + TRANSIENT_TRAVEL_M - 100

        self.assertLess(tolerance(233), 100)
        self.assertGreater(tolerance(300), 150)
        self.assertGreater(tolerance(500), 400)

    def test_a_forward_throw_term_would_have_made_the_good_runs_worse(self):
        """The residual was 520 m at a 208.3 m/s exit and 604 m at 124.8 m/s. A throw
        with any fixed decay scales linearly with exit speed, so it cannot produce
        both. Applying one anyway would have displaced run D's exit far enough to
        push it out of the box it actually landed in."""
        c_resid, c_speed = 520.0, 208.3
        d_resid, d_speed = 604.0, 124.8
        linear_prediction = d_resid * (c_speed / d_speed)
        self.assertGreater(
            abs(linear_prediction - c_resid) / c_resid, 0.4,
            "a linear throw would fit both residuals; the no-throw rationale fails",
        )
        # Run D flew 463 m against a rule of 443 m and missed by 72 m. Subtracting a
        # throw of even the smaller residual moves the exit by far more than the box.
        self.assertGreater(min(c_resid, d_resid), 200)


class RecoveryAsymmetryTests(unittest.TestCase):
    """The exit point sits UPWIND of the DZ, so an exit error has a sign.

    Early means opening upwind and flying DOWNWIND to the DZ, at airspeed plus wind.
    Late means opening downwind and flying UPWIND, at airspeed minus wind. Those are
    not remotely the same journey, and the whole biasing strategy follows from it.
    """

    AIRSPEED = 11.4
    DESCENT = 9.1
    MARGIN = 0.7

    def canopy_time(self, open_agl):
        return max(0.0, open_agl - TRANSIENT_M) / self.DESCENT

    def test_late_exits_are_far_less_recoverable_than_early_ones(self):
        t = self.canopy_time(600)
        for wind, min_ratio in ((5, 2.0), (10, 10.0)):
            early = (self.AIRSPEED + wind) * t
            late = max(0.0, self.AIRSPEED - wind) * t
            self.assertGreater(
                early, late * min_ratio,
                f"at {wind} m/s early recovery {early:.0f} m vs late {late:.0f} m",
            )

    def test_above_canopy_airspeed_there_is_no_upwind_recovery_at_all(self):
        t = self.canopy_time(600)
        self.assertEqual(max(0.0, self.AIRSPEED - 15) * t, 0.0)
        self.assertIn("NO UPWIND RECOVERY", code(SOLUTION))

    def test_run_h_is_consistent_with_the_downwind_budget(self):
        """Run H exited 1964 m early and still landed 179 m out, having covered
        1273 m downwind under canopy plus 596 m of freefall tracking. The downwind
        budget has to be able to account for that; a symmetric 460 m cannot."""
        t = 61.94
        downwind_available = (self.AIRSPEED + 10.0) * t
        self.assertGreater(downwind_available, 1273, "measured canopy travel exceeds the model")
        self.assertGreater(downwind_available, RECOVERY_M * 2, "a flat 460 m cannot explain run H")

    def test_cross_track_budget_scales_with_opening_altitude(self):
        """The old test applied the along-track 460 m to a perpendicular error and
        did not scale with opening altitude, so it was equally permissive at 259 m
        and 600 m -- which is exactly backwards."""
        low = self.AIRSPEED * self.canopy_time(259) * self.MARGIN
        high = self.AIRSPEED * self.canopy_time(600) * self.MARGIN
        self.assertLess(low, 200)
        self.assertGreater(high, 400)
        self.assertGreater(high, low * 2)


class StickLeadTests(unittest.TestCase):
    def test_the_whole_stick_is_led_not_centred(self):
        """Centring the stick on the ideal exit puts its back half LATE, which is the
        unrecoverable side. Leading the full length puts the last jumper on the aim
        point and everyone ahead of them early."""
        text = code(SOLUTION)
        self.assertIn("_leadM = _trackOffsetM + _stickLengthM + _earlyBiasM", text)
        self.assertNotIn("_stickLengthM / 2)", text)
        self.assertIn('["stickLeadM", _stickLengthM]', text)

    def test_early_bias_defaults_to_the_measured_timing_spread(self):
        """Exit timing was measured at 18 m late and 274 m early on two cue-flown
        runs. There is no consistent lead to compute, but the spread should land on
        the recoverable side."""
        post = read(POSTINIT)
        self.assertIn("USAFDC_setting_jumpEarlyBiasM", post)
        self.assertIn('["TLB CARP", "Jump Run"], [0, 800, 250, 0], 1]', post)
        self.assertIn(
            'missionNamespace getVariable ["USAFDC_setting_jumpEarlyBiasM", 250]',
            code(SOLUTION),
        )

    def test_every_bias_moves_the_exit_earlier(self):
        """Signs matter here more than anywhere else in the file: a bias applied the
        wrong way round would move every exit onto the side that cannot be flown
        back from."""
        text = code(SOLUTION)
        self.assertIn("_exitE = _exitE - (_tE * _leadM)", text)
        self.assertIn("_exitN = _exitN - (_tN * _leadM)", text)


class JumpSolutionSourceTests(unittest.TestCase):
    def test_constants_are_pinned_with_their_provenance(self):
        text = read(SOLUTION)
        for token in (
            "#define JUMP_FF_TERMINAL_MS 66",
            "#define JUMP_FF_ACCEL_S 3",
            "#define JUMP_CANOPY_GLIDE 1.27",
            "#define JUMP_CANOPY_TRANSIENT_M 105",
            "#define JUMP_CANOPY_TRANSIENT_TRAVEL_M 20",
            "#define JUMP_RECOVERY_M 460",
            "#define JUMP_CANOPY_AIRSPEED_MS 11.4",
            "#define JUMP_CANOPY_DESCENT_MS 9.1",
            "#define JUMP_RECOVERY_MARGIN 0.7",
        ):
            self.assertIn(token, text)
        # Each constant must carry its sample, the same rule model.json follows.
        # Tokens only -- a wrapped comment line breaks any longer phrase.
        for evidence in ("63.15", "66.41", "1.274", "1.271", "106 m across four runs", "463"):
            self.assertIn(evidence, text)

    def test_jump_solution_does_not_require_cargo(self):
        """fn_buildWorldSolution.sqf:19 hard-exits with NO USAF CARGO on an empty
        aircraft, which is every jump aircraft. Jump mode must not depend on it."""
        text = code(SOLUTION)
        self.assertNotIn("USAFDC_fnc_buildWorldSolution", text)
        self.assertNotIn("USAFDC_fnc_getLoadedCargo", text)
        self.assertNotIn("NO USAF CARGO", text)
        self.assertNotIn("cargoCount", text)

    def test_jump_solution_never_writes_cargo_solver_state(self):
        """USAFDC_state_solution is the live authoritative CARGO state. Writing jump
        geometry into it would make an invalid cargo solver look valid to
        operational logic, which is the one way display problems must not be fixed."""
        for rel in (SOLUTION, CUE, ARM, DISARM, LIGHT):
            text = code(rel)
            self.assertNotIn("USAFDC_state_solution =", text, rel)
            self.assertNotIn("USAFDC_state_displaySolution =", text, rel)
            self.assertNotIn("USAFDC_state_guidanceArmed =", text, rel)

    def test_jump_mode_does_not_touch_the_cargo_canopy_model(self):
        """calibration/model.json and the empirical canopy are protected assets."""
        for rel in (SOLUTION, CUE, ARM, DISARM, LIGHT):
            text = code(rel)
            for forbidden in ("empiricalCanopy", "USAFDC_fnc_getModel", "zeroWorldM", "releaseDelayS"):
                self.assertNotIn(forbidden, text, f"{rel} references {forbidden}")

    def test_no_forward_throw_applied_to_exit_velocity(self):
        """The 0.9x exit velocity is documented but must not be turned into a
        correction. Only the operator-set bias may move the exit along track."""
        text = code(SOLUTION)
        self.assertIn("USAFDC_setting_jumpTrackOffsetM", text)
        self.assertIn("_trackOffsetM", text)
        self.assertNotIn("0.9 *", text)
        self.assertNotIn("* 0.9", text)

    def test_exit_point_is_placed_upwind_by_subtracting_the_drift(self):
        text = read(SOLUTION)
        self.assertIn("_exitE = (_dz # 0) - (_windE * _freefallS)", text)
        self.assertIn("_exitN = (_dz # 1) - (_windN * _freefallS)", text)

    def test_off_track_offset_is_reported_not_hidden(self):
        """The ideal exit is a point and the aircraft flies a line; unless the wind
        lies along the track they do not coincide. That offset is the first call on
        the recovery budget and the pilot has to be able to see it."""
        text = read(SOLUTION)
        self.assertIn("_offTrackM", text)
        self.assertIn('["offTrackM", _offTrackM]', text)
        self.assertIn('["requiredCorrectionM", _requiredM]', text)
        self.assertIn('["achievable", _achievable]', text)

    def test_track_geometry_uses_degrees(self):
        """Arma trig takes degrees. A radians slip here misplaces the exit entirely."""
        text = read(SOLUTION)
        self.assertIn("_tE = sin _runInDeg", text)
        self.assertIn("_tN = cos _runInDeg", text)

    def test_low_opening_altitude_warns(self):
        text = read(SOLUTION)
        self.assertIn("LEAVES NO GLIDE", text)
        self.assertIn("ABOVE MEASURED RANGE", text)


class JumpCueTests(unittest.TestCase):
    def test_the_aircraft_is_latched_not_resolved_per_call(self):
        """FFR's fnc_standUp calls moveOut before teleporting a jumper into its
        hidden dummy, so a standing jumper's objectParent is null and they are on
        foot 2 km away. Resolving the aircraft that way would drop the cue exactly
        when the people who need it are on the ramp."""
        self.assertIn("objectParent player", code(ARM))
        self.assertIn("USAFDC_state_jumpAircraft = _aircraft", code(ARM))
        cue = code(CUE)
        self.assertNotIn("objectParent player", cue)
        self.assertIn("private _aircraft = USAFDC_state_jumpAircraft", cue)

    def test_countdown_latches_once_started(self):
        """Range-to-exit is not monotonic -- the exit point moves with altitude,
        speed and wind -- so without a latch a wobble across the threshold restarts
        the count and the jumpers hear two overlapping countdowns."""
        cue = read(CUE)
        self.assertIn("USAFDC_state_jumpCountdownLatched || {_secondsToExit <= _countdownS}", cue)
        self.assertIn("USAFDC_state_jumpCountdownLatched = true", cue)

    def test_countdown_uses_ceil_so_the_first_tick_is_not_doubled(self):
        cue = read(CUE)
        self.assertIn("(ceil _secondsToExit) + 1", cue)
        self.assertIn("private _remaining = ceil _secondsToExit", cue)
        self.assertIn("if (_remaining < USAFDC_state_jumpLastTickAnnounced)", cue)

    def test_audio_is_broadcast_to_the_crew_not_played_locally(self):
        """CARP's existing sounds are local because only the pilot needs them. This
        is the opposite: the jumpers need to hear it and the pilot runs it."""
        cue = code(CUE)
        self.assertIn('["USAFDC_jumpCue", [_sound], _targets] call CBA_fnc_targetEvent', cue)
        self.assertNotIn("playSound", cue)
        post = read(POSTINIT)
        self.assertIn('["USAFDC_jumpCue", {', post)
        self.assertIn("playSound _sound", post)

    def test_countdown_reaches_jumpers_who_have_stood_up(self):
        """FFR's fnc_standUp calls moveOut, so a standing jumper is NOT in
        crew _aircraft. The countdown only starts 10 s before green, by which time
        every jumper is on the ramp -- so targeting crew alone makes the countdown
        inaudible to exactly the people it exists for, while sounding perfectly
        correct to the pilot. The roster is snapshotted at arm time."""
        cue = code(CUE)
        self.assertIn("USAFDC_state_jumpRoster select {alive _x}", cue)
        self.assertIn("crew USAFDC_state_jumpAircraft", cue)
        self.assertIn("_roster arrayIntersect _roster", cue, "targets must be deduplicated")
        self.assertIn("[_sound], _targets] call CBA_fnc_targetEvent", cue)
        self.assertIn("USAFDC_state_jumpRoster = crew _aircraft", code(ARM))
        self.assertIn("USAFDC_state_jumpRoster = []", code(DISARM))
        self.assertIn("USAFDC_state_jumpRoster = []", read(POSTINIT))

    def test_green_is_refused_when_the_geometry_cannot_be_made_good(self):
        """The cue fires on the ALONG-track projection reaching zero, so without this
        it goes green as the aircraft passes abeam an exit point that may be a
        kilometre to one side. The first flown test did exactly that: green at 1569 m
        against a 420 m rule, 596 m miss. CARP already refuses a cargo pass on a
        geometry that will miss; this is the same position."""
        cue = code(CUE)
        self.assertIn('if (!(_solution get "achievable")', cue)
        self.assertIn('USAFDC_state_jumpPhase = "REFUSED"', cue)
        self.assertIn("NO JUMP", cue)
        self.assertIn("OFF TRACK", cue)
        # A refusal must not be reachable once the light is already green, or a
        # momentary wobble would yank the light back mid-exit.
        self.assertIn('!(USAFDC_state_jumpPhase in ["GREEN", "PASSED"])', cue)
        # The countdown latch is deliberately NOT cleared, so correcting onto the
        # line resumes the count rather than restarting it at ten.
        refusal = cue.split('USAFDC_state_jumpPhase = "REFUSED"')[1].split("};")[0]
        self.assertNotIn("USAFDC_state_jumpCountdownLatched = false", refusal)

    def test_hold_state_says_why_rather_than_freezing_the_readout(self):
        """The invalid-solution exit happens before the readout block, so without its
        own hint a hold looks identical to a stalled system."""
        cue = code(CUE)
        self.assertIn("JUMP HOLD", cue)

    def test_countdown_and_green_use_existing_bis_sounds(self):
        cue = read(CUE)
        for sound in ("FD_Timer_F", "FD_Start_F", "FD_Finish_F"):
            self.assertIn(sound, cue)

    def test_an_invalid_solution_holds_rather_than_disarming(self):
        """A go-around that drops below the opening altitude is still a jump run."""
        cue = read(CUE)
        self.assertIn('USAFDC_state_jumpPhase = "HOLD"', cue)
        self.assertIn("AIRCRAFT LOST", cue)

    def test_readout_is_throttled(self):
        """The cue loop runs at the guidance interval, 20 Hz by default."""
        self.assertIn("(time - USAFDC_state_jumpHintTick) >= 0.25", read(CUE))


class JumpLightTests(unittest.TestCase):
    def test_uses_ffrs_documented_event(self):
        text = read(LIGHT)
        self.assertIn('["ffr_main_setJumplight", [_aircraft, _state]] call CBA_fnc_globalEvent', text)

    def test_checks_for_the_light_object_not_just_the_mod(self):
        """The light object does not exist until someone uses FFR's Prep Ramp action,
        which is itself gated above 200 m. Firing the event before that is a silent
        no-op, so the caller has to be told to fall back to the HUD and audio."""
        text = read(LIGHT)
        self.assertIn('_light = _aircraft getVariable ["ffr_jumplight", objNull]', text)
        self.assertIn("if (isNull _light) exitWith {false}", text)

    def test_ffr_presence_is_resolved_in_postinit_not_latched_false(self):
        """A lazy isNil check against a variable already initialised to false would
        latch false forever and silently kill the light."""
        post = read(POSTINIT)
        self.assertIn(
            'USAFDC_state_jumpFfrLoaded = isClass (configFile >> "CfgPatches" >> "ffr_main")',
            post,
        )

    def test_disarm_turns_the_light_off_not_red(self):
        """Red means stand by, do not jump. An unarmed system must not say that."""
        self.assertIn('[_aircraft, "off"] call USAFDC_fnc_setJumpLight', read(DISARM))


class JumpRegistrationTests(unittest.TestCase):
    def test_every_jump_function_is_in_the_runtime_compile_table(self):
        """config.bin is pre-binarized, so this table is the ONLY way a new function
        reaches the engine. A file that is not listed here silently does not exist."""
        post = read(POSTINIT)
        for name in (
            "buildJumpSolution",
            "setJumpLight",
            "armJumpRun",
            "disarmJumpRun",
            "updateJumpCue",
        ):
            self.assertIn(f'["USAFDC_fnc_{name}", ', post, f"{name} not registered")
            self.assertIn(f"functions\\jump\\fn_{name}.sqf", post)

    def test_state_globals_are_initialised(self):
        post = read(POSTINIT)
        for name in (
            "USAFDC_state_jumpArmed",
            "USAFDC_state_jumpAircraft",
            "USAFDC_state_jumpSolution",
            "USAFDC_state_jumpPfh",
            "USAFDC_state_jumpPhase",
            "USAFDC_state_jumpCountdownLatched",
            "USAFDC_state_jumpLastTickAnnounced",
            "USAFDC_state_jumpGreenUntil",
            "USAFDC_state_jumpHintTick",
            "USAFDC_state_jumpFfrLoaded",
        ):
            self.assertIn(f"{name} = ", post, f"{name} not initialised")

    def test_settings_are_registered(self):
        post = read(POSTINIT)
        for name in (
            "USAFDC_setting_jumpOpenAglM",
            "USAFDC_setting_jumpCountdownS",
            "USAFDC_setting_jumpGreenWindowS",
            "USAFDC_setting_jumpTrackOffsetM",
        ):
            self.assertIn(name, post)
        # The bias defaults to 0.
        self.assertIn(
            '["TLB CARP", "Jump Run"], [-600, 600, 0, 0], 1] call CBA_fnc_addSetting', post
        )

    def test_default_opening_altitude_leaves_usable_tolerance(self):
        """300 m was the first default and it is too tight: 268 m of canopy range
        against a 200 m box is +/-168 m of exit tolerance, and the first flown test
        reported there was no time to reach the DZ. 600 m is also the realistic
        military freefall opening."""
        post = read(POSTINIT)
        self.assertIn('"Jump Run"], [150, 1200, 600, 0], 1]', post)
        tolerance = CANOPY_GLIDE * (600 - TRANSIENT_M) + TRANSIENT_TRAVEL_M - 100
        self.assertGreater(tolerance, 500)

    def test_option_descriptions_describe_the_option(self):
        """Addon Options tooltips are read by people who have never touched this
        system. They must say what the setting does -- not what was measured, which
        runs it came from, or what was tried and rejected."""
        post = read(POSTINIT)
        import re
        descriptions = re.findall(r'"USAFDC_setting_\w+",\s*"\w+",\s*\["[^"]*",\s*"([^"]*)"\]', post)
        self.assertGreaterEqual(len(descriptions), 15, "setting descriptions not parsed")
        # Phrases, not bare words: "run-in" is domain vocabulary, not history.
        banned = (
            "flown", "measured", "tested", "left no margin", "budget is made of",
            "runs did", "1.27", "105 m", "460 m", "+/-", "sd ", " n=",
        )
        for desc in descriptions:
            lowered = desc.lower()
            for token in banned:
                self.assertNotIn(
                    token, lowered,
                    f"tooltip explains project history rather than the option: {desc!r}",
                )

    def test_no_sqfc_sibling_shadows_a_jump_function(self):
        """A compiled sibling shadows the raw .sqf at load. That trap cost this
        project 16 runs of garbage in v0.4.43."""
        for path in (ROOT / "addon/functions/jump").glob("*.sqfc"):
            self.fail(f"stale compiled sibling would shadow the source: {path.name}")


if __name__ == "__main__":
    unittest.main()

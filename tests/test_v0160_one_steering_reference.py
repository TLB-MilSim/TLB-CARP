"""v0.16.0 -- the needle and the aircraft now fly the same reference, and the AP is instrumented.

WHERE THIS CAME FROM

The pilot reported "AP feels really jittery and off. It's even more pronounced on a
server." Six independent readers were run over the AP chain -- the controller, the
actuation rate limit, the path manager, the loop rates, server locality and the vertical
channel -- raising 38 candidate mechanisms between them. Three adversarial refuters were
run per candidate, each told to default to refuted.

ALL 38 WERE REFUTED. Not one offered a magnitude, and several rested on misread arithmetic
that the refutations worked out properly. That is a real result and it is recorded as one:
this release does NOT claim to have found the cause of the jitter.

WHAT IT DID FIND, THROUGH CONVERGENCE RATHER THAN SURVIVAL

Three of the six readers independently observed the same structural fact, and it checks out
directly:

    fn_updateGuidance:68-80   rate-limits the raw path track into
                              USAFDC_state_smoothedDesiredTrackDeg and writes it to the
                              solution as "desiredTrackDeg"    <- the flight director
    fn_updateAutopilot:113    reads "pathDesiredTrackDeg"      <- the RAW key, never
                              overwritten, straight out of the path manager

The needle and the aircraft were following two different steering references. That is
indefensible however small the difference happens to be on any given tick, and it is the
literal reading of "the AP feels off".

It is also plausible as a jitter source, and deliberately not claimed as one: the raw
bearing is pure-pursuit, recomputed from the aircraft's OWN live position every tick, so it
carries the aircraft's motion back into its own command. Rate-limiting the TARGET is a
different thing from rate-limiting the NOSE, and the AP only ever did the second.

WHY THE SMOOTHING RATE HAD TO MOVE WITH IT

The smoother was a flat 4 deg/s, which was right while only the display read it. The AP's
own schedule allows 6 during INTERCEPT, so handing it a 4 deg/s-limited target would have
turned a display filter into a silent cap on intercept authority -- a behaviour regression
introduced by a correctness fix, which is the worst kind.

So the smoother now uses the AP's schedule. No new constant is introduced and the AP
remains the single authority on slew rate. These tests pin the two lists identical, because
two copies of a schedule is exactly how they drift.

WHAT IS STILL UNKNOWN

Whether any of this is the jitter. The instrumentation added here is the point: twice a
second while the AP is armed it logs the raw track, the commanded track, the nose, the
slew step against its limit, dt and fps. One flight turns "feels jittery" into numbers --
specifically whether the step is saturated continuously (a target moving faster than the
follower can track) or whether dt is not what it is supposed to be.
"""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.exists() else ""


def code(rel: str) -> str:
    """Comments stripped, string literals intact."""
    sys.path.insert(0, str(ROOT / "tools"))
    from strip_sqf_comments import strip_comments

    path = ROOT / rel
    return strip_comments(path.read_text(encoding="utf-8")) if path.exists() else ""


GUIDANCE = "addon/functions/guidance/fn_updateGuidance.sqf"
AP = "addon/functions/autopilot/fn_updateAutopilot.sqf"
PATH = "addon/functions/path/fn_buildPathSolution.sqf"
POSTINIT = "addon/functions/fn_postInit.sqf"


def turn_rates(src: str) -> list[tuple[str, str]]:
    """The per-state turn-rate schedule, as (state, rate) in source order.

    Fed from read(), not code(): this module's code() strips string LITERALS as well as
    comments, and the state names ARE string literals -- `case "INTERCEPT"` comes back as
    `case "         "` and the schedule reads as empty.
    """
    block = src[src.index("_turnRateDegS = switch"):]
    # NOT the first "};" -- that is the end of `case "INTERCEPT": {6};`, which cuts the
    # block after one entry and before its closing brace, so the regex matches NOTHING.
    # The switch itself closes with "};" at column zero.
    block = block[:block.index(chr(10) + "};")]
    found = re.findall(r'case "([A-Z ]+)":\s*\{([0-9.]+)\}', block)
    # An empty schedule made "both schedules are identical" pass by matching [] to [],
    # which is a test that cannot fail and therefore protects nothing. Refuse it.
    assert found, "no turn-rate schedule parsed -- the helper is broken, not the code"
    return found


class OneReferenceTests(unittest.TestCase):
    def test_the_autopilot_and_the_needle_read_the_same_key(self):
        """THE DEFECT. fn_updateAutopilot read pathDesiredTrackDeg -- the raw bearing --
        while the flight director read the smoothed desiredTrackDeg."""
        guid = code(GUIDANCE)
        self.assertIn('_solution set ["desiredTrackDeg", USAFDC_state_smoothedDesiredTrackDeg];', guid)
        self.assertIn('_solution set ["pathDesiredTrackDeg", USAFDC_state_smoothedDesiredTrackDeg];', guid)

    def test_the_raw_value_is_overwritten_not_read_differently_downstream(self):
        """Leaving the raw key in place and teaching one more consumer to prefer another
        is how a THIRD reference appears later. There is one key anything can reach."""
        guid = code(GUIDANCE)
        smoothed = guid.index('_solution set ["pathDesiredTrackDeg", USAFDC_state_smoothedDesiredTrackDeg];')
        ap_call = guid.index("USAFDC_fnc_updateAutopilot")
        self.assertLess(smoothed, ap_call, "the overwrite must happen before the AP is called")

    def test_the_raw_value_is_kept_for_the_instrument_only(self):
        """It is the thing the log needs in order to show how noisy the commanded track
        is. Keeping it under its own name is not the same as steering by it."""
        self.assertIn('_solution set ["rawDesiredTrackDeg", _rawDesired];', code(GUIDANCE))
        self.assertIn('getOrDefault ["rawDesiredTrackDeg", -1]', code(AP))

    def test_the_path_manager_still_publishes_the_raw_bearing(self):
        """The overwrite happens in the guidance loop, downstream. The path manager is not
        the place to smooth -- it has no dt and no notion of the AP's state schedule."""
        self.assertIn('["pathDesiredTrackDeg", _pathDesiredTrackDeg]', code(PATH))


class ScheduleAgreementTests(unittest.TestCase):
    def test_both_schedules_are_identical(self):
        """Two copies of a schedule is how they drift. If the AP's turn rates are retuned
        and the smoother's are not, the smoother silently becomes the binding constraint
        again -- which is the regression this whole change exists to avoid."""
        self.assertEqual(turn_rates(read(AP)), turn_rates(read(GUIDANCE)))

    def test_the_schedule_is_the_approved_one(self):
        """Pinned so a change to either copy is a deliberate act, not a side effect."""
        self.assertEqual(
            turn_rates(read(AP)),
            [("INTERCEPT", "6"), ("CAPTURE FINAL", "4"), ("FINAL RUN", "2.5"),
             ("RELEASE STABLE", "2.0"), ("POST DROP", "2.0")],
        )

    def test_the_smoother_can_never_bind_against_the_autopilot(self):
        """A flat 4 would have capped INTERCEPT, where the AP is allowed 6 -- a display
        filter quietly limiting how fast the aircraft may intercept."""
        guid = code(GUIDANCE)
        self.assertIn("private _maxStep = _turnRateDegS * _dt;", guid)
        self.assertNotIn("private _maxStep = 4 * _dt;", guid)

    def test_the_smoother_reads_the_path_state_it_is_smoothing_for(self):
        guid = code(GUIDANCE)
        self.assertIn('_solution getOrDefault ["pathState", ""]', guid)

    def test_the_autopilot_keeps_its_own_limiter(self):
        """The smoother limits how fast the TARGET moves; the AP limits how fast the NOSE
        moves toward it. Removing the second because the first exists would hand the
        aircraft straight to a step change in the reference."""
        src = code(AP)
        self.assertIn("private _maxHeadingStep = _turnRateDegS * _dt;", src)
        self.assertIn("_headingStep = (_headingError max (-_maxHeadingStep)) min _maxHeadingStep;", src)


class InstrumentTests(unittest.TestCase):
    def test_the_autopilot_logs_what_it_is_chasing_and_what_it_achieved(self):
        """38 candidate mechanisms were refuted for want of a magnitude. This is the
        magnitude."""
        src = code(AP)
        self.assertIn("[TLB CARP][AP TRACK]", src)
        for field in ["raw=", "des=", "dir=", "err=", "step=", "lim=", "dt=", "fps="]:
            self.assertIn(field, src, field)

    def test_saturation_is_readable_from_one_line(self):
        """step against lim is the whole question: a follower pinned at its limit for a
        whole run-in means the target is moving faster than it can track."""
        src = code(AP)
        line = src[src.index("[TLB CARP][AP TRACK]"):]
        line = line[:line.index("];")]
        self.assertIn("_headingStep", line)
        self.assertIn("_maxHeadingStep", line)

    def test_the_log_is_rate_limited(self):
        """The AP actuates at 20 Hz. Logging every actuation would be 1200 lines a minute
        and would itself cost frame time in the function under investigation."""
        src = code(AP)
        self.assertIn('USAFDC_state_apTrackLogTick', src)
        self.assertIn(">= 0.5", src)

    def test_the_tick_is_initialised(self):
        """An unset tick reads nil and `nil >= 0.5` throws -- inside the AP, every frame."""
        self.assertIn("USAFDC_state_apTrackLogTick = -1e9;", read(POSTINIT))

    def test_the_instrument_does_not_write_aircraft_state(self):
        """CLAUDE.md: do not add a per-frame transform write anywhere. A diagnostic that
        changes what it measures is worse than none."""
        src = code(AP)
        block = src[src.index("[TLB CARP][AP TRACK]"):]
        block = block[:block.index("];")]
        for forbidden in ["setVelocity", "setDir", "setPos", "setAirplaneThrottle"]:
            self.assertNotIn(forbidden, block)


if __name__ == "__main__":
    unittest.main(verbosity=2)

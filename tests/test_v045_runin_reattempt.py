"""v0.4.5: a missed run-in permanently refused every later attempt.

Reported in-engine: three consecutive drops all refused with UNSTABLE RUN-IN,
debug snapshot showing crossTrackM = -45.6 while signedRpM = -784 (i.e. the
aircraft was already 784 m PAST the release point and departing the line).

Two independent pre-existing defects combined:

1. `_insideFinal = _signedRpM <= 800` had no lower bound, so the release gate
   kept judging the aircraft for the entire egress and go-around. Cross-track
   naturally grows once the pass is over, so the HUD sat on NO DROP forever.
2. `USAFDC_state_passMissed` was only cleared by arming/disarming guidance --
   not by re-locking the run-in, changing the DZ, or repositioning upstream --
   so every subsequent RP crossing was force-failed regardless of how it was
   flown. Note `USAFDC_state_dropLatched`, the analogous per-attempt latch, is
   cleared in eleven places including lockRunIn/unlockRunIn/setDZ/clearDZ.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


class FinalEnvelopeBoundsTests(unittest.TestCase):
    def test_final_envelope_is_bounded_below_so_the_gate_stops_after_the_pass(self):
        text = read("addon/functions/guidance/fn_buildWorldSolution.sqf")
        self.assertIn("_signedRpM <= 800", text)
        self.assertIn("_signedRpM > -250", text)

    def test_failing_gate_term_is_named_in_the_warnings(self):
        """The pilot saw only UNSTABLE RUN-IN with no indication of which
        tolerance failed, so there was nothing to correct."""
        text = read("addon/functions/guidance/fn_buildWorldSolution.sqf")
        self.assertIn("CROSS TRACK", text)
        self.assertIn("TRACK ERROR", text)
        self.assertIn("PRE-CHUTE LATERAL DRIFT", text)


class PassMissedLifecycleTests(unittest.TestCase):
    def test_pass_missed_clears_on_a_new_attempt_setup(self):
        for rel in [
            "addon/functions/guidance/fn_lockRunIn.sqf",
            "addon/functions/guidance/fn_unlockRunIn.sqf",
            "addon/functions/dz/fn_setDZ.sqf",
            "addon/functions/dz/fn_clearDZ.sqf",
        ]:
            self.assertIn(
                "USAFDC_state_passMissed = false", read(rel),
                f"{rel} resets dropLatched but leaves passMissed latched",
            )

    def test_pass_missed_clears_when_repositioned_upstream_for_a_go_around(self):
        """A pilot who goes around without touching the panel must get a fresh
        judgement, otherwise GO AROUND is advice that cannot be acted on."""
        text = read("addon/functions/guidance/fn_updateGuidance.sqf")
        self.assertIn("USAFDC_state_passMissed && {_current > 800}", text)
        self.assertIn("USAFDC_state_passMissed = false", text)
        # The clear must precede the check that forces UNSTABLE RUN-IN.
        clear = text.index("USAFDC_state_passMissed && {_current > 800}")
        force = text.index("USAFDC_state_passMissed && {_current <= 0}")
        self.assertLess(clear, force)

    def test_missed_pass_is_logged_with_the_terms_that_failed(self):
        """There was no log at all for a failed crossing, only for a good one,
        so a refusal left no evidence behind."""
        text = read("addon/functions/guidance/fn_updateGuidance.sqf")
        self.assertIn("[TLB CARP][NO DROP]", text)
        for term in ["crossTrack", "trackError", "preChuteDrift"]:
            self.assertIn(term, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)

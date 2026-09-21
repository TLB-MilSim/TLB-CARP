"""v0.16.7 -- the forward throw finally knows how fast the aircraft was going.

THE QUESTION THAT FOUND IT, asked after a 94 m miss: "there's no difference between flying
a C17, C130 or V44 Blackfish, the drop should be the same for all -- why are we missing so
much? Did we not use the tests we conducted as a matrix for all the drops?"

Right on both counts. The matrix was real, and its axes were HEADING and WIND. Every one of
the original 140 bench runs flew at about 500 km/h, and `zeroWorldM` -- the zero-wind canopy
displacement -- was applied unchanged at every airspeed thereafter. The model had no way to
know how fast you were going.

MEASURED 2026-09-21. 8 headings x 4 speeds at 3000 m, verified zero wind on all four
batches, 32 runs, 0 degraded:

    350 km/h   along bias -40.03 m  (sem 4.90)     500 km/h   along bias  +4.08 m  (sem 1.91)
    425 km/h   along bias -18.04 m  (sem 3.70)     600 km/h   along bias +24.08 m  (sem 1.32)

Cross-track bias stayed inside 2.2 m at every speed, which is the signature of a forward-
throw term rather than a heading or wind effect.

AND A NEGATIVE RESULT WORTH AS MUCH AS THE POSITIVE ONE

A fifth batch at 1500 m / 500 km/h gave +2.61 m against +4.08 m at 3000 m. Halving the drop
altitude moved the answer by 1.5 m. DROP ALTITUDE IS NOT AN AXIS -- the freefall solver
already handles it correctly, and the two flown misses that started this were not about
altitude either.

THE FORM IS DERIVED, NOT FITTED

A body decelerating under quadratic drag covers a distance proportional to ln(v0/vt). Tested
against a power law and a straight line on the same four points:

    log (drag)   RMS 0.96 m   chi 0.45      <- inside the measurement error
    power        RMS 2.13 m   chi 1.09
    linear       RMS 2.33 m   chi 1.29

Only the two constants are fitted. That the physically-derived form wins on data it was not
constructed from is the reason this is trusted outside the four sampled speeds -- but only
gently, and the model says where it stops being measured.

WHAT IT DOES NOT TOUCH

The wind correction. That is drift, and drift scales with canopy DURATION, not with entry
speed. Scaling it would have been fitting one error with another -- and the flown drops show
the wind term still has an error of its own, which this deliberately leaves visible instead
of letting two mistakes cancel.
"""
from pathlib import Path
import json
import math
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from empirical_reference import solve_empirical_canopy  # noqa: E402


def read(rel: str) -> str:
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.exists() else ""


def code(rel: str) -> str:
    sys.path.insert(0, str(ROOT / "tools"))
    from strip_sqf_comments import strip_comments

    path = ROOT / rel
    return strip_comments(path.read_text(encoding="utf-8")) if path.exists() else ""


CANOPY = "addon/functions/solver/fn_empiricalCanopyC17.sqf"
SOLVER = "addon/functions/solver/fn_solveRelative.sqf"
MODEL = json.loads(read("calibration/model.json"))

# The five flown batches, as (label, speed km/h, measured along-track bias).
MEASURED = [(350, -40.03), (425, -18.04), (500, 4.08), (600, 24.08)]


class ConstantsTests(unittest.TestCase):
    def test_both_canopy_tables_carry_the_constants(self):
        for name in ["empiricalC17", "empiricalC130"]:
            t = MODEL["canopy"][name]
            self.assertAlmostEqual(t["throwRefSpeedMs"], 138.89, places=2, msg=name)
            self.assertAlmostEqual(t["throwTerminalMs"], 21.9, places=2, msg=name)

    def test_the_reference_speed_is_the_speed_the_baseline_was_measured_at(self):
        """138.89 m/s is 500 km/h. If this drifts from the speed zeroWorldM was flown at,
        the scale silently biases every drop including the calibrated one."""
        self.assertAlmostEqual(MODEL["canopy"]["empiricalC17"]["throwRefSpeedMs"] * 3.6,
                               500.0, places=1)

    def test_the_c130_shares_them_and_says_why(self):
        """The throw is a property of the load and its canopy, not of the aircraft -- which
        is the whole point the question raised. The C-130's baseline is already a shifted
        C-17 baseline, so a separate constant would be inventing a difference."""
        src = MODEL["canopy"]["empiricalC130"]["throwScaleSource"]
        self.assertIn("property of the LOAD", src)
        self.assertIn("Not separately measured", src)

    def test_the_provenance_records_the_measurement(self):
        src = MODEL["canopy"]["empiricalC17"]["throwScaleSource"]
        for token in ["-40.03", "-18.04", "+4.08", "+24.08", "0 degraded",
                      "ALTITUDE IS NOT AN AXIS", "DERIVED, NOT FITTED",
                      "UNMEASURED OUTSIDE 350-600"]:
            self.assertIn(token, src, token)


class ScaleTests(unittest.TestCase):
    def test_the_calibrated_speed_scales_by_exactly_one(self):
        """The whole point: a change that moves the validated operating point is a
        regression wearing a fix's clothes."""
        emp = MODEL["canopy"]["empiricalC17"]
        r = solve_empirical_canopy(45, [0, 0, 0], emp, 138.89)
        self.assertAlmostEqual(r["throwScale"], 1.0, places=6)

    def test_slower_throws_shorter_and_faster_throws_further(self):
        emp = MODEL["canopy"]["empiricalC17"]
        slow = solve_empirical_canopy(45, [0, 0, 0], emp, 97.22)["throwScale"]
        fast = solve_empirical_canopy(45, [0, 0, 0], emp, 166.67)["throwScale"]
        self.assertLess(slow, 1.0)
        self.assertGreater(fast, 1.0)
        self.assertAlmostEqual(slow, 0.8069, places=3)
        self.assertAlmostEqual(fast, 1.0987, places=3)

    def test_it_reproduces_every_measured_bias(self):
        """The fit, checked against the numbers it was fitted to -- which is only worth
        anything because the FORM came from physics rather than from these points."""
        emp = MODEL["canopy"]["empiricalC17"]
        for kmh, measured in MEASURED:
            v = kmh / 3.6
            # along-component of the baseline at heading 0 is its y term
            base = solve_empirical_canopy(0, [0, 0, 0], emp)["baselineWorld"]
            scale = solve_empirical_canopy(0, [0, 0, 0], emp, v)["throwScale"]
            predicted = (base[1] * scale) - base[1]
            self.assertLess(abs(predicted - measured), 8.0,
                            f"{kmh} km/h: predicted {predicted:.1f} vs measured {measured:.1f}")

    def test_an_unknown_speed_changes_nothing(self):
        """Callers that do not supply a speed, and any model without the constants, must
        behave exactly as they did before this existed."""
        emp = MODEL["canopy"]["empiricalC17"]
        self.assertAlmostEqual(solve_empirical_canopy(45, [0, 0, 0], emp)["throwScale"], 1.0)
        self.assertAlmostEqual(solve_empirical_canopy(45, [0, 0, 0], emp, -1)["throwScale"], 1.0)
        stripped = {k: v for k, v in emp.items() if not k.startswith("throw")}
        self.assertAlmostEqual(
            solve_empirical_canopy(45, [0, 0, 0], stripped, 97.22)["throwScale"], 1.0)

    def test_a_speed_at_or_below_terminal_is_refused(self):
        """ln of a ratio at or below one goes non-positive and would invert the throw."""
        emp = MODEL["canopy"]["empiricalC17"]
        for v in (0.0, 5.0, 21.9):
            self.assertAlmostEqual(
                solve_empirical_canopy(45, [0, 0, 0], emp, v)["throwScale"], 1.0, msg=str(v))


class WindIsUntouchedTests(unittest.TestCase):
    def test_the_wind_correction_does_not_scale_with_entry_speed(self):
        """Drift scales with canopy DURATION. Scaling it here would fit one error with
        another, and the flown drops show the wind term still has an error of its own."""
        emp = MODEL["canopy"]["empiricalC17"]
        slow = solve_empirical_canopy(45, [0, -5, 0], emp, 97.22)["windCorrectionWorld"]
        fast = solve_empirical_canopy(45, [0, -5, 0], emp, 166.67)["windCorrectionWorld"]
        self.assertAlmostEqual(slow[0], fast[0], places=6)
        self.assertAlmostEqual(slow[1], fast[1], places=6)

    def test_only_the_baseline_is_multiplied_in_the_sqf(self):
        src = code(CANOPY)
        self.assertIn("_baselineWorld = [(_baselineWorld # 0) * _throwScale, (_baselineWorld # 1) * _throwScale];", src)
        self.assertNotIn("_windCorrectionWorld # 0) * _throwScale", src)


class WiringTests(unittest.TestCase):
    def test_the_canopy_function_takes_an_entry_speed(self):
        # v0.16.9 appended _freefallS for the canopy-duration altitude term. The entry
        # speed parameter and its position are unchanged.
        self.assertIn('params ["_headingDeg", "_windVectorWorld", "_model", ["_entrySpeedMs", -1], ["_freefallS", -1]];',
                      code(CANOPY))

    def test_the_solver_passes_the_release_along_speed(self):
        """The load enters the canopy phase at essentially its release ground speed -- a
        flown release at 97.27 m/s along reached the canopy at 97.3."""
        # v0.16.9 appended the freefall time after it; the speed argument is unmoved.
        self.assertIn('_canopyRoot get _canopyRef, _velocityAlongMs, _ballistic get "attachTimeS"] call USAFDC_fnc_empiricalCanopyC17;',
                      code(SOLVER))

    def test_the_ratio_of_logs_makes_the_log_base_irrelevant(self):
        """SQF's `log` is base 10 and Python's math.log is natural. Both sides take a RATIO
        of two logs, so the base cancels and the two implementations agree exactly. Pinned
        because someone will one day 'fix' one of them to match the other."""
        src = code(CANOPY)
        self.assertIn("(log (_entrySpeedMs / _throwTerminalMs)) / (log (_throwRefMs / _throwTerminalMs))", src)
        emp = MODEL["canopy"]["empiricalC17"]
        for v in (97.22, 118.06, 138.89, 166.67):
            py = math.log(v / 21.9) / math.log(138.89 / 21.9)
            log10 = math.log10(v / 21.9) / math.log10(138.89 / 21.9)
            self.assertAlmostEqual(py, log10, places=12)
            self.assertAlmostEqual(solve_empirical_canopy(0, [0, 0, 0], emp, v)["throwScale"],
                                   py, places=9)

    def test_the_scale_is_exported_for_the_record(self):
        """So a flown CAL record says which scale was applied, rather than leaving the next
        investigation to infer it from the speed."""
        self.assertIn('["throwScale", _throwScale],', code(CANOPY))


if __name__ == "__main__":
    unittest.main(verbosity=2)

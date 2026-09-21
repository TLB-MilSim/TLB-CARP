"""v0.16.9 -- canopy duration depends on how high you dropped from.

`zeroTimeS` is a canopy duration measured at ONE drop altitude. Every one of the original
runs had a freefall of 23.26 +/- 0.41 s -- about 3000 m -- and that single duration was
applied at every altitude since.

THE MECHANISM, WHICH THE FLOWN TRANSIENTS SHOW DIRECTLY

From 3000 m the load reaches the chute at about -230 m/s and PLUNGES during inflation,
spending most of the 300 m fast. From 1500 m it arrives at -153 m/s, does not plunge as far,
and has far more altitude left to spend at the canopy's ~4.3 m/s terminal:

    300 m -> 182 m in three seconds, then 182 m at 4.3 m/s for another forty-two.

MEASURED. 8 headings x 4 drop altitudes (freefall 11.91 / 15.59 / 19.54 / 23.24 s), verified
zero wind on all four batches, 32 runs, 0 degraded. Mean duration error 4.43 -> 2.08 s.

PER-HEADING, because every other axis in this table is, and because it had to be: a single
global slope fitted headings 0/45/90/135 beautifully (-0.851, RMS 0.56 s) and made 180, 225
and 270 WORSE. Those three do not track the altitude trend the other five do, which is the
same unexplained heading dependence this dataset has carried from the beginning.

THE 315 SLOPE EXCLUDES ONE RUN. Its 1900 m reading of 23.34 s sits more than three standard
deviations from every neighbour, and fitting it gave -1.203 against -0.96 and -0.74 either
side. That is fitting scatter, which this model's own methodology already refuses. Refitted
on the other three: -0.978.

SCOPE, AND IT IS NARROW ON PURPOSE

predictedCanopyTimeS reaches the TOT countdown and the calibration record. It does NOT reach
the release point -- the canopy displacement is a stored vector, not a time multiplied by
anything -- so no drop geometry moves.

WHAT WAS DELIBERATELY NOT DONE

Scaling the wind correction by the corrected duration. Drift is wind times time, so that is
physically the right idea, and it was tested against the three flown drops before shipping:

    canopy-phase error   27.2 -> 39.8 m      19.0 -> 39.0 m      113.6 -> 105.4 m

Two of three WORSE. The model over-corrects wind on some drops and under-corrects on others,
and duration does not resolve that. The measurement said no, so it was not shipped.

STILL UNEXPLAINED: a flown C-130 canopy lasts about 9 s longer than the bench C-17 at the
same drop altitude and the same entry vertical speed.
"""
from pathlib import Path
import json
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
EMP = MODEL["canopy"]["empiricalC17"]
REF = 23.24


class ConstantsTests(unittest.TestCase):
    def test_both_tables_carry_the_slope_and_the_anchor(self):
        for name in ["empiricalC17", "empiricalC130"]:
            t = MODEL["canopy"][name]
            self.assertAlmostEqual(t["canopyTimeRefFreefallS"], REF, places=2, msg=name)
            self.assertEqual(len(t["canopyTimeSlopeS"]), len(t["headingAnchorsDeg"]), name)

    def test_the_anchor_is_the_freefall_zerotimes_was_measured_at(self):
        """If this drifts from the altitude zeroTimeS came from, the term biases every drop
        including the one condition that was already right."""
        self.assertAlmostEqual(EMP["canopyTimeRefFreefallS"], 23.24, places=2)

    def test_every_slope_is_negative(self):
        """Lower drop, longer canopy. A positive slope anywhere means the sign convention
        was inverted somewhere between the fit and the file."""
        for s in EMP["canopyTimeSlopeS"]:
            self.assertLess(s, 0)

    def test_the_315_slope_is_the_refit_not_the_outlier_fit(self):
        """Fitting the 1900 m run gave -1.203 against -0.96 and -0.74 either side. That is
        scatter, and model.json's own methodology refuses to fit it."""
        self.assertAlmostEqual(EMP["canopyTimeSlopeS"][7], -0.978, places=3)

    def test_the_provenance_records_what_was_refused(self):
        src = EMP["canopyTimeSlopeSource"]
        for token in ["0 degraded", "4.43 -> 2.08", "does not reach the "
                      "release point", "WORSE", "STILL UNEXPLAINED", "EXCLUDES"]:
            self.assertIn(token, src, token)


class BehaviourTests(unittest.TestCase):
    def test_the_measured_altitude_changes_nothing(self):
        """The condition zeroTimeS was measured at must come back exactly as measured."""
        for h in [0, 45, 90, 135, 180, 225, 270, 315]:
            a = solve_empirical_canopy(h, [0, 0, 0], EMP)["predictedCanopyTimeS"]
            b = solve_empirical_canopy(h, [0, 0, 0], EMP, -1, REF)["predictedCanopyTimeS"]
            self.assertAlmostEqual(a, b, places=6, msg=str(h))

    def test_a_lower_drop_gives_a_longer_canopy(self):
        lo = solve_empirical_canopy(45, [0, 0, 0], EMP, -1, 15.59)["predictedCanopyTimeS"]
        hi = solve_empirical_canopy(45, [0, 0, 0], EMP, -1, 23.24)["predictedCanopyTimeS"]
        self.assertGreater(lo, hi)
        # 15.59 s of freefall is about 1200 m; measured 34.91 s at heading 45.
        self.assertLess(abs(lo - 34.91), 2.0, f"predicted {lo:.2f} vs measured 34.91")

    def test_an_unknown_freefall_changes_nothing(self):
        """Any caller that does not supply it, and any model without the constants, must
        behave exactly as before."""
        base = solve_empirical_canopy(45, [0, 0, 0], EMP)["predictedCanopyTimeS"]
        self.assertAlmostEqual(solve_empirical_canopy(45, [0, 0, 0], EMP, -1, -1)["predictedCanopyTimeS"], base)
        stripped = {k: v for k, v in EMP.items() if not k.startswith("canopyTime")}
        self.assertAlmostEqual(
            solve_empirical_canopy(45, [0, 0, 0], stripped, -1, 15.59)["predictedCanopyTimeS"], base)

    def test_the_duration_can_never_go_non_positive(self):
        """An absurd freefall time must not produce a zero or negative canopy, which would
        divide by zero in the TOT estimate."""
        for ff in (1.0, 200.0):
            self.assertGreater(
                solve_empirical_canopy(45, [0, 0, 0], EMP, -1, ff)["predictedCanopyTimeS"], 0)


class ScopeTests(unittest.TestCase):
    def test_the_canopy_displacement_is_untouched(self):
        """THE WHOLE SAFETY ARGUMENT. Duration feeds the TOT countdown; the RP is built from
        the displacement vector. If this term moved the displacement it would be a
        calibration change to drop geometry rather than to a readout."""
        for ff in (11.91, 15.59, 23.24):
            a = solve_empirical_canopy(45, [0, -5, 0], EMP, -1, REF)["canopyWorld"]
            b = solve_empirical_canopy(45, [0, -5, 0], EMP, -1, ff)["canopyWorld"]
            self.assertAlmostEqual(a[0], b[0], places=9)
            self.assertAlmostEqual(a[1], b[1], places=9)

    def test_the_wind_correction_is_not_scaled_by_duration(self):
        """Tested against three flown drops and REFUSED: two of three got worse."""
        for ff in (11.91, 23.24):
            a = solve_empirical_canopy(45, [0, -5, 0], EMP, -1, REF)["windCorrectionWorld"]
            b = solve_empirical_canopy(45, [0, -5, 0], EMP, -1, ff)["windCorrectionWorld"]
            self.assertAlmostEqual(a[0], b[0], places=9)
            self.assertAlmostEqual(a[1], b[1], places=9)

    def test_nothing_ballistic_reads_the_canopy_time(self):
        """Checked rather than assumed: only the package-timing estimate and the debug
        records consume it."""
        allowed = {
            # produces it
            "fn_empiricalCanopyC17.sqf", "fn_solveRelative.sqf",
            # the TOT countdown and the package tracker -- the intended consumers
            "fn_estimatePackageTiming.sqf", "fn_updatePackageTiming.sqf",
            # records and self-test
            "fn_beginCalibrationRun.sqf", "fn_debugSnapshot.sqf", "fn_formatCalibrationRun.sqf",
            "fn_runSolverSelfTest.sqf", "fn_getTestVectors.sqf",
            # the generated model, which carries this term's provenance note
            "fn_getModel.sqf",
        }
        # Walked rather than shelled out to grep: the repository path contains a space, and
        # splitting grep's output on whitespace turns "E:\CARP MOD" into two paths.
        for f in (ROOT / "addon" / "functions").rglob("*.sqf"):
            if "predictedCanopyTimeS" in f.read_text(encoding="utf-8", errors="replace"):
                self.assertIn(f.name, allowed, f"new consumer of canopy time: {f}")


class WiringTests(unittest.TestCase):
    def test_the_canopy_function_takes_the_freefall_time(self):
        self.assertIn('params ["_headingDeg", "_windVectorWorld", "_model", ["_entrySpeedMs", -1], ["_freefallS", -1]];',
                      code(CANOPY))

    def test_the_solver_passes_the_ballistic_attach_time(self):
        """The same number the freefall along-track distance is built from, so the two can
        never disagree about how long the load fell."""
        self.assertIn('_velocityAlongMs, _ballistic get "attachTimeS"] call TLB_CARP_fnc_empiricalCanopyC17;',
                      code(SOLVER))

    def test_the_slope_is_interpolated_per_heading(self):
        self.assertIn("private _slope = ([_heading, _headingAnchors, _timeSlopes] call _interpScalar) # 0;",
                      code(CANOPY))

    def test_the_guard_requires_a_complete_table(self):
        """A slope array of the wrong length would silently interpolate against the wrong
        anchors rather than failing."""
        self.assertIn("(count _timeSlopes) isEqualTo (count _headingAnchors)", code(CANOPY))


if __name__ == "__main__":
    unittest.main(verbosity=2)

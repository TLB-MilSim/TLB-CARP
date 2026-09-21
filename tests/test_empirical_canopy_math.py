from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
from tests.empirical_reference import solve_empirical_canopy


class EmpiricalCanopyMathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        model = json.loads((ROOT / "calibration/model.json").read_text(encoding="utf-8"))
        cls.emp = model["canopy"]["empiricalC17"]

    def assert_vec_close(self, actual, expected, tol=1e-4):
        self.assertEqual(len(actual), len(expected))
        for a, e in zip(actual, expected):
            self.assertAlmostEqual(a, e, delta=tol)

    def solve(self, heading, wind):
        return solve_empirical_canopy(heading, wind, self.emp)

    def anchor(self, deg):
        """zeroWindDrift entry for an exact heading anchor."""
        return self.emp["zeroWorldM"][self.emp["headingAnchorsDeg"].index(deg)]

    def corrected(self, deg, key, cardinal=False):
        """Baseline at an exact anchor plus that anchor's measured wind delta.

        Expectations below are derived from the table's STRUCTURE rather than
        hardcoded, because these tests are about the interpolation contract -- that
        an exact anchor returns the measured entry and not an interpolation -- not
        about the table's current values. zeroWorldM was re-fitted on 2026-08-31 and
        hardcoded numbers made four of these tests fail for a reason that had
        nothing to do with the behaviour they check.
        """
        anchors = self.emp["cardinalHeadingAnchorsDeg" if cardinal else "headingAnchorsDeg"]
        delta = self.emp[key][anchors.index(deg)]
        base = self.anchor(deg)
        return [base[0] + delta[0], base[1] + delta[1]]

    def test_zero_wind_reproduces_anchor_and_wraps_360_to_zero(self):
        at_zero = self.solve(0, [0, 0, 0])
        at_360 = self.solve(360, [0, 0, 0])
        self.assert_vec_close(at_zero["canopyWorld"], self.anchor(0))
        self.assert_vec_close(at_360["canopyWorld"], at_zero["canopyWorld"])
        self.assertEqual(at_zero["headingBracket"], [0, 0])

    def test_heading_midpoint_interpolates_cyclic_baseline(self):
        result = self.solve(22.5, [0, 0, 0])
        lo, hi = self.anchor(0), self.anchor(45)
        self.assert_vec_close(
            result["baselineWorld"], [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2]
        )
        self.assertEqual(result["headingBracket"], [0, 45])

    def test_exact_5_ms_cardinal_anchors_use_direct_measurements(self):
        east = self.solve(180, [5, 0, 0])
        north = self.solve(180, [0, 5, 0])
        south = self.solve(180, [0, -5, 0])
        west = self.solve(180, [-5, 0, 0])
        self.assert_vec_close(east["canopyWorld"], self.corrected(180, "east5CorrectionWorldM"), 1e-3)
        self.assert_vec_close(north["canopyWorld"], self.corrected(180, "north5CorrectionWorldM"), 1e-3)
        self.assert_vec_close(south["canopyWorld"], self.corrected(180, "south5CorrectionWorldM"), 1e-3)
        self.assert_vec_close(west["canopyWorld"], self.corrected(180, "west5CorrectionWorldM"), 1e-3)
        self.assertFalse(south["usedOppositeDirectionSymmetry"])
        self.assertFalse(west["usedOppositeDirectionSymmetry"])

    def test_exact_10_ms_cardinal_anchors_use_direct_measurements(self):
        south = self.solve(180, [0, -10, 0])
        west = self.solve(180, [-10, 0, 0])
        self.assert_vec_close(
            south["canopyWorld"], self.corrected(180, "south10CorrectionWorldM", cardinal=True), 1e-3
        )
        self.assert_vec_close(
            west["canopyWorld"], self.corrected(180, "west10CorrectionWorldM", cardinal=True), 1e-3
        )
        self.assertEqual(south["windSpeedBracket"], [10, 10])
        self.assertEqual(west["windSpeedBracket"], [10, 10])

    def test_speed_interpolation_at_2_5_and_7_5_ms(self):
        """Speed interpolation is linear: 2.5 m/s is half the 5 m/s delta, and
        7.5 m/s is the midpoint of the 5 and 10 m/s deltas.

        Derived from the table rather than hardcoded. The wind deltas were
        counter-shifted on 2026-08-31 when zeroWorldM was re-fitted, which changed
        every stored delta without changing this interpolation contract at all.
        """
        a5 = self.emp["east5CorrectionWorldM"]
        a10 = self.emp["east10CorrectionWorldM"]
        i0 = self.emp["headingAnchorsDeg"].index(0)
        i90 = self.emp["headingAnchorsDeg"].index(90)
        c90 = self.emp["cardinalHeadingAnchorsDeg"].index(90)

        low = self.solve(0, [2.5, 0, 0])
        self.assert_vec_close(
            low["windCorrectionWorld"], [a5[i0][0] / 2, a5[i0][1] / 2]
        )
        high = self.solve(90, [7.5, 0, 0])
        self.assert_vec_close(
            high["windCorrectionWorld"],
            [(a5[i90][0] + a10[c90][0]) / 2, (a5[i90][1] + a10[c90][1]) / 2],
        )
        self.assertEqual(low["windSpeedBracket"], [0, 5])
        self.assertEqual(high["windSpeedBracket"], [5, 10])

    def test_diagonal_wind_sums_measured_axis_component_responses(self):
        heading = 225
        combined = self.solve(heading, [-3.0, -4.0, 0])
        west = self.solve(heading, [-3.0, 0, 0])
        south = self.solve(heading, [0, -4.0, 0])
        expected = [
            west["windCorrectionWorld"][0] + south["windCorrectionWorld"][0],
            west["windCorrectionWorld"][1] + south["windCorrectionWorld"][1],
        ]
        self.assert_vec_close(combined["windCorrectionWorld"], expected)
        self.assertEqual(combined["windDirectionBracket"], [180, 270])
        self.assertIn("DIAGONAL WIND COMPONENT COMBINATION PROVISIONAL", combined["warnings"])

    def test_above_10_ms_component_extrapolates_and_warns(self):
        result = self.solve(180, [0, 12, 0])
        self.assertIn("WIND ABOVE EMPIRICAL RANGE", result["warnings"])
        self.assertEqual(result["windSpeedBracket"], [5, 10])

    def test_live_sw_wind_inside_calibrated_axis_range_uses_nonzero_correction(self):
        result = self.solve(180, [-2.32918, -2.77918, 0])
        self.assertNotEqual(result["windCorrectionWorld"], [0.0, 0.0])
        self.assertNotIn("WIND ABOVE EMPIRICAL RANGE", result["warnings"])
        self.assertEqual(result["windSpeedBracket"], [0, 5])

    def test_sqf_uses_direct_four_direction_model_keys(self):
        sqf = (ROOT / "addon/functions/solver/fn_empiricalCanopyC17.sqf").read_text(encoding="utf-8")
        for prefix in ("north", "east", "south", "west"):
            self.assertIn(f'"{prefix}"', sqf)
        self.assertNotIn('_heading + 180', sqf)
        self.assertNotIn('_result set [3, true]', sqf)

    def test_sqf_source_exposes_contract_and_component_algorithm_markers(self):
        sqf = (ROOT / "addon/functions/solver/fn_empiricalCanopyC17.sqf").read_text(encoding="utf-8")
        for key in [
            '"modelId"', '"baselineWorld"', '"windCorrectionWorld"', '"canopyWorld"',
            '"predictedCanopyTimeS"', '"headingBracket"', '"windDirectionBracket"',
            '"windSpeedBracket"', '"usedOppositeDirectionSymmetry"', '"warnings"'
        ]:
            self.assertIn(key, sqf)
        self.assertIn('abs _wx', sqf)
        self.assertIn('abs _wy', sqf)
        self.assertIn('DIAGONAL WIND COMPONENT COMBINATION PROVISIONAL', sqf)
        self.assertIn('WIND ABOVE EMPIRICAL RANGE', sqf)


if __name__ == "__main__":
    unittest.main(verbosity=2)

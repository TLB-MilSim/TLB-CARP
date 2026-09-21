from pathlib import Path
import json
import math
import statistics
import unittest

from tests.empirical_reference import solve_empirical_canopy

ROOT = Path(__file__).resolve().parents[1]


def radial_error(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def legacy_canopy_world(row):
    heading = math.radians(row["headingDeg"])
    forward = [math.sin(heading), math.cos(heading)]
    right = [math.cos(heading), -math.sin(heading)]
    base = [
        forward[0] * 234.37 + right[0] * -51.3,
        forward[1] * 234.37 + right[1] * -51.3,
    ]
    t = row["legacyPredictedCanopyTimeS"]
    tau = 4.19
    acquired_time = t - tau * (1.0 - math.exp(-t / tau))
    wind = row["windWorldMs"]
    return [base[0] + wind[0] * acquired_time, base[1] + wind[1] * acquired_time]


class C17DatasetRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        model = json.loads((ROOT / "calibration/model.json").read_text(encoding="utf-8"))
        cls.emp = model["canopy"]["empiricalC17"]
        rows = json.loads((ROOT / "calibration/c17_controlled_observations_v1.json").read_text(encoding="utf-8"))
        # This regression compares against the v0.19b legacy model, which was only
        # ever evaluated over the original controlled-wind set. Later campaigns in
        # the same file carry no legacy prediction to compare against.
        # Superseded rows are excluded. The 5 m/s south singles were measured by the
        # pre-v0.4.24 harness, which solved runs in the same frame as setWind (wind
        # unverified) and starved USAF's chute-attach detection; they are replaced by
        # 8 headings x n=5 at verified [0,-5,0]. Requiring the model to fit both the
        # old single and the new mean is requiring it to fit a 20 m contradiction.
        cls.rows = [r for r in rows if "legacyPredictedCanopyTimeS" in r and "supersededBy" not in r]

    def test_empirical_model_materially_beats_v019b_horizontal_canopy_model(self):
        empirical_errors = []
        legacy_errors = []
        for row in self.rows:
            predicted = solve_empirical_canopy(row["headingDeg"], row["windWorldMs"], self.emp)["canopyWorld"]
            empirical_errors.append(radial_error(predicted, row["canopyWorldM"]))
            legacy_errors.append(radial_error(legacy_canopy_world(row), row["canopyWorldM"]))
        mean_empirical = statistics.mean(empirical_errors)
        mean_legacy = statistics.mean(legacy_errors)
        self.assertLess(mean_empirical, 15.0)
        self.assertLess(max(empirical_errors), 20.0)
        self.assertLess(mean_empirical, mean_legacy * 0.35)

    def test_matched_heavy_and_light_cargo_support_universal_horizontal_model(self):
        def find(cargo, wind):
            return next(row for row in self.rows if row["cargoClass"] == cargo and row["headingDeg"] == 180 and row["windWorldMs"] == wind)

        mrzr_zero = find("rhsusf_mrzr4_d", [0, 0, 0])
        hemtt_zero = find("rhsusf_M977A4_usarmy_d", [0, 0, 0])
        mrzr_east = find("rhsusf_mrzr4_d", [5, 0, 0])
        hemtt_east = find("rhsusf_M977A4_usarmy_d", [5, 0, 0])
        self.assertLess(radial_error(mrzr_zero["canopyWorldM"], hemtt_zero["canopyWorldM"]), 5.0)
        self.assertLess(radial_error(mrzr_east["canopyWorldM"], hemtt_east["canopyWorldM"]), 2.0)
        self.assertGreater(abs(mrzr_zero["canopyDurationS"] - hemtt_zero["canopyDurationS"]), 5.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

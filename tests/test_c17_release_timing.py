from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]


class C17ReleaseTimingCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = json.loads((ROOT / "calibration/model.json").read_text(encoding="utf-8"))

    def test_c17_uses_measured_operational_release_delay(self):
        # Was 0.585 through v0.4.5. Re-measured 2026-08-31 from 10 zero-wind harness
        # runs at two ground speeds (500 and 350 km/h), back-propagating the real
        # chute-attach position along the real release velocity. The two speeds
        # separate delay from the dropPos offset; the fit is exact on both groups.
        # 0.5607 s from 15 clean bench runs across two speeds. The lag is a fixed
        # TIME: lagS 0.602 s at 500 km/h vs 0.601 s at 350, while lagM scaled 81.48
        # -> 56.78 m (ratio 0.70, expected 350/500 = 0.70). Directly measured lag is
        # 0.601 s; 0.5607 is the least-squares value minimising openAlong at both
        # speeds, so it also absorbs a small freefall bias. See model.json
        # releaseDelaySource for the full history including the reverted 0.211.
        self.assertAlmostEqual(self.model["aircraft"]["c17"]["releaseDelayS"], 0.5607, places=6)

    def test_c130_release_delay_is_shared_with_the_c17(self):
        """0.5607 s, same as the C-17, and this sharing is justified rather than
        assumed: the delay is script timing inside USAF's fn_dropCargo.sqf -- a
        hardcoded `sleep 0.5` plus door check and remoteExec -- which is the same code
        for every airframe. It was 0.5 s (a nominal guess) until 2026-09-01.

        This is NOT the canopy table, which is empirical per airframe and must not be
        shared silently; see test_c130_profile_is_flagged_as_borrowed.
        """
        self.assertAlmostEqual(
            self.model["aircraft"]["c130"]["releaseDelayS"],
            self.model["aircraft"]["c17"]["releaseDelayS"],
            places=6,
        )
        self.assertAlmostEqual(self.model["aircraft"]["c130"]["releaseDelayS"], 0.5607, places=6)

    def test_c17_500_kmh_action_to_cargo_release_distance(self):
        c17 = self.model["aircraft"]["c17"]
        groundspeed_ms = 500 / 3.6
        rear_offset_m = c17["dropPos"][1]
        action_to_cargo_release_m = groundspeed_ms * c17["releaseDelayS"] + rear_offset_m
        # 51.25 m through v0.4.5; 46.40 m on the two-speed debug-series fit;
        # 50.88 m on the 0.5607 s bench-measured delay.
        # delta, not places: the value is exactly 50.875, which sits on the
        # places=2 rounding boundary and fails by a hair.
        self.assertAlmostEqual(action_to_cargo_release_m, 50.875, delta=0.01)

    def test_c17_release_timing_fit_holds_at_the_second_measured_speed(self):
        """The two-speed fit is what separates delay from offset -- pin both ends."""
        c17 = self.model["aircraft"]["c17"]
        for kmh, expected in ((500, 50.88), (350, 27.51)):
            got = (kmh / 3.6) * c17["releaseDelayS"] + c17["dropPos"][1]
            self.assertAlmostEqual(got, expected, places=1, msg=f"{kmh} km/h")

    def test_c17_drop_pos_rear_offset(self):
        self.assertEqual(self.model["aircraft"]["c17"]["dropPos"], [0, -27, -5])


if __name__ == "__main__":
    unittest.main(verbosity=2)

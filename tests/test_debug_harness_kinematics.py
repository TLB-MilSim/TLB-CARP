from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "addon/functions/debug/fn_debugDropTest.sqf"


class DebugHarnessKinematicPinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = HARNESS.read_text(encoding="utf-8")

    def test_release_window_pins_position_from_elapsed_sim_time(self):
        self.assertIn(
            'private _pinOriginPosASL = +(USAFDC_state_calibrationRun getOrDefault ["cueAircraftPosASL", getPosASL _carrier]);',
            self.text,
        )
        self.assertIn(
            'private _pinOriginSimTime = USAFDC_state_calibrationRun getOrDefault ["cueSimTime", time];',
            self.text,
        )
        self.assertIn("private _pinElapsedS = (time - _pinOriginSimTime) max 0;", self.text)
        self.assertIn("(_pinOriginPosASL # 0) + ((_velocity # 0) * _pinElapsedS)", self.text)
        self.assertIn("(_pinOriginPosASL # 1) + ((_velocity # 1) * _pinElapsedS)", self.text)
        self.assertIn("(_pinOriginPosASL # 2) + ((_velocity # 2) * _pinElapsedS)", self.text)
        self.assertIn("_carrier setPosASL _pinPosASL;", self.text)

    def test_position_pin_is_limited_to_real_usaf_release_window(self):
        pin_marker = 'private _pinOriginPosASL = +(USAFDC_state_calibrationRun getOrDefault ["cueAircraftPosASL", getPosASL _carrier]);'
        self.assertIn(pin_marker, self.text)
        can_drop = self.text.index("[_carrier] spawn USAF_CARGO_fnc_canDrop;")
        pin_origin = self.text.index(pin_marker)
        release_wait = self.text.index("private _releaseObserved = false;")
        cleanup_comment = self.text.index("// USAF_CARGO owns its native side-selected smoke effect")
        self.assertLess(pin_origin, can_drop)
        self.assertLess(can_drop, release_wait)
        self.assertLess(release_wait, cleanup_comment)
        self.assertNotIn("_cargo setPosASL", self.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)

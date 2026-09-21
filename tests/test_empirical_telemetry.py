from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BEGIN = ROOT / "addon/functions/debug/fn_beginCalibrationRun.sqf"
FORMATTER = ROOT / "addon/functions/debug/fn_formatCalibrationRun.sqf"

FIELDS = [
    "canopyModel",
    "canopyBaselineWorld",
    "canopyWindCorrectionWorld",
    "canopyPredictedWorld",
    "canopyHeadingBracket",
    "canopyWindDirectionBracket",
    "canopyWindSpeedBracket",
    "canopyUsedOppositeDirectionSymmetry",
]


class EmpiricalTelemetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.begin = BEGIN.read_text(encoding="utf-8")
        cls.formatter = FORMATTER.read_text(encoding="utf-8")

    def test_begin_calibration_copies_empirical_relative_fields(self):
        for field in FIELDS:
            self.assertIn(f'["{field}", _relative getOrDefault ["{field}"', self.begin)

    def test_formatter_emits_empirical_fields(self):
        for field in FIELDS:
            self.assertIn(f'format ["{field}=%1"', self.formatter)


if __name__ == "__main__":
    unittest.main(verbosity=2)

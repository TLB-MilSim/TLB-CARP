from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "addon/functions/debug/fn_debugDropTest.sqf"


class NativeSmokeHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = HARNESS.read_text(encoding="utf-8")

    def test_debug_harness_does_not_create_or_override_usaf_smoke(self):
        self.assertNotIn("SmokeShellBlue", self.text)
        self.assertNotIn("SmokeShellRed", self.text)
        self.assertNotIn("SmokeShellGreen", self.text)
        self.assertNotRegex(self.text, r'\bSmokeShell\b.*createVehicle')

    def test_debug_harness_still_uses_real_usaf_drop_path(self):
        self.assertIn("USAF_CARGO_fnc_canDrop", self.text)
        self.assertNotIn("USAF_CARGO_fnc_smoke", self.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)

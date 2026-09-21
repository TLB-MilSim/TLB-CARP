from pathlib import Path
import os
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = Path(os.environ.get("TLB_CARP_HARNESS", ROOT / "addon/functions/debug/fn_debugDropTest.sqf"))


class DebugHarnessCargoInitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = HARNESS.read_text(encoding="utf-8")

    def test_uses_real_usaf_force_loader(self):
        self.assertIn(
            "[_carrier, _cargo, 0, false] call USAF_CARGO_fnc_forceLoadCargo;",
            self.text,
        )

    def test_does_not_manually_register_or_attach_cargo(self):
        self.assertNotIn('_carrier setVariable ["usaf_cargo", [_cargo], true];', self.text)
        self.assertNotRegex(self.text, r"\b_cargo\s+attachTo\s*\[")

    def test_validates_usaf_initialized_state(self):
        self.assertIn('_cargo in (_carrier getVariable ["usaf_cargo", []])', self.text)
        self.assertIn('(_cargo getVariable ["carrier", objNull]) isEqualTo _carrier', self.text)
        self.assertIn('isNil {_cargo getVariable "getoutevh"}', self.text)
        self.assertIn('(attachedTo _cargo) isEqualTo _carrier', self.text)
        self.assertIn('USAF cargo initialization failed', self.text)

    def test_preserves_real_usaf_drop_trigger(self):
        self.assertIn('[_carrier] spawn USAF_CARGO_fnc_canDrop;', self.text)
        self.assertNotIn('USAF_CARGO_fnc_prepareForDrop', self.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)

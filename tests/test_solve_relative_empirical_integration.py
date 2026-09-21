from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOLVER = ROOT / "addon/functions/solver/fn_solveRelative.sqf"


class SolveRelativeEmpiricalIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SOLVER.read_text(encoding="utf-8")

    def test_lazily_loads_and_calls_empirical_c17_solver(self):
        self.assertIn('isNil "TLB_CARP_fnc_empiricalCanopyC17"', self.text)
        self.assertIn('fn_empiricalCanopyC17.sqf', self.text)
        # The table is now selected per aircraft via the profile's canopyRef rather
        # than hardcoded to c17. Hardcoding meant any other airframe would silently
        # borrow the C-17 table by accident instead of by declaration.
        self.assertIn("_canopyRef = _aircraft getOrDefault", self.text)
        self.assertIn("_canopyRoot get _canopyRef", self.text)
        self.assertNotIn('_canopyRoot get "empiricalC17"', self.text)
        self.assertIn('call TLB_CARP_fnc_empiricalCanopyC17', self.text)

    def test_touchdown_uses_world_canopy_and_wind_correction_projection(self):
        self.assertIn('private _canopyWorld = +(_empirical get "canopyWorld")', self.text)
        self.assertIn('private _windCorrectionWorld = +(_empirical get "windCorrectionWorld")', self.text)
        self.assertIn('(_canopyWorld # 0) * (_forward # 0)', self.text)
        self.assertIn('(_windCorrectionWorld # 0) * (_forward # 0)', self.text)

    def test_legacy_fixed_horizontal_canopy_constants_are_not_used(self):
        self.assertNotIn('_canopy get "forwardThrowM"', self.text)
        self.assertNotIn('_canopy get "intrinsicRightM"', self.text)
        self.assertNotIn('_canopy get "windTauS"', self.text)
        self.assertNotIn('TLB_CARP_fnc_acquiredWindDisplacement', self.text)

    def test_chute_mode_keeps_zero_canopy_displacement_and_time(self):
        self.assertIn('if (_chuteMode) then', self.text)
        self.assertIn('["predictedCanopyTimeS", if (_chuteMode) then {0}', self.text)
        self.assertIn('private _canopyAlongM = 0;', self.text)
        self.assertIn('private _canopyRightM = 0;', self.text)

    def test_relative_solution_exposes_empirical_telemetry_fields(self):
        for key in [
            '"canopyModel"', '"canopyBaselineWorld"', '"canopyWindCorrectionWorld"',
            '"canopyPredictedWorld"', '"canopyHeadingBracket"', '"canopyWindDirectionBracket"',
            '"canopyWindSpeedBracket"', '"canopyUsedOppositeDirectionSymmetry"'
        ]:
            self.assertIn(key, self.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)

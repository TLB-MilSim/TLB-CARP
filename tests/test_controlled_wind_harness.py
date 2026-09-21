from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SERIES = ROOT / "addon/functions/debug/fn_debugDropSeries.sqf"
DROP = ROOT / "addon/functions/debug/fn_debugDropTest.sqf"
FORMAT = ROOT / "addon/functions/debug/fn_formatCalibrationRun.sqf"


class ControlledWindHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.series = SERIES.read_text(encoding="utf-8")
        cls.drop = DROP.read_text(encoding="utf-8")
        cls.formatter = FORMAT.read_text(encoding="utf-8")

    def test_series_accepts_backwards_compatible_wind_control_parameters(self):
        self.assertIn('["_windMode", "LIVE", [""]]', self.series)
        self.assertIn('["_controlledWindVector", [0, 0], [[]]]', self.series)
        self.assertIn('toUpper _windMode', self.series)
        self.assertIn('["LIVE", "ZERO", "FIXED"]', self.series)

    def test_zero_and_fixed_modes_lock_engine_wind_and_remove_gusts(self):
        self.assertIn('0 setGusts 0;', self.series)
        self.assertIn('setWind [_requestedWindVector # 0, _requestedWindVector # 1, true];', self.series)
        self.assertIn('case "ZERO": {[0, 0, 0]};', self.series)
        self.assertIn('TLB CARP DEBUG SERIES\\nControlled wind did not lock', self.series)

    def test_series_snapshots_and_restores_environment(self):
        self.assertIn('private _windBeforeSeries = +(wind);', self.series)
        self.assertIn('private _gustsBeforeSeries = gusts;', self.series)
        self.assertIn('setWind [_windBeforeSeries # 0, _windBeforeSeries # 1, false];', self.series)
        self.assertIn('0 setGusts _gustsBeforeSeries;', self.series)

    def test_controlled_wind_waits_for_ace_disable_and_reasserts_requested_wind(self):
        self.assertIn('private _aceDisableSettleDeadline = diag_tickTime + 1;', self.series)
        self.assertIn('diag_tickTime >= _aceDisableSettleDeadline', self.series)
        self.assertGreaterEqual(self.series.count('setWind [_requestedWindVector # 0, _requestedWindVector # 1, true];'), 2)

    def test_control_metadata_flows_into_each_calibration_record(self):
        self.assertIn('_windMode,', self.series)
        self.assertIn('+_requestedWindVector', self.series)
        self.assertIn('["_testWindMode", "LIVE", [""]]', self.drop)
        self.assertIn('["_testRequestedWindVector", [], [[]]]', self.drop)
        self.assertIn('["testWindMode", _testWindMode]', self.drop)
        self.assertIn('["testRequestedWindVector", +_testRequestedWindVector]', self.drop)
        self.assertIn('["testEngineWindAtHarnessStart", +(wind)]', self.drop)
        self.assertIn('["testGustsAtHarnessStart", gusts]', self.drop)

    def test_controlled_wind_disables_and_restores_ace_wind_simulation(self):
        self.assertIn('private _aceWindSimulationWasDefined = !(isNil "ace_weather_disableWindSimulation");', self.series)
        self.assertIn('private _aceWindSimulationBeforeSeries = missionNamespace getVariable ["ace_weather_disableWindSimulation", false];', self.series)
        self.assertIn('ace_weather_disableWindSimulation = true;', self.series)
        self.assertIn('missionNamespace setVariable ["ace_weather_disableWindSimulation", _aceWindSimulationBeforeSeries];', self.series)
        self.assertIn('missionNamespace setVariable ["ace_weather_disableWindSimulation", nil];', self.series)

    def test_formatter_emits_control_metadata(self):
        self.assertIn('format ["testWindMode=%1"', self.formatter)
        self.assertIn('format ["testRequestedWindVector=%1"', self.formatter)
        self.assertIn('format ["testEngineWindAtHarnessStart=%1"', self.formatter)
        self.assertIn('format ["testGustsAtHarnessStart=%1"', self.formatter)


if __name__ == "__main__":
    unittest.main(verbosity=2)

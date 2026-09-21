from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class EmpiricalModelDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = json.loads((ROOT / "calibration/model.json").read_text(encoding="utf-8"))
        cls.emp = cls.model["canopy"]["empiricalC17"]
        cls.observations = json.loads((ROOT / "calibration/c17_controlled_observations_v1.json").read_text(encoding="utf-8"))

    def test_model_identity_and_envelope(self):
        self.assertEqual(self.emp["modelId"], "EMPIRICAL_C17_V2")
        self.assertEqual(self.model["confidence"]["testedWindMsMax"], 10)

    def test_heading_anchor_shapes_cover_all_four_measured_wind_directions(self):
        self.assertEqual(self.emp["headingAnchorsDeg"], [0, 45, 90, 135, 180, 225, 270, 315])
        self.assertEqual(len(self.emp["zeroWorldM"]), 8)
        for prefix in ("east", "north", "south", "west"):
            self.assertEqual(len(self.emp[f"{prefix}5CorrectionWorldM"]), 8, prefix)
            self.assertEqual(len(self.emp[f"{prefix}5TimeDeltaS"]), 8, prefix)
        self.assertEqual(self.emp["cardinalHeadingAnchorsDeg"], [0, 90, 180, 270])
        for prefix in ("east", "north", "south", "west"):
            self.assertEqual(len(self.emp[f"{prefix}10CorrectionWorldM"]), 4, prefix)
            self.assertEqual(len(self.emp[f"{prefix}10TimeDeltaS"]), 4, prefix)

    def test_observation_fixture_contains_all_60_controlled_drops(self):
        """The original controlled-wind set stays pinned at 60 independently of any
        later campaign appended to the same file. Rows are tagged by `dataset` so
        adding data cannot silently dilute this assertion."""
        controlled = [r for r in self.observations if r.get("dataset") == "controlledWindV1"]
        self.assertEqual(len(controlled), 60)
        self.assertEqual(sum(1 for row in controlled if row["cargoClass"] == "rhsusf_mrzr4_d"), 56)
        self.assertEqual(sum(1 for row in controlled if row["cargoClass"] == "rhsusf_M977A4_usarmy_d"), 4)

    def test_zero_wind_baseline_campaign_is_present_and_tagged(self):
        camp = [r for r in self.observations if r.get("dataset") == "zeroWindBaseline_2026_08_31"]
        self.assertEqual(len(camp), 40)
        self.assertTrue(all(r["windWorldMs"] == [0, 0, 0] for r in camp))
        headings = sorted({r["headingDeg"] for r in camp})
        self.assertEqual(headings, [0, 45, 90, 135, 180, 225, 270, 315])
        for h in headings:
            self.assertEqual(sum(1 for r in camp if r["headingDeg"] == h), 5)

    def test_observation_fixture_has_complete_direct_south_and_west_sets(self):
        for wind in ([0, -5, 0], [-5, 0, 0]):
            headings = sorted(row["headingDeg"] for row in self.observations if row.get("dataset") == "controlledWindV1" and row["cargoClass"] == "rhsusf_mrzr4_d" and row["windWorldMs"] == wind)
            self.assertEqual(headings, [0, 45, 90, 135, 180, 225, 270, 315])
        for wind in ([0, -10, 0], [-10, 0, 0]):
            headings = sorted(row["headingDeg"] for row in self.observations if row.get("dataset") == "controlledWindV1" and row["cargoClass"] == "rhsusf_mrzr4_d" and row["windWorldMs"] == wind)
            self.assertEqual(headings, [0, 90, 180, 270])

    def test_cargo_is_generic_not_profile_selector(self):
        self.assertNotIn("MRZR", self.model["cargo"]["default"]["displayName"].upper())
        self.assertNotIn("cargoProfiles", self.emp)

class ZeroWindBaselineRefit2026_08_31Tests(unittest.TestCase):
    """Explicit pin on the approved zeroWorldM re-fit.

    The interpolation tests in test_empirical_canopy_math are deliberately
    table-independent so a re-fit does not break them. This class is the opposite:
    it is the RECORD of an approved tuning decision, so an accidental or unreviewed
    change to a protected calibration asset still fails the suite.

    Source: 40 bench runs, 8 headings x n=5, verified zero wind (setWind converged
    to 0.000 m/s, gusts 0), batches capped at 8 concurrent runs with chuteAgl held
    296.5-299.9 m, heading-to-cell assignment rotated across batches.
    Effect: mean radial miss 5.94 -> 2.24 m, median 6.16 -> 1.62 m, 40/40 in box.
    """

    ORIGINAL_SOUTH5 = {'135': [-0.1954, -219.4972], '225': [-0.9139, -221.2701]}

    APPROVED = [
        [9.477, 223.8235],
        [128.1455, 168.01],
        [229.89, 35.3113],
        [186.6334, -128.5538],
        [-0.6216, -214.131],
        [-185.6151, -126.5329],
        [-229.34, 34.2744],
        [-126.0995, 166.2315],
    ]

    @classmethod
    def setUpClass(cls):
        model = json.loads((ROOT / "calibration/model.json").read_text(encoding="utf-8"))
        cls.emp = model["canopy"]["empiricalC17"]
        cls.observations = json.loads(
            (ROOT / "calibration/c17_controlled_observations_v1.json").read_text(encoding="utf-8")
        )

    def test_zero_world_matches_the_approved_refit(self):
        self.assertEqual(len(self.emp["zeroWorldM"]), 8)
        for i, (got, want) in enumerate(zip(self.emp["zeroWorldM"], self.APPROVED)):
            for axis, (g, w) in enumerate(zip(got, want)):
                self.assertAlmostEqual(
                    g, w, delta=1e-3,
                    msg=f"zeroWorldM[{i}][{axis}] (heading {self.emp['headingAnchorsDeg'][i]})",
                )

    def test_generated_sqf_carries_the_same_values(self):
        """The generated file must never be hand-edited or left stale.

        Compared numerically, not by string: the generator renders via repr() and
        Arma is single-precision, so "168.01" and "168.0100" are the same value and
        a string match would fail for a formatting difference that does not matter.
        """
        sqf = (ROOT / "addon/functions/generated/fn_getModel.sqf").read_text(encoding="utf-8")
        m = re.search(r'\["zeroWorldM", (\[\[.*?\]\])\]', sqf)
        self.assertIsNotNone(m, "zeroWorldM not found in generated model")
        got = json.loads(m.group(1))
        self.assertEqual(len(got), len(self.APPROVED))
        for i, (g, w) in enumerate(zip(got, self.APPROVED)):
            for axis in (0, 1):
                self.assertAlmostEqual(
                    g[axis], w[axis], delta=1e-3,
                    msg=f"generated zeroWorldM[{i}][{axis}] disagrees with model.json",
                )

    def test_wind_deltas_were_counter_shifted(self):
        """Re-fitting zeroWorldM without counter-shifting the wind deltas
        double-corrects every wind case: a 5 m/s south batch measured mean radial
        12.93 m against 9.52 m for the pre-change table. The deltas had been fitted
        as (observed drift with wind) - (OLD baseline), so the two halves must move
        together or the decomposition is not physical.
        """
        # north5 at heading 0, NOT south5: south5 has since been re-fitted from the
        # 2026-08-31 campaign, so it no longer reflects the counter-shift alone.
        i0 = self.emp["headingAnchorsDeg"].index(0)
        self.assertAlmostEqual(self.emp["north5CorrectionWorldM"][i0][0], -5.7465, delta=1e-3)
        self.assertAlmostEqual(self.emp["north5CorrectionWorldM"][i0][1], 163.9495, delta=1e-3)
        src = self.emp.get("windCorrectionSource", "")
        self.assertIn("counter-shifted", src)
        self.assertIn("double-corrected", src)

    # Headings whose 5 m/s south delta was deliberately NOT re-fitted, because no
    # component was resolved above noise. Their original n=1 consistency must hold.
    SOUTH5_NOT_REFITTED = [135, 225]

    def test_south5_untouched_headings_stay_consistent_with_original_data(self):
        anchors = self.emp["headingAnchorsDeg"]
        checked = 0
        for row in self.observations:
            if row.get("dataset") != "controlledWindV1": continue
            if row["windWorldMs"] != [0, -5, 0] or row["cargoClass"] != "rhsusf_mrzr4_d": continue
            if int(row["headingDeg"]) not in self.SOUTH5_NOT_REFITTED: continue
            i = anchors.index(row["headingDeg"])
            base = self.emp["zeroWorldM"][i]
            delta = self.emp["south5CorrectionWorldM"][i]
            for axis in (0, 1):
                self.assertAlmostEqual(
                    base[axis] + delta[axis], row["canopyWorldM"][axis], delta=2e-2,
                    msg=f"heading {row['headingDeg']} axis {axis}",
                )
            checked += 1
        self.assertEqual(checked, len(self.SOUTH5_NOT_REFITTED))

    def test_south5_refit_only_moved_resolved_components(self):
        """The re-fit is the record of an approved decision: only components with
        |mean|/sem >= 3 were corrected. Fitting the unresolved ones would be fitting
        this batch's scatter, which at heading 180 reaches sd 15.8 m."""
        anchors = self.emp["headingAnchorsDeg"]
        for h in self.SOUTH5_NOT_REFITTED:
            i = anchors.index(float(h))
            self.assertEqual(
                self.emp["south5CorrectionWorldM"][i],
                self.ORIGINAL_SOUTH5[str(h)],
                msg=f"heading {h} was re-fitted but no component was resolved",
            )
        src = self.emp.get("south5Source", "")
        self.assertIn("resolved above noise", src)
        self.assertIn("UNCHANGED", src)

    def test_south5_campaign_observations_are_recorded(self):
        camp = [r for r in self.observations if r.get("dataset") == "windSouth5_2026_08_31"]
        self.assertEqual(len(camp), 40)
        self.assertTrue(all(r["windWorldMs"] == [0, -5, 0] for r in camp))
        self.assertTrue(all(r["chuteAttachAglM"] >= 290 for r in camp),
                        "a late chute attach in the source data would invalidate the re-fit")

    def test_provenance_is_recorded_in_the_model(self):
        """A protected asset changed without a stated source is unauditable."""
        src = self.emp.get("zeroWorldMSource", "")
        self.assertIn("verified", src)
        self.assertIn("zero wind", src)
        # The wind deltas were NOT re-fitted; that caveat must travel with the data.
        self.assertIn("NOT re-fitted", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)

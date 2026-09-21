"""v0.16.12 -- the canopy must open facing backward.

THE MEASUREMENT, three flown drops on one path at one condition (C-17, MRZR, 1485 m,
383 km/h, run-in 058) plus sixteen bench runs:

    chute hdg   canopy duration   miss      release path
     58 deg      42.910 s         113.5 m   CARP,  canopy forward
     59 deg      44.031 s          76.6 m   CARP,  canopy forward
    238 deg      35.126 s          21.1 m   USAF,  canopy backward

Runs 2 and 3 were flown at the same wind (4.23 and 4.16 m/s) on the same line minutes
apart. The only difference was the release path, and the canopy lasted 8.9 s longer.

THE CAUSE. Nothing in fn_canopyWatch ever set the chute's heading. `attachTo` then
`detach` leaves it on the CARGO's heading, so the canopy faced wherever the load
happened to be sitting. USAF's loader turns every load 180 -- fn_loadAttach copies that
`setDir 180` -- so anything USAF loaded and released opened its canopy pointing back
down the run-in. A vehicle-in-vehicle, ACE or mission-maker load did not.

B_Parachute_02_F is a steerable canopy and it flies. Facing into 106 m/s of forward
airflow it balloons: the flown transients brake to -1.8 m/s at t=4 s and level off 41 m
higher, then spend that altitude at the same 4.4 m/s terminal both paths share.

    run 2 (forward)   t=3  178.1 m   t=4  174.1 m   t=5  173.1 m   vz -6.9, -1.8, -2.0
    run 3 (backward)  t=3  152.8 m   t=4  139.9 m   t=5  133.3 m   vz -17.4, -8.5, -5.5

THE CALIBRATION WAS NEVER WRONG, WHICH IS THE POINT. fn_parallelDropBench drops through
USAF_CARGO_fnc_canDrop, so all 140 calibration runs flew a backward canopy. Sixteen bench
runs at this condition gave 35.29-35.65 s with wind and landed 18.7-20.0 m out; run 3
gave 35.126 s and landed 21.1 m out. The bench reproduces a flown drop to ~2 m. Since
v0.10.0 CARP had stopped producing the canopy its own tables describe.

WHAT WAS RETRACTED. Runs 1 and 2 were used to argue the canopy wind coefficient should be
1.0 rather than the model's ~0.6, from a two-point fit that looked clean because both runs
shared the fault. Run 3 fits the existing tables to 16.9 m over the canopy phase. That
analysis was fitted to a broken canopy and is withdrawn -- no calibration value changed.

WHY HERE AND NOT AT THE LOAD. All four cargo sources (usaf / ace / viv / attached)
converge on this one line. Fixing it at fn_loadAttach would leave every other source
wrong, and what a drop does must not depend on how the loadmaster packed it.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.exists() else ""


def code(rel: str) -> str:
    sys.path.insert(0, str(ROOT / "tools"))
    from strip_sqf_comments import strip_comments

    path = ROOT / rel
    return strip_comments(path.read_text(encoding="utf-8")) if path.exists() else ""


WATCH = "addon/functions/cargo/fn_canopyWatch.sqf"


class OrientationTests(unittest.TestCase):
    def test_the_chute_is_yawed_180_after_it_is_detached(self):
        src = code(WATCH)
        self.assertIn("private _cd = vectorDir _chute;", src)
        self.assertIn("private _cu = vectorUp _chute;", src)
        self.assertIn("_chute setVectorDirAndUp [", src)
        self.assertIn("[-(_cd # 0), -(_cd # 1), _cd # 2],", src)
        self.assertIn("[-(_cu # 0), -(_cu # 1), _cu # 2]", src)

    def test_the_vertical_component_is_kept_not_negated(self):
        """A yaw about world Z maps (x,y,z) -> (-x,-y,z). Negating z as well would pitch
        the canopy over instead of turning it, and the drop would be far worse than the
        bug this replaces."""
        src = code(WATCH)
        self.assertNotIn("-(_cd # 2)", src)
        self.assertNotIn("-(_cu # 2)", src)

    def test_it_runs_after_the_detach_and_before_the_cargo_is_hung(self):
        """Order is the whole fix. Before the detach the chute is a child and the write
        would be in the cargo's frame; after the cargo is attached the cargo would be
        rotated separately from the canopy carrying it."""
        src = code(WATCH)
        detach = src.index("detach _chute;")
        yaw = src.index("_chute setVectorDirAndUp [")
        hang = src.index("_cargo attachTo [_chute,")
        self.assertLess(detach, yaw)
        self.assertLess(yaw, hang)

    def test_setdir_is_not_used_on_the_chute(self):
        """v0.3.0: setDir wipes velocity. This object is about to carry the load down."""
        self.assertNotIn("setDir", code(WATCH))


class ProvenanceTests(unittest.TestCase):
    def test_the_source_records_the_three_flown_drops(self):
        src = read(WATCH)
        for token in ["42.910", "44.031", "35.126", "238 deg", "113.5", "21.1"]:
            self.assertIn(token, src, token)

    def test_the_source_records_that_the_calibration_was_not_at_fault(self):
        """The next person to read this will be tempted to retune the tables. They are
        correct; the canopy was not the one they describe."""
        src = read(WATCH)
        self.assertIn("CALIBRATION WAS NEVER WRONG", src)
        self.assertIn("canDrop", src)

    def test_the_fix_is_at_the_convergence_point_and_says_why(self):
        src = read(WATCH)
        self.assertIn("all four cargo sources converge", src)


class NoCalibrationChangeTests(unittest.TestCase):
    def test_no_canopy_table_value_moved(self):
        """THE SAFETY ARGUMENT. This release restores the condition the tables were
        measured under. If it also moved a table value, the two changes could not be told
        apart on the next flown drop."""
        import json

        model = json.loads(read("calibration/model.json"))
        c17 = model["canopy"]["empiricalC17"]
        self.assertAlmostEqual(c17["throwRefSpeedMs"], 138.89, places=2)
        self.assertAlmostEqual(c17["throwTerminalMs"], 21.9, places=2)
        self.assertAlmostEqual(c17["canopyTimeRefFreefallS"], 23.24, places=2)
        self.assertAlmostEqual(
            model["aircraft"]["c17"]["releaseDelayS"], 0.5607, places=4)

    def test_the_release_sequence_timing_is_untouched(self):
        """releaseDelayS was measured against this sequence. The yaw sits inside the
        canopy watcher, which fires ~15 s after the release and cannot reach it."""
        src = code("addon/functions/cargo/fn_releaseCargo.sqf")
        self.assertIn("sleep 0.5;", src)
        self.assertIn("call USAFDC_fnc_canopyWatch;", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)

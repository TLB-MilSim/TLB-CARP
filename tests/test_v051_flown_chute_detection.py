"""Per-frame canopy-attach detection in the flown calibration recorder.

fn_pollCalibrationRun detected the canopy in a `uiSleep 0.05` scheduled loop. Under
flight load that loop was starved by 0.3-0.5 s, and the resulting readings looked
like a physical fault:

    recorded attach AGL   vz at that instant
        299.7 m               -232 m/s      freefall terminal
        298.4 m               -251 m/s      freefall terminal
        296.3 m               -231 m/s      freefall terminal
        253.7 m               -124 m/s      already decelerating
        236.7 m               -145 m/s      already decelerating
        229.8 m               -180 m/s      already decelerating

A load that genuinely fell longer before its chute attached would be going FASTER.
Every low reading is slower, so the canopy was already open and slowing it: the chute
was on time and the poll was late. The parallel bench, whose detection is per frame,
reads 293-300 m on every run against the same USAF code.

That artefact was briefly reported as "chute-attach altitude is the dominant flown
error" and drove the v0.5.1 solver throttle. It also corrupted everything derived
from the attach point: chuteOpeningError*, canopyDuration* and canopySample00.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = "addon/functions/debug/fn_pollCalibrationRun.sqf"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def code(rel: str) -> str:
    """Source with comments stripped, string literals intact.

    Ordering assertions must measure EXECUTABLE order. The driver gate added to
    fn_triggerAutoDrop explains, in prose above the stamp, why a second crew member
    must not reach `spawn USAF_CARGO_fnc_canDrop` -- and a raw-text index would find
    that sentence rather than the call.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    from strip_sqf_comments import strip_comments

    return strip_comments((ROOT / rel).read_text(encoding="utf-8"))


class PerFrameChuteDetectionTests(unittest.TestCase):
    def setUp(self):
        self.src = read(SRC)
        self.handler = self.src[self.src.index('addMissionEventHandler ["EachFrame"'):]
        self.handler = self.handler[:self.handler.index("}];") + 3]

    def test_attach_is_stamped_in_a_per_frame_handler(self):
        self.assertIn('addMissionEventHandler ["EachFrame"', self.src)
        self.assertIn('_c setVariable ["TLB_CARP_calChuteStamp"', self.handler)

    def test_handler_stamps_once_only(self):
        self.assertIn('if !(isNil {_c getVariable "TLB_CARP_calChuteStamp"}) exitWith {}', self.handler)

    def test_handler_still_rejects_the_carrier(self):
        """The cargo is attached to the carrier during release; only a ParachuteBase
        counts, or the attach would be stamped at the moment of release."""
        self.assertIn('_att isKindOf "ParachuteBase"', self.handler)
        self.assertIn("_att isEqualTo _carr", self.handler)

    def test_loop_reads_the_stamp_and_does_not_re_detect(self):
        loop = self.src[self.src.index("private _touchdownConfirmed"):]
        self.assertIn('_releasedCargo getVariable ["TLB_CARP_calChuteStamp", []]', loop)
        self.assertNotIn("attachedTo _releasedCargo", loop)

    def test_every_attach_field_comes_from_the_stamp(self):
        """Any field still sampled at read time would carry the loop's latency."""
        loop = self.src[self.src.index("private _touchdownConfirmed"):]
        block = loop[loop.index('_run set ["chuteDetectionStatus"'):loop.index('_run set ["chuteWindTelemetry"')]
        for banned in ("getPosATL _releasedCargo", "getDir _parachute",
                       "vectorDir _parachute", "vectorUp _parachute", "velocity _parachute"):
            self.assertNotIn(banned, block, f"{banned} is sampled late, not stamped")
        self.assertIn("_stamp # 4", block)   # attach AGL
        self.assertIn("_stamp # 9", block)   # velocity at attach

    def test_detection_lag_is_recorded_and_surfaced(self):
        """The lag no longer corrupts the attach point, but a large value means the
        loop is starved and the still-scheduled canopy samples are suspect."""
        self.assertIn('_run set ["chuteAttachDetectionLagS"', self.src)
        self.assertIn("diag_tickTime - (_stamp # 2)", self.src)
        self.assertIn("chuteAttachDetectionLagS=%1", read("addon/functions/debug/fn_formatCalibrationRun.sqf"))

    def test_watcher_is_torn_down_on_every_exit_path(self):
        """A leaked EachFrame handler would stamp the NEXT run's cargo."""
        self.assertIn("private _stopChuteWatch = {", self.src)
        self.assertIn('removeMissionEventHandler ["EachFrame", TLB_CARP_state_calChuteWatchEh]', self.src)
        # the abort path and the success path must both call it
        self.assertGreaterEqual(self.src.count("call _stopChuteWatch"), 2)
        self.assertLess(self.src.index("private _stopChuteWatch = {"), self.src.index("private _abort = {"))

    def test_stale_handler_is_replaced_not_stacked(self):
        head = self.src[:self.src.index("private _touchdownConfirmed")]
        self.assertIn('if ((missionNamespace getVariable ["TLB_CARP_state_calChuteWatchEh", -1]) >= 0) then {', head)

    def test_state_globals_are_initialised(self):
        post = read("addon/functions/fn_postInit.sqf")
        for g in ("TLB_CARP_state_calChuteWatchEh", "TLB_CARP_state_calChuteWatchCargo",
                  "TLB_CARP_state_calChuteWatchCarrier"):
            self.assertIn(f"{g} = ", post)

    def test_no_compiled_sibling_shadows_this_file(self):
        """A stale .sqfc would silently revert all of the above -- it shadowed
        fn_buildDebugDropSolution for several builds and cost 16 runs of garbage."""
        self.assertFalse((ROOT / "addon/functions/debug/fn_pollCalibrationRun.sqfc").exists())
        self.assertIn(SRC, read("tests/test_source_precedence.py"))


class AttachLatchTests(unittest.TestCase):
    """The stamp-read block must run exactly ONCE.

    v0.5.2 guarded it with `isNull _parachute`. The parachute reference goes null
    again when USAF deletes the canopy, so the block re-ran and overwrote the attach
    fields every iteration until touchdown: chuteAttachDetectionLagS came back as
    26.9 / 26.8 / 26.0 s -- exactly the canopy durations -- with an empty
    actualChuteClass and an empty canopySample00, because the final overwrite
    happened with an already-deleted canopy.

    The stamped values (position, altitude, velocity) were unaffected, which is why
    the attach-altitude result from those drops still stands: 299.7 / 299.8 / 297.1 m
    at -231 m/s, all prompt.
    """

    def setUp(self):
        self.src = read(SRC)

    def test_latch_is_a_value_that_is_never_invalidated(self):
        self.assertIn("if (_chuteAttachSimTime < 0) then {", self.src)

    def test_does_not_latch_on_the_parachute_reference(self):
        loop = self.src[self.src.index("private _touchdownConfirmed"):]
        self.assertNotIn("if (isNull _parachute) then {", loop)


class DropCommandInstantTests(unittest.TestCase):
    """Three v0.5.2 drops measured 34-57 m between cue and detected release -- 0.24 to
    0.41 s at 140 m/s -- which cannot be reconciled with the hardcoded `sleep 0.5` in
    USAF's fn_dropCargo.sqf. An inference from the cue was already acted on once
    (releaseDelayS 0.211, retracted). Measure both ends instead."""

    def test_trigger_stamps_the_command(self):
        src = read("addon/functions/auto/fn_triggerAutoDrop.sqf")
        self.assertIn("TLB_CARP_state_autoDropCommand = [time, diag_tickTime, getPosASL _carrier];", src)

    def test_stamp_precedes_the_actual_drop_call(self):
        """Stamping after canDrop would fold the door wait into the measurement."""
        src = code("addon/functions/auto/fn_triggerAutoDrop.sqf")
        # v0.8.0: the release goes through fn_releaseSelected, which routes a USAF
        # airframe carrying USAF-loaded cargo back to USAF's own canDrop unchanged. The
        # stamp must still precede whichever path runs, for the same reason as before.
        self.assertLess(
            src.index("TLB_CARP_state_autoDropCommand ="),
            src.index("TLB_CARP_fnc_releaseSelected"),
        )

    def test_command_to_release_distance_uses_a_live_position(self):
        """v0.5.3 used _releaseAircraftPosASL, which is computed further down the
        file, so the field came back blank."""
        src = read(SRC)
        self.assertIn("distance2D (getPosASL _carrier)", src)
        self.assertNotIn("distance2D _releaseAircraftPosASL", src)

    def test_recorder_reads_the_command_stamp(self):
        self.assertIn('missionNamespace getVariable ["TLB_CARP_state_autoDropCommand", []]', read(SRC))
        for f in ("cueToCommandM", "commandToReleaseM", "commandToReleaseS"):
            self.assertIn(f, read(SRC), f)

    def test_fields_are_surfaced_in_the_record(self):
        fmt = read("addon/functions/debug/fn_formatCalibrationRun.sqf")
        for f in ("cueToCommandM=%1", "commandToReleaseM=%1", "commandToReleaseS=%1"):
            self.assertIn(f, fmt, f)

    def test_state_global_is_initialised(self):
        self.assertIn("TLB_CARP_state_autoDropCommand = [];", read("addon/functions/fn_postInit.sqf"))

    def test_trigger_has_no_compiled_shadow(self):
        self.assertFalse((ROOT / "addon/functions/auto/fn_triggerAutoDrop.sqfc").exists())
        self.assertIn("addon/functions/auto/fn_triggerAutoDrop.sqf", read("tests/test_source_precedence.py"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
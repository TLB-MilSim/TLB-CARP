"""v0.16.5 -- the instruments that were supposed to answer "are we landing short".

FLOWN 2026-09-20. Three drops, a consistent ~15 m along-track shortfall, and no way to tell
whether it was release timing, the canopy model or the measurement itself. Every tool that
could have settled it was broken, and each in a way that produced a plausible number rather
than an obvious failure.

1. ARMA TRUNCATES diag_log AT ABOUT A KILOBYTE, SILENTLY

   Every TLB_CARP_CAL_V3 record in every RPT ends mid-field at `interceptAngleDeg`. Every
   [TLB CARP][DROP] line is exactly 1031 bytes and stops inside an array. What was cut is
   what the record exists for -- release geometry, the chute event, the impact position, the
   computed miss, and commandToReleaseS.

   That stamp is the one CLAUDE.md names as the ONLY trustworthy source for release timing:
   "never infer release timing from positions again; read the stamp." It was being written
   every drop and thrown away every drop.

2. THE RECORDER TESTED THE WRONG ARRAY, SO IT REPORTED THE CUE AS THE RELEASE

   fn_beginCalibrationRun builds initialCargo from the MANIFEST. fn_pollCalibrationRun
   compared it against `usaf_cargo`. A viv, ace or attached load is in the first and never
   in the second, so `findIf {!(_x in _currentCargo)}` matched on the FIRST poll -- at the
   cue, before anything had left the aircraft.

   The same sortie logged signedRp -36.30 for a usaf-source load and -4.62 / -4.05 for a viv
   and an attached one. The flattering pair were the bug, and they are the ones that look
   like a healthy system. fn_beginCalibrationRun's own header records this exact fix being
   applied to itself earlier the same day; its sibling was left alone.

3. THE HINT TOLD THE PILOT TO RUN A FUNCTION WITHOUT `call`

   "Run TLB_CARP_fnc_copyLastCalibrationRun to copy it". A bare function name is a variable
   reference. The RPT carries the result four times:
       Error in expression <[] TLB_CARP_fnc_copyLastCalibrationRun;>

4. A VEHICLE-IN-VEHICLE DROP LATCHED THE ENGINE'S OWN PARACHUTE

   Vanilla gives an in-flight viv unload its own canopy, which fn_releaseCargo sweeps within
   three seconds. The package tracker detects CHUTE by "attached to a ParachuteBase" and
   caught that one at 1005 m against a 300 m trigger -- TOT twelve seconds early, and the
   calibration run failed outright with TOUCHDOWN NOT DETECTED WITHIN 180S.

5. AND THAT SAME RELEASE PUBLISHED TWO GUIDED-CARGO JOBS FOR ONE LOAD

   Freeing a viv load removes it from the manifest; fn_releaseCargo then attaches it to the
   carrier for half a second, putting it back as an "attached" entry; the detach removes it
   again. fn_updatePackageTiming diffs the manifest, so one load departs twice. The wasted
   call also consumes the next slot index, so a later load of the stick flies to a pattern
   position nothing else is using.

None of this changes a solver constant, a release offset or any calibrated value. It changes
what can be SEEN.
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


LOGLONG = "addon/functions/debug/fn_logLong.sqf"
POLL = "addon/functions/debug/fn_pollCalibrationRun.sqf"
BEGIN = "addon/functions/debug/fn_beginCalibrationRun.sqf"
GUIDANCE = "addon/functions/guidance/fn_updateGuidance.sqf"
TIMING = "addon/functions/timing/fn_updatePackageTiming.sqf"
STEER = "addon/functions/jpads/fn_steerBegin.sqf"
POSTINIT = "addon/functions/fn_postInit.sqf"


class TruncationTests(unittest.TestCase):
    def test_the_splitter_exists_and_is_registered(self):
        """A new .sqf reaches the engine only through the compile table -- there is no other
        way to register one."""
        self.assertTrue(read(LOGLONG).strip())
        self.assertIn('["TLB_CARP_fnc_logLong", "', read(POSTINIT))

    def test_every_part_is_numbered_so_the_record_can_be_reassembled(self):
        """A split record that cannot be put back together is no better than a cut one."""
        src = code(LOGLONG)
        self.assertIn('diag_log format ["[TLB CARP][%1 %2/%3] %4"', src)
        self.assertIn("_forEachIndex + 1", src)

    def test_the_chunk_stays_clear_of_the_limit(self):
        """The engine's exact cap is undocumented and unmeasured. Sitting just under a
        number nobody has verified is how this bug survives its own fix."""
        src = code(LOGLONG)
        self.assertIn("#define CHUNK 820", src)

    def test_it_splits_on_the_records_own_lines_first(self):
        """So a wrapped part is still a whole field wherever one fits."""
        src = code(LOGLONG)
        self.assertIn("_text splitString _nl", src)
        self.assertIn("while {(count _rest) > CHUNK} do {", src)

    def test_both_long_records_go_through_it(self):
        self.assertIn('["CAL", _text] call TLB_CARP_fnc_logLong;', code(POLL))
        self.assertEqual(code(POLL).count("call TLB_CARP_fnc_logLong"), 2,
                         "the failure record needs it as much as the success one")
        self.assertIn('["DROP", format [', code(GUIDANCE))
        self.assertIn("call TLB_CARP_fnc_logLong", code(GUIDANCE))

    def test_no_long_record_is_still_written_the_old_way(self):
        self.assertNotIn('diag_log format ["[TLB CARP][CAL] %1", _text]', code(POLL))
        self.assertNotIn('diag_log format ["[TLB CARP][DROP] sim=', code(GUIDANCE))


class RecorderSourceTests(unittest.TestCase):
    def test_the_poll_watches_the_manifest_it_was_given(self):
        """THE DEFECT. initialCargo comes from the manifest; this compared it against
        usaf_cargo, so a viv or attached load matched on the first poll."""
        src = code(POLL)
        self.assertIn("private _currentCargo = [_carrier] call TLB_CARP_fnc_getLoadedCargo;", src)
        self.assertNotIn('_carrier getVariable ["usaf_cargo", []]', src)

    def test_both_halves_of_the_recorder_now_read_the_same_source(self):
        """They disagreed for a day. One function's list and another function's test are
        the same contract and have to be checked together."""
        self.assertIn("TLB_CARP_fnc_getLoadedCargo", code(BEGIN))
        self.assertIn("TLB_CARP_fnc_getLoadedCargo", code(POLL))


class HintTests(unittest.TestCase):
    def test_the_hint_is_something_the_pilot_can_actually_type(self):
        src = read(POLL)
        self.assertEqual(src.count("Run: [] call TLB_CARP_fnc_copyLastCalibrationRun"), 2)
        self.assertNotIn("Run TLB_CARP_fnc_copyLastCalibrationRun to copy it", src)


class ChuteDetectionTests(unittest.TestCase):
    def test_a_canopy_above_the_trigger_is_not_this_drops_canopy(self):
        """The engine's orphan viv parachute exists at release altitude for up to three
        seconds. A canopy seven hundred metres above the altitude that creates canopies is
        an instrument reading, not an event."""
        src = code(TIMING)
        self.assertIn('private _chuteCeilingM = (missionNamespace getVariable ["TLB_CARP_setting_canopyTriggerAglM", 300]) + 100;', src)
        self.assertIn('{_aglM <= _chuteCeilingM}', src)

    def test_the_margin_is_generous_rather_than_tight(self):
        """The real trigger is tested per frame at about 230 m/s, so a true event can land
        a few metres high. It can never land hundreds."""
        src = code(TIMING)
        self.assertIn('"TLB_CARP_setting_canopyTriggerAglM", 300]) + 100', src)


class OneJobPerLoadTests(unittest.TestCase):
    def test_a_load_can_only_publish_one_steer_job(self):
        src = code(STEER)
        self.assertIn('if (_cargo getVariable ["TLB_CARP_steerPublished", false]) exitWith {""};', src)
        self.assertIn('_cargo setVariable ["TLB_CARP_steerPublished", true, true];', src)

    def test_the_guard_runs_before_any_slot_index_is_consumed(self):
        """A duplicate call that exits after taking an index is worse than no guard: it
        silently shifts every later load in the stick onto the wrong slot."""
        src = code(STEER)
        self.assertLess(src.index('"TLB_CARP_steerPublished", false'),
                        src.index('"TLB_CARP_stickTotal"'))

    def test_the_stamp_is_public(self):
        """The release runs where the cargo is local, which need not be where the tracker
        that calls this is running."""
        self.assertIn('setVariable ["TLB_CARP_steerPublished", true, true]', code(STEER))


class NothingBallisticMovedTests(unittest.TestCase):
    def test_no_calibration_constant_is_touched(self):
        import json
        model = json.loads(read("calibration/model.json"))
        self.assertAlmostEqual(model["aircraft"]["c17"]["releaseDelayS"], 0.5607, places=6)
        self.assertAlmostEqual(model["multiCargo"]["sequenceIntervalS"], 0.5880, places=6)

    def test_the_release_sequence_is_untouched(self):
        src = code("addon/functions/cargo/fn_releaseCargo.sqf")
        self.assertIn("sleep 0.5;", src)
        self.assertIn("_cargo setVelocity (velocity _carrier);", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)

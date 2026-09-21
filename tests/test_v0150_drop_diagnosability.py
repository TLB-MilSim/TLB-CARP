"""v0.15.0 -- a drop that does not happen has to say why.

FLOWN, 2026-09-20, Blackfish. The pilot reported the aircraft never released.

WHAT THE LOG COULD ESTABLISH

    [TLB CARP][LOAD]    carrier=B_T_VTOL_01_vehicle_F method=viv     sim=944
    [TLB CARP][PROFILE] profile=generic doors=[]                     sim=~950
    [TLB CARP][AP]      disconnect reason=PILOT OVERRIDE             sim=1115
    [TLB CARP][DROP]    signedRp=-0.51 crossTrack=-0.27              sim=1219
    [TLB CARP][CAL]     no cargo loaded at cue                       sim=1219
    ... and no [TLB CARP][AUTO] start, ever.

So the load went aboard, the aircraft crossed the release point with 0.5 m of along error
and 0.3 m of cross-track, the cue fired -- which means `_crossed` and `_releaseStable` were
both true -- and fn_triggerAutoDrop was never called.

WHAT THE LOG COULD NOT ESTABLISH, AND THAT IS THE DEFECT

Between the cue and the trigger sit exactly two more gates: USAFDC_state_autoArmed and
USAFDC_state_dropLatched. Neither said anything. Neither did fn_armAutoDrop when it
succeeded, nor fn_validateAutoDrop when it refused -- a refusal reached the pilot as a hint
and the log not at all.

So "it did not drop" could not be resolved into "it was never armed" / "arming was refused
for reason X" / "it was armed and something later cleared it", which are three completely
different bugs. After the flight is when this is always diagnosed, and after the flight the
hint is gone.

This release does not guess at which one it was. It makes the next occurrence answerable in
one grep.

THE REAL BUG FOUND ON THE WAY

"[TLB CARP][CAL] no cargo loaded at cue" was literally true and completely wrong.
fn_beginCalibrationRun read `usaf_cargo` directly, so it was blind to vehicle-in-vehicle,
ACE, attached and CARP-loaded cargo -- three of four sources plus everything the v0.13.0
loader puts aboard.

v0.8.0 swept every usaf_cargo read into the manifest and left functions/debug/ exempt. That
exemption was for the harnesses that deliberately drive USAF's own path. It was never meant
to cover the recorder that runs on flown drops.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.exists() else ""


def code(rel: str) -> str:
    """Comments stripped, string literals intact."""
    sys.path.insert(0, str(ROOT / "tools"))
    from strip_sqf_comments import strip_comments

    path = ROOT / rel
    return strip_comments(path.read_text(encoding="utf-8")) if path.exists() else ""


ARM = "addon/functions/auto/fn_armAutoDrop.sqf"
DISARM = "addon/functions/auto/fn_disarmAutoDrop.sqf"
VALIDATE = "addon/functions/auto/fn_validateAutoDrop.sqf"
RECORDER = "addon/functions/debug/fn_beginCalibrationRun.sqf"
GUIDANCE = "addon/functions/guidance/fn_updateGuidance.sqf"


class RefusalIsLoggedTests(unittest.TestCase):
    def test_a_refused_validate_says_why(self):
        """A refusal the pilot sees as a hint and the log does not see at all cannot be
        diagnosed after the flight, which is when it is always diagnosed."""
        src = code(VALIDATE)
        self.assertIn("[TLB CARP][AUTO] validate refused:", src)

    def test_the_refusal_carries_every_gate_between_the_cue_and_the_trigger(self):
        """Naming only the reason would leave the same question one level down. These are
        the exact variables fn_updateGuidance tests before calling the trigger."""
        src = code(VALIDATE)
        for state in ["USAFDC_state_autoArmed", "USAFDC_state_dropLatched",
                      "USAFDC_state_guidanceArmed", "USAFDC_state_runInLocked",
                      "USAFDC_state_mode"]:
            self.assertIn(state, src, state)

    def test_the_gates_logged_are_the_gates_actually_tested(self):
        """If fn_updateGuidance grows a gate and this does not, the log goes back to being
        unable to answer the question."""
        gate_line = [ln for ln in code(GUIDANCE).splitlines()
                     if "USAFDC_fnc_triggerAutoDrop" in ln and "isNil" in ln]
        self.assertEqual(len(gate_line), 1, "the trigger gate moved -- re-check this test")
        for state in ["USAFDC_state_autoArmed", "USAFDC_state_dropLatched"]:
            self.assertIn(state, gate_line[0])
            self.assertIn(state, code(VALIDATE))

    def test_arming_is_logged_too(self):
        """Success as silent as failure is what made "was it even armed" unanswerable."""
        self.assertIn("[TLB CARP][AUTO] armed", code(ARM))

    def test_the_arm_log_records_what_would_be_dropped(self):
        """"Armed with nothing aboard" and "armed with four" fail differently."""
        src = code(ARM)
        self.assertIn("USAFDC_fnc_getLoadedCargo", src)

    def test_disarming_is_logged_only_when_it_changes_something(self):
        """fn_disarmAutoDrop is called on every refusal path in fn_triggerAutoDrop and on
        mode changes. Logging unconditionally would bury the real ones."""
        src = code(DISARM)
        self.assertIn('if (missionNamespace getVariable ["USAFDC_state_autoArmed", false]) then {', src)
        self.assertIn("[TLB CARP][AUTO] disarmed", src)


class RecorderSeesEverySourceTests(unittest.TestCase):
    def test_the_recorder_reads_the_manifest_not_usaf_cargo(self):
        """THE BUG. It was blind to vehicle-in-vehicle, ACE, attached and CARP-loaded
        cargo -- three of four sources plus everything the v0.13.0 loader puts aboard."""
        src = code(RECORDER)
        self.assertIn("[_carrier] call USAFDC_fnc_getLoadedCargo", src)
        self.assertNotIn('getVariable ["usaf_cargo"', src)

    def test_the_empty_message_names_the_carrier(self):
        """"no cargo loaded at cue" with a vehicle visibly in the hold read as a broken
        detector, which is exactly what it was."""
        self.assertIn("no cargo aboard at cue, carrier=", code(RECORDER))

    def test_the_debug_exemption_no_longer_hides_the_flown_recorder(self):
        """functions/debug/ is exempt from the manifest-discipline test. That exemption is
        for harnesses that deliberately drive USAF's own path -- fn_parallelDropBench calls
        USAF_CARGO_fnc_canDrop directly and must. The recorder runs on FLOWN drops and had
        no business inside it."""
        src = code(RECORDER)
        self.assertNotIn("usaf_cargo", src)

    def test_the_stale_compiled_sibling_is_pinned(self):
        """It was not in the PBO so the fix landed, but it sat in source next to the file
        being edited and one careless --include would have resurrected the old read."""
        self.assertIn("addon/functions/debug/fn_beginCalibrationRun.sqf",
                      read("tests/test_source_precedence.py"))
        self.assertFalse((ROOT / "addon/functions/debug/fn_beginCalibrationRun.sqfc").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)

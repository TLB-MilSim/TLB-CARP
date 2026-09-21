"""Stick drops (multi-cargo release) and the sequenceIntervalS calibration.

fn_buildWorldSolution centres a stick on the DZ by moving the RP upstream by half
the predicted stick length:
    spacingM    = groundSpeedMs * multiCargo.sequenceIntervalS
    stickLength = spacingM * (count - 1)
    firstLead   = stickLength * 0.5
so sequenceIntervalS alone decides whether a stick lands centred. It is 0.53 s and
flagged calibrationState "provisional".

The interval is script timing, not ballistics: fn_sequenceCargo commands canDrop,
waits for that load to leave usaf_cargo, then commands the next. USAF's
fn_dropCargo.sqf has a hardcoded `sleep 0.5` before it detaches and updates
usaf_cargo, and the measured single-drop lag is 0.601 s. If the true interval is
~0.61, a 5-load stick is ~45 m longer than predicted and mis-centred by ~22 m.
"""
from pathlib import Path
import json
import unittest

from tests.test_sqf_structure import strip_comments_and_strings

ROOT = Path(__file__).resolve().parents[1]
PROBE = "addon/functions/debug/fn_stickTimingProbe.sqf"
SEQ = "addon/functions/auto/fn_sequenceCargo.sqf"
SOLVER = "addon/functions/guidance/fn_buildWorldSolution.sqf"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class StickSolverContractTests(unittest.TestCase):
    def setUp(self):
        self.src = read(SOLVER)
        self.model = json.loads(read("calibration/model.json"))

    def test_stick_is_centred_on_the_dz(self):
        """Half the stick length upstream, so loads straddle the X rather than the
        first one landing on it."""
        self.assertIn("_firstReleaseLeadM = _stickLengthM * 0.5;", self.src)

    def test_stick_length_uses_the_model_interval_and_actual_groundspeed(self):
        self.assertIn('_sequenceIntervalS = _multiCargo getOrDefault ["sequenceIntervalS", 0.53]', self.src)
        self.assertIn('_spacingM = (_airState get "groundSpeedMs") * _sequenceIntervalS', self.src)
        self.assertIn("_stickLengthM = _spacingM * (_cargoSequenceCount - 1);", self.src)

    def test_oversized_stick_warns(self):
        """v0.16.3 REWROTE THIS, AND IT CAUGHT ITSELF PASSING VACUOUSLY.

        It used to assert the literal "FULL STICK CANNOT FIT 50 m DZ". When that message
        was replaced the test stayed GREEN -- because the replacement's comment quotes the
        old wording to record what changed. A substring test over a whole file is satisfied
        by prose, and this one silently stopped protecting anything for exactly as long as
        it took to notice.

        So it now reads the format string itself, off the pushBack line, where a comment
        cannot reach.

        The message changed because the old one was wrong in flight: it hardcoded "50" into
        text whose threshold is a model value, and it described the BALLISTIC stick even
        when guided slots were about to replace it."""
        line = [l for l in self.src.splitlines()
                if "_warnings pushBack format" in l and "PREDICTED" in l]
        self.assertEqual(len(line), 1, "one predicted-footprint warning")
        self.assertIn("WILL NOT FIT %4 m DZ", line[0])
        self.assertNotIn("50 m DZ", line[0], "the threshold is a model value, not text")

    def test_the_warning_describes_the_pass_that_will_happen(self):
        """THE FLOWN BUG. Two loads with JPADS on warned "PREDICTED STICK 65 m - FULL STICK
        CANNOT FIT 50 m DZ"; both landed inside a 50 m box. 65 m is the ballistic spread,
        which guided cargo replaces with a slot pattern jpadsStickSpacingM wide -- 35 m for
        two loads.

        It was never a borderline call: for two loads the ballistic figure exceeds 50 m
        above 85 m/s, and the calibrated drop band is 480-525 km/h, so this fired on every
        multi-cargo pass the system has ever flown."""
        self.assertIn("_slotSpacingM = missionNamespace getVariable "
                      '["USAFDC_setting_jpadsStickSpacingM", 35]', self.src)
        self.assertIn("_predictedFootprintM = if (_guidedSlots) then "
                      "{_slotSpacingM * (_cargoSequenceCount - 1)} else {_stickLengthM};",
                      self.src)

    def test_the_guided_predicate_mirrors_the_one_that_assigns_slots(self):
        """Two copies of a condition is how they drift, and this pair drifting would put a
        number on the HUD describing a pattern that was never assigned."""
        solver = [l.strip() for l in self.src.splitlines()
                  if "_guidedSlots =" in l and "USAFDC_state_jpadsEnabled" in l]
        self.assertEqual(len(solver), 1, "one place decides whether slots will be assigned")
        begin = read("addon/functions/jpads/fn_steerBegin.sqf")
        gate = [l.strip() for l in begin.splitlines()
                if "_spacing > 0" in l and "USAFDC_state_runInLocked" in l]
        self.assertEqual(len(gate), 1, "fn_steerBegin's slot gate moved -- re-pair them")
        for term in ["_slotSpacingM > 0", "USAFDC_state_runInLocked",
                     "USAFDC_state_jpadsEnabled"]:
            self.assertIn(term, solver[0])
        # steerBegin exits early on jpadsEnabled rather than testing it inline.
        self.assertIn('["USAFDC_state_jpadsEnabled", false]) exitWith', begin)

    def test_release_geometry_is_untouched_by_the_warning_change(self):
        """THE TRAP THAT WAS AVOIDED. Redefining _stickLengthM as the guided span would
        have halved _firstReleaseLeadM -- 32.5 m to 17.5 m on the flown pass -- moving the
        RP 15 m along-track on every guided stick. That is 0.14 s of release timing at
        110 m/s, and it would have surfaced later as an unexplained calibration bias.

        These two lines are the record that it did not happen. If either goes red, the
        display fix has reached into the solver and is wrong."""
        self.assertIn("_stickLengthM = _spacingM * (_cargoSequenceCount - 1);", self.src)
        self.assertIn("_firstReleaseLeadM = _stickLengthM * 0.5;", self.src)

    def test_interval_matches_the_measured_value(self):
        """0.5880 s from USAFDC_fnc_stickTimingProbe over 39 gaps / 10 reps, sd 0.0159.

        NOT 0.7603 -- that value shipped in v0.4.40 from a 12-gap sample which was the
        probe's first invocation and warm-up contaminated (reps trended
        0.788 -> 0.765 -> 0.728, sd 0.0646). A high sd relative to a later settled
        sample is the signal that a run is not yet representative.
        """
        mc = self.model["multiCargo"]
        self.assertAlmostEqual(mc["sequenceIntervalS"], 0.5880, places=6)

    def test_source_records_the_warmup_retraction(self):
        """The wrong value must stay documented so it is not re-derived."""
        src = self.model["multiCargo"].get("sequenceIntervalSource", "")
        self.assertIn("0.7603", src)
        self.assertIn("warm-up", src)

    def test_calibration_state_records_what_is_and_is_not_verified(self):
        """The interval is measured; the resulting stick CENTRING has not been checked
        against landing positions, so this must not claim to be fully calibrated."""
        mc = self.model["multiCargo"]
        self.assertEqual(mc["calibrationState"], "interval-measured")
        src = mc.get("sequenceIntervalSource", "")
        self.assertIn("STILL UNVERIFIED", src)
        self.assertIn("firstReleaseDelayS", src)

    def test_measured_interval_exceeds_the_single_drop_lag(self):
        """Sanity check on the mechanism: fn_sequenceCargo is serial, so each gap is
        the previous load's detection plus a full canDrop cycle. An interval at or
        below the single-drop lag would mean the probe measured the wrong thing."""
        self.assertGreater(
            self.model["multiCargo"]["sequenceIntervalS"],
            self.model["aircraft"]["c17"]["releaseDelayS"],
        )


class SequenceCargoTests(unittest.TestCase):
    def setUp(self):
        self.src = read(SEQ)

    def test_waits_for_each_load_to_clear_before_commanding_the_next(self):
        """Commanding them all at once would leave the per-load scripts racing.

        v0.8.0 changed WHAT is counted, not the waiting. The manifest spans every
        carriage source, so a sequence over a mixed bay now sees each load leave;
        reading usaf_cargo alone, a non-USAF load never appeared to clear and every
        iteration ran to its 3 s timeout.
        """
        self.assertIn("_after = count ([_carrier] call USAFDC_fnc_getLoadedCargo)", self.src)
        self.assertIn("(_after < _before)", self.src)

    def test_uses_the_same_drop_entry_point_as_a_single_release(self):
        """Still one entry point for one load and for a stick -- it is just no longer
        USAF's own function called directly.

        fn_releaseSelected routes a USAF airframe carrying USAF-loaded cargo straight
        back to USAF_CARGO_fnc_canDrop, so the calibrated path is unchanged; anything
        else takes CARP's release. What matters here is that the sequencer and the
        single release cannot drift apart, which is why both go through the same call.
        """
        self.assertIn("USAFDC_fnc_releaseSelected", self.src)
        self.assertNotIn("spawn USAF_CARGO_fnc_canDrop", self.src)

    def test_per_load_timeout_is_bounded_and_logged(self):
        self.assertIn("cargo sequence timeout", self.src)


class StickTimingProbeTests(unittest.TestCase):
    def setUp(self):
        self.src = read(PROBE)
        self.code = strip_comments_and_strings(self.src)

    def test_probe_is_registered_for_runtime_compilation(self):
        """config.bin is pre-binarized, so a new function reaches the engine only via
        the fn_postInit compile table."""
        post = read("addon/functions/fn_postInit.sqf")
        self.assertIn('["USAFDC_fnc_stickTimingProbe", "', post)
        sep = chr(92)  # literal backslash; the SQF path separator
        self.assertIn(sep.join(["functions", "debug", "fn_stickTimingProbe.sqf"]), post)

    def test_release_times_are_stamped_per_frame(self):
        """A 0.05 s scheduled poll would quantise a ~0.6 s interval by up to 8% --
        the same order as the discrepancy being measured."""
        handler = self.src[self.src.index('addMissionEventHandler ["EachFrame"'):]
        self.assertIn('_x setVariable ["USAFDC_stickReleaseTime", time, false]', handler)

    def test_each_load_is_stamped_only_once(self):
        self.assertIn('isNil {_x getVariable "USAFDC_stickReleaseTime"}', self.src)

    def test_doors_are_opened_before_commanding(self):
        """Commanding in the same frame as the animate adds the door animation to the
        measured interval; the parallel bench needed the same correction."""
        self.assertIn("animationPhase", self.src)
        self.assertLess(self.src.index("animationPhase"), self.src.index("spawn USAFDC_fnc_sequenceCargo"))

    def test_intervals_are_computed_from_sorted_times(self):
        """Stamps arrive in frame order but the list must not be assumed ordered."""
        self.assertIn("_times sort true;", self.src)

    def test_reports_the_model_error_in_metres(self):
        self.assertIn("stickErrorM_per_gap", self.src)
        self.assertIn("modelIntervalS", self.src)

    def test_discards_a_warmup_repetition(self):
        """The probe's first invocation is measurably slower and produced the wrong
        value that shipped in v0.4.40. The warm-up must be excluded from the summary
        and labelled in the log, not left for the reader to spot."""
        self.assertIn('for "_rep" from 0 to _repeats do', self.src)
        self.assertIn("private _isWarmup = (_rep isEqualTo 0);", self.src)
        self.assertIn("if (!_isWarmup) then {_allIntervals append _intervals};", self.src)
        self.assertIn("[WARMUP - DISCARDED]", self.src)

    def test_refuses_a_single_load(self):
        """One load yields no interval at all."""
        self.assertIn("if (_cargoCount < 2) exitWith", self.src)

    def test_cleans_up_handler_and_objects(self):
        self.assertIn('removeMissionEventHandler ["EachFrame", USAFDC_state_stickProbeEh]', self.src)
        self.assertIn("deleteVehicle _carrier;", self.src)
        self.assertIn("USAFDC_state_stickProbeActive = false;", self.src)

    def test_state_globals_are_initialised(self):
        post = read("addon/functions/fn_postInit.sqf")
        for g in ("USAFDC_state_stickProbeActive", "USAFDC_state_stickProbeEh",
                  "USAFDC_state_stickProbePin", "USAFDC_state_stickProbeStamps"):
            self.assertIn(f"{g} = ", post)

    def test_does_not_use_setpos_as_a_position_rail_on_cargo(self):
        """Project invariant: the pin may drive the carrier, never the load. Every
        setPos in this file must target a carrier."""
        for line in self.src.splitlines():
            if "setPos" not in line or line.strip().startswith("//"):
                continue
            self.assertIn("arrier", line, f"setPos on a non-carrier: {line.strip()}")


class MultiAircraftHarnessTests(unittest.TestCase):
    """The harnesses hardcoded USAF_C17, so the C-130 could not be measured at all.
    Carrier class now comes from the profile's classNames."""

    def test_bench_takes_an_aircraft_id(self):
        src = read("addon/functions/debug/fn_parallelDropBench.sqf")
        self.assertIn('["_aircraftId", "c17", [""]]', src)
        self.assertIn("13 aircraftId", src)
        self.assertNotIn('createVehicle ["USAF_C17"', src)

    def test_bench_resolves_class_from_the_profile_and_refuses_early(self):
        src = read("addon/functions/debug/fn_parallelDropBench.sqf")
        self.assertIn('_carrierProfile getOrDefault ["classNames", []]', src)
        self.assertIn("Unknown aircraft profile", src)
        self.assertIn("Missing class", src)

    def test_bench_logs_which_airframe_and_calibration_state(self):
        """A batch flown on a borrowed profile must be identifiable in the log."""
        src = read("addon/functions/debug/fn_parallelDropBench.sqf")
        self.assertIn("aircraft=%2 class=%3 calibrationState=%4", src)

    def test_solution_builder_takes_an_aircraft_id(self):
        src = read("addon/functions/debug/fn_buildDebugDropSolution.sqf")
        self.assertIn('["_aircraftId", "c17", [""]]', src)
        self.assertIn('_aircraftProfiles getOrDefault [_aircraftId, createHashMap]', src)
        self.assertIn('["aircraft", _aircraftId],', src)
        self.assertNotIn('"CfgVehicles" >> "USAF_C17"', src)

    def test_every_profile_state_in_the_model_is_accepted_by_both_gates(self):
        """Two independent accepted-state lists exist -- fn_solveRelative for flight
        and fn_buildDebugDropSolution for the harnesses. v0.4.45 added
        "zero-wind-measured" to the solver but not the harness, so the C-130 became
        solvable in flight and unmeasurable on the bench: all 16 runs returned
        SOLVE FAILED. Cross-check both against what the model actually declares.
        """
        import re
        model = json.loads(read("calibration/model.json"))
        states = {p.get("calibrationState") for p in model["aircraft"].values()}
        states.discard("uncalibrated")   # deliberately refused by both
        self.assertTrue(states, "no calibrated profiles to check")

        def accepted(rel):
            src = read(rel)
            found = set()
            for m in re.finditer(r'in \[((?:\s*"[a-z-]+"\s*,?)+)\]', src):
                for s in re.findall(r'"([a-z-]+)"', m.group(1)):
                    found.add(s)
            return found

        solver = accepted("addon/functions/solver/fn_solveRelative.sqf")
        harness = accepted("addon/functions/debug/fn_buildDebugDropSolution.sqf")
        for state in states:
            self.assertIn(state, solver, f"fn_solveRelative rejects {state}")
            self.assertIn(state, harness, f"fn_buildDebugDropSolution rejects {state}")
        # Both gates must list exactly the same states, not merely cover the model's.
        self.assertEqual(solver, harness, "accepted-state lists have drifted apart")
        # And the sets must be non-empty, or this test passes vacuously.
        self.assertTrue(solver, "no accepted states parsed from fn_solveRelative")

    def test_stick_probe_takes_an_aircraft_id(self):
        src = read("addon/functions/debug/fn_stickTimingProbe.sqf")
        self.assertIn('["_aircraftId", "c17", [""]]', src)
        self.assertNotIn("USAF_C17", src)

    def test_stick_probe_reads_doors_from_the_actual_carrier(self):
        """Door names differ per airframe; the C-130 uses ramp_top/ramp_bottom."""
        src = read("addon/functions/debug/fn_stickTimingProbe.sqf")
        self.assertIn('_carrierClass >> "USAF_Cargo_Doors"', src)

    def test_default_stays_c17_everywhere(self):
        """Existing commands must keep working unchanged."""
        for rel in ("addon/functions/debug/fn_parallelDropBench.sqf",
                    "addon/functions/debug/fn_buildDebugDropSolution.sqf",
                    "addon/functions/debug/fn_stickTimingProbe.sqf"):
            self.assertIn('["_aircraftId", "c17", [""]]', read(rel), rel)


class DoorAnimationChannelTests(unittest.TestCase):
    """The C-17 ramp is an animation; the C-130's ramp_top/ramp_bottom are
    AnimationSources, and `animate` does nothing to them.

    A v0.4.42 C-130 batch logged phases=["0.00" x5] after 20 s of waiting, so USAF's
    own canDrop then spent ~10 s opening the ramp itself and every load released
    10.5 s late -- roughly 2800 m downrange, with a radial "miss" of 2830 m. Both
    channels must be driven and both accepted as open."""

    HARNESSES = ("addon/functions/debug/fn_parallelDropBench.sqf",
                 "addon/functions/debug/fn_stickTimingProbe.sqf")

    def test_both_animation_channels_are_driven(self):
        for rel in self.HARNESSES:
            src = read(rel)
            self.assertIn("_carrier animate [_x, 1, true];", src, rel)
            self.assertIn("_carrier animateSource [_x, 1, true];", src, rel)

    def test_either_channel_counts_as_open(self):
        """Requiring animationPhase alone is what hung the C-130."""
        for rel in self.HARNESSES:
            src = read(rel)
            self.assertIn("(_carrier animationSourcePhase _x) < 0.99", src, rel)

    def test_timeout_message_reports_both_phases(self):
        """Reporting only one channel would hide which mechanism failed -- the
        all-zero animationPhase list is exactly what identified this."""
        src = read("addon/functions/debug/fn_parallelDropBench.sqf")
        self.assertIn("(_carrier animationSourcePhase _x) toFixed 2", src)


class C130CarrierVariantTests(unittest.TestCase):
    """The harnesses spawn classNames[0], so it must be the variant actually flown.
    A base class can differ in doors and cargo config: USAF_C130J lists 5 cargo doors
    against the 2 on USAF_C130J_Cargo."""

    def setUp(self):
        self.c130 = json.loads(read("calibration/model.json"))["aircraft"]["c130"]

    def test_flown_variant_is_first(self):
        self.assertEqual(self.c130["classNames"][0], "USAF_C130J_Cargo")

    def test_base_class_is_still_recognised(self):
        """Profile resolution must still match a pilot in any variant."""
        self.assertIn("USAF_C130J", self.c130["classNames"])

    def test_reason_is_recorded(self):
        self.assertIn("classNames[0]", self.c130.get("profileSource", ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
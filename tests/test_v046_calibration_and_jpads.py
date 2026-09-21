"""v0.4.6: measured calibration correction, plus guided cargo (JPADS).

Calibration
-----------
The canopy table was fitted from `c17_controlled_observations_v1.json`, which
held exactly **one** observation per condition. Canopy duration is bimodal in
Arma (see the accuracy analysis), so roughly a fifth of those single samples
caught the short mode and baked it into the table. The heading-0 / south-5 entry
was one of them: it predicted 21.84 s where 5 fresh harness runs measure 24.52 s
(sd 0.22), and it poisoned both interpolations whose brackets touch it.

Release timing was re-measured from 10 zero-wind runs at two ground speeds.

JPADS
-----
Guided cargo steers the canopy onto the DZ after chute open. It must never
become a position rail, must not touch vertical speed, and must be off by
default so the unguided ballistic path stays the baseline.
"""
from pathlib import Path
import json
import unittest

from tests.test_sqf_structure import strip_comments_and_strings

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.exists() else ""


def code(rel: str) -> str:
    """Executable SQF only -- prose in comments is not a position rail."""
    return strip_comments_and_strings(read(rel))


class CanopyTableCorrectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.emp = json.loads(read("calibration/model.json"))["canopy"]["empiricalC17"]
        cls.obs = json.loads(read("calibration/c17_controlled_observations_v1.json"))

    def test_south5_heading0_entry_matches_the_five_run_remeasurement(self):
        zero_t = self.emp["zeroTimeS"][0]
        self.assertAlmostEqual(zero_t + self.emp["south5TimeDeltaS"][0], 24.515, places=2)

    def test_other_heading0_axis_entries_are_untouched(self):
        """Those three exact lookups measured accurate to +/-0.22 s, so they must
        not be 'corrected' along with the bad one."""
        zero_t = self.emp["zeroTimeS"][0]
        for key, expected in (("north5TimeDeltaS", 29.966), ("east5TimeDeltaS", 24.854),
                              ("west5TimeDeltaS", 24.610)):
            self.assertAlmostEqual(zero_t + self.emp[key][0], expected, places=2, msg=key)

    def test_superseded_observation_records_its_sample_count(self):
        row = next(o for o in self.obs if o["headingDeg"] == 0.0
                   and o["windWorldMs"] == [0, -5, 0] and o["cargoClass"] == "rhsusf_mrzr4_d")
        self.assertEqual(row["sampleCount"], 5)
        self.assertAlmostEqual(row["canopyDurationS"], 24.515, places=2)

    def test_c130_zero_wind_baseline_is_measured_not_borrowed(self):
        """The C-130 was populated as provisional-borrowed on 2026-09-01 so it could
        be MEASURED. 48 bench runs (8 headings x n=6, verified zero wind, chuteAgl
        293.7-299.9 on every run, 0 degraded) produced empiricalC130, taking the
        zero-wind canopy residual from 5.47 m to 3.21 m.

        The project invariant is that C-17 empirical results must not be copied to the
        C-130 and PRESENTED as its calibration. This table is forked from the C-17's
        but its zero-wind baseline now carries C-130 measurements, and everything still
        borrowed is named as such in the source note and in the runtime warning.
        """
        model = json.loads(read("calibration/model.json"))
        c130 = model["aircraft"]["c130"]
        self.assertEqual(c130["calibrationState"], "zero-wind-measured")
        self.assertEqual(c130["canopyRef"], "empiricalC130")
        table = model["canopy"]["empiricalC130"]
        self.assertEqual(table["modelId"], "EMPIRICAL_C130_V1")
        src = table.get("source", "")
        self.assertIn("n=6", src)
        self.assertIn("STILL BORROWED AND UNMEASURED", src)

    def test_c130_wind_predictions_match_the_borrowed_tables(self):
        """Shifting the baseline without counter-shifting the deltas double-corrects
        every wind case -- the error made in v0.4.26 and corrected in v0.4.27. The
        counter-shift means measured C-130 wind behaviour (26.30 m at 5 m/s diagonal,
        indistinguishable from the C-17) is preserved exactly."""
        model = json.loads(read("calibration/model.json"))
        c17 = model["canopy"]["empiricalC17"]
        c130 = model["canopy"]["empiricalC130"]
        anchors = c17["headingAnchorsDeg"]
        for direction in ("east", "north", "south", "west"):
            key = f"{direction}5CorrectionWorldM"
            for i, h in enumerate(anchors):
                base_delta = c17["zeroWorldM"][i][0] + c17[key][i][0]
                new_delta = c130["zeroWorldM"][i][0] + c130[key][i][0]
                self.assertAlmostEqual(base_delta, new_delta, delta=2e-3,
                                       msg=f"{key} heading {h} axis E")

    def test_ten_ms_anchor_grid_caveat_is_recorded(self):
        """The 10 m/s deltas use a 4-entry cardinal grid while the baseline uses 8, so
        the counter-shift cancels exactly only at 0/90/180/270 -- up to 8.47 m
        elsewhere. Documented rather than silently accepted."""
        src = json.loads(read("calibration/model.json"))["canopy"]["empiricalC130"]["source"]
        self.assertIn("8.47", src)
        self.assertIn("cardinalHeadingAnchorsDeg", src)

    def test_no_solve_raises_a_calibration_warning_any_more(self):
        """WAS: the borrowed-wind-table warning fires in wind and not at zero wind.

        v0.14.0 removed the DEGRADED tier on the project owner's flown evidence: the C-17
        model held against the C-17, the C-130 and the V-44 Blackfish, and guided cargo
        absorbs the residual. A warning that fired on every drop of every airframe was
        furniture, not information.

        The borrowed wind tables are still borrowed -- that fact did not change, only
        where it is recorded. It lives in the C-130's profileSource note in model.json,
        where somebody changing the number reads it, instead of on the HUD where a pilot
        read it on every drop and learned to read past it."""
        solver = code("addon/functions/solver/fn_solveRelative.sqf")
        for gone in [
            "WIND TABLES BORROWED", "CANOPY TABLE BORROWED", "SPEED OUTSIDE CALIBRATED RANGE",
            "WIND ABOVE EMPIRICAL RANGE", "LOW-ENERGY CANOPY PROFILE NOT FULLY CALIBRATED",
        ]:
            self.assertNotIn(gone, solver)
        self.assertIn('private _warnings = [];', solver)
        # Still recorded where it belongs.
        import json
        model = json.loads((ROOT / "calibration" / "model.json").read_text(encoding="utf-8"))
        self.assertIn("hypothesis", model["aircraft"]["c130"]["profileSource"])

    def test_a_successful_solve_reports_good_and_there_is_no_other_tier(self):
        """WAS: borrowed profiles can never report GOOD.

        v0.14.0 removed the DEGRADED tier on the project owner's flown evidence: the C-17
        model held against the C-17, the C-130 and the V-44 Blackfish, and guided cargo
        absorbs the residual. A warning that fired on every drop of every airframe was
        furniture, not information.

        What this test protects now is the half that did NOT go: the line between a rough
        answer and NO answer. Every genuine failure still exits INVALID before confidence
        is reached, and those are the checks that stop a drop."""
        # read(), not code(): this module's code() strips string LITERALS as well as
        # comments, so every assertion below about a quoted value has to see the raw file.
        # The negatives are quoted for the same reason -- DEGRADED appears in the comment
        # that explains its removal, and matching the bare word would fail on the
        # explanation rather than on the behaviour.
        solver = read("addon/functions/solver/fn_solveRelative.sqf")
        self.assertIn('private _confidence = "GOOD";', solver)
        self.assertNotIn('"DEGRADED"', solver)
        self.assertNotIn('"%1 PROFILE PROVISIONAL', solver)
        self.assertNotIn('pushBackUnique', solver)
        # The refusals that matter, all still ahead of the GOOD.
        good = solver.index('private _confidence = "GOOD";')
        for refusal in [
            '"UNSUPPORTED AIRCRAFT PROFILE"',
            '"AIRCRAFT PROFILE NOT CALIBRATED"',
            '"EMPIRICAL CANOPY MODEL NOT AVAILABLE FOR AIRCRAFT"',
        ]:
            self.assertIn(refusal, solver)
            self.assertLess(solver.index(refusal), good, refusal)

    def test_every_empirical_table_has_measurements_behind_it(self):
        """A table appearing without a documented measurement campaign would be the
        invariant violation this arrangement exists to prevent."""
        model = json.loads(read("calibration/model.json"))
        empirical = sorted(k for k in model["canopy"] if k.startswith("empirical"))
        self.assertEqual(empirical, ["empiricalC130", "empiricalC17"])
        for name in empirical:
            table = model["canopy"][name]
            note = table.get("source", "") + table.get("zeroWorldMSource", "")
            self.assertIn("runs", note, f"{name} has no measurement provenance")

    def test_the_two_tables_are_not_identical(self):
        """If the fork carried no C-130 measurements it would be a copy wearing a new
        name, which is worse than borrowing openly."""
        model = json.loads(read("calibration/model.json"))
        self.assertNotEqual(
            model["canopy"]["empiricalC17"]["zeroWorldM"],
            model["canopy"]["empiricalC130"]["zeroWorldM"],
        )


class JpadsGuidedCargoTests(unittest.TestCase):
    def test_steers_with_velocity_never_position(self):
        self.assertIn("setVelocity", read("addon/functions/jpads/fn_steerCargo.sqf"))
        text = code("addon/functions/jpads/fn_steerCargo.sqf")
        self.assertNotIn("setPos", text)
        self.assertNotIn("setPosASL", text)
        self.assertNotIn("setPosATL", text)

    def test_vertical_speed_is_passed_through_untouched(self):
        text = read("addon/functions/jpads/fn_steerCargo.sqf")
        self.assertIn("_vz = _vel # 2", text)
        self.assertIn("setVelocity [_cmdE, _cmdN, _vz]", text)

    def test_only_runs_while_the_canopy_is_open(self):
        """Still gated on the canopy being open -- but on an OBSERVABLE FACT now.

        v0.8.1 replaced `USAFDC_state_packageTimingState isEqualTo "CHUTE"` with the
        thing that global was standing in for: is the load hanging under a
        ParachuteBase. The global is written only by the guidance loop, on a client,
        with a panel open. A dedicated server has no such thing, and on a dedicated
        server the server is normally the machine that OWNS the canopy and therefore the
        only one whose setVelocity does anything -- so the old gate meant guided cargo
        could never run on the one machine able to run it.

        The replacement is strictly stricter: the tracker reached CHUTE by testing
        exactly this attachment (fn_updatePackageTiming), so anything that satisfied the
        old gate satisfies the new one, and a load whose chute has not yet attached can
        no longer slip through on a stale tracker state.
        """
        self.assertIn('isKindOf "ParachuteBase"', read("addon/functions/jpads/fn_steerCargo.sqf"))
        self.assertNotIn("packageTimingState", code("addon/functions/jpads/fn_steerCargo.sqf"))

    def test_everything_the_control_law_needs_is_passed_in(self):
        """It has to run on a machine that has no CARP state and no CBA settings.

        The canopy usually belongs to the dedicated server, and setVelocity only works
        where the object is local -- so the server is the machine that must steer, and
        it has no USAFDC_state_dzPosASL and reads every USAFDC_setting_jpads* as its
        scope-0 default. Anything this function looked up for itself would be wrong
        there, silently. It is handed the DZ and all four parameters instead, and reads
        the settings only as defaults for callers that do have them.
        """
        text = code("addon/functions/jpads/fn_steerCargo.sqf")
        for name in ["_cargo", "_dz", "_glideMs", "_scatterM", "_releaseAglM", "_engageVzMs"]:
            self.assertIn(name, text)
        self.assertNotIn("USAFDC_state_packagePrimaryCargo", text)
        self.assertNotIn("USAFDC_state_dzPosASL", text)
        self.assertNotIn("USAFDC_setting_jpadsEnabled", text)

    def test_the_bench_entry_point_is_unchanged(self):
        """fn_parallelDropBench calls `[_x, _sdz] call USAFDC_fnc_steerCargo` per frame
        for many loads, and gates on its own flag rather than the CBA setting."""
        text = read("addon/functions/jpads/fn_steerCargo.sqf")
        self.assertIn('["_cargo", objNull, [objNull]]', text)
        self.assertIn('["_dz", [], [[]]]', text)
        self.assertIn("[_x, _sdz] call USAFDC_fnc_steerCargo",
                      read("addon/functions/debug/fn_parallelDropBench.sqf"))

    def test_aim_offset_is_stored_per_load_and_broadcast(self):
        """Per load, because concurrent packages would overwrite each other's offset.

        BROADCAST as of v0.8.1, because the machine that steers and the machines that
        display the closing error are no longer the same machine. A local-only offset
        left every other client's readout wrong by up to the scatter radius while the
        load flew perfectly.
        """
        text = read("addon/functions/jpads/fn_steerCargo.sqf")
        self.assertIn('_cargo getVariable ["USAFDC_jpadsTargetOffset", []]', text)
        self.assertIn('_cargo setVariable ["USAFDC_jpadsTargetOffset", _offset, true]', text)

    def test_the_control_law_writes_no_hud_state_at_all(self):
        """A bench run steering one of many loads must not drive the pilot's HUD -- and
        now neither must a SERVER steering the crew's load.

        The readout moved to fn_steerTick, which writes it only on a machine with a
        screen and only for the load that machine's own tracker calls the live package.
        Every input is locally visible, so nothing about the HUD line crosses the wire.
        """
        text = code("addon/functions/jpads/fn_steerCargo.sqf")
        for global_name in [
            "USAFDC_state_jpadsActive", "USAFDC_state_jpadsPhase", "USAFDC_state_jpadsErrorM",
            "USAFDC_state_jpadsClosingMs", "USAFDC_state_jpadsGroundMs",
            "USAFDC_state_jpadsTimeRemainingS",
        ]:
            self.assertNotIn(global_name, text)
        tick = code("addon/functions/jpads/fn_steerTick.sqf")
        self.assertIn("hasInterface", tick)
        self.assertIn("_cargo isEqualTo _live", tick)

    def test_steers_the_parachute_when_the_load_is_slung_under_one(self):
        text = read("addon/functions/jpads/fn_steerCargo.sqf")
        self.assertIn("attachedTo _cargo", text)
        self.assertIn('isKindOf "ParachuteBase"', text)

    def test_aim_scatter_keeps_loads_off_dead_centre(self):
        text = read("addon/functions/jpads/fn_steerCargo.sqf")
        self.assertIn("USAFDC_jpadsTargetOffset", text)
        self.assertIn("_scatterM", text)
        self.assertIn("random", text)
        # Carried in the job so the steering machine uses the PILOT's value.
        self.assertIn("jpadsScatterM", read("addon/functions/jpads/fn_steerBegin.sqf"))

    def test_last_metres_are_unguided(self):
        text = read("addon/functions/jpads/fn_steerCargo.sqf")
        self.assertIn("jpadsReleaseAglM", text)

    def test_commanded_airspeed_is_capped_by_glide(self):
        text = read("addon/functions/jpads/fn_steerCargo.sqf")
        self.assertIn("jpadsGlideMs", text)
        self.assertIn("_airM > _glideMs", text)
        self.assertIn("_glideMs / _airM", text)

    def test_disabled_by_default_and_registered_at_runtime(self):
        """OFF BY DEFAULT IS THE INVARIANT; where the switch lives is not. v0.11.1 moved
        it from a per-client Addon Option to a panel toggle shared with the crew, because
        a per-client switch let the two seats disagree about whether the load they are
        both dropping is guided."""
        post_init = read("addon/functions/fn_postInit.sqf")
        self.assertIn("USAFDC_state_jpadsEnabled = false;", post_init,
                      "guided cargo must default to off")
        self.assertNotIn("USAFDC_setting_jpadsEnabled", post_init)
        self.assertIn("USAFDC_fnc_steerCargo", post_init)
        self.assertIn("jpads\\fn_steerCargo.sqf", post_init)

    def test_steering_runs_per_frame_not_on_the_guidance_tick(self):
        """v0.4.6 ran it at the 0.05 s guidance interval and only 41% of the
        commanded closing speed survived -- the parachute's physics reasserted
        between calls. Measured: 8.0 m/s commanded, 3.28 m/s achieved."""
        post_init = read("addon/functions/fn_postInit.sqf")
        self.assertIn('addMissionEventHandler ["EachFrame"', post_init)
        self.assertIn("USAFDC_state_jpadsEh", post_init)
        guidance = read("addon/functions/guidance/fn_updateGuidance.sqf")
        self.assertEqual(guidance.count("call USAFDC_fnc_steerCargo"), 0,
                         "the per-frame handler owns steering; guidance must not double-apply")

    def test_solver_authority_is_untouched(self):
        """Guided cargo is additive: it must not write solver or path state."""
        text = read("addon/functions/jpads/fn_steerCargo.sqf")
        for forbidden in ("USAFDC_state_solution", "USAFDC_state_displaySolution",
                          "USAFDC_state_pathSolution", "releaseStable"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class JpadsInflationGateTests(unittest.TestCase):
    """v0.4.6 first flight: steering engaged at chute attach while the load was
    still doing 140 m/s, clamped horizontal speed to ~6 m/s, and deleted 72.7 m
    of natural forward throw -- landing 93 m out where unguided landed 16 m.
    Instantaneous vertical speed also read ~3 s to ground when 26 s remained."""

    def test_steering_waits_for_near_terminal_descent(self):
        """Unchanged in substance. The threshold is now a passed parameter rather than a
        CBA setting read in place, because the machine that steers is usually the server
        and reads every scope-0 setting as its default."""
        text = read("addon/functions/jpads/fn_steerCargo.sqf")
        self.assertIn("_vz < -_engageVzMs", text)
        self.assertIn("jpadsEngageVzMs", read("addon/functions/jpads/fn_steerBegin.sqf"))

    def test_inflation_phase_is_reported_not_silently_skipped(self):
        """The phase is still distinguished from "not steering"; it is now returned to
        the caller instead of written to a global, so a server that has no HUD can still
        report it and fn_steerTick can put it on the screens that do."""
        law = read("addon/functions/jpads/fn_steerCargo.sqf")
        self.assertIn('"INFLATING"', law)
        self.assertIn('"STEERING"', law)
        self.assertIn('["phase", "STEERING"]', law)
        self.assertIn('_result get "phase"', read("addon/functions/jpads/fn_steerTick.sqf"))
        self.assertIn("USAFDC_state_jpadsPhase = _phase;", read("addon/functions/jpads/fn_steerTick.sqf"))

    def test_engage_gate_defaults_above_terminal_descent(self):
        post_init = read("addon/functions/fn_postInit.sqf")
        line = next(l for l in post_init.splitlines() if "jpadsEngageVzMs" in l and "CBA_fnc_addSetting" in l)
        self.assertIn("[5, 30, 12, 0]", line, "terminal descent is ~4-6 m/s; the gate must sit above it")


class JpadsParafoilLawTests(unittest.TestCase):
    """v0.4.8 flight: the gate and the per-frame handler both worked (error fell
    46.4 -> 8.7 m), then the error grew back to 21.6 m. Cause: the command was
    wind + direction*closing, so ground speed could never fall below wind speed
    and the load could not hold against a 5.5 m/s wind once the steering term
    shrank with the error."""

    def test_solves_for_airspeed_against_wind(self):
        text = read("addon/functions/jpads/fn_steerCargo.sqf")
        self.assertIn("_airE = _reqE - (_wind # 0)", text)
        self.assertIn("_airN = _reqN - (_wind # 1)", text)
        self.assertIn("_airM > _glideMs", text)

    def test_no_longer_commands_wind_plus_direction_times_closing(self):
        text = code("addon/functions/jpads/fn_steerCargo.sqf")
        self.assertNotIn("_dirE", text)
        self.assertNotIn("_dirN", text)

    def test_reports_both_airspeed_and_ground_speed(self):
        """Both still reach the HUD; the control law returns them rather than writing
        them, because it may be running on a machine with no HUD to write to."""
        law = read("addon/functions/jpads/fn_steerCargo.sqf")
        self.assertIn('["closingMs", _airM]', law)
        self.assertIn('["groundMs"', law)
        tick = read("addon/functions/jpads/fn_steerTick.sqf")
        self.assertIn("USAFDC_state_jpadsGroundMs", tick)
        self.assertIn("USAFDC_state_jpadsClosingMs", tick)

    def test_steers_almost_to_the_ground(self):
        """A 15 m release left ~19 m of unguided drift in a 5.5 m/s wind. The
        random aim offset is what provides deliberate scatter, not this."""
        post_init = read("addon/functions/fn_postInit.sqf")
        line = next(l for l in post_init.splitlines() if "jpadsReleaseAglM" in l and "CBA_fnc_addSetting" in l)
        self.assertIn("[0, 60, 3, 0]", line)


class HudCuePlacementTests(unittest.TestCase):
    """STANDBY / DROP / NO DROP is the one line the pilot cannot afford to lose,
    and at the end of the block it was the first thing to clip -- reported in
    v0.4.9 flight. It now sits directly under the centred run-in status."""

    def test_cue_has_its_own_reserved_row(self):
        """The cue used to be appended to the status line, so the panel grew and every
        row below it shifted the moment STANDBY appeared. It now owns a row that is
        ALWAYS rendered -- a single pad character when idle -- so nothing moves.
        """
        text = read("addon/functions/ui/fn_updateHud.sqf")
        self.assertIn("private _cueText = PAD_CHAR;", text)
        cue_push = text.index("align='center' color='%2'>%3</t>")
        self.assertLess(cue_push, text.index('"ALT"'), "cue must precede the ALT row")
        self.assertGreater(cue_push, text.index('"TRK"'), "cue must follow the TRK row")

    def test_every_font_size_derives_from_hud_scale(self):
        """The reported bug: cue and flight-director glyphs were hardcoded at 1.20 /
        1.45 / 1.25 / 1.35 while body rows multiplied by _scale, so at hudScale 0.7
        the cue was ~3x the body and overflowed a container that had shrunk with it.
        No literal size may remain in the rendered markup.
        """
        text = read("addon/functions/ui/fn_updateHud.sqf")
        import re
        literals = re.findall(r"size='(\d[\d.]*)'", text)
        self.assertEqual(literals, [], f"hardcoded font sizes remain: {literals}")
        for step in ("_fLabel = 0.66 * _scale", "_fData = 0.94 * _scale",
                     "_fCue = 1.28 * _scale", "_fGlyph = 1.28 * _scale"):
            self.assertIn(step, text)

    def test_every_field_gap_has_a_minimum(self):
        """Flown v0.5.5 collided a value with its note whenever the value exceeded its
        column: "AP    INTERCEPTINTERCEPT", "DROP T-01:20CHUTE T-01:39",
        "TOT 18:37:46T-02:09", and "DRIFT-73.0" where a 5-char label consumed its own
        column.

        v0.5.8 keeps that guarantee but moves it: the columns are derived from the rows
        actually rendered, with 4 and 5 as FLOORS, so the gaps are still >=1 after the
        label and >=2 after the value while the columns can widen for long content."""
        text = read("addon/functions/ui/fn_updateHud.sqf")
        self.assertIn("private _labelW = 4;", text)
        self.assertIn("private _valueW = 5;", text)
        self.assertIn("_labelW = _labelW max (count (_x select 0))", text)
        self.assertIn("if (_vw <= VALUE_CEIL) then {_valueW = _valueW max _vw}", text)
        self.assertIn("[(_labelW + 1 - (count _label)) max 1] call _pad", text)
        self.assertIn("[(_valueW + 2 - (count _value)) max 2] call _pad", text)
        # The fixed column it replaced must not come back; it is what misaligned the
        # note column for any value of 5 characters or more.
        self.assertNotIn("(6 - (count _value)) max 2", text)
        self.assertIn("#define VALUE_CEIL 6", text)
        # A label longer than the 4-char floor widens EVERY row, costing horizontal
        # space on all of them, so keep them short.
        import re
        labels = re.findall(r'\[\s*"([A-Z]{2,6})",', text)
        for lab in set(labels):
            self.assertLessEqual(len(lab), 4, f"label {lab} widens the column for every row")

    def test_note_column_aligns_at_every_value_width(self):
        """RP renders "16.02" -- 5 characters -- while XTK, TRK, GS and VS render 3 or
        4. Under the old fixed column with a floor, (6 - len) max 2, that put the RP
        note at column 7 and every other note at column 6. Visible in flight at
        hudScale 1.00 as "km PASSED" sitting one character right of every note below
        it. This is the layout arithmetic itself, not an assertion about the text."""
        CEIL = 6
        numeric = [("RP", "16.02"), ("XTK", "4738"), ("TRK", "263"), ("ALT", "1209"),
                   ("GS", "575"), ("VS", "0.0"), ("DRFT", "-0.0")]
        wide = [("AP", "RELEASE STABLE"), ("DROP", "T-00:20"), ("TOT", "18:36:21")]
        rows = numeric + wide

        def lay(rows):
            label_w = max([4] + [len(l) for l, _ in rows])
            value_w = max([5] + [len(v) for _, v in rows if len(v) <= CEIL])
            return {(l, v): len(l) + max(label_w + 1 - len(l), 1)
                             + len(v) + max(value_w + 2 - len(v), 2) for l, v in rows}

        at = lay(rows)
        # Every NUMERIC row -- the column the pilot reads down -- lands identically.
        num_at = {at[k] for k in numeric}
        self.assertEqual(len(num_at), 1, f"numeric notes not aligned: {sorted(num_at)}")
        # Values align for those rows too.
        label_w = max([4] + [len(l) for l, _ in rows])
        self.assertEqual(len({len(l) + max(label_w + 1 - len(l), 1) for l, _ in rows}), 1)
        # Gaps never fall below what the old fixed columns guaranteed, wide rows included.
        value_w = max([5] + [len(v) for _, v in rows if len(v) <= CEIL])
        for l, v in rows:
            self.assertGreaterEqual(max(label_w + 1 - len(l), 1), 1)
            self.assertGreaterEqual(max(value_w + 2 - len(v), 2), 2)
        # The formula this replaced provably did NOT align the numeric rows.
        old = {len(l) + max(5 - len(l), 1) + len(v) + max(6 - len(v), 2) for l, v in numeric}
        self.assertGreater(len(old), 1, "the old formula would have aligned; test is moot")
        # And a column sized by EVERY value is the regression that ceiling prevents:
        # "RELEASE STABLE" would push the RP note 9 characters further right.
        no_ceil_w = max([5] + [len(v) for _, v in rows])
        self.assertGreater(no_ceil_w + 2 - len("16.02"), value_w + 2 - len("16.02") + 8)

    def test_panel_width_scales_with_hud_scale(self):
        """Width was the one dimension that never scaled -- a bare safeZoneW * 0.33 --
        so at hudScale 0.70 the background box stood nearly twice as wide as its text,
        and above ~1.3 the longest rows would have run out through its right edge."""
        text = read("addon/functions/ui/fn_updateHud.sqf")
        self.assertIn("private _hudW = (0.33 * _scale) min 0.60;", text)
        self.assertIn("safeZoneW * _hudW", text)
        self.assertNotIn("safeZoneW * 0.33,", text)
        # It must stay on screen at the top of the scale range: left edge 0.335 plus
        # the capped width.
        self.assertLess(0.335 + 0.60, 1.0)
        # The flight director is anchored to screen centre, so widening cannot move it.
        self.assertIn("safeZoneX + (safeZoneW * 0.5) - (_cueW * 0.5)", text)

    def test_rule_colour_survives_a_bright_sky(self):
        """#3a464e against the translucent panel over daylight sky was invisible in
        flight: all three separator rules vanished, leaving what looked like random
        blank gaps in the middle of the panel."""
        text = read("addon/functions/ui/fn_updateHud.sqf")
        self.assertNotIn('#define C_RULE  "#3a464e"', text)
        self.assertIn('#define C_RULE  "#5c6b75"', text)
        # Still dimmer than the label colour, or it competes with the data.
        rule = int("5c", 16) + int("6b", 16) + int("75", 16)
        label = int("7e", 16) + int("92", 16) + int("9f", 16)
        self.assertLess(rule, label, "rule is no dimmer than the labels")

    def test_chute_note_does_not_repeat_the_state_word(self):
        """chuteTMinusText is a countdown before the chute event and the word "CHUTE"
        after it, so a literal "CHUTE %1" prefix rendered "DROP RELEASED  CHUTE CHUTE"
        once the canopy was out."""
        text = read("addon/functions/ui/fn_updateHud.sqf")
        self.assertIn('_chuteNote = if (_chuteT isEqualTo "CHUTE") then {_chuteT}', text)
        self.assertNotIn('"DROP", _dropT, format ["CHUTE %1", _chuteT]', text)

    def test_confidence_reason_budget_matches_the_scaled_panel(self):
        """22 characters was set when the panel width did not scale, and cut the longest
        reason to "DIAGONAL WIND COMPONEN..." with a third of the line empty. 30 then
        overshot the other way: it made the warning the widest line in the panel at 43
        characters against a capacity of about 41.

        Capacity, measured off a flown screenshot at hudScale 1.00:
        "VS   0.0    HOLD  ALT UNAVAILABLE" is 32 characters spanning 485 px in a
        635 px box, so ~15.2 px per character and ~41 characters before the inset."""
        text = read("addon/functions/ui/fn_updateHud.sqf")
        self.assertIn('if ((count _reason) > 26) then {_reason = (_reason select [0, 26]) + "..."};', text)
        self.assertNotIn("(count _reason) > 22", text)
        self.assertNotIn("(count _reason) > 30", text)
        capacity = 41
        # Both the warning and the widest data row must fit. The warning is allowed to
        # be the widest line in the panel -- at 26 it comes to 39 against the data
        # rows' 33 -- because fitting is the requirement and a warning that says which
        # term degraded is worth six columns.
        self.assertLessEqual(len("DEGRADED") + 2 + 26 + len("..."), capacity)
        widest_data = max(
            4 + 1 + 5 + 2 + len("m PRE-CHUTE  LIM 15"),
            4 + 1 + 5 + 2 + len("DESC  ALT UNAVAILABLE"),
        )
        self.assertLessEqual(widest_data, capacity)

    def test_ap_row_does_not_print_the_same_state_twice(self):
        """apState and pathState were identical on every flown drop, so the AP row
        rendered "RELEASE STABLE RELEASE STABLE"."""
        text = read("addon/functions/ui/fn_updateHud.sqf")
        self.assertIn("if (_apState isEqualTo _pathState) then {\"\"}", text)

    def test_stick_length_reaches_the_hud(self):
        """A 3-cargo stick predicted at 116 m against a 50 m DZ is the most actionable
        warning available, and only confidenceReason was being rendered."""
        text = read("addon/functions/ui/fn_updateHud.sqf")
        self.assertIn('_stickCount = _solution getOrDefault ["cargoSequenceCount", 1]', text)
        self.assertIn('_stickLength = _solution getOrDefault ["stickLengthM", 0]', text)
        self.assertIn('"STK"', text)

    def test_cue_slot_is_bracketed_by_one_rule(self):
        """An empty reserved slot between two rules left a conspicuous void mid-panel
        at high hudScale."""
        text = read("addon/functions/ui/fn_updateHud.sqf")
        cue = text.index("align='center' color='%2'>%3</t>")
        before = text[:cue]
        after = text[cue:text.index('"ALT"')]
        self.assertEqual(after.count("_rows pushBack _rule"), 0, "second rule after the cue")
        self.assertTrue(before.rstrip().endswith("_rule;") or "_rows pushBack _rule" in before[-400:])

    def test_rp_keeps_its_unit_when_passed(self):
        """"RP 18.85 PASSED" gave no way to tell 18.85 m from 18.85 km, and the
        difference matters rather a lot on a run-in."""
        text = read("addon/functions/ui/fn_updateHud.sqf")
        self.assertIn('format ["%1 PASSED", _rpUnit]', text)

    def test_dz_prefix_is_not_duplicated(self):
        """A DZ named "MAP DZ" rendered as "DZ MAP DZ"."""
        text = read("addon/functions/ui/fn_updateHud.sqf")
        self.assertIn('if ("DZ" in (toUpper USAFDC_state_dzName splitString " "))', text)

    def test_flight_director_glyphs_share_one_size(self):
        """The caret and the post must have identical line boxes or the apex of ^ does
        not sit inline with the top of | and the pair stops reading as one arrow."""
        text = read("addon/functions/ui/fn_updateHud.sqf")
        self.assertEqual(text.count("_fGlyph"), 3)  # one definition, two uses

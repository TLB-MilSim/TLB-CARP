"""v0.11.0 -- a guided stick lands as a stick, and the jump numbers live in the computer.

THE STICK. Guided cargo steers every load onto the drop zone. The only thing separating
two loads was jpadsScatterM: a random offset with a 2 m default radius, sized so ONE load
does not sit exactly on its aim point. Four vehicles on a 2 m circle land on top of each
other, and two of them can roll nearly the same offset.

It is worse than doing nothing. Ballistically a stick is already strung out along the
run-in by sequenceIntervalS * groundspeed -- about 82 m at 140 m/s -- so turning guidance
on took a correctly spread stick and pulled it into a heap.

Each load now gets a deterministic SLOT along the run-in, in release order, centred on the
DZ. Release order matters: the stick is already strung out in that direction, so keeping
it means each canopy flies the smallest correction that separates it rather than crossing
over its neighbours. The scatter stays, on top, and at 2 m against a 35 m slot it cannot
undo one.

Where the slot is computed is the whole MP question. fn_steerBegin runs on the machine
that has the crew's run-in; fn_steerCargo may run on a dedicated server that has neither a
run-in nor a panel. So the slot travels IN THE JOB, like the DZ and the four settings
before it, and fn_steerCargo stays a pure function of its arguments.

THE JUMP FIELDS. Stick size and canopy opening altitude were Addon Options. They change
per serial and Addon Options are not reachable in flight. They are now panel fields and
crew intent, with the Addon Options kept as mission defaults -- 0 in a field means "use
the default" -- so a mission that sets them once still works.

The aircraft's own altitude on the run is deliberately NOT a new field. That is TARGET
AGL, which the panel already has.
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


BEGIN = "addon/functions/jpads/fn_steerBegin.sqf"
TICK = "addon/functions/jpads/fn_steerTick.sqf"
STEER = "addon/functions/jpads/fn_steerCargo.sqf"
POSTINIT = "addon/functions/fn_postInit.sqf"
ARMJUMP = "addon/functions/jump/fn_armJumpRun.sqf"
JUMPSOL = "addon/functions/jump/fn_buildJumpSolution.sqf"
ENHANCE = "addon/functions/ui/fn_ensurePanelEnhancements.sqf"
PANEL = "addon/functions/ui/fn_refreshPanel.sqf"
APPLY = "addon/functions/sync/fn_syncApply.sqf"
SNAPSHOT = "addon/functions/sync/fn_syncSnapshot.sqf"


class StickSlotTests(unittest.TestCase):
    def test_the_slot_is_centred_on_the_drop_zone(self):
        """Not anchored at it. Anchoring would put the DZ at the leading edge of the
        pattern and throw the whole stick to one side of the point that was briefed."""
        src = code(BEGIN)
        self.assertIn("(_index - ((_total - 1) / 2)) * _spacing", src)

    def test_the_slots_run_along_the_locked_run_in(self):
        """The axis the stick is already strung out along, so each canopy flies the
        smallest correction that separates it."""
        src = code(BEGIN)
        self.assertIn("sin USAFDC_state_runInDeg", src)
        self.assertIn("cos USAFDC_state_runInDeg", src)

    def test_no_run_in_lock_means_no_slot(self):
        """There is no axis to spread along, and an empty offset is what tells
        fn_steerCargo to fall back to its random scatter."""
        src = code(BEGIN)
        self.assertIn("USAFDC_state_runInLocked", src)
        self.assertIn("private _aimOffset = [];", src)

    def test_a_single_load_gets_no_slot(self):
        """_total > 1. One load offset from the DZ by half a spacing would just be a
        miss."""
        self.assertIn("{_total > 1}", code(BEGIN))

    def test_zero_spacing_restores_aiming_every_load_at_the_dz(self):
        self.assertIn("if (_spacing > 0 &&", code(BEGIN))

    def test_a_stick_is_closed_by_time(self):
        """Ten seconds after the last release the stick is over whatever the stamp says,
        which covers a pass abandoned part-way."""
        src = code(BEGIN)
        self.assertIn('_carrier getVariable ["USAFDC_stickLastReleaseS", -1e9]', src)
        self.assertIn("if ((time - _lastS) > 10) then", src)

    def test_the_total_is_what_was_commanded_never_what_is_in_the_hold(self):
        """THE v0.11.2 BUG, FLOWN. fn_steerBegin counted what was left in the hold and
        added the load that had just gone -- which is the size of the aircraft's LOAD, not
        of the stick. Dropping one pallet from a hold of five made a stick of five, put the
        pallet in slot 1 of 5 and steered it 70 m short of the DZ, while the HUD correctly
        reported it steering."""
        src = code(BEGIN)
        self.assertNotIn("USAFDC_fnc_getLoadedCargo", src)
        self.assertIn('_total = _carrier getVariable ["USAFDC_stickTotal", 1]', src)

    def test_an_unknown_stick_costs_accuracy_nothing(self):
        """Default 1 -> no slot -> aims at the DZ. A release this code did not see
        commanded (USAF's own action, a mission script) must not be offset on a guess: a
        wrong offset is far worse than no offset."""
        self.assertIn('getVariable ["USAFDC_stickTotal", 1]', code(BEGIN))

    def test_more_loads_than_the_stick_expected_stop_spreading(self):
        """Otherwise each extra one lands progressively further downrange."""
        src = code(BEGIN)
        self.assertIn("if (_index >= _total) then", src)

    def test_the_commanded_count_is_stamped_where_it_is_known(self):
        """_requested is the crew's own CARGO count. It is the only place the stick size
        exists, and by the time fn_steerBegin runs the load has already left the
        manifest."""
        trigger = code("addon/functions/auto/fn_triggerAutoDrop.sqf")
        self.assertIn('_carrier setVariable ["USAFDC_stickTotal", _requested, false]', trigger)
        self.assertIn('_carrier setVariable ["USAFDC_stickIndex", -1, false]', trigger)
        seq = code("addon/functions/auto/fn_sequenceCargo.sqf")
        self.assertIn('_carrier setVariable ["USAFDC_stickTotal", _countToDrop, false]', seq)

    def test_the_stamp_precedes_the_release(self):
        """Stamped after the load is gone is stamped too late."""
        src = code("addon/functions/auto/fn_triggerAutoDrop.sqf")
        self.assertLess(src.index("USAFDC_stickTotal"), src.index("USAFDC_fnc_sequenceCargo"))
        self.assertLess(src.index("USAFDC_stickTotal"), src.index("USAFDC_fnc_releaseSelected"))

    def test_the_index_advances_within_a_stick(self):
        src = code(BEGIN)
        self.assertIn('_index = (_carrier getVariable ["USAFDC_stickIndex", -1]) + 1', src)
        self.assertIn('_carrier setVariable ["USAFDC_stickIndex", _index, false]', src)


class SlotDeliveryTests(unittest.TestCase):
    def test_the_slot_travels_in_the_job(self):
        """THE MP POINT. fn_steerCargo can run on a dedicated server, which has no
        run-in, no panel and no crew state. Anything it needs has to arrive as an
        argument -- the same rule the DZ and the four settings already follow."""
        src = code(BEGIN)
        job = src[src.index("private _job = ["):]
        job = job[:job.index("];")]
        self.assertIn("_aimOffset", job)

    def test_the_tick_unpacks_it_with_a_default(self):
        """A job published by a machine on an older build is nine elements short of one.
        Defaulting keeps that load steering, unspread, rather than erroring every frame."""
        self.assertIn('["_aimOffset", []]', code(TICK))

    def test_the_tick_hands_it_to_the_steering(self):
        self.assertIn(
            "[_cargo, _dz, _glideMs, _scatterM, _releaseAglM, _engageVzMs, _aimOffset] call USAFDC_fnc_steerCargo",
            code(TICK),
        )

    def test_steer_cargo_takes_it_as_an_argument_and_reads_no_state_for_it(self):
        src = code(STEER)
        self.assertIn('["_stickOffset", [], [[]]]', src)
        self.assertNotIn("USAFDC_state_runInDeg", src)
        self.assertNotIn("USAFDC_setting_jpadsStickSpacingM", src)

    def test_the_slot_and_the_scatter_add_rather_than_replace(self):
        """The scatter still keeps a load off the exact point; the slot is what separates
        loads. At 2 m against 35 m the scatter cannot undo a slot."""
        src = code(STEER)
        self.assertIn(
            "_offset = [(_offset # 0) + (_stickOffset # 0), (_offset # 1) + (_stickOffset # 1)]",
            src,
        )

    def test_the_combined_offset_is_still_picked_once_and_broadcast(self):
        """Two machines computing it independently would put the steering and the
        readout on different aim points."""
        src = code(STEER)
        self.assertIn('_cargo setVariable ["USAFDC_jpadsTargetOffset", _offset, true]', src)
        self.assertIn("if (_commanding) then {", src)

    def test_the_spacing_setting_exists_and_is_server_forced(self):
        lines = [
            ln for ln in read(POSTINIT).splitlines()
            if "USAFDC_setting_jpadsStickSpacingM" in ln and "addSetting" in ln
        ]
        self.assertEqual(len(lines), 1)
        self.assertIn("[0, 150, 35, 0], 1]", lines[0])


class JumpPanelFieldTests(unittest.TestCase):
    def test_both_fields_exist_as_controls_with_their_own_idcs(self):
        """v0.15.0 moved the panel into addon/config.cpp, generated from a layout
        spec by tools/gen_dialog.py. What this used to assert about runtime ctrlCreate is
        now a config declaration, which is the better contract: the generator refuses to
        write if any two control rectangles overlap -- the check v0.11.0 did not have when
        it put four controls on top of the CARGO row and shipped it."""
        cfg = read("addon/config.cpp")
        self.assertIn("idc=9332;", cfg)
        self.assertIn("idc=9333;", cfg)
        self.assertIn("RscEdit", cfg)
        self.assertIn("STICK", cfg)
        self.assertIn("OPEN m", cfg)

    def test_the_commit_handler_is_bound_once(self):
        """The controls are declared in config now, so they cannot be duplicated. What
        still can is the KillFocus HANDLER -- fn_ensurePanelEnhancements runs on every
        refresh, and without the guard it would fire once per refresh the panel has seen."""
        src = code(ENHANCE)
        self.assertIn('getVariable ["USAFDC_commitBound", false]', src)
        self.assertIn('ctrlAddEventHandler ["KillFocus", _commitJump]', src)

    def test_a_field_commits_on_kill_focus_not_on_every_keystroke(self):
        """The commit calls fn_refreshPanel, which repaints the panel AND publishes to
        the other seat. Per character that would fight the typist and flood the record."""
        src = code(ENHANCE)
        self.assertIn('ctrlAddEventHandler ["KillFocus", _commitJump]', src)
        self.assertIn("USAFDC_fnc_refreshPanel", src)

    def test_a_negative_entry_is_clamped(self):
        self.assertIn("if (_value < 0) then {_value = 0}", code(ENHANCE))

    def test_the_panel_never_repaints_a_field_the_user_is_typing_in(self):
        """fn_refreshPanel runs on every crew change. Rewriting the box under the typist
        would eat what they are entering."""
        src = code(PANEL)
        self.assertIn("focusedCtrl _display", src)
        self.assertIn("[9332,", src)
        self.assertIn("[9333,", src)

    def test_there_is_no_second_altitude_field_for_the_aircraft(self):
        """TARGET AGL already is that number. A second field for the same quantity is how
        a crew flies one altitude and briefs another."""
        src = code(ENHANCE)
        self.assertNotIn("USAFDC_state_targetAglM", src)


class JumpValueResolutionTests(unittest.TestCase):
    def test_the_crews_stick_size_beats_the_mission_default(self):
        src = code(ARMJUMP)
        planned = src.index("USAFDC_state_jumpPlannedStick")
        setting = src.index("USAFDC_setting_jumpStickCount")
        self.assertLess(planned, setting, "the panel value must be consulted first")
        self.assertIn("if (_planned >= 1) then {_planned}", src)

    def test_counting_the_cabin_is_still_the_last_resort(self):
        """0 in the field and 0 in the option still means 'everyone aboard but the
        pilot', which is the behaviour a crew that sets nothing gets."""
        self.assertIn('(count ((crew _aircraft) select {_x != (driver _aircraft)})) max 1', code(ARMJUMP))

    def test_the_crews_opening_altitude_beats_the_mission_default(self):
        src = code(JUMPSOL)
        self.assertIn('missionNamespace getVariable ["USAFDC_state_jumpOpenAglM", 0]', src)
        self.assertIn('if (_openAgl <= 0) then {_openAgl = missionNamespace getVariable ["USAFDC_setting_jumpOpenAglM", 600]}', src)

    def test_zero_means_use_the_default_not_open_at_ground_level(self):
        """A jumper opening at 0 m is the one reading of an empty field that must never
        happen."""
        self.assertIn("if (_openAgl <= 0) then", code(JUMPSOL))

    def test_the_addon_options_survive_as_mission_defaults(self):
        """A mission that already sets them keeps working."""
        post = read(POSTINIT)
        self.assertIn("USAFDC_setting_jumpOpenAglM", post)
        self.assertIn("USAFDC_setting_jumpStickCount", post)

    def test_both_are_crew_intent(self):
        snap = code(SNAPSHOT)
        self.assertIn("USAFDC_state_jumpPlannedStick", snap)
        self.assertIn("USAFDC_state_jumpOpenAglM", snap)
        apply_src = code(APPLY)
        self.assertIn('"_jumpPlannedStick", "_jumpOpenAglM"', apply_src)
        self.assertIn("USAFDC_state_jumpPlannedStick = _jumpPlannedStick;", apply_src)
        self.assertIn("USAFDC_state_jumpOpenAglM = _jumpOpenAglM;", apply_src)

    def test_both_are_initialised(self):
        """An unset state variable reads nil, and `nil >= 1` throws rather than being
        false."""
        post = read(POSTINIT)
        self.assertIn("USAFDC_state_jumpPlannedStick = 0;", post)
        self.assertIn("USAFDC_state_jumpOpenAglM = 0;", post)


if __name__ == "__main__":
    unittest.main(verbosity=2)

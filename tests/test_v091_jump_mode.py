"""v0.9.1 -- the auto-drop button that lied, and a run-in you can fly without cargo.

TWO FAULTS FROM ONE FLOWN SESSION ON v0.9.0.

THE BUTTON. After a drop the go-around would not release, and pressing a button reading
DISARM AUTO answered "AUTO DROP ARMED". Two symptoms, one cause, in two halves:

  The label was painted from `autoArmed || syncWantAuto` while config.bin's handler --
  which cannot be edited -- branches on `autoArmed` alone. Whenever those disagreed the
  control lied about its own action.

  And they disagreed permanently. fn_syncPublish detects a human's intent by watching
  the armed flag change since USAFDC_state_syncSeenAuto, but fn_syncReconcile re-points
  that marker at the live flag every tick, 5 Hz. So when fn_triggerAutoDrop cleared
  autoArmed, the marker followed it 200 ms later -- long before anyone could open the
  panel -- and the publisher saw nothing to publish. syncWantAuto stayed true for the
  rest of the sortie with auto genuinely off. The reconcile erased the evidence the
  publisher depended on.

Fixed at the source rather than by defending the detector: disarming for a real reason
ends the crew's intent in fn_disarmAutoDrop, which every such path now goes through.

THE JUMP RUN. fn_buildWorldSolution refused NO CARGO ABOARD with an empty hold, which
blocked fn_armGuidance and therefore the autopilot -- so a HALO run could not use the
run-in it exists to fly. Run-in lock itself was never affected and was confirmed working.

The fix is an explicit third mode rather than inferring a jump from an empty hold, so a
jump run still works with cargo aboard for a later pass. Its aim point is the JUMP EXIT
POINT, not the drop zone: fn_buildJumpSolution already computes where the aircraft must
be for a jumper to reach the DZ under canopy, which is upwind of it by the freefall
drift and led by the stick. Aiming at the DZ would put the aircraft a kilometre or more
downwind of where the jumpers actually have to leave.
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


DISARM = "addon/functions/auto/fn_disarmAutoDrop.sqf"
ARM = "addon/functions/auto/fn_armAutoDrop.sqf"
TRIGGER = "addon/functions/auto/fn_triggerAutoDrop.sqf"
PANEL = "addon/functions/ui/fn_refreshPanel.sqf"
TELEMETRY = "addon/functions/ui/fn_updatePanelTelemetry.sqf"
ENHANCE = "addon/functions/ui/fn_ensurePanelEnhancements.sqf"
SOLVER = "addon/functions/guidance/fn_buildWorldSolution.sqf"
GUIDANCE = "addon/functions/guidance/fn_updateGuidance.sqf"
VALIDATE = "addon/functions/auto/fn_validateAutoDrop.sqf"
POSTINIT = "addon/functions/fn_postInit.sqf"


class AutoDropIntentLifecycleTests(unittest.TestCase):
    def test_disarming_ends_the_crews_intent_too(self):
        src = code(DISARM)
        self.assertIn("USAFDC_state_syncWantAuto = false;", src)
        self.assertIn("USAFDC_state_syncSeenAuto = false;", src)
        self.assertIn("USAFDC_state_syncAutoAttempted = false;", src)

    def test_releasing_the_attempt_latch_is_what_lets_a_go_around_re_arm(self):
        """fn_syncReconcile arms auto once per intent and suppresses it thereafter as
        'already attempted'. Leaving that latched after a drop is what stopped the second
        pass from ever arming again."""
        self.assertIn("USAFDC_state_syncAutoAttempted", code(DISARM))

    def test_the_trigger_does_not_clear_the_armed_flag_behind_disarms_back(self):
        """Four sites in fn_triggerAutoDrop set the flag directly. The pass is over in
        every one of them, so they mean what fn_disarmAutoDrop means."""
        src = code(TRIGGER)
        self.assertNotIn("USAFDC_state_autoArmed = false", src)
        self.assertIn("USAFDC_fnc_disarmAutoDrop", src)

    def test_a_refused_arm_does_not_disarm_the_crew(self):
        """THE ASYMMETRY. fn_armAutoDrop's failure paths set the flag directly and never
        route through fn_disarmAutoDrop -- otherwise one co-pilot's bad geometry would
        cancel the pilot's pass."""
        src = code(ARM)
        self.assertIn("USAFDC_state_autoArmed = false;", src)
        self.assertNotIn("USAFDC_fnc_disarmAutoDrop", src)

    def test_the_button_label_reads_what_the_button_does(self):
        """config.bin's handler is `if (autoArmed) then {disarm} else {arm}`, so the label
        must read the same variable or the control lies about its own action.

        THE CONTRACT IS UNCHANGED; THE ADDRESS MOVED IN v0.16.2. The label was painted in
        fn_refreshPanel, which runs on a human press. When ARM AUTO DROP gained a red/green
        state colour, that colour had to be painted somewhere that repaints between presses
        -- auto drop disarms itself after a release and on an AP disconnect, neither of
        which is a press -- so both moved to fn_updatePanelTelemetry, off the guidance loop.
        Leaving the label behind would have been two writers on one control, which is
        exactly how a button ends up green and reading ARM."""
        src = code(TELEMETRY)
        label = src[src.index("displayCtrl 9311"):]
        label = label[:label.index("} forEach [")]
        self.assertIn("USAFDC_state_autoArmed", label)
        self.assertNotIn("syncWantAuto", label)
        # And it is not still being written in the old place as well.
        self.assertNotIn("displayCtrl 9311", code(PANEL))


class JumpActionPlacementTests(unittest.TestCase):
    """WAS: the jump actions live on the vehicle's ACE menu, not the player's.

    v0.15.0 moved the panel into addon/config.cpp, generated from a layout
        spec by tools/gen_dialog.py. What this used to assert about runtime ctrlCreate is
        now a config declaration, which is the better contract: the generator refuses to
        write if any two control rectangles overlap -- the check v0.11.0 did not have when
        it put four controls on top of the CARGO row and shipped it.

    The jump run is now a panel BUTTON (idc 9337) and both ACE entries are gone. That is
    better than either menu: the label reads USAFDC_jumpArmedBy, which is public and set on
    the AIRCRAFT, so every seat sees the run is armed and by whom -- an ACE action could
    only ever show its own client's flag."""

    def test_the_jump_run_is_a_panel_button(self):
        cfg = read("addon/config.cpp")
        self.assertIn("idc=9337;", cfg)
        self.assertIn("USAFDC_fnc_armJumpRun", cfg)
        self.assertIn("USAFDC_fnc_disarmJumpRun", cfg)

    def test_no_carp_action_is_left_on_any_ace_self_menu(self):
        """The panel itself is reached from Air's ACE_SelfActions and stays there. What
        must not remain is a SECOND CARP system living in a different menu."""
        src = code(POSTINIT)
        for gone in ["_jumpArmAction", "_jumpDisarmAction", "USAFDC_JumpArm", "USAFDC_JumpDisarm"]:
            self.assertNotIn(gone, src)

    def test_the_cargo_actions_were_not_taken_with_them(self):
        """They sat BETWEEN the two jump registrations and the first cut removed them
        along with it. Load and unload are unrelated and must survive."""
        src = code(POSTINIT)
        self.assertIn("USAFDC_LoadCargo", src)
        self.assertIn("USAFDC_UnloadCargo", src)
        self.assertIn("ACE_MainActions", src)

    def test_the_label_comes_from_the_airframe_claim_not_this_client(self):
        """USAFDC_jumpArmedBy is set on the aircraft with the public flag, so a co-pilot
        sees the armed state even though only one machine runs the cue handler."""
        src = code("addon/functions/ui/fn_updatePanelTelemetry.sqf")
        self.assertIn("displayCtrl 9337", src)
        self.assertIn('getVariable ["USAFDC_jumpArmedBy", objNull]', src)

    def test_a_second_crew_member_still_cannot_start_a_competing_run(self):
        """The check that made the ACE condition safe lives in fn_armJumpRun, not in the
        menu, so moving the control did not move the guard."""
        self.assertIn("USAFDC_jumpArmedBy", code("addon/functions/jump/fn_armJumpRun.sqf"))


class JumpModeSolverTests(unittest.TestCase):
    def test_the_mode_is_explicit_not_inferred_from_an_empty_hold(self):
        """Inferring it would break a jump run flown with cargo aboard for a later pass,
        and would silently turn a cargo drop with an empty hold into a jump."""
        src = code(SOLVER)
        self.assertIn('private _jumpRun = USAFDC_state_mode isEqualTo "JUMP";', src)

    def test_cargo_is_required_for_a_cargo_drop_and_only_for_that(self):
        src = code(SOLVER)
        self.assertIn('if (!_jumpRun && {(_airState get "cargoCount") <= 0}) exitWith', src)

    def test_a_jump_run_aims_at_the_exit_point_not_the_drop_zone(self):
        """The exit point is upwind of the DZ by the freefall drift and led by the stick.
        Aiming at the DZ would put the aircraft a kilometre or more downwind of where the
        jumpers have to leave."""
        src = code(SOLVER)
        self.assertIn("USAFDC_fnc_buildJumpSolution", src)
        self.assertIn('_jump getOrDefault ["exitPointPosASL", _dz]', src)
        # The exit point stands in for the release point, so nothing downstream needs to
        # know this is a jump.
        for key in ['["rpPosASL", _aim]', '["liveRpPosASL", _aim]', '["plannedRpPosASL", _aim]']:
            self.assertIn(key, src)

    def test_an_unusable_jump_solution_still_guides_the_run_in(self):
        """Refusing to guide at all because the exit point is unavailable would take the
        autopilot away at the moment it is most wanted.

        v0.14.0 removed the DEGRADED tier, so the fallback no longer announces itself as a
        confidence word on the pilot's HUD. The BEHAVIOUR is unchanged and is what this
        test protects: an unavailable exit point still falls back to the drop zone and
        still guides. What says so is fn_updateJumpCue's JUMP HOLD readout, which reaches
        the jumpers rather than only the pilot."""
        src = code(SOLVER)
        self.assertIn("if (_jumpValid) then", src)
        self.assertIn('_jump getOrDefault ["exitPointPosASL", _dz]', src)
        self.assertIn('["confidence", "GOOD"]', src)
        self.assertIn("JUMP SOLUTION UNAVAILABLE", src)

    def test_the_jump_branch_skips_the_cargo_ballistics_entirely(self):
        """No release delay, no forward throw, no canopy table -- none of it applies."""
        src = code(SOLVER)
        branch = src.index("if (_jumpRun) exitWith")
        solve = src.index("USAFDC_fnc_solveWorldReference")
        self.assertLess(branch, solve, "the jump branch must return before the ballistic solve")


class JumpRunReleaseMachineryTests(unittest.TestCase):
    def test_guidance_reads_the_jump_flag_from_the_solution(self):
        self.assertIn('private _jumpRun = _solution getOrDefault ["jumpRun", false];', code(GUIDANCE))

    def test_no_drop_cue_no_missed_pass_and_no_auto_drop_on_a_jump_run(self):
        """Crossing the exit point would otherwise sound a cargo drop cue, and a latched
        miss would tell the pilot to go around on a perfectly good jump pass."""
        src = code(GUIDANCE)
        self.assertEqual(src.count("if (!_jumpRun && {_crossed}"), 3)
        self.assertIn("if (!_jumpRun && {(_current > 0)}", src)

    def test_auto_drop_refuses_a_jump_run(self):
        self.assertIn('USAFDC_state_mode isEqualTo "JUMP"', code(VALIDATE))
        self.assertIn("JUMP RUN - NO CARGO RELEASE", code(VALIDATE))


class JumpModeMenuTests(unittest.TestCase):
    def test_the_mode_list_offers_all_three(self):
        src = code(PANEL)
        self.assertIn('["TOUCHDOWN ON DZ", "TOUCHDOWN"], ["CHUTE ON DZ", "CHUTE"], ["HALO JUMP", "JUMP"]', src)

    def test_the_config_handler_knows_all_three_modes(self):
        """WAS: config.bin's handler whitelisted TOUCHDOWN and CHUTE and ignored anything
        else, so v0.9.1 bolted a second LBSelChanged on at runtime to carry HALO JUMP.

        v0.15.0 moved the panel into addon/config.cpp, generated from a layout
        spec by tools/gen_dialog.py. What this used to assert about runtime ctrlCreate is
        now a config declaration, which is the better contract: the generator refuses to
        write if any two control rectangles overlap -- the check v0.11.0 did not have when
        it put four controls on top of the CARGO row and shipped it.

        The whitelist is editable now, so the third mode is IN it and the bolt-on is gone.
        One handler, in the place the other two modes were always handled."""
        self.assertIn("'TOUCHDOWN','CHUTE','JUMP'", read("addon/config.cpp"))
        self.assertNotIn('ctrlAddEventHandler ["LBSelChanged"', code(ENHANCE))

    def test_the_mode_change_still_has_its_side_effects(self):
        """A mode change invalidates any armed release and any latched drop. True when the
        config handled two modes; must stay true now it handles three."""
        cfg = read("addon/config.cpp")
        tail = cfg[cfg.index("'TOUCHDOWN','CHUTE','JUMP'"):]
        handler = tail[:tail.index('";')]
        self.assertIn("USAFDC_fnc_disarmAutoDrop", handler)
        self.assertIn("USAFDC_state_dropLatched", handler)

    def test_the_refresh_guard_is_still_respected(self):
        """lbClear and lbSetCurSel inside fn_refreshPanel's rebuild both fire
        LBSelChanged. Without the guard the rebuild re-enters and sets the mode itself."""
        cfg = read("addon/config.cpp")
        head = cfg[:cfg.index("'TOUCHDOWN','CHUTE','JUMP'")]
        self.assertIn("USAFDC_state_panelRefreshing", head[-500:])

    def test_the_mode_is_crew_shared_so_a_jump_run_is_not_one_seats_idea(self):
        self.assertIn("USAFDC_state_mode", code("addon/functions/sync/fn_syncSnapshot.sqf"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

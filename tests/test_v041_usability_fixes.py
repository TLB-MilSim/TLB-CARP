from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


class VerticalCaptureTuningTests(unittest.TestCase):
    def test_vertical_profile_uses_early_capture_horizon_and_preserves_limits(self):
        text = read("addon/functions/path/fn_buildPathSolution.sqf")
        self.assertIn("verticalCaptureTimeS", text)
        self.assertIn("_routeEtaS * 0.60", text)
        self.assertIn("max 8", text)
        self.assertIn("max -20", text)
        self.assertIn("min 12", text)
        self.assertNotIn("_routeEtaS - 12", text)


class FreelookFocusTests(unittest.TestCase):
    def test_input_focus_helper_covers_held_and_toggle_freelook(self):
        text = read("addon/functions/autopilot/fn_inputFocusActive.sqf")
        self.assertIn('inputAction "lookAround"', text)
        self.assertIn('inputAction "lookAroundToggle"', text)
        self.assertIn("> 0.1", text)

    def test_ap_keeps_existing_half_second_handoff_after_freelook_focus(self):
        text = read("addon/functions/autopilot/fn_updateAutopilot.sqf")
        self.assertIn("TLB_CARP_fnc_inputFocusActive", text)
        self.assertIn("diag_tickTime + 0.5", text)
        self.assertIn("TLB_CARP_state_apOverrideInhibitUntil", text)


class PersistentTotDisplayTests(unittest.TestCase):
    def test_guidance_refreshes_ui_when_solution_invalid_but_package_is_tracking(self):
        text = read("addon/functions/guidance/fn_updateGuidance.sqf")
        invalid = text[text.index('if !(_solution getOrDefault ["valid", false])'):text.index("private _path")]
        self.assertIn("TLB_CARP_state_displaySolution", invalid)
        self.assertIn("TLB_CARP_fnc_updateHud", invalid)
        self.assertIn("TLB_CARP_fnc_updatePanelTelemetry", invalid)
        self.assertIn('in ["RELEASED", "CHUTE", "ARRIVED"]', invalid)

    def test_valid_guidance_latches_display_solution_for_post_release_use(self):
        text = read("addon/functions/guidance/fn_updateGuidance.sqf")
        self.assertIn("TLB_CARP_state_displaySolution = _solution", text)
        self.assertIn('set ["packageTrackingOnly", false]', text)

    def test_the_hud_uses_display_solution_during_post_release_tracking(self):
        """WAS "hud and panel". v0.11.2 removed the panel status block (control 9314) on a flown request,
        and the panel no longer reads a solution at all -- it paints three controls from
        flags. The requirement is unchanged and unweakened where it counts: the HUD must
        keep refreshing through RELEASED / CHUTE / ARRIVED after the solver goes invalid,
        which is the display-lifecycle bug this test was written for."""
        hud = read("addon/functions/ui/fn_updateHud.sqf")
        self.assertIn("TLB_CARP_state_displaySolution", hud)
        self.assertIn("packageTrackingOnly", hud)
        self.assertNotIn('if !(_solution getOrDefault ["valid", false]) exitWith {false};', hud)


class HudReadabilityTests(unittest.TestCase):
    def test_hud_keeps_a_colour_coded_runin_status_and_grouped_sections(self):
        """v0.5.5 replaced the wall of pipe-separated text with a monospace
        label/value grid. The requirement this test was written for -- a prominent,
        colour-coded run-in status and visually separated sections -- still holds;
        only the mechanism changed, from double <br/> to rule-separated groups.

        Status wording was shortened (ON RUN-IN / GO AROUND) so it cannot wrap; the
        old strings ran to 19 characters and wrapped at large hudScale.
        """
        text = read("addon/functions/ui/fn_updateHud.sqf")
        for marker in [
            "CORRECT TO RUN-IN", "ON RUN-IN", "GO AROUND",
            "_statusColor", "_pathColor", "_altColor", "_packageColor",
            "PKG", "CHUTE", "TOT",
        ]:
            self.assertIn(marker, text)
        # Sections are separated by a rule rather than a blank line.
        self.assertIn("_rows pushBack _rule", text)
        self.assertNotIn("TGT ASL", text)
        self.assertNotIn("CAP %", text)

    def test_flight_director_arrow_is_above_center_post(self):
        # v0.4.1 encoded this as ui/hud.hpp geometry and shipped believing it
        # was fixed. In-engine validation proved otherwise: hud.hpp is compiled
        # into the pre-binarized config.bin, so only the caret (positioned at
        # runtime) actually moved, leaving | above ^ and overlapping the HUD
        # block. v0.4.2 positions BOTH controls from SQF.
        hpp = read("addon/ui/hud.hpp")
        self.assertIn(
            "pre-binarized config.bin", hpp,
            "hud.hpp must carry the warning that its geometry is inert in-engine",
        )
        hud = read("addon/functions/ui/fn_updateHud.sqf")
        self.assertIn("_steerCtrl ctrlSetPosition", hud)
        self.assertIn("_centerCtrl ctrlSetPosition", hud)
        # Caret sits just below the block; the post sits one tight gap under the
        # caret so ^ is above | and the two read as a single arrow. The 0.038
        # offset shipped in the first v0.4.2 build was too loose to line up by
        # eye, per in-engine feedback; the gap is now the tunable _fdGapY.
        self.assertIn("_hudBottomY + 0.013", hud)
        self.assertIn("_centerY = _cueY + _fdGapY", hud)

    def test_the_panel_carries_no_engineering_detail_at_all(self):
        """v0.4.1 hid engineering telemetry behind the diagnostics setting so the normal
        panel stayed readable. v0.11.2 removed the panel status block (control 9314) on a flown request,
        which takes that argument to its conclusion: there is no engineering detail on the
        panel to gate, and no diagnostics-enabled branch to get it wrong.

        The panel is now a setup surface -- DZ, mode, profile, wind, targets, the toggles
        and the arm buttons. Flight state is the HUD's job and always was."""
        text = read("addon/functions/ui/fn_updatePanelTelemetry.sqf")
        for gone in ["RUN-IN STATUS", "_diagEnabled", "CAPTURE", "LAT VEL", "PRE-CHUTE", "DIAG PATH"]:
            self.assertNotIn(gone, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)

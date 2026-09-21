from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def code(rel: str) -> str:
    """Source with comments stripped, string literals intact.

    Ordering assertions below must measure EXECUTABLE order, not the order words
    happen to appear in prose. The comment above the actuation block in
    fn_updateAutopilot names setVelocity while explaining why the orientation write is
    now conditional, and a raw-text index would read that as the call site.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    from strip_sqf_comments import strip_comments

    path = ROOT / rel
    if not path.exists():
        return ""
    return strip_comments(path.read_text(encoding="utf-8"))


class AutopilotSourceTests(unittest.TestCase):
    def test_postinit_loads_ap_functions_and_registers_override_threshold(self):
        text = read("addon/functions/fn_postInit.sqf")
        self.assertIn("TLB_CARP_setting_apOverrideThreshold", text)
        self.assertIn("[0.10, 0.60, 0.25, 2]", text)
        for name in ["armAutopilot", "disarmAutopilot", "updateAutopilot"]:
            self.assertIn(f"TLB_CARP_fnc_{name}", text)
            self.assertIn(f"functions\\autopilot\\fn_{name}.sqf", text)

    def test_arm_ap_requires_pilot_guidance_locked_runin_and_fresh_rp(self):
        text = read("addon/functions/autopilot/fn_armAutopilot.sqf")
        self.assertIn("driver _vehicle", text)
        self.assertIn("TLB_CARP_state_guidanceArmed", text)
        self.assertIn("TLB_CARP_state_runInLocked", text)
        self.assertIn('getOrDefault ["valid", false]', text)
        self.assertIn('getOrDefault ["signedRpM", -1]', text)
        self.assertIn('inputAction "HeliThrottlePos"', text)

    def test_ap_manual_override_and_controller_contract(self):
        text = read("addon/functions/autopilot/fn_updateAutopilot.sqf")
        for action in [
            "HeliForward", "HeliBack", "AirBankLeft", "AirBankRight",
            "HeliRudderLeft", "HeliRudderRight", "HeliUp", "HeliDown",
            "HeliThrottlePos",
        ]:
            self.assertIn(action, text)
        self.assertIn("TLB_CARP_setting_apOverrideThreshold", text)
        self.assertIn("0.12", text)
        self.assertIn("PILOT OVERRIDE", text)
        self.assertIn("setVelocity", text)
        self.assertIn("setDir", text)
        self.assertIn("setAirplaneThrottle", text)
        self.assertNotIn("setPos", text)
        self.assertNotIn("setPosASL", text)
        self.assertIn("pathState", text)
        self.assertIn("pathDesiredTrackDeg", text)
        self.assertIn("commandVerticalSpeedMs", text)
        self.assertIn("runInDeg", text)

    def test_ap_applies_heading_before_restoring_velocity(self):
        text = code("addon/functions/autopilot/fn_updateAutopilot.sqf")
        heading_idx = text.index("setDir")
        velocity_idx = text.index("setVelocity")
        self.assertLess(
            heading_idx,
            velocity_idx,
            "Arma setDir resets vehicle velocity, so AP must apply heading before setVelocity",
        )

    def test_ap_suppresses_override_during_carp_or_zeus_ui_focus(self):
        update = read("addon/functions/autopilot/fn_updateAutopilot.sqf")
        arm = read("addon/functions/autopilot/fn_armAutopilot.sqf")
        post = read("addon/functions/fn_postInit.sqf")
        self.assertIn("findDisplay 9300", update)
        self.assertIn("findDisplay 312", update)
        self.assertIn("TLB_CARP_state_apOverrideInhibitUntil", update)
        self.assertIn("diag_tickTime + 0.5", update)
        self.assertIn("TLB_CARP_state_apOverrideInhibitUntil", arm)
        self.assertIn("TLB_CARP_state_apOverrideInhibitUntil", post)

    def test_ap_horizontal_velocity_stays_aligned_with_commanded_heading(self):
        text = read("addon/functions/autopilot/fn_updateAutopilot.sqf")
        self.assertIn("private _newHeading", text)
        self.assertIn("private _newGroundSpeed", text)
        self.assertIn("_newGroundSpeed * sin _newHeading", text)
        self.assertIn("_newGroundSpeed * cos _newHeading", text)
        self.assertNotIn("private _targetVx", text)
        self.assertNotIn("private _targetVy", text)

    def test_guidance_calls_ap_and_disconnect_paths_clear_it(self):
        update = read("addon/functions/guidance/fn_updateGuidance.sqf")
        disarm = read("addon/functions/guidance/fn_disarmGuidance.sqf")
        unlock = read("addon/functions/guidance/fn_unlockRunIn.sqf")
        self.assertIn("TLB_CARP_fnc_updateAutopilot", update)
        self.assertIn("TLB_CARP_fnc_disarmAutopilot", disarm)
        self.assertIn("TLB_CARP_fnc_disarmAutopilot", unlock)


class ReleaseStabilityTests(unittest.TestCase):
    def test_world_solution_exposes_lateral_drift_and_tight_gate(self):
        text = read("addon/functions/guidance/fn_buildWorldSolution.sqf")
        self.assertIn("freefallLateralDriftM", text)
        self.assertIn("preChuteLateralDriftM", text)
        self.assertIn('getOrDefault ["chuteAttachTimeS", 0]', text)
        self.assertIn('get "releaseDelayS"', text)
        self.assertIn("<= 25", text)
        self.assertIn("<= 2", text)
        # v0.16.10: the limit became a setting, default 25 m, matching the cross-track
        # limit. It was 15 m and NOTHING COULD EVER VIOLATE IT: until v0.16.8 the AP
        # wrote horizontal velocity from the commanded heading, so velocityRightMs was
        # identically zero by construction. The force autopilot flies for real, and the
        # first flown session refused five passes -- one with crossTrack -1.19 m and
        # trackError -0.57 deg -- on 16.6 m of drift. The gate is still geometry-only.
        self.assertIn("<= _driftLimitM", text)
        self.assertIn("PRE-CHUTE LATERAL DRIFT", text)


class PackageTimingSourceTests(unittest.TestCase):
    def test_timing_helper_uses_route_release_ballistic_canopy_and_mission_clock(self):
        text = read("addon/functions/guidance/fn_estimatePackageTiming.sqf")
        self.assertIn("capturePosASL", text)
        self.assertIn("signedRpM", text)
        self.assertIn('get "releaseDelayS"', text)
        self.assertIn("chuteAttachTimeS", text)
        self.assertIn("predictedCanopyTimeS", text)
        self.assertIn("daytime", text)
        for key in [
            "dropEtaS", "chuteEtaS", "touchdownEtaS", "dropClockText",
            "chuteClockText", "totClockText", "dropTMinusText",
            "chuteTMinusText", "totTMinusText", "timingState",
        ]:
            self.assertIn(key, text)

    def test_guidance_merges_timing_into_live_solution(self):
        text = read("addon/functions/guidance/fn_updateGuidance.sqf")
        self.assertIn("TLB_CARP_fnc_estimatePackageTiming", text)
        self.assertIn("keys _timing", text)


class PanelDiagnosticsTests(unittest.TestCase):
    def test_panel_has_dynamic_ap_control_and_runtime_telemetry(self):
        ensure = read("addon/functions/ui/fn_ensurePanelEnhancements.sqf")
        telem = read("addon/functions/ui/fn_updatePanelTelemetry.sqf")
        open_panel = read("addon/functions/ui/fn_openPanel.sqf")
        cfg = read("addon/config.cpp")
        self.assertIn("idc=9330;", cfg)
        self.assertIn("TLB_CARP_fnc_armAutopilot", cfg)
        self.assertIn("TLB_CARP_fnc_disarmAutopilot", cfg)
        self.assertIn("TLB_CARP_fnc_ensurePanelEnhancements", open_panel)
        # The AP button is what this test is really for, and it is untouched: created at
        # runtime, labelled from live state, enabled only when the AP could arm.
        self.assertIn("ctrlSetText format [\"AP: %1\"", telem)
        self.assertIn("ctrlEnable _canArm", telem)
        # v0.11.2 removed the panel status block (control 9314) on a flown request, and the
        # AP STATE / PRE-CHUTE / PACKAGE TIMING / TOT lines were in it. TOT and the
        # package lifecycle are still on the HUD (test_hud_shows_ap_drift_and_timing
        # below); the rest was engineering detail and is gone from the aircraft.
        for gone in ["AP STATE", "PRE-CHUTE", "PACKAGE TIMING", "TLB_CARP_setting_debug"]:
            self.assertNotIn(gone, telem)

    def test_debug_master_is_not_toggled_by_panel(self):
        refresh = read("addon/functions/ui/fn_refreshPanel.sqf")
        self.assertNotIn("TLB_CARP_setting_debug=!TLB_CARP_setting_debug", refresh)
        self.assertIn("TLB_CARP_fnc_updatePanelTelemetry", refresh)

    def test_hud_shows_ap_drift_and_timing(self):
        hud = read("addon/functions/ui/fn_updateHud.sqf")
        for marker in ["TLB_CARP_state_apState", "preChuteLateralDriftM", "totTMinusText", "totClockText"]:
            self.assertIn(marker, hud)


if __name__ == "__main__":
    unittest.main(verbosity=2)

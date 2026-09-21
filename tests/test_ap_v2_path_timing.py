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

    The setDir/setVelocity ordering assertion must measure EXECUTABLE order. The
    comment introducing the actuation rate limit in fn_updateAutopilot names both
    commands while explaining why the orientation write is conditional, and a raw-text
    index would find the prose rather than the call.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    from strip_sqf_comments import strip_comments

    path = ROOT / rel
    if not path.exists():
        return ""
    return strip_comments(path.read_text(encoding="utf-8"))


class AutopilotV2PathTests(unittest.TestCase):
    def test_path_manager_contract_and_states(self):
        text = read("addon/functions/path/fn_buildPathSolution.sqf")
        self.assertTrue(text, "missing path manager")
        for marker in [
            '"INTERCEPT"', '"CAPTURE FINAL"', '"FINAL RUN"',
            '"RELEASE STABLE"', '"POST DROP"',
            "pathDesiredTrackDeg", "captureGateASL", "captureDistanceM",
            "routeDistanceM", "routeEtaS", "targetDropAslM",
            "altitudeErrorM", "requiredVerticalSpeedMs",
            "commandVerticalSpeedMs", "altitudePathState", "altitudeReachable",
        ]:
            self.assertIn(marker, text)
        self.assertIn("3 * abs _crossTrackM", text)
        self.assertIn("1500", text)
        self.assertIn("5000", text)
        self.assertIn("getTerrainHeightASL", text)
        self.assertIn("max -20", text)
        self.assertIn("min 12", text)
        self.assertNotIn("max -2 min 2", text)
        self.assertNotIn("max -1 min 1", text)

    def test_locked_runin_still_uses_current_ground_track(self):
        text = read("addon/functions/guidance/fn_lockRunIn.sqf")
        self.assertIn('USAFDC_state_runInDeg = _state get "trackDeg"', text)

    def test_guidance_merges_path_before_ap_and_uses_path_desired_track(self):
        text = read("addon/functions/guidance/fn_updateGuidance.sqf")
        self.assertIn("USAFDC_fnc_buildPathSolution", text)
        self.assertIn("keys _path", text)
        self.assertIn('getOrDefault ["pathDesiredTrackDeg"', text)
        self.assertLess(text.index("USAFDC_fnc_buildPathSolution"), text.index("USAFDC_fnc_updateAutopilot"))

    def test_ap_consumes_path_commands_without_old_final_vertical_clamps(self):
        text = read("addon/functions/autopilot/fn_updateAutopilot.sqf")
        self.assertIn('getOrDefault ["pathState"', text)
        self.assertIn('getOrDefault ["pathDesiredTrackDeg"', text)
        self.assertIn('getOrDefault ["commandVerticalSpeedMs"', text)
        self.assertNotIn("USAFDC_fnc_interceptLimitDeg", text)
        self.assertNotIn("max -2 min 2", text)
        self.assertNotIn("max -1 min 1", text)
        self.assertIn("_newGroundSpeed * sin _newHeading", text)
        self.assertIn("_newGroundSpeed * cos _newHeading", text)
        self.assertNotIn("setPos", text)
        self.assertNotIn("setPosASL", text)
        executable = code("addon/functions/autopilot/fn_updateAutopilot.sqf")
        self.assertLess(executable.index("setDir"), executable.index("setVelocity"))

    def test_release_stability_remains_geometry_only(self):
        text = read("addon/functions/guidance/fn_buildWorldSolution.sqf")
        self.assertIn("((abs _crossTrackM) <= 25)", text)
        self.assertIn("(abs _trackErrorDeg) <= 2", text)
        # v0.16.10: the limit became a setting, default 25 m, matching the cross-track
        # limit. It was 15 m and NOTHING COULD EVER VIOLATE IT: until v0.16.8 the AP
        # wrote horizontal velocity from the commanded heading, so velocityRightMs was
        # identically zero by construction. The force autopilot flies for real, and the
        # first flown session refused five passes -- one with crossTrack -1.19 m and
        # trackError -0.57 deg -- on 16.6 m of drift. The gate is still geometry-only.
        self.assertIn("(abs _preChuteLateralDriftM) <= _driftLimitM", text)
        self.assertIn('getVariable ["USAFDC_setting_releaseDriftLimitM", 25]', text)
        final_gate = text[text.index("private _insideFinal"):text.index("private _finalRunLineOffsetM")]
        self.assertNotIn("altitudeErrorM", final_gate)
        self.assertNotIn("targetGroundSpeedKmh", final_gate)
        self.assertNotIn("verticalSpeed", final_gate)


class InputFocusTests(unittest.TestCase):
    def test_shared_focus_helper_covers_carp_zeus_and_ace(self):
        text = read("addon/functions/autopilot/fn_inputFocusActive.sqf")
        self.assertIn("findDisplay 9300", text)
        self.assertIn("findDisplay 312", text)
        self.assertIn("USAFDC_state_apAceInteractOpen", text)

    def test_postinit_registers_ace_open_close_and_grace_period(self):
        text = read("addon/functions/fn_postInit.sqf")
        self.assertIn("USAFDC_state_apAceInteractOpen", text)
        self.assertIn('"ace_interactMenuOpened"', text)
        self.assertIn('"ace_interactMenuClosed"', text)
        self.assertIn("diag_tickTime + 0.5", text)
        self.assertIn("USAFDC_fnc_inputFocusActive", text)

    def test_ap_override_uses_focus_helper_and_keeps_debounce(self):
        text = read("addon/functions/autopilot/fn_updateAutopilot.sqf")
        self.assertIn("USAFDC_fnc_inputFocusActive", text)
        self.assertIn("USAFDC_state_apOverrideInhibitUntil", text)
        self.assertIn("0.12", text)
        self.assertIn("PILOT OVERRIDE", text)


class PackageTimingV2Tests(unittest.TestCase):
    def test_reset_function_initializes_package_lifecycle(self):
        text = read("addon/functions/timing/fn_resetPackageTiming.sqf")
        self.assertTrue(text, "missing package timing reset")
        for marker in [
            "USAFDC_state_packageTimingState", "IDLE",
            "USAFDC_state_packageCargoSnapshot", "USAFDC_state_packagePrimaryCargo",
            "USAFDC_state_packageReleaseSimTime", "USAFDC_state_packagePredictedChuteSimTime",
            "USAFDC_state_packagePredictedTouchdownSimTime", "USAFDC_state_packageActualChuteSimTime",
            "USAFDC_state_packageActualTouchdownSimTime",
        ]:
            self.assertIn(marker, text)

    def test_pre_release_estimator_uses_path_route_eta_when_ap_path_valid(self):
        text = read("addon/functions/guidance/fn_estimatePackageTiming.sqf")
        self.assertIn("pathValid", text)
        self.assertIn("routeEtaS", text)
        self.assertIn("USAFDC_state_apArmed", text)
        self.assertIn('get "releaseDelayS"', text)
        self.assertIn("chuteAttachTimeS", text)
        self.assertIn("predictedCanopyTimeS", text)

    def test_tracker_latches_actual_usaf_release_and_post_release_countdown(self):
        text = read("addon/functions/timing/fn_updatePackageTiming.sqf")
        self.assertTrue(text, "missing package timing tracker")
        for marker in [
            # v0.8.0: release is detected by an object leaving the MANIFEST rather
            # than usaf_cargo, so an ACE or vehicle-in-vehicle load leaving the aircraft
            # is now seen. The detection mechanism -- set difference against the
            # previous snapshot -- is unchanged.
            "USAFDC_fnc_getLoadedCargo", "select {!(_x in _currentCargo)}",
            '"RELEASED"', '"CHUTE"', '"ARRIVED"', '"LOST"',
            "attachedTo", 'isKindOf "ParachuteBase"', "isTouchingGround",
            "predictedTouchdownSimTime", "predictedTouchdownSimTime - time",
            "predictedCanopyTimeS", "daytime",
            "packageState", "totTMinusText", "totClockText",
        ]:
            self.assertIn(marker, text)
        self.assertNotIn("USAFDC_setting_calibrationRecorder", text)

    def test_chute_rebases_touchdown_and_arrived_latches_actual_clock(self):
        text = read("addon/functions/timing/fn_updatePackageTiming.sqf")
        self.assertIn("USAFDC_state_packageActualChuteSimTime = time", text)
        self.assertIn("time + USAFDC_state_packagePredictedCanopyTimeS", text)
        self.assertIn("USAFDC_state_packageActualTouchdownSimTime = time", text)
        self.assertIn("USAFDC_state_packageActualTouchdownClockSeconds", text)

    def test_guidance_calls_lifecycle_tracker_and_reset_paths_exist(self):
        update = read("addon/functions/guidance/fn_updateGuidance.sqf")
        post = read("addon/functions/fn_postInit.sqf")
        disarm = read("addon/functions/guidance/fn_disarmGuidance.sqf")
        clear = read("addon/functions/dz/fn_clearDZ.sqf")
        set_dz = read("addon/functions/dz/fn_setDZ.sqf")
        self.assertIn("USAFDC_fnc_updatePackageTiming", update)
        self.assertIn("USAFDC_fnc_resetPackageTiming", post)
        self.assertIn("USAFDC_fnc_updatePackageTiming", post)
        for text in [disarm, clear, set_dz]:
            self.assertIn("USAFDC_fnc_resetPackageTiming", text)


class HudAndPanelV2Tests(unittest.TestCase):
    def test_hud_layout_separates_telemetry_and_steering_strip(self):
        # Was asserted against ui/hud.hpp until v0.4.2. In-engine validation
        # showed hud.hpp is inert: it is compiled into the pre-binarized
        # config.bin, so its geometry never reaches the engine. HUD layout is a
        # runtime contract in fn_updateHud.sqf and must be asserted there.
        hud = read("addon/functions/ui/fn_updateHud.sqf")
        self.assertIn("_hudH", hud)
        self.assertIn("_hudBottomY", hud)
        self.assertIn("_steerCtrl ctrlSetPosition", hud)
        self.assertIn("_centerCtrl ctrlSetPosition", hud)

    def test_the_hud_shows_path_altitude_and_package_state(self):
        """WAS "hud and panel". v0.11.2 removed the panel status block (control 9314) on a flown request, so the
        panel half of this went with it. The HUD half is the half that matters -- it is
        what a pilot reads in the air, and it still carries all of it.

        altitudeErrorM and targetDropAslM were panel-only engineering detail and are now
        gone from the aircraft entirely. The HUD conveys capture state through the ALT
        row's colour rather than the signed error, which the pilot cannot act on
        differently from the state word, so nothing actionable was lost."""
        hud = read("addon/functions/ui/fn_updateHud.sqf")
        for marker in [
            "pathState", "altitudePathState",
            "commandVerticalSpeedMs", "packageState",
            "totTMinusText", "totClockText",
        ]:
            self.assertIn(marker, hud)
        self.assertNotIn("TGT ASL", hud)


if __name__ == "__main__":
    unittest.main(verbosity=2)

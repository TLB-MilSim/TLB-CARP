"""v0.7.0 -- making CARP work with a crew, on a dedicated server.

Five defects were reported from one multiplayer session. Three of them are pinned here
(the autopilot freeze, crew state sharing, and the multiplayer-safety fixes found while
auditing); the cargo rework and the repository cleanup carry their own records.

THE AUTOPILOT FREEZE, AND WHY IT IS A FRAMERATE CLIFF

The control law cannot command a stationary aircraft. fn_updateAutopilot floors the
target at (targetGroundSpeedKmh max 100) / 3.6 = 27.78 m/s and blends toward it with
alpha = min(dt * 1.6, 0.18), so from a standstill it recovers to ~22 m/s inside a
second. A sustained hover is therefore not something this code asks for -- it is the
engine declining to act on what it is asked for.

v0.6.3 measured that decline exactly, on this project's own aircraft. An EachFrame loop
that wrote orientation immediately before setVelocity produced:

    rail with per-frame orientation :   2.0 m/s of actual travel
    no rail at all                  : 138.3 m/s
    velocity only                   : 130.8 m/s

Velocity read the commanded 138.9 m/s on the correct bearing throughout. The commit
that fixed the harness concluded the autopilot was safe "because it runs on the 20 Hz
guidance loop, not EachFrame. The ordering invariant stands; frequency is what broke
this." That conclusion was wrong, and CBA's scheduler says why
(cba_common, init_perFrameHandler.sqf):

    if (diag_tickTime > _delta) then {_x set [2, _delta + _delay]; ... call _function};

A handler whose interval is shorter than the frame time fires EVERY frame, so at or
below 20 fps -- ordinary on a populated dedicated server, essentially unreachable in
the singleplayer testing this project has always used -- a 0.05 s handler IS an
EachFrame handler. And _delta advances by exactly _delay per execution while real time
advances by a whole frame, so once it falls behind it never catches up: one hitch
latches per-frame firing for the rest of the mission. That is why the freeze appeared
on a re-engagement rather than from the first one.
"""
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

    Every absence assertion below has to run against executable code. These files
    explain at length what they deliberately do NOT do -- fn_syncApply names the raw
    globals it refuses to write, fn_steerCargo names setVelocity while explaining that
    it is inert on a remote canopy -- and a raw-text search would find the explanation.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    from strip_sqf_comments import strip_comments

    path = ROOT / rel
    if not path.exists():
        return ""
    return strip_comments(path.read_text(encoding="utf-8"))


AP_UPDATE = "addon/functions/autopilot/fn_updateAutopilot.sqf"
AP_ARM = "addon/functions/autopilot/fn_armAutopilot.sqf"
POSTINIT = "addon/functions/fn_postInit.sqf"
# The PBO-internal path prefix the compile table uses, with single backslashes.
SYNC_PREFIX = "\\x\\usafdc\\addons\\drop_computer\\functions\\sync\\"


class AutopilotActuationRateTests(unittest.TestCase):
    """The freeze fix: bound how often the aircraft transform is written."""

    def test_actuation_is_throttled_against_the_wall_clock(self):
        src = code(AP_UPDATE)
        self.assertIn("USAFDC_state_apLastActuateTick", src)
        self.assertIn('missionNamespace getVariable ["USAFDC_setting_updateInterval", 0.05]', src)
        self.assertIn("(_interval * 0.9)", src)

    def test_throttle_returns_without_stamping_the_tick_used_for_dt(self):
        """dt must stay the real actuation interval.

        If an early return stamped apLastTick, dt would collapse to the PFH period
        while actuation stayed at the configured rate, and the bounded turn rate at
        `_turnRateDegS * _dt` would silently become degrees per call instead of degrees
        per second -- the AP would turn several times too slowly.
        """
        src = code(AP_UPDATE)
        guard = src[src.index("USAFDC_state_apLastActuateTick"):src.index("private _dt =")]
        self.assertIn("exitWith", guard)
        self.assertNotIn("USAFDC_state_apLastTick =", guard)

    def test_orientation_write_requires_a_free_frame(self):
        """The engine needs a frame in which nothing re-seats the transform."""
        src = code(AP_UPDATE)
        self.assertIn("diag_frameNo", src)
        self.assertIn("USAFDC_state_apLastDirFrame", src)
        self.assertIn(">= 2", src)

    def test_velocity_is_still_commanded_on_every_actuation(self):
        """Velocity-only at high rate is measured safe; only orientation is gated.

        v0.6.3's A/B/C gave 130.8 m/s for velocity alone against 2.0 m/s for
        orientation plus velocity, so gating setVelocity would fix nothing and cost
        the AP its speed authority. setDir must therefore sit INSIDE the frame-gap
        block and setVelocity OUTSIDE it, which is a brace-depth question.
        """
        src = code(AP_UPDATE)
        setdir = src.index("_vehicle setDir")
        setvel = src.index("_vehicle setVelocity")
        self.assertLess(setdir, setvel, "setDir wipes velocity; it must come first")

        def depth(idx):
            return src[:idx].count("{") - src[:idx].count("}")

        # v0.16.8: both writes moved one level deeper, inside the legacy `else` branch.
        # The AUTOPILOT NOW FLIES WITH FORCES BY DEFAULT and never writes the transform at
        # all -- so the v0.6.3 invariant this test guards ("velocity every actuation,
        # orientation frame-gated") still governs the transform path, but that path is no
        # longer the one normally taken.
        #
        # The contract is unchanged where it applies: setDir before setVelocity, setDir
        # inside the frame-gap block, setVelocity outside it. Only the nesting moved.
        self.assertEqual(depth(setdir), 2, "setDir is not inside the frame-gap block")
        self.assertEqual(depth(setvel), 1, "setVelocity must run on every legacy actuation")
        # And the legacy path must remain reachable, or the fallback is a fiction.
        self.assertIn('missionNamespace getVariable ["USAFDC_setting_apForceMode", true]', src)

    def test_rate_limit_state_is_initialised_and_reset_on_arm(self):
        post = code(POSTINIT)
        arm = code(AP_ARM)
        for name in ["USAFDC_state_apLastActuateTick", "USAFDC_state_apLastDirFrame"]:
            self.assertIn(f"{name} = -1;", post)
            self.assertIn(f"{name} = -1;", arm)


class AutopilotArmGateTests(unittest.TestCase):
    def test_path_validity_is_checked_at_function_scope(self):
        """exitWith leaves only the innermost scope, and a then-block is a scope.

        Nested inside `if !(isNil ...) then {...}`, the refusal hinted "valid path
        required" and then fell through to USAFDC_state_apArmed = true, so the pilot
        saw a refusal immediately followed by AP ENGAGED and the stale path solution
        from the previous run survived the arm.
        """
        src = code(AP_ARM)
        check = 'if !(_path getOrDefault ["pathValid", false]) exitWith'
        self.assertIn(check, src)
        prefix = src[:src.index(check)]
        self.assertEqual(
            prefix.count("{"), prefix.count("}"),
            "the pathValid exitWith is still nested inside a block and exits only that block",
        )

    def test_arm_refuses_a_non_local_aircraft(self):
        self.assertIn("local _vehicle", code(AP_ARM))

    def test_update_disconnects_when_locality_is_lost(self):
        src = code(AP_UPDATE)
        self.assertIn("AIRCRAFT NOT LOCAL", src)
        self.assertIn("if !(local _vehicle) exitWith", src)

    def test_arm_clears_the_ace_interaction_latch(self):
        """A missed ace_interactMenuClosed latches override detection off forever."""
        self.assertIn("USAFDC_state_apAceInteractOpen = false;", code(AP_ARM))


class CrewSyncContractTests(unittest.TestCase):
    """Defects 2 and 3: pilot and co-pilot share one CARP."""

    FILES = [
        "addon/functions/sync/fn_syncSnapshot.sqf",
        "addon/functions/sync/fn_syncPublish.sqf",
        "addon/functions/sync/fn_syncApply.sqf",
        "addon/functions/sync/fn_syncReconcile.sqf",
        "addon/functions/sync/fn_syncTick.sqf",
        "addon/functions/sync/fn_syncMerge.sqf",
    ]

    def test_every_sync_function_exists_and_is_registered(self):
        """config.bin is pre-binarized, so the compile table is the only way in."""
        post = read(POSTINIT)
        for rel in self.FILES:
            self.assertTrue((ROOT / rel).exists(), rel)
            name = Path(rel).stem.replace("fn_", "")
            self.assertIn(f'["USAFDC_fnc_{name}", "{SYNC_PREFIX}{Path(rel).name}"]', post)

    def test_no_sync_function_has_a_compiled_sibling(self):
        for rel in self.FILES:
            self.assertFalse((ROOT / rel).with_suffix(".sqfc").exists(), rel)

    def test_snapshot_is_intent_only(self):
        """Derived state must never be shared: every client solves for itself.

        Sharing the solution would replace a correct local computation -- one made
        against that client's own view of the aircraft -- with a stale remote one, and
        put a solver on the network at the guidance rate.
        """
        src = code("addon/functions/sync/fn_syncSnapshot.sqf")
        for shared in [
            "USAFDC_state_dzPosASL", "USAFDC_state_dzName", "USAFDC_state_mode",
            "USAFDC_state_profileOverride", "USAFDC_state_manualWind",
            "USAFDC_state_targetAglM", "USAFDC_state_targetGroundSpeedKmh",
            "USAFDC_state_cargoCount", "USAFDC_state_runInLocked", "USAFDC_state_runInDeg",
        ]:
            self.assertIn(shared, src)
        for derived in [
            "USAFDC_state_solution", "USAFDC_state_pathSolution",
            "USAFDC_state_displaySolution", "USAFDC_state_packageTiming",
            "USAFDC_state_apArmed", "USAFDC_state_lastSignedRpM",
        ]:
            self.assertNotIn(derived, src)

    def test_snapshot_reports_want_flags_not_live_armed_flags(self):
        """A client that cannot arm must not publish "off" and disarm the crew."""
        src = code("addon/functions/sync/fn_syncSnapshot.sqf")
        self.assertIn("USAFDC_state_syncWantGuidance", src)
        self.assertIn("USAFDC_state_syncWantAuto", src)
        self.assertNotIn("USAFDC_state_guidanceArmed", src)
        self.assertNotIn("USAFDC_state_autoArmed", src)

    def test_tuple_arity_is_consistent_across_publish_and_apply(self):
        """Two metadata fields plus the payload fields (fifteen since v0.10.1)."""
        snapshot = code("addon/functions/sync/fn_syncSnapshot.sqf")
        payload = snapshot[snapshot.index("["):snapshot.rindex("]") + 1]
        # Count commas at the payload's own bracket depth: several fields are
        # getVariable calls whose default argument carries a comma of its own.
        depth = 0
        fields = 1
        for ch in payload[1:-1]:
            if ch in "[(":
                depth += 1
            elif ch in "])":
                depth -= 1
            elif ch == "," and depth == 0:
                fields += 1
        # EIGHTEEN since v0.11.1. The number moves whenever the panel gains a control. Not
        # sacred --
        # what matters is that the snapshot and fn_syncApply move together, because an
        # apply that expects a different length refuses the record wholesale rather than
        # reading one field wrong. Change both or neither.
        self.assertEqual(fields, 18, "snapshot payload is not 18 fields")
        # v0.9.0: [rev, uid, name, version, payload] -- the payload inside five.
        self.assertIn("if ((count _record) < 5) exitWith {false};", code("addon/functions/sync/fn_syncApply.sqf"))
        self.assertIn("(count _payload) isEqualTo 18", code("addon/functions/sync/fn_syncApply.sqf"))
        self.assertIn("(count _record) >= 5", code("addon/functions/sync/fn_syncTick.sqf"))

    def test_record_lives_on_the_aircraft_with_the_public_flag(self):
        """Airframe-scoped so two crews cannot overwrite each other, and JIP-correct.
        Since v0.9.0 the server's fn_syncMerge is the only machine that writes it."""
        src = code("addon/functions/sync/fn_syncMerge.sqf")
        self.assertIn('_aircraft setVariable ["USAFDC_carpRecord", _newRecord, true]', src)
        self.assertIn('["USAFDC_carpRecordChanged", [_aircraft, _newRecord], crew _aircraft] call CBA_fnc_targetEvent', src)
        self.assertIn('_aircraft getVariable ["USAFDC_carpRecord", []]', code("addon/functions/sync/fn_syncTick.sqf"))

    def test_publish_is_guarded_against_echo_and_against_having_no_aircraft(self):
        src = code("addon/functions/sync/fn_syncPublish.sqf")
        self.assertIn('USAFDC_state_syncApplying', src)
        self.assertIn("if (isNull _aircraft) exitWith", src)

    def test_publish_is_called_only_from_the_two_human_intent_choke_points(self):
        """A polling publisher cannot tell "I changed this" from "I failed to apply
        what someone else changed", and sending the second clobbers the author."""
        self.assertIn("USAFDC_fnc_syncPublish", code("addon/functions/ui/fn_refreshPanel.sqf"))
        self.assertIn("USAFDC_fnc_syncPublish", code("addon/functions/dz/fn_setDZ.sqf"))
        callers = []
        for path in (ROOT / "addon" / "functions").rglob("*.sqf"):
            rel = path.relative_to(ROOT).as_posix()
            if rel.startswith("addon/functions/sync/"):
                continue
            # The compile table in fn_postInit names every function; that is a
            # registration, not a call site.
            if "call USAFDC_fnc_syncPublish" in code(rel):
                callers.append(rel)
        self.assertEqual(
            sorted(callers),
            ["addon/functions/dz/fn_setDZ.sqf", "addon/functions/ui/fn_refreshPanel.sqf"],
        )

    def test_apply_uses_the_real_functions_for_side_effecting_values(self):
        """A raw write would skip the marker, the reset and the per-client solver."""
        src = code("addon/functions/sync/fn_syncApply.sqf")
        self.assertIn("USAFDC_fnc_setDZ", src)
        self.assertIn("USAFDC_fnc_clearDZ", src)
        self.assertIn("USAFDC_fnc_unlockRunIn", src)
        self.assertIn("USAFDC_fnc_syncReconcile", src)
        self.assertNotIn("USAFDC_state_dzPosASL =", src)

    def test_apply_writes_the_run_in_as_a_number_rather_than_recapturing_it(self):
        """fn_lockRunIn reads this client's own view of the track. On a dedicated
        server the co-pilot's copy is network-interpolated, so two independent captures
        give two final lines against a 2-degree release gate."""
        src = code("addon/functions/sync/fn_syncApply.sqf")
        self.assertIn("USAFDC_state_runInDeg = _runInDeg;", src)
        self.assertNotIn("USAFDC_fnc_lockRunIn", src)

    def test_a_record_is_adopted_when_it_differs_not_only_when_it_is_newer(self):
        """v0.7.0 dropped any tuple not numbered above a counter each client kept for
        itself, and that counter could run ahead of the aircraft. See
        test_v090_crew_access.AdoptionTests."""
        src = code("addon/functions/sync/fn_syncTick.sqf")
        self.assertIn("!([_record # 0, _record # 1] isEqualTo [USAFDC_state_syncRev, USAFDC_state_syncUid])", src)

    def test_apply_repaints_an_open_panel(self):
        """Safe to re-enter: refreshPanel raises panelRefreshing and every binarized
        control handler tests it, so a repaint cannot re-fire the handlers."""
        src = code("addon/functions/sync/fn_syncApply.sqf")
        self.assertIn("findDisplay 9300", src)
        self.assertIn("USAFDC_fnc_refreshPanel", src)

    def test_auto_drop_arm_is_attempted_once_and_never_retried(self):
        """fn_armAutoDrop refuses an RP already behind the aircraft and hints why;
        retrying it on a 5 Hz tick would hint that refusal all the way down the run."""
        src = code("addon/functions/sync/fn_syncReconcile.sqf")
        self.assertIn("USAFDC_state_syncAutoAttempted", src)

    def test_guidance_arm_is_probed_before_being_attempted(self):
        """fn_armGuidance hints its failure reason; a 5 Hz retry would paper the
        screen with it."""
        src = code("addon/functions/sync/fn_syncReconcile.sqf")
        self.assertIn("USAFDC_fnc_buildWorldSolution", src)
        self.assertIn('_probe getOrDefault ["valid", false]', src)

    def test_sync_runs_on_its_own_handler_outside_the_guidance_loop(self):
        """Adoption has to work before guidance is armed -- that is exactly when a
        co-pilot needs to pick up the pilot's DZ."""
        post = code(POSTINIT)
        self.assertIn('USAFDC_state_syncPfh = [{[] call USAFDC_fnc_syncTick}, 0.2, []] call CBA_fnc_addPerFrameHandler;', post)
        self.assertIn('["USAFDC_carpRecordChanged", {', post)
        self.assertNotIn("USAFDC_fnc_syncTick", code("addon/functions/guidance/fn_updateGuidance.sqf"))


class CrewAuthorityTests(unittest.TestCase):
    def test_only_the_driver_commands_a_release(self):
        """Once auto drop is shared intent, every crew member's guidance loop holds the
        same armed solution and crosses its own RP within tens of milliseconds of the
        others. USAF's canDrop takes the LAST element of usaf_cargo each time it runs,
        so a second caller releases a second load nobody asked for -- and the
        usaf_cargo_loading flag cannot catch it, because canDrop only raises that after
        a scheduled door animation.
        """
        src = code("addon/functions/auto/fn_triggerAutoDrop.sqf")
        gate = src[:src.index("USAFDC_state_autoDropCommand")]
        self.assertIn("(driver _vehicle) isEqualTo player", gate)
        self.assertIn("exitWith", gate)

    def test_the_autopilot_is_still_the_driver_alone(self):
        self.assertIn("(driver _vehicle) isEqualTo player", code(AP_ARM))

    def test_display_settings_stay_per_player(self):
        """A co-pilot who turned his HUD off must keep it off. CBA scope 0 is
        per-client; scope 1 is server-forced."""
        post = read(POSTINIT)
        for setting in ["hudEnabled", "hudScale", "3dEnabled", "mapTrajectory", "sounds"]:
            line = [ln for ln in post.splitlines() if f"USAFDC_setting_{setting}" in ln and "CBA_fnc_addSetting" in ln]
            self.assertEqual(len(line), 1, setting)
            self.assertTrue(line[0].rstrip().endswith("0] call CBA_fnc_addSetting;"), setting)


class MarkerLocalityTests(unittest.TestCase):
    def test_every_marker_command_stays_local(self):
        """The marker names are fixed literals. A global createMarker with a name that
        already exists fails and returns "", after which a second aircraft's
        setMarkerPos would move the FIRST aircraft's marker -- two crews steering each
        other's map. Crew visibility comes from sharing intent and letting each client
        draw its own, not from replicating markers.
        """
        offenders = []
        for path in (ROOT / "addon" / "functions").rglob("*.sqf"):
            rel = path.relative_to(ROOT).as_posix()
            src = code(rel)
            for cmd in [
                "createMarker ", "setMarkerPos ", "setMarkerType ", "setMarkerColor ",
                "setMarkerText ", "setMarkerShape ", "setMarkerSize ", "setMarkerDir ",
                "setMarkerAlpha ", "setMarkerBrush ", "deleteMarker ",
            ]:
                if cmd in src:
                    offenders.append((rel, cmd.strip()))
        self.assertEqual(offenders, [], f"global marker commands found: {offenders}")


class GuidedCargoLocalityTests(unittest.TestCase):
    def test_steering_commands_only_a_canopy_it_owns(self):
        """v0.7.0 made this refuse and say so, because USAF's release runs where the
        CARGO is local -- on a dedicated server, the server -- so every setVelocity from
        a client was discarded while the HUD reported a closing error.

        v0.8.1 made it work instead: the job goes to whichever machine owns the canopy.
        The locality test survives and still guards the command, but it no longer stops
        the calculation, so every machine can show the crew a true closing error.
        """
        src = code("addon/functions/jpads/fn_steerCargo.sqf")
        self.assertIn("private _commanding = local _steerTarget;", src)
        # Two blocks are gated on _commanding -- rolling the aim offset and issuing
        # the command. The actuation is the last one.
        commanded = src[src.rindex("if (_commanding) then {"):]
        self.assertIn("_steerTarget setVelocity", commanded)
        # ...and nowhere else.
        self.assertEqual(src.count("_steerTarget setVelocity"), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class DedicatedServerLoadTests(unittest.TestCase):
    """fn_postInit used to exit immediately on any machine without a screen."""

    def test_settings_and_compile_table_run_on_every_machine(self):
        """A server that registers no settings cannot force any of them.

        CBA settings must be registered on the server for a server-side
        cba_settings.sqf to pin them, which is how a unit standardises a mod. And
        config.bin's own functions compile everywhere regardless, so a server that
        skipped the state block held functions whose every global read was nil.
        """
        src = code(POSTINIT)
        guard = 'if (!hasInterface) exitWith {'
        self.assertIn(guard, src)
        head = src[:src.index(guard)]
        self.assertIn("CBA_fnc_addSetting", head)
        self.assertIn("compile preprocessFileLineNumbers", head)
        self.assertIn("USAFDC_state_dzPosASL = [];", head)
        self.assertIn('["USAFDC_carpRecordChanged", {', head)
        self.assertIn('["USAFDC_carpPatch", {', head)

    def test_everything_needing_a_screen_is_below_the_guard(self):
        src = code(POSTINIT)
        tail = src[src.index('if (!hasInterface) exitWith {'):]
        for needsScreen in [
            "BIS_fnc_rscLayer",
            "CBA_fnc_addKeybind",
            "ace_interact_menu_fnc_createAction",
            'addMissionEventHandler ["Draw3D"',
            "USAFDC_fnc_syncTick",
        ]:
            self.assertIn(needsScreen, tail, needsScreen)

    def test_the_guided_cargo_loop_runs_on_the_server_too(self):
        """It was below the guard, and that was one of the three reasons guided cargo
        did nothing on a dedicated server.

        setVelocity only works where the object is local, and USAF releases cargo where
        the CARGO is local -- which for an Eden-placed, Zeus-spawned or script-spawned
        load is the server. So the one machine that owned the canopy was also the one
        machine not running the steering loop.
        """
        src = code(POSTINIT)
        head = src[:src.index("if (!hasInterface) exitWith {")]
        self.assertIn('addMissionEventHandler ["EachFrame"', head)
        self.assertIn("USAFDC_fnc_steerTick", head)
        self.assertIn('["USAFDC_steerBegin", {', head)

    def test_the_guard_appears_exactly_once(self):
        self.assertEqual(code(POSTINIT).count("if (!hasInterface) exitWith {"), 1)


class JumpRunMultiplayerTests(unittest.TestCase):
    def test_the_jumplight_is_driven_only_on_a_state_change(self):
        """fn_updateJumpCue calls setJumpLight unconditionally from every branch, and
        INBOUND lasts the whole run-in while PASSED lasts until the pilot disarms. With
        no change detection a GLOBAL event went to every machine in the mission twenty
        times a second for minutes, and each receiver re-coloured the light.
        """
        src = code("addon/functions/jump/fn_setJumpLight.sqf")
        guard = 'if (_state isEqualTo (missionNamespace getVariable ["USAFDC_state_jumpLightState", ""])) exitWith'
        self.assertIn(guard, src)
        self.assertLess(
            src.index(guard),
            src.index("CBA_fnc_globalEvent"),
            "the change test must precede the broadcast",
        )

    def test_the_cache_is_written_only_after_a_successful_broadcast(self):
        src = code("addon/functions/jump/fn_setJumpLight.sqf")
        self.assertLess(
            src.index("CBA_fnc_globalEvent"),
            src.index("USAFDC_state_jumpLightState = _state;"),
        )

    def test_arming_claims_the_airframe_not_just_the_client(self):
        """Two crew arming the same aircraft produced two 20 Hz handlers driving the
        same light from two different views of the aircraft's position: one sent green
        once while the other went on sending red, so the light stayed red through the
        whole green window and every jumper heard two countdowns.
        """
        arm = code("addon/functions/jump/fn_armJumpRun.sqf")
        self.assertIn('_aircraft getVariable ["USAFDC_jumpArmedBy", objNull]', arm)
        self.assertIn('_aircraft setVariable ["USAFDC_jumpArmedBy", player, true]', arm)
        self.assertIn("already armed by", arm)

    def test_disarm_releases_the_claim_only_if_it_is_ours(self):
        src = code("addon/functions/jump/fn_disarmJumpRun.sqf")
        self.assertIn("_armedBy isEqualTo player", src)
        self.assertIn('_aircraft setVariable ["USAFDC_jumpArmedBy", objNull, true]', src)

    def test_the_arm_path_respects_the_claim(self):
        # v0.15.0 moved the control onto the panel, so the ACE condition that mirrored
        # this check is gone. The check itself never lived there -- it is in fn_armJumpRun,
        # which is what actually refuses, and that is the one worth pinning.
        self.assertIn('getVariable ["USAFDC_jumpArmedBy", objNull]',
                      code("addon/functions/jump/fn_armJumpRun.sqf"))


class ObserverClientTests(unittest.TestCase):
    def test_only_the_owner_latches_a_missed_pass(self):
        """A non-owner judges the gate against a replica updated at ~10 Hz and
        extrapolated in between -- metres of error at 140 m/s, against tolerances of
        25 m and 2 degrees."""
        src = code("addon/functions/guidance/fn_updateGuidance.sqf")
        self.assertIn("private _authoritative = local _vehicle;", src)
        self.assertIn('_solution set ["authoritative", _authoritative];', src)
        latch = src[src.index("USAFDC_state_passMissed = true;") - 400:src.index("USAFDC_state_passMissed = true;")]
        self.assertIn("_authoritative", latch)

    def test_the_go_around_instruction_is_owner_only(self):
        src = code("addon/functions/guidance/fn_updateGuidance.sqf")
        hint_idx = src.index("UNSTABLE RUN-IN - NO DROP - GO AROUND")
        gate_idx = src.index("{_authoritative}")
        self.assertLess(gate_idx, hint_idx)

    def test_the_display_still_shows_the_state_on_every_client(self):
        """Withholding the latch must not blank a co-pilot's HUD."""
        src = code("addon/functions/guidance/fn_updateGuidance.sqf")
        gate = src.index("{_authoritative}")
        before = src[:gate]
        self.assertIn('_solution set ["guidanceState", "UNSTABLE RUN-IN"];', before)

    def test_a_non_owning_client_is_still_refused_where_it_matters(self):
        """WAS: the panel says OBSERVING when this client does not own the aircraft.
        v0.11.2 removed the panel status block (control 9314) on a flown request and the notice went with it.

        THIS IS A REAL LOSS AND IT IS RECORDED AS ONE -- a co-pilot gets no hint that the
        numbers in front of them are a replicated copy. What is NOT lost is every refusal
        that depends on it, which is what stops a non-owner acting on that copy, so the
        cost is a missing explanation rather than a wrong action."""
        self.assertIn("aircraft not local to this machine", code("addon/functions/autopilot/fn_armAutopilot.sqf"))
        self.assertIn("(driver _vehicle) isEqualTo player", code("addon/functions/auto/fn_triggerAutoDrop.sqf"))


class SyncEchoGuardTests(unittest.TestCase):
    def test_opening_the_panel_does_not_publish(self):
        """config.bin's onLoad spawns fn_refreshPanel, and fn_refreshPanel publishes -- so
        merely opening the panel looked exactly like a human changing something. On a
        client that had not yet adopted the crew's state that published its factory
        defaults with a higher sequence number and wiped the DZ for everybody.

        The 5 Hz tick normally adopts first, which makes this a race rather than a
        certainty. A race is not a defence.
        """
        src = code("addon/functions/ui/fn_openPanel.sqf")
        # v0.9.0 adopts the aircraft's record before the display exists instead of
        # seeding the payload, so the onLoad refresh finds nothing of its own to send.
        self.assertIn('if !(isNil "USAFDC_fnc_syncTick") then {[] call USAFDC_fnc_syncTick};', src)
        self.assertLess(src.index("USAFDC_fnc_syncTick"), src.index("createDisplay"))

    def test_the_apply_guard_spans_the_panel_repaint(self):
        """fn_refreshPanel publishes. If the guard dropped first, a co-pilot
        whose replica of usaf_cargo was merely lagging would reset the cargo count and
        broadcast that reset over the pilot's deliberate stick size.
        """
        src = code("addon/functions/sync/fn_syncApply.sqf")
        self.assertLess(
            src.index("USAFDC_fnc_refreshPanel"),
            src.index("USAFDC_state_syncApplying = false;"),
        )

    def test_the_cargo_clamp_never_mutates_intent_from_a_non_owner(self):
        src = code("addon/functions/ui/fn_refreshPanel.sqf")
        clamp = src[src.index("USAFDC_state_cargoCount > _availableCargo"):]
        clamp = clamp[:clamp.index("lbClear")]
        self.assertIn("local _cargoVehicle", clamp)

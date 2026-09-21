"""v0.8.1 -- guided cargo on a dedicated server.

WHY IT DID NOTHING, IN THREE PARTS

1. THE COMMAND WENT TO THE WRONG MACHINE. `setVelocity` is a local-effect command, and
   USAF releases cargo where the CARGO is local -- `USAF_CARGO_fnc_canDrop` ends with
   `remoteExec ["USAF_CARGO_fnc_dropCargo", _cargo]`, and the parachute is created inside
   that function. On a dedicated server, anything placed in Eden, spawned by Zeus or
   spawned by a mission script belongs to the server, and neither USAF's loading nor
   `attachTo` transfers ownership. The pilot's client was commanding an object it did not
   own, and Arma discards that silently.

2. THE LOOP DID NOT RUN ON THE SERVER. Its `EachFrame` handler was registered below
   `fn_postInit`'s `hasInterface` guard, so the one machine that owned the canopy was
   also the one machine not trying to steer it.

3. THE GATE WAS CLIENT STATE. Steering required
   `TLB_CARP_state_packageTimingState isEqualTo "CHUTE"`, a global written only by the
   guidance loop, on a client, with a panel open, plus `TLB_CARP_state_dzPosASL` and five
   `TLB_CARP_setting_jpads*` values that are CBA scope-0 and read their defaults on a
   server. Even with 1 and 2 fixed, the server would not have known where the drop zone
   was or that guided cargo was switched on.

THE SHAPE OF THE FIX

The pilot's client -- the only machine holding the crew's DZ and the pilot's settings --
publishes a steer JOB when its package tracker latches RELEASED. Every machine keeps the
job; each acts only on canopies local to it, re-tested every frame because ownership can
move. The control law became a pure function of its arguments so it can run on a machine
with no CARP state at all.
"""
from pathlib import Path
import re
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


LAW = "addon/functions/jpads/fn_steerCargo.sqf"
BEGIN = "addon/functions/jpads/fn_steerBegin.sqf"
TICK = "addon/functions/jpads/fn_steerTick.sqf"
POSTINIT = "addon/functions/fn_postInit.sqf"
TRACKER = "addon/functions/timing/fn_updatePackageTiming.sqf"


class RegistrationTests(unittest.TestCase):
    def test_the_new_functions_exist_and_are_registered(self):
        post = read(POSTINIT)
        for rel in [LAW, BEGIN, TICK]:
            self.assertTrue((ROOT / rel).exists(), rel)
            self.assertIn(Path(rel).name, post)
            self.assertIn(f'"TLB_CARP_fnc_{Path(rel).stem.replace("fn_", "")}"', post)

    def test_no_compiled_sibling_shadows_them(self):
        for rel in [LAW, BEGIN, TICK]:
            self.assertFalse((ROOT / rel).with_suffix(".sqfc").exists(), rel)

    def test_the_receiver_and_the_loop_are_above_the_interface_guard(self):
        """Both have to exist on a machine with no screen, because that machine is
        normally the one that owns the canopy."""
        src = code(POSTINIT)
        head = src[:src.index("if (!hasInterface) exitWith {")]
        self.assertIn('["TLB_CARP_steerBegin", {', head)
        self.assertIn('addMissionEventHandler ["EachFrame"', head)
        self.assertIn("TLB_CARP_fnc_steerTick", head)
        self.assertIn("TLB_CARP_state_steerJobs = [];", head)


class JobDeliveryTests(unittest.TestCase):
    def test_the_job_is_published_with_a_jip_persistent_event(self):
        """A canopy takes most of a minute to come down. A plain globalEvent would leave
        a player who joined during the descent unable to display it, and -- if ownership
        moved to them -- unable to steer it either. globalEventJIP reaches every machine
        now and every machine that joins later."""
        src = code(BEGIN)
        self.assertIn("CBA_fnc_globalEventJIP", src)
        self.assertNotIn("call CBA_fnc_globalEvent;", src)

    def test_the_jip_id_is_derived_from_the_load_so_anyone_can_retire_it(self):
        src = code(BEGIN)
        self.assertIn("netId _cargo", src)
        self.assertIn("TLB_CARP_steer_", src)
        self.assertIn("CBA_fnc_removeGlobalEventJIP", code(TICK))

    def test_the_job_carries_the_pilots_settings_not_the_servers(self):
        """Every TLB_CARP_setting_jpads* is CBA scope 0. On a dedicated server they read
        their defaults, so a server asked to steer would use 12 m/s glide and a 3 m
        release height no matter what the crew had configured -- and would never even
        start, because jpadsEnabled defaults to false."""
        src = code(BEGIN)
        for setting in ["jpadsGlideMs", "jpadsScatterM", "jpadsReleaseAglM", "jpadsEngageVzMs"]:
            self.assertIn(setting, src)
        self.assertIn("TLB_CARP_state_dzPosASL", src)

    def test_guided_cargo_off_means_no_job_at_all(self):
        """The switch still belongs to the pilot. With it off nothing is published, so
        nothing anywhere steers."""
        src = code(BEGIN)
        gate = src[:src.index("TLB_CARP_state_dzPosASL")]
        # Crew state since v0.11.1, so both seats agree on it; still read HERE, on the
        # publishing machine, because the machine that steers cannot read the panel.
        self.assertIn("TLB_CARP_state_jpadsEnabled", gate)
        self.assertIn("exitWith", gate)

    def test_exactly_one_machine_publishes_and_it_is_a_human(self):
        """Every crew member's tracker sees the same load leave. Three publishers would
        be three aim points and three sets of settings for one load.

        And the publisher cannot simply be `local _vehicle`: an AI-flown C-17 with human
        loadmasters aboard belongs to the server, which runs no guidance loop and has no
        DZ, so nobody would publish at all. The choice is computed from `crew _vehicle`,
        which every machine sees identically, so no election is needed.
        """
        src = code(TRACKER)
        self.assertIn("TLB_CARP_fnc_steerPublisher", src)
        self.assertIn("TLB_CARP_fnc_steerBegin", src)
        pub = code("addon/functions/jpads/fn_steerPublisher.sqf")
        self.assertIn("isPlayer _driver", pub)
        self.assertIn("getPlayerUID", pub)
        self.assertIn("crew _vehicle", pub)

    def test_a_job_is_published_for_every_load_that_leaves(self):
        """A stick of four produced ONE guided canopy and three ballistic ones, with the
        HUD reporting STEERING for all of them: the RELEASED transition fires once and
        names one object, and loads 2..n leave while the tracker is already past it.

        Diffing the manifest every tick also catches a drop the pilot made through USAF's
        own action rather than through CARP.
        """
        src = code(TRACKER)
        self.assertIn("forEach _departed", src)
        self.assertIn("TLB_CARP_state_steerSeenCargo", src)
        # The carrier check stops "the player changed aircraft" reading as a mass release.
        self.assertIn("TLB_CARP_state_steerSeenCarrier", src)

    def test_an_unsteered_canopy_is_reported_rather_than_assumed_fine(self):
        """"Another machine is flying it" and "no machine can fly it" look identical from
        the cockpit. The heartbeat is what separates them."""
        self.assertIn('setVariable ["TLB_CARP_steerBeat", time, true]', code(LAW))
        self.assertIn("UNSTEERED - NO OWNER", code(TICK))

    def test_a_canopy_is_a_precondition_not_a_choice_of_target(self):
        """Resolving the parachute as a TARGET is not the same as requiring one, and the
        difference very nearly reintroduced the v0.4.6 defect.

        In level flight the released load inherits the carrier's vertical speed, which is
        about zero, so gravity walks it through the engage window over roughly a second --
        at drop altitude, with 140 m/s of forward throw and no parachute. Time-to-ground
        reads 1500 s there, so the commanded ground velocity is about zero and the whole
        forward throw the release point was computed around is deleted. That landed a load
        93 m out where unguided landed 16 m.
        """
        src = code(LAW)
        self.assertIn('if !(_steerTarget isKindOf "ParachuteBase") exitWith', src)
        self.assertIn("NO CANOPY", src)
        # Before any command, and before the engage-window tests it is protecting.
        self.assertLess(src.index("NO CANOPY"), src.index("_steerTarget setVelocity"))
        self.assertLess(src.index("NO CANOPY"), src.index("-_engageVzMs"))

    def test_wind_is_never_carried_in_the_job(self):
        """The wind term cancels out of the command unless the glide clamp binds, so the
        machine that reads wind only has to be the machine whose simulation applies it.
        Shipping a remote machine's wind reading would break that identity."""
        self.assertNotIn("wind", code(BEGIN))
        self.assertIn("private _wind = wind;", code(LAW))

    def test_the_phase_reaches_the_hud(self):
        """UNSTEERED - NO OWNER is the one state that says guided cargo is on, a canopy
        is open, and no machine is flying it. Showing only the closing error left it with
        nowhere to appear -- indistinguishable from an unguided load."""
        hud = code("addon/functions/ui/fn_updateHud.sqf")
        self.assertIn("TLB_CARP_state_jpadsPhase", hud)
        self.assertIn('format ["JPADS %1", _jpadsPhase]', hud)

    # Read by the HUD, which is where a pilot needs them.
    ON_THE_HUD = [
        "TLB_CARP_state_jpadsActive", "TLB_CARP_state_jpadsPhase", "TLB_CARP_state_jpadsErrorM",
    ]
    # Written every frame and read by no UI since v0.11.2 removed the panel status block (control 9314).
    #
    # They are KEPT rather than deleted, and the distinction is the open measurement
    # question: these are the numbers that decide whether the 0.76 m / 1.15 m guided
    # accuracy transfers to a dedicated server, and that has not been measured yet. They
    # are console instruments now -- `TLB_CARP_state_jpadsClosingMs` in the debug console
    # while a load descends -- rather than a panel line.
    #
    # If that measurement is ever made and closed, delete the writes with the question.
    CONSOLE_INSTRUMENTS = [
        "TLB_CARP_state_jpadsClosingMs", "TLB_CARP_state_jpadsGroundMs",
        "TLB_CARP_state_jpadsTimeRemainingS", "TLB_CARP_state_jpadsTargetOffset",
        "TLB_CARP_state_jpadsPackage", "TLB_CARP_steerSurvival",
    ]

    def test_the_pilot_facing_telemetry_is_on_the_hud(self):
        """Whether guided cargo is steering, what phase it is in and how far off it is --
        including UNSTEERED - NO OWNER, which is the whole difference between guided cargo
        working and guided cargo appearing to work."""
        hud = read("addon/functions/ui/fn_updateHud.sqf")
        for name in self.ON_THE_HUD:
            self.assertIn(name, hud, f"{name} is written every frame and read nowhere")
        self.assertIn("UNSTEERED", hud)

    def test_no_telemetry_global_is_written_without_being_accounted_for(self):
        """State written at frame rate and read by nothing is bookkeeping nobody asked
        for. A new one must land in ON_THE_HUD or be declared a console instrument with a
        reason -- it cannot simply appear."""
        written = set(re.findall(r"(TLB_CARP_(?:state_jpads|steerSurvival)\w*)\s*=", code(TICK) + code(LAW)))
        accounted = set(self.ON_THE_HUD) | set(self.CONSOLE_INSTRUMENTS)
        self.assertEqual(written - accounted, set(),
                         "written every frame and neither on the HUD nor declared an instrument")

    def test_the_survival_ratio_is_still_measured(self):
        """The one figure that predicts whether 0.76 m transfers to a server. It lost its
        panel line but not its measurement -- read it from the console while steering."""
        self.assertIn("TLB_CARP_steerSurvival", code(LAW))

    def test_command_survival_is_measured_not_assumed(self):
        """v0.4.6 measured 8.0 m/s commanded against 3.28 m/s achieved at a 0.05 s
        interval. An EachFrame handler on a 20 fps server IS a 0.05 s interval, so the
        ratio has to be read on the machine now doing the flying."""
        self.assertIn("TLB_CARP_steerSurvival", code(LAW))
        self.assertIn("TLB_CARP_steerSurvival", code(TICK))

    def test_the_steering_rate_is_instrumented(self):
        """The 0.76 m and 1.15 m figures were measured with the steering on a CLIENT.
        This now normally runs on a dedicated server at an unmeasured frame rate, and the
        control law integrates once per frame."""
        src = code(TICK)
        self.assertIn("diag_fps", src)
        self.assertIn("diag_deltaTime", src)
        self.assertIn("isServer", src)

    def test_a_republished_job_replaces_rather_than_stacks(self):
        src = code(POSTINIT)
        handler = src[src.index('["TLB_CARP_steerBegin", {'):]
        handler = handler[:handler.index("CBA_fnc_addEventHandler")]
        self.assertIn("select {!((_x # 0) isEqualTo _cargo)}", handler)


class OwnershipTests(unittest.TestCase):
    def test_every_machine_calculates_but_only_the_owner_commands(self):
        """Holding the job everywhere is what makes an ownership transfer mid-descent
        safe: the machine that gains the canopy already has it.

        And ownership gates the COMMAND only, not the calculation. A pilot whose canopy
        is being flown by the server still needs a true closing error on his HUD; which
        machine happens to hold the object is a networking fact with no business on a
        readout.
        """
        src = code(LAW)
        self.assertIn("private _commanding = local _steerTarget;", src)
        # Two blocks are gated on _commanding -- rolling the aim offset and issuing
        # the command. The actuation is the last one.
        commanded = src[src.rindex("if (_commanding) then {"):]
        self.assertIn("_steerTarget setVelocity", commanded)
        # ...and nowhere else.
        self.assertEqual(src.count("_steerTarget setVelocity"), 1)
        self.assertNotIn("exitWith {[\"REMOTE CANOPY\"]", src)

    def test_locality_is_tested_on_the_canopy_not_the_load(self):
        """They can be owned by different machines, and setVelocity goes to the canopy."""
        src = code(LAW)
        target = src.index("private _steerTarget =")
        check = src.index("local _steerTarget")
        self.assertLess(target, check)
        self.assertIn('_attached isKindOf "ParachuteBase"', src)

    def test_the_control_law_reads_no_carp_state(self):
        """It must produce the same answer on a machine that has never seen the panel."""
        src = code(LAW)
        for forbidden in [
            "TLB_CARP_state_packageTimingState", "TLB_CARP_state_dzPosASL",
            "TLB_CARP_state_packagePrimaryCargo", "TLB_CARP_state_jpadsEnabled",
            "hasInterface",
        ]:
            self.assertNotIn(forbidden, src)


class JobLifecycleTests(unittest.TestCase):
    def test_a_landed_job_is_dropped(self):
        src = code(TICK)
        self.assertIn("<= _releaseAglM", src)

    def test_there_is_a_backstop_for_a_load_that_never_lands(self):
        """A load deleted mid-descent, or one that comes to rest where the height test
        never sees it, would otherwise leak a job and its JIP entry for the mission."""
        src = code(TICK)
        self.assertIn("(time - _startedS) > 600", src)

    def test_the_job_clock_is_mission_time_not_uptime(self):
        """diag_tickTime is the publishing machine's own uptime and means nothing to
        whichever machine ends up pruning the job."""
        src = code(BEGIN)
        self.assertIn("time", src)
        self.assertNotIn("diag_tickTime", src)

    def test_only_one_machine_retires_the_jip_entry(self):
        src = code(TICK)
        retire = src[src.index("CBA_fnc_removeGlobalEventJIP") - 200:src.index("CBA_fnc_removeGlobalEventJIP")]
        self.assertIn("isServer", retire)


class DisplayTests(unittest.TestCase):
    def test_the_readout_is_computed_on_each_display_machine(self):
        """Every input is locally visible -- the load's position, the shared DZ, the aim
        offset broadcast on the load -- so nothing about the HUD line crosses the wire or
        can go stale."""
        src = code(TICK)
        self.assertIn("hasInterface", src)
        self.assertIn("_cargo isEqualTo _live", src)
        for name in [
            "TLB_CARP_state_jpadsActive", "TLB_CARP_state_jpadsPhase", "TLB_CARP_state_jpadsErrorM",
            "TLB_CARP_state_jpadsClosingMs", "TLB_CARP_state_jpadsGroundMs",
            "TLB_CARP_state_jpadsTimeRemainingS",
        ]:
            self.assertIn(name, src)

    def test_the_aim_offset_is_broadcast_so_readouts_agree(self):
        """Steering machine and display machine are no longer the same machine. A
        local-only offset left every other client's closing error wrong by up to the
        scatter radius."""
        self.assertIn('setVariable ["TLB_CARP_jpadsTargetOffset", _offset, true]', code(LAW))

    def test_the_stale_remote_canopy_message_is_gone(self):
        """v0.7.0 made the HUD admit guided cargo could not work on a server. It can
        now, so the admission has to go with it -- a phase the code can no longer reach
        is worse than none."""
        self.assertNotIn("JPADS REMOTE", code("addon/functions/ui/fn_updateHud.sqf"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Parallel drop bench.

TLB_CARP_fnc_debugDropSeries is hard-serialised: TLB_CARP_state_debugHarnessActive
admits one run at a time and the calibration recorder is a singleton, so a batch
of N runs costs N descents. Time acceleration is not a workaround either -- the
carrier kinematic pin uses real-time uiSleep, so accelerating degrades the very
release window being measured.

This bench bypasses the recorder and runs every descent concurrently.
"""
from pathlib import Path
import unittest

from tests.test_sqf_structure import strip_comments_and_strings

ROOT = Path(__file__).resolve().parents[1]
SRC = "addon/functions/debug/fn_parallelDropBench.sqf"


def read(rel: str) -> str:
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.exists() else ""


def code(rel: str) -> str:
    """Executable SQF only -- a comment describing a bug is not the bug."""
    return strip_comments_and_strings(read(rel))


class ParallelBenchTests(unittest.TestCase):
    def test_registered_at_runtime(self):
        post_init = read("addon/functions/fn_postInit.sqf")
        self.assertIn("TLB_CARP_fnc_parallelDropBench", post_init)
        self.assertIn("debug\\fn_parallelDropBench.sqf", post_init)

    def test_does_not_use_the_singleton_calibration_recorder(self):
        text = read(SRC)
        for singleton in ("beginCalibrationRun", "pollCalibrationRun",
                          "TLB_CARP_state_calibrationRun", "TLB_CARP_setting_calibrationRecorder"):
            self.assertNotIn(singleton, text, f"{singleton} would serialise the batch")

    def test_refuses_to_run_alongside_the_series_harness(self):
        text = read(SRC)
        self.assertIn("TLB_CARP_state_debugHarnessActive", text)
        self.assertIn("TLB_CARP_state_pbenchActive", text)

    def test_each_run_gets_its_own_virtual_dz(self):
        """Shared DZ would pile every load into one spot and let them collide."""
        text = read(SRC)
        self.assertIn("_vdz", text)
        self.assertIn("_spacingM", text)
        self.assertIn("getTerrainHeightASL", text)

    def test_restores_the_real_dz_before_spawning_anything(self):
        text = read(SRC)
        solve_restore = text.index("TLB_CARP_state_dzPosASL = +_realDz;")
        spawn_phase = text.index("Phase 2")
        self.assertLess(solve_restore, spawn_phase)

    def test_logs_terrain_height_so_bad_virtual_dzs_can_be_discarded(self):
        text = read(SRC)
        self.assertIn("dzTerrain=%4", text)

    def test_uses_the_real_usaf_drop_path(self):
        text = read(SRC)
        self.assertIn("USAF_CARGO_fnc_forceLoadCargo", text)
        self.assertIn("USAF_CARGO_fnc_canDrop", text)

    def test_keeps_the_kinematic_pin(self):
        """Without it an uncrewed C-17 bleeds speed and the release geometry is
        no longer the requested one."""
        text = read(SRC)
        self.assertIn("setVelocity _velocity", text)
        self.assertIn("_released", text)

    def test_restores_wind_and_cleans_up_after_the_last_run(self):
        text = read(SRC)
        self.assertIn("TLB_CARP_state_pbenchPending <= 0", text)
        self.assertIn("setWind", text)
        self.assertIn("deleteVehicle _x", text)

    def test_single_player_only(self):
        self.assertIn("isMultiplayer", read(SRC))



class ParallelBenchV0413FixTests(unittest.TestCase):
    """First live batch (v0.4.12, 20 runs) exposed three defects:
      1. `_build get "chutePosASL"` -- the key is in the NESTED solution hashmap,
         so it returned nil, and assigning nil in SQF DELETES the variable. Hence
         "Undefined variable in expression: _openalong" and two blank fields.
      2. Each run pinned its carrier from its own scheduled loop on uiSleep 0.01.
         With 20 concurrent loops none got per-frame slices; 9 of 14 loads were
         released at ~0 m/s instead of 139 m/s and fell ~3400 m short.
      3. A grid cell landed in the sea (terrain -18.6 m)."""

    def test_reads_chute_position_from_the_nested_solution_hashmap(self):
        text = read(SRC)
        self.assertIn('getOrDefault ["solution", createHashMap]', text)
        self.assertIn('getOrDefault ["chutePosASL", []]', text)
        self.assertNotIn('_build get "chutePosASL"', text)

    def test_guards_against_nil_reaching_an_assignment(self):
        """nil on the right of `=` silently undefines the variable in SQF."""
        text = read(SRC)
        self.assertIn('(count _predChute) >= 2', text)

    def test_pins_every_carrier_from_one_per_frame_handler(self):
        text = read(SRC)
        self.assertIn('addMissionEventHandler ["EachFrame"', text)
        self.assertIn("TLB_CARP_state_pbenchPins", text)
        self.assertIn("TLB_CARP_pbenchReleased", text)

    def test_no_per_run_pin_loop_remains(self):
        """A per-run pin loop is what starved the scheduler.

        Scoped to the spawned run body: the batch's one-time wind frame-settle wait
        legitimately uses uiSleep 0.01 and runs once, before any run is launched.
        Asserting against the whole file conflated the two."""
        text = code(SRC)
        # Anchors must be CODE: code() strips comments, so a comment anchor vanishes.
        run_body = text[text.index("private _launch ="):text.index("private _effectiveWave =")]
        self.assertNotIn("uiSleep 0.01", run_body)

    def test_removes_the_per_frame_handler_when_the_batch_ends(self):
        text = read(SRC)
        self.assertIn('removeMissionEventHandler ["EachFrame"', text)

    def test_skips_virtual_dzs_in_water(self):
        text = read(SRC)
        self.assertIn("surfaceIsWater", text)
        self.assertIn("SKIPPED", text)


class ParallelBenchWaveTests(unittest.TestCase):
    """A 0.5 s launch stagger does not separate landings: every load takes ~50 s
    to fall, so it becomes a 0.5 s landing stagger. Against a single DZ the loads
    would land on top of each other before their settled positions are sampled.
    Waves bound concurrency instead, and spacingM=0 trades speed for the real DZ."""

    def test_wave_size_and_gap_are_parameters(self):
        text = read(SRC)
        self.assertIn('["_waveSize", 5, [0]]', text)
        self.assertIn('["_waveGapS", 2, [0]]', text)

    def test_launches_in_waves_not_all_at_once(self):
        text = read(SRC)
        self.assertIn("private _launch = {", text)
        self.assertIn("wave=%2 launching runs", text)
        self.assertNotIn("} forEach _plans;", text)

    def test_zero_spacing_uses_the_real_dz_and_waits_for_each_wave(self):
        text = read(SRC)
        self.assertIn("if (_spacingM <= 0) then {_offE = 0; _offN = 0}", text)
        self.assertIn("TLB_CARP_state_pbenchPending <= _remainingAfterWave", text)

    def test_water_check_only_applies_to_the_virtual_grid(self):
        """Superseded form: the check moved into a nudge loop guarded by
        `if (_spacingM > 0)`, so it still cannot fire in real-DZ mode."""
        text = read(SRC)
        self.assertIn("if (_spacingM > 0) then {", text)
        self.assertIn("surfaceIsWater", text)


class ParallelBenchExitWithTests(unittest.TestCase):
    """v0.4.13 used exitWith for the water skip inside the phase-1 forEach.
    exitWith exits the ENTIRE forEach, not the iteration, so run index 4 hitting
    water silently killed runs 5-19: a 20-run request produced 4 results and then
    logged COMPLETE, which looked like success."""

    def test_water_skip_does_not_abort_the_solve_loop(self):
        text = read(SRC)
        self.assertIn("private _dzUsable =", text)
        self.assertIn("if (!_dzUsable) then {", text)

    def test_no_exitwith_inside_the_phase_one_loop(self):
        text = code(SRC)
        loop = text[text.index("private _plans = []"):text.index("forEach _headings")]
        self.assertNotIn("exitWith", loop,
                         "exitWith inside forEach aborts the whole batch")

    def test_logs_how_many_runs_actually_solved(self):
        """A truncated batch must not be able to look complete."""
        self.assertIn("solved %2 of %3 requested runs", read(SRC))


class ParallelBenchSpawnCollisionTests(unittest.TestCase):
    """v0.4.14 real-DZ mode: every run shares the DZ, runs with the same heading
    share an RP, and the carrier spawns directly above its RP -- so a wave of five
    heading-0 runs spawned five C-17s inside each other. They shoved each other off
    the pinned path and the loads were released off-course or destroyed."""

    def test_real_dz_mode_is_forced_serial(self):
        text = read(SRC)
        self.assertIn("private _effectiveWave = if (_spacingM > 0) then {_waveSize max 1} else {1}", text)
        self.assertIn("real-DZ mode forces waveSize 1", text)

    def test_virtual_grid_is_what_makes_concurrency_safe(self):
        """Independent spawn points, not just independent landing sites."""
        text = read(SRC)
        self.assertIn("own spawn point as well as its own landing site", text)

    def test_water_cells_are_nudged_to_land_not_dropped(self):
        text = read(SRC)
        self.assertIn("virtual DZ nudged", text)
        self.assertIn("_tries < 24", text)


class ParallelBenchSpacingFloorTests(unittest.TestCase):
    """One number sets both spawn separation and landing separation. A C-17 is
    ~52 m span / ~53 m long, and observed misses reach ~40 m radial, so a grid
    tighter than ~200 m collides carriers at spawn and loads at touchdown."""

    def test_spacing_has_a_floor(self):
        text = read(SRC)
        self.assertIn("private _minSpacingM = 200;", text)
        self.assertIn("_spacingM = _minSpacingM;", text)

    def test_floor_does_not_disturb_real_dz_mode(self):
        """spacingM = 0 selects the real DZ and must stay 0."""
        text = read(SRC)
        self.assertIn("_spacingM > 0 && {_spacingM < _minSpacingM}", text)

    def test_raise_is_logged_not_silent(self):
        self.assertIn("raised to %2 m", read(SRC))


class ParallelBenchIndestructibleTests(unittest.TestCase):
    """A destroyed load cannot be measured, and destruction is not what this bench
    measures. Landing damage was turning valid data points into wrecks."""

    def test_cargo_and_carrier_are_indestructible(self):
        text = read(SRC)
        self.assertIn("_cargo allowDamage false;", text)
        self.assertIn("_carrier allowDamage false;", text)

    def test_documents_why_allow_damage_alone_was_insufficient(self):
        """v0.4.17 shipped allowDamage false and the loads still exploded; the
        comment must record that setDamage bypasses it, or the next person will
        re-try the same insufficient guard."""
        text = read(SRC)
        self.assertIn("setDamage explicitly ignores allowDamage false", text)


class ParallelBenchDamageResetTests(unittest.TestCase):
    """v0.4.17 set allowDamage false and the loads still exploded. setDamage
    explicitly ignores allowDamage false, and HandleDamage is not raised by
    setDamage either, so whatever destroys them gets through both guards. The
    reliable answer is to keep resetting damage, and to log what damage was taken
    so a destroyed load can never pass as a clean measurement."""

    def test_keeps_all_three_guards(self):
        text = read(SRC)
        self.assertIn("_cargo allowDamage false;", text)
        self.assertIn('_cargo addEventHandler ["HandleDamage", {0}]', text)
        self.assertIn("_cargo setDamage 0;", text)

    def test_damage_is_reset_inside_the_tracking_loop(self):
        text = read(SRC)
        loop = text[text.index("private _peakDamage = 0;"):text.index("private _settled =")]
        self.assertIn("damage _cargo", loop)
        self.assertIn("setDamage 0", loop)

    def test_peak_damage_is_reported(self):
        text = read(SRC)
        self.assertIn("peakDamage=%14", text)
        self.assertIn("_peakDamage toFixed 2", text)


class ParallelBenchDamageOriginTests(unittest.TestCase):
    """peakDamage came back 1.00 on every run: the loads are all destroyed, not
    occasionally colliding. Whether that matters depends on WHEN it happens -- at
    ~0 m AGL it is a landing artefact and the measurements stand; mid-air means the
    trajectory was disturbed and the numbers are worthless."""

    def test_records_the_altitude_at_first_damage(self):
        text = read(SRC)
        self.assertIn("_damageFirstAgl", text)
        self.assertIn("dmgPostRelAgl=%15", text)

    def test_altitude_is_sampled_before_the_damage_check(self):
        """Otherwise the recorded altitude is a tick stale."""
        text = read(SRC)
        block = text[text.index("private _dmg = damage _cargo;"):text.index("if (_agl >= 10)")]
        self.assertLess(block.index("private _agl ="), block.index("_damageFirstAgl = _agl"))


class ParallelBenchCarrierCollisionTests(unittest.TestCase):
    """Uncoupling carrier and cargo is correct in principle and stays, but it did
    NOT fix the damage: v0.4.20 shipped it and 19 of 20 loads were still damaged.
    The "collision at the ramp" reading came from a defect in the harness -- see
    DamageWindowInstrumentationTests."""

    def test_carrier_and_cargo_cannot_collide(self):
        text = read(SRC)
        self.assertIn("_carrier disableCollisionWith _cargo;", text)
        self.assertIn("_cargo disableCollisionWith _carrier;", text)

    def test_does_not_claim_the_pin_collision_was_the_cause(self):
        """v0.4.19-v0.4.20 recorded "the hull sweeps through it at 2.3 m per frame"
        as the cause. It was not: uncoupling the bodies changed nothing. Keep the
        retracted explanation out of the source so it cannot be re-adopted."""
        text = read(SRC)
        self.assertNotIn("2.3 m per frame", text)
        self.assertIn("did NOT stop the damage", text)


class DamageWindowInstrumentationTests(unittest.TestCase):
    """The v0.4.19 "collision at the ramp" conclusion was read off an artefact:
    dmgFirstAgl was only sampled by the post-release loop, so the earliest value it
    could report was the release altitude. Damage taken at spawn, during
    forceLoadCargo, or anywhere in the pinned flight was invisible and got
    attributed to the release frame. All three windows must stay observed."""

    def setUp(self):
        self.src = read(SRC)

    def test_damage_is_sampled_at_spawn_and_after_load(self):
        self.assertIn("private _dmgSpawn = damage _cargo;", self.src)
        self.assertIn("private _dmgLoaded = damage _cargo;", self.src)
        # Spawn sampling must precede the load, and the load sampling must follow it,
        # or the two windows are not actually separated.
        self.assertLess(self.src.index("private _dmgSpawn"), self.src.index("USAF_CARGO_fnc_forceLoadCargo"))
        self.assertLess(self.src.index("USAF_CARGO_fnc_forceLoadCargo"), self.src.index("private _dmgLoaded"))

    def test_pinned_flight_window_is_observed_inside_the_per_frame_handler(self):
        handler = self.src[self.src.index('addMissionEventHandler ["EachFrame"'):]
        handler = handler[:handler.index("} forEach TLB_CARP_state_pbenchPins")]
        self.assertIn("private _pinDmg = damage _pinCargo;", handler)
        self.assertIn("TLB_CARP_pbenchDmgPinnedAgl", handler)

    def test_pin_window_reading_is_read_before_the_carrier_is_deleted(self):
        # The value lives on the carrier, so reading it after deleteVehicle _carrier
        # would silently always return the -1 default.
        read_at = self.src.index('_carrier getVariable ["TLB_CARP_pbenchDmgPinnedAgl"')
        # Anchor on the deletion that FOLLOWS the read: the first "deleteVehicle
        # _carrier;" in the file belongs to the LOAD FAILED branch, which never
        # reaches this code, so comparing against it asserted nothing.
        self.assertNotEqual(-1, self.src.find("deleteVehicle _carrier;", read_at))
        self.assertLess(read_at, self.src.index("private _releasePos = getPosASL _carrier;"))

    def test_all_three_windows_are_logged_separately(self):
        for token in ("dmgSpawn=%16", "dmgLoaded=%17", "dmgPinnedAgl=%18"):
            self.assertIn(token, self.src)
        # The old ambiguous name must not survive -- it now means one specific window.
        self.assertIn("dmgPostRelAgl=%15", self.src)
        self.assertNotIn("dmgFirstAgl=%15", self.src)


class CanopyOpenSamplingTests(unittest.TestCase):
    """Canopy open must be detected per frame, not from each run's scheduled loop.

    v0.4.22 measured chuteAgl 238-300 m when USAF's trigger is a fixed ~300 m, and
    the four runs detecting below 280 m averaged openAlong +36.5 m against +16.1 m
    for prompt ones. The load is doing ~100 m/s horizontally at canopy open, so
    0.76 s of scheduler lag manufactures ~76 m of phantom openAlong -- and openAlong
    is what the canopy table is fitted from."""

    def setUp(self):
        self.src = read(SRC)
        self.handler = self.src[self.src.index('addMissionEventHandler ["EachFrame"'):]
        self.handler = self.handler[:self.handler.index("private _launch =")]

    def test_canopy_open_is_detected_inside_the_per_frame_handler(self):
        self.assertIn("TLB_CARP_state_pbenchChuteWatch", self.handler)
        self.assertIn('_att isKindOf "ParachuteBase"', self.handler)
        for key in ("TLB_CARP_pbenchChuteTime", "TLB_CARP_pbenchChutePos", "TLB_CARP_pbenchChuteAgl"):
            self.assertIn(key, self.handler)

    def test_scheduled_loop_reads_the_reading_instead_of_re_detecting(self):
        loop = self.src[self.src.index("private _damageFirstAgl = -1;"):self.src.index("private _settled =")]
        self.assertIn('_cargo getVariable ["TLB_CARP_pbenchChuteTime"', loop)
        # Re-detecting here would reintroduce the starvation lag.
        self.assertNotIn("ParachuteBase", loop)

    def test_settle_detection_stays_in_the_scheduled_loop(self):
        """A load at rest does not move while the loop is starved, so late settle
        detection is harmless -- and moving it per-frame would cost 20x the work."""
        loop = self.src[self.src.index("private _damageFirstAgl = -1;"):self.src.index("private _settled =")]
        self.assertIn("isTouchingGround _cargo", loop)
        self.assertNotIn("isTouchingGround", self.handler)

    def test_watch_registry_is_initialised_and_torn_down(self):
        self.assertIn("TLB_CARP_state_pbenchChuteWatch = [];", self.src)
        post = read("addon/functions/fn_postInit.sqf")
        self.assertIn("TLB_CARP_state_pbenchChuteWatch = [];", post)


class CargoSpawnPositionTests(unittest.TestCase):
    """dmgSpawn was 1.00 on all 20 runs of v0.4.22 with every later window clean:
    createVehicle at [0,0,200] -- the map corner -- destroyed the load before it
    reached the aircraft. Harmless to the trajectory (setDamage 0 repaired it
    immediately) but it is what made the cook-off audible."""

    def test_no_object_is_created_at_the_map_corner(self):
        self.assertNotIn("[0, 0, 200]", code(SRC))

    def test_load_and_probe_spawn_at_a_valid_in_bounds_position(self):
        # Raw source, not code(): strip_comments_and_strings removes the class and
        # "NONE" literals this assertion depends on.
        text = read(SRC)
        self.assertIn('createVehicle [_cargoClass, [_spawnPosASL # 0, _spawnPosASL # 1, 0], [], 0, "NONE"]', text)
        self.assertIn('createVehicle [_cargoClass, [_vdz # 0, _vdz # 1, 0], [], 0, "NONE"]', text)


class WindVerificationTests(unittest.TestCase):
    """v0.4.23 called setWind and then solved all 20 runs in the same frame. Arma's
    `wind` does not update until the next simulation step, so every run was solved
    against the previous wind and the header logged the previous wind too
    (wind=ZERO [-3.437,-2.414,0]). The batch showed heading-dependent residuals,
    which zero wind cannot produce.

    The fix is fn_debugDropSeries' sequence, which has in-engine evidence behind it.
    These tests pin the bench to it so the two harnesses cannot drift apart."""

    def setUp(self):
        self.src = read(SRC)
        self.block = self.src[self.src.index('if !(_windMode isEqualTo "LIVE") then {'):self.src.index("private _batchId =")]
        self.series = read("addon/functions/debug/fn_debugDropSeries.sqf")

    def test_waits_for_frames_not_just_time(self):
        """THE missing step. uiSleep alone does not guarantee a simulation step has
        published the new wind."""
        self.assertIn("diag_frameNo + 3", self.block)
        self.assertIn("diag_frameNo >= _settleFrame", self.block)

    def test_ace_wind_simulation_is_disabled(self):
        """Verified against ACE 3.21.2.113 ace_weather fnc_updateWind.sqf line 19:
        if (missionNamespace getVariable ["ace_weather_disableWindSimulation", false]) exitWith {};
        """
        self.assertIn("ace_weather_disableWindSimulation = true;", self.block)

    def test_reasserts_for_a_full_second_before_measuring(self):
        """ACE can finish an already-scheduled wind update just after the flag flips."""
        self.assertIn("diag_tickTime + 1", self.block)
        settle = self.block[self.block.index("_aceSettleDeadline"):]
        self.assertIn("setWind [_windTarget # 0, _windTarget # 1, true];", settle)
        self.assertIn("0 setGusts 0;", settle)

    def test_tolerance_matches_the_series_harness(self):
        self.assertIn("private _windControlToleranceMs = 0.05;", self.src)
        self.assertIn("private _windControlToleranceMs = 0.05;", self.series)

    def test_ordering_settle_then_verify_then_solve(self):
        """Solving before the wind is verified is the entire original defect."""
        self.assertLess(self.src.index("diag_frameNo >= _settleFrame"), self.src.index("_achieved = +(wind)"))
        self.assertLess(self.src.index("_achieved = +(wind)"), self.src.index("Phase 1: solve every run"))

    def test_batch_aborts_rather_than_running_with_unverified_wind(self):
        self.assertIn("[PBENCH] ABORT wind never converged", self.block)
        self.assertIn("TLB_CARP_state_pbenchActive = false;", self.block)
        # exitWith inside the wind block leaves only that block, so the abort has to
        # be re-checked at function scope or the batch runs on regardless.
        self.assertIn(
            'if (!(_windMode isEqualTo "LIVE") && {!TLB_CARP_state_pbenchActive}) exitWith {false};',
            self.src,
        )
        self.assertLess(
            self.src.index('&& {!TLB_CARP_state_pbenchActive}) exitWith'),
            self.src.index("Phase 1: solve every run"),
        )

    def test_live_mode_is_not_gated_on_convergence(self):
        """LIVE deliberately takes whatever the mission weather is doing."""
        self.assertIn('if !(_windMode isEqualTo "LIVE") then {', self.src)

    def test_wind_at_release_is_logged_per_run(self):
        """The commanded wind is a request; this records what actually flew."""
        self.assertIn("private _windAtRelease = +(wind);", self.src)
        self.assertIn("windRel=%19", self.src)


class ReleaseLatencyInstrumentationTests(unittest.TestCase):
    """releaseDelayS is script latency, not physics, and it scales with scheduler
    load. A single flown aircraft measured 0.211 s (cue -> cargo leaving usaf_cargo,
    from three CAL_V3 records); this bench runs 8 carriers concurrently and its
    latency is longer, which is why the bench validated the old 0.5285 s while every
    flown drop landed 44 m short. The bench must measure its own lag so bench and
    flown numbers are never conflated."""

    def setUp(self):
        self.src = read(SRC)

    def test_command_instant_is_captured(self):
        self.assertIn("private _cmdSimTime = time;", self.src)
        self.assertIn("private _cmdPosASL = getPosASL _carrier;", self.src)

    def test_command_instant_is_captured_before_the_drop_is_commanded(self):
        """Capturing it after canDrop would measure zero."""
        self.assertLess(
            self.src.index("private _cmdSimTime = time;"),
            self.src.index("spawn USAF_CARGO_fnc_canDrop"),
        )

    def test_lag_is_measured_before_the_carrier_is_deleted(self):
        lag_at = self.src.index("private _lagS = time - _cmdSimTime;")
        self.assertLess(lag_at, self.src.index("deleteVehicle _carrier;", lag_at))

    def test_lag_is_logged_in_both_time_and_distance(self):
        """Time and distance distinguish a fixed-time lag from a fixed-distance ramp
        offset -- the ambiguity three flown drops at one speed could not resolve."""
        self.assertIn("lagS=%20", self.src)
        self.assertIn("lagM=%21", self.src)


class DoorStateBeforeDropTests(unittest.TestCase):
    """Measured in v0.4.30: bench release lag was 0.594 s alone and 0.619-0.722 s at
    8 concurrent, against 0.167-0.300 s flown. Load accounts for only ~0.07 s, so
    concurrency was not the cause. The bench commanded the doors open in the same
    frame it called canDrop, so USAF's drop path waited on the animation."""

    def setUp(self):
        self.src = read(SRC)

    def test_waits_for_doors_before_commanding_the_drop(self):
        self.assertIn("animationPhase", self.src)
        self.assertLess(
            self.src.index("animationPhase"),
            self.src.index("spawn USAF_CARGO_fnc_canDrop"),
        )

    def test_door_wait_precedes_pin_registration(self):
        """Waiting after the pin starts would mean the carrier flies unpinned."""
        self.assertLess(
            self.src.index("animationPhase"),
            self.src.index("TLB_CARP_state_pbenchPins pushBack"),
        )

    def test_door_wait_is_bounded_and_reports_failure(self):
        """A silent timeout would produce runs whose release timing does not match
        flown, indistinguishable from good data."""
        self.assertIn("_doorDeadline", self.src)
        self.assertIn("DOORS NOT FULLY OPEN", self.src)

    def test_lag_instrumentation_survives(self):
        """The lag is how we confirm the fix worked; it must keep being logged."""
        self.assertIn("lagS=%20", self.src)
        self.assertIn("lagM=%21", self.src)


class PerformanceInstrumentationTests(unittest.TestCase):
    """Low frame rate degrades bench runs in a way that is invisible in the results.

    Physics stays consistent in sim time, but the EachFrame pin applies fewer
    velocity corrections per sim second and USAF's own chute-attach check is
    starved. v0.4.31 batch 372 spawned 8 C-17s in one frame; two runs attached their
    chute at 270.1 m and 282.9 m instead of ~298 m and had the batch's worst
    openAlong (78.3 m and 64.8 m). Degraded runs must be identifiable, not averaged
    in with good ones."""

    def setUp(self):
        self.src = read(SRC)

    def test_release_samples_both_clocks_and_fps(self):
        for token in ("_relRealTime = diag_tickTime", "_relSimTime = time", "_fpsAtRelease = diag_fps"):
            self.assertIn(token, self.src)

    def test_sim_to_real_time_ratio_is_computed_over_the_descent(self):
        self.assertIn("_simElapsedS = time - _relSimTime", self.src)
        self.assertIn("_realElapsedS = diag_tickTime - _relRealTime", self.src)
        self.assertIn("_timeRatio", self.src)

    def test_ratio_guards_against_divide_by_zero(self):
        self.assertIn("if (_realElapsedS > 0.001) then", self.src)

    def test_perf_fields_are_logged(self):
        self.assertIn("fps=%22", self.src)
        self.assertIn("timeRatio=%23", self.src)


class SpawnStaggerTests(unittest.TestCase):
    """Creating several C-17s in one frame is a large hitch. Freefall lasts ~23 s, so
    spreading spawns over a fraction of a second does not measurably change descent
    overlap -- it only removes the hitch."""

    def setUp(self):
        self.src = read(SRC)

    def test_stagger_is_a_parameter_with_a_nonzero_default(self):
        self.assertIn('["_spawnStaggerS", 0.35, [0]]', self.src)

    def test_stagger_is_applied_between_launches_within_a_wave(self):
        code_src = code(SRC)
        # code() strips string literals, so the loop variable "_k" is gone from the
        # header -- anchor on the part that survives.
        loop = code_src[code_src.index("from _i to _end do"):]
        loop = loop[:loop.index("_i = _end + 1")]
        self.assertIn("uiSleep _spawnStaggerS", loop)

    def test_stagger_is_not_applied_after_the_last_launch_of_a_wave(self):
        """Otherwise the wave gap is silently longer than requested."""
        self.assertIn("if (_k < _end) then {uiSleep _spawnStaggerS};", self.src)

    def test_stagger_is_threaded_into_the_wave_scheduler(self):
        """A param not passed into the spawned scheduler would read as nil."""
        sched = self.src[self.src.index("[_plans, _launch, _cargoClass"):]
        header = sched[:sched.index("spawn {")]
        self.assertIn("_spawnStaggerS", header)
        self.assertIn('"_spawnStaggerS"', sched[:600])


class DegradedRunFlaggingTests(unittest.TestCase):
    """A degraded run is indistinguishable from a real measurement unless it is
    labelled. v0.4.33 batch 812: seven runs attached the chute at 296.5-299.1 m and
    measured openAlong +4.8 to +9.3 m; the one that attached at 263.3 m measured
    +45.5 m. Averaging those together would put ~5 m of pure artefact into the fit."""

    def setUp(self):
        self.src = read(SRC)

    def test_late_chute_attach_is_flagged(self):
        self.assertIn("LATE_CHUTE_ATTACH", self.src)
        self.assertIn("_chuteAgl < 290", self.src)

    def test_sim_behind_real_is_flagged(self):
        self.assertIn("SIM_BEHIND_REAL", self.src)
        self.assertIn("_timeRatio < 0.9", self.src)

    def test_flags_guard_against_the_sentinel_values(self):
        """chuteAgl and timeRatio are -1 when never measured; -1 < 290 would flag
        every no-chute run as merely degraded."""
        self.assertIn("_chuteAgl >= 0 && {_chuteAgl < 290}", self.src)
        self.assertIn("_timeRatio >= 0 && {_timeRatio < 0.9}", self.src)

    def test_degraded_runs_are_reported_not_discarded(self):
        """Silently dropping them would hide how much of a batch was unusable."""
        self.assertIn("exclude from fits", self.src)
        self.assertIn("degraded=%24", self.src)


class BenchGuidedModeTests(unittest.TestCase):
    """The bench could not exercise JPADS at all: fn_steerCargo read single-package
    globals set only from the player's aircraft. Guided drops measure 0.501 m in live
    flight against ~20 m of unguided canopy scatter in 5 m/s wind, so the path that
    actually delivers accuracy was the one path untestable in bulk."""

    def setUp(self):
        self.src = read(SRC)

    def test_jpads_is_a_batch_parameter(self):
        self.assertIn('["_jpads", false, [false]]', self.src)

    def test_jpads_precedes_the_spawn_stagger_parameter(self):
        """Argument order matters: v0.4.36 shipped jpads as arg 12 behind
        spawnStaggerS, so passing `true` in slot 11 raised
        "Error Params: Type Bool, expected Number". The guided flag is the argument
        callers actually reach for, so it comes first."""
        self.assertLess(
            self.src.index('["_jpads", false, [false]]'),
            self.src.index('["_spawnStaggerS", 0.35, [0]]'),
        )

    def test_argument_order_is_documented_in_the_header(self):
        self.assertIn("11 jpads (bool)", self.src)
        self.assertIn("12 spawnStaggerS", self.src)

    def test_setting_is_forced_on_and_restored(self):
        """fn_steerCargo refuses to run unless the CBA setting is on."""
        # v0.11.1 made guided cargo a panel toggle and crew state. The bench still has
        # to force it on and put back what it found, or a batch run with jpads=false
        # would leave it on for the crew.
        self.assertIn("if (_jpads) then {TLB_CARP_state_jpadsEnabled = true}", self.src)
        self.assertIn("TLB_CARP_state_jpadsEnabled = _jpadsBefore;", self.src)
        self.assertIn('"_jpadsBefore"', self.src)

    def test_steering_calls_the_real_function_with_explicit_target(self):
        """Reimplementing the control law here would test the bench, not the mod."""
        self.assertIn("[_x, _sdz] call TLB_CARP_fnc_steerCargo", self.src)

    def test_steering_runs_in_the_per_frame_handler(self):
        """At the 0.05 s guidance interval only 41% of commanded steering survived
        the parachute's own physics."""
        handler = self.src[self.src.index('addMissionEventHandler ["EachFrame"'):]
        handler = handler[:handler.index("private _launch =")]
        self.assertIn("TLB_CARP_fnc_steerCargo", handler)

    def test_each_load_steers_to_its_own_virtual_cell(self):
        """Otherwise every guided load converges on the real DZ and they collide."""
        self.assertIn('_cargo setVariable ["TLB_CARP_pbenchDz", +_vdz, false]', self.src)
        self.assertIn('_x getVariable ["TLB_CARP_pbenchDz", []]', self.src)

    def test_loads_enter_the_steer_list_only_after_canopy_open(self):
        """Steering during inflation deletes the forward throw the RP is built on."""
        idx = self.src.index("TLB_CARP_state_pbenchSteer pushBack _x")
        chute = self.src.index('_x setVariable ["TLB_CARP_pbenchChuteTime"')
        self.assertLess(chute, idx)

    def test_guided_flag_is_logged_and_state_is_reset(self):
        self.assertIn("jpads=%2", self.src)
        post = read("addon/functions/fn_postInit.sqf")
        self.assertIn("TLB_CARP_state_pbenchSteer = [];", post)
        self.assertIn("TLB_CARP_state_pbenchJpads = false;", post)


if __name__ == "__main__":
    unittest.main(verbosity=2)
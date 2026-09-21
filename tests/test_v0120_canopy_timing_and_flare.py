"""v0.12.0 -- the canopy opens on time, and a guided load lands instead of arriving.

FLOWN, v0.11.3: a stick of three. The canopies opened well below 300 m and the middle
load hit the ground hard enough to destroy the vehicle.

TWO FAULTS, AND ONLY ONE OF THEM IS THE OBVIOUS ONE.

THE CANOPY. USAF's fn_dropCargo does `waitUntil {getPos _obj select 2 < 300}` inside a
spawned script, and CARP's release copied it faithfully. A scheduled script shares roughly
three milliseconds of frame time with every other scheduled script, so a condition written
as "check every frame" means "check whenever the scheduler reaches me".

With ONE load that is prompt, which is why single drops passed acceptance. With a stick it
is not: three release threads, the guidance loop, the package tracker and the steering all
want the same three milliseconds. Cargo freefalls at about 230 m/s, so every slipped frame
is another four to five metres.

And 300 m is not generous -- the load decelerates from terminal over about five seconds,
which needs most of it. A canopy that opens late does not open in time.

This project has met the same trap from the other side. v0.4.x read canopy attach altitudes
of 229.8, 236.7 and 253.7 m against a fixed 300 m trigger and reported it as "the chute
attaches late", which was the poll rather than the physics, and it drove a release-throttle
change that had to be reverted. There the poll was the instrument. Here it was the
MECHANISM, which is worse, and the same answer applies: detect per frame.

THE LANDING. Fixing the canopy would probably have been enough, but it would have left the
real hazard in place. The control law commanded up to jpadsGlideMs of airspeed right down
to jpadsReleaseAglM, three metres. A canopy still chasing its aim point at touchdown
arrives SIDEWAYS carrying that speed across the ground, and a vehicle does not survive it
politely.

The steering term now tapers to zero below a flare height while the WIND term is kept in
full. That distinction is the design: dropping the wind term too would have the load
fighting the air mass all the way down, which is the opposite of gentle.
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


WATCH = "addon/functions/cargo/fn_canopyWatch.sqf"
RELEASE = "addon/functions/cargo/fn_releaseCargo.sqf"
STEER = "addon/functions/jpads/fn_steerCargo.sqf"
POSTINIT = "addon/functions/fn_postInit.sqf"


class CanopyTriggerTests(unittest.TestCase):
    def test_the_release_no_longer_polls_for_the_trigger_altitude(self):
        """THE DEFECT. A scheduled waitUntil is not a per-frame test, and with a stick it
        slipped far enough below 300 m that a load could not decelerate in time."""
        src = code(RELEASE)
        self.assertNotIn("waitUntil", src)
        self.assertNotIn("300", src)

    def test_the_release_hands_the_load_to_the_frame_loop(self):
        src = code(RELEASE)
        self.assertIn("[_cargo, _carrier, _smoke] call TLB_CARP_fnc_canopyWatch;", src)

    def test_the_timed_release_sequence_is_untouched(self):
        """releaseDelayS was measured against the attach / sleep 0.5 / detach / inherit
        sequence. The canopy trigger sits after all of it and moving the trigger must not
        move any of it."""
        src = code(RELEASE)
        self.assertIn("_cargo attachTo [_carrier, [_offset # 0, _offset # 1, _offset # 2]];", src)
        self.assertIn("_cargo setVelocity (velocity _carrier);", src)
        self.assertEqual(src.count("sleep 0.5;"), 2, "USAF's two half-seconds, both kept")

    def test_the_altitude_test_runs_on_the_frame_loop(self):
        src = code(WATCH)
        self.assertIn("CBA_fnc_addPerFrameHandler", src)
        self.assertIn("}, 0] call CBA_fnc_addPerFrameHandler", src)
        # v0.16.4: read through getPosASL. getPos on an ATTACHED object returns its offset
        # from the parent, which opened a canopy at the ramp and destroyed an aircraft.
        # See tests/test_v0164_canopy_altitude.py. The contract here is unchanged.
        self.assertIn("((ASLToAGL (getPosASL _cargo)) # 2) >= _triggerAglM", src)

    def test_the_canopy_is_created_inline_not_handed_back_to_a_scheduler(self):
        """A spawn here would put the scheduler back between the crossing and the chute,
        which is the whole fault."""
        src = code(WATCH)
        cross = src.index("_cargo setVariable [\"TLB_CARP_canopyPending\", false, false]")
        chute = src.index("private _chute = _chuteClass createVehicle")
        self.assertLess(cross, chute)
        self.assertNotIn("spawn", src[cross:chute])

    def test_one_handler_serves_any_number_of_loads(self):
        """A handler per load would be the same scheduling problem in a different
        costume: a stick of eight would be eight handlers competing."""
        src = code(WATCH)
        self.assertEqual(src.count("CBA_fnc_addPerFrameHandler"), 1)
        self.assertIn("if !(isNil \"TLB_CARP_state_canopyPfh\") exitWith {true};", src)
        self.assertIn("} forEach TLB_CARP_state_canopyPending;", src)

    def test_the_handler_stops_when_nothing_is_falling(self):
        """Otherwise it runs every frame for the rest of the mission."""
        src = code(WATCH)
        self.assertIn("CBA_fnc_removePerFrameHandler", src)
        self.assertIn("TLB_CARP_state_canopyPfh = nil;", src)

    def test_the_pending_list_is_initialised(self):
        self.assertIn("TLB_CARP_state_canopyPending = [];", read(POSTINIT))

    def test_the_watcher_is_registered_in_the_compile_table(self):
        """config.bin is pre-binarized, so this is the only way a new function exists."""
        self.assertIn("TLB_CARP_fnc_canopyWatch", read(POSTINIT))
        self.assertIn("fn_canopyWatch.sqf", read(POSTINIT))

    def test_the_opening_altitude_is_logged(self):
        """So a late canopy is never again argued about from memory. The trigger and what
        it actually opened at, in one line."""
        src = code(WATCH)
        self.assertIn("[TLB CARP][CANOPY]", src)
        self.assertIn("_triggerAglM", src)

    def test_the_canopy_geometry_is_unchanged(self):
        """USAF's attach geometry, its side table and its ReammoBox special case all move
        across untouched -- the trigger moved, not what it triggers."""
        src = code(WATCH)
        self.assertIn('_strobe attachTo [_cargo, [0, -2, 0.5]];', src)
        self.assertIn('_cargo attachTo [_chute, [0, 0, -0.5 - (((0 boundingBoxReal _cargo) # 1) # 2)]];', src)
        self.assertIn('case east: {_chuteClass = "O_Parachute_02_F"; _strobeClass = "NVG_TargetW"};', src)

    def test_the_post_canopy_housekeeping_stays_scheduled(self):
        """The five-second level-off, the descent and the tidy-up all sleep and none is
        critical to a metre. Running them on the frame loop would be the opposite
        mistake."""
        src = code(WATCH)
        tail = src[src.index("private _chute = _chuteClass createVehicle"):]
        self.assertIn("spawn {", tail)
        self.assertIn("sleep 5;", tail)


class FlareTests(unittest.TestCase):
    def test_the_steering_term_tapers_near_the_ground(self):
        src = code(STEER)
        self.assertIn('missionNamespace getVariable ["TLB_CARP_setting_jpadsFlareAglM", 25]', src)
        self.assertIn("private _taper = (_aglM / _flareAglM) max 0;", src)

    def test_the_wind_term_is_kept_in_full(self):
        """THE DESIGN. Tapering the wind term too would have the load fighting the air
        mass all the way down, which is the opposite of gentle. Riding the wind is what an
        uncorrected canopy does and what the ballistic solution already predicts."""
        src = code(STEER)
        flare = src.index("_flareAglM")
        cmd = src.index("private _cmdE = (_wind # 0) + _airE;")
        self.assertLess(flare, cmd, "the taper must be applied before the command is built")
        taper = src[flare:cmd]
        self.assertIn("_airE = _airE * _taper;", taper)
        self.assertNotIn("_wind set", taper)
        self.assertNotIn("_windE", taper)

    def test_the_flare_can_be_switched_off(self):
        self.assertIn("if (_flareAglM > 0 &&", code(STEER))

    def test_the_setting_is_server_forced(self):
        """It decides what happens to a load, not what one client sees, and the steering
        may run on a machine that has never had the panel open."""
        lines = [
            ln for ln in read(POSTINIT).splitlines()
            if "TLB_CARP_setting_jpadsFlareAglM" in ln and "addSetting" in ln
        ]
        self.assertEqual(len(lines), 1)
        self.assertIn("[0, 100, 25, 0], 1]", lines[0])

    def test_vertical_speed_is_still_never_touched(self):
        """A long-standing invariant: guided cargo steers horizontally and lets the canopy
        fall at its own rate. Flaring by slowing the descent would be inventing physics."""
        src = code(STEER)
        self.assertIn("_steerTarget setVelocity [_cmdE, _cmdN, _vz];", src)
        self.assertEqual(src.count("setVelocity"), 1)

    def test_the_engine_still_gets_the_last_few_metres(self):
        """The flare tapers steering; jpadsReleaseAglM ends it. Both, not either."""
        self.assertIn("if (_aglM <= _releaseAglM) exitWith", code(STEER))


if __name__ == "__main__":
    unittest.main(verbosity=2)

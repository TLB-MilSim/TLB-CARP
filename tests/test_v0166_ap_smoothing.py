"""v0.16.6 -- the autopilot flies a commanded state instead of correcting the engine.

FLOWN REPORT, and it is three complaints that turn out to be one cause:

    "the moment I enable AP the flying is jittery -- it jitters forward and back very
     slightly every half second or so"
    "it feels like we are by force controlling the speed and movement instead of smoothing
     it out and for example using throttle to adjust for speed"
    "if I'm on a 20 degree dive it will immediately snap level and drop speed even from
     1000 km/h to 350 -- it should slow down smoothly"

WHAT IT USED TO DO

    _alphaSpeed = (_dt * 1.6) min 0.18;
    _newGroundSpeed = _current + ((_target - _current) * _alphaSpeed);

That is a first-order filter on the MEASURED velocity, and it fails in three separate ways
that the crew felt as three separate symptoms.

1. IT IS NOT A COMMAND. Whatever the engine did to the velocity between writes is fed
   straight back into the next write, so the aircraft spends every tick correcting the
   engine rather than flying a trajectory. That is the "forcing" in the report.

2. ITS TIME CONSTANT IS ABOUT 0.6 SECONDS. Roughly two seconds to wash off 180 m/s and to
   pull level from a dive. No transport does either.

3. THE 0.18 CLAMP BREAKS ITS OWN dt SCALING. The measured actuation interval is bimodal --
   a mode at the configured 0.05 s and a second at 0.09-0.10 s, about 23% of ticks -- so a
   long tick applies a disproportionately large correction and the irregular interval
   becomes an irregular lurch.

WHAT IT DOES NOW

The commanded speed and vertical speed are held as AP state and moved toward their targets
by at most (rate * dt). Seeded from the ACTUAL velocity on the first actuation, so engaging
is continuous with whatever the pilot was doing. Both rates are accelerations, both are CBA
settings, because the right numbers are a flying judgement and not a measurement.

And the throttle became a real speed loop. It read (_target - _newGroundSpeed) where
_newGroundSpeed had already been dragged to within a few per cent of the target, so the
error was near zero and the throttle sat at its baseline doing nothing -- every bit of speed
authority came from setVelocity. It now reads the MEASURED speed.

THE HALF-SECOND PERIOD

The AP TRACK instrument ran at exactly 0.5 s and diag_log is a synchronous write to the RPT.
A period that matches the reported symptom to the tick is worth removing from the normal
flight path before anything subtler is blamed, so it is now behind the debug setting. That
is a CANDIDATE, not a finding, and this file says so: the 15.8 Hz actuation rate against a
configured 20 is a second irregularity that this does not explain.

WHAT DELIBERATELY DID NOT CHANGE

setDir still precedes setVelocity (the v0.3.0 invariant), commanded horizontal velocity is
still aligned with commanded nose heading (v0.3.2), setVelocity still runs on every
actuation because gating it costs speed authority and fixes nothing (v0.6.3), and no
per-frame transform write was added. The turn-rate schedule is untouched.

v0.16.8 NOTE: those transform invariants still hold, but that path is no longer the default.
The autopilot now flies with forces and never writes the transform at all; the paragraph
above describes the legacy path, kept behind TLB_CARP_setting_apForceMode.
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
    sys.path.insert(0, str(ROOT / "tools"))
    from strip_sqf_comments import strip_comments

    path = ROOT / rel
    return strip_comments(path.read_text(encoding="utf-8")) if path.exists() else ""


AP = "addon/functions/autopilot/fn_updateAutopilot.sqf"
ARM = "addon/functions/autopilot/fn_armAutopilot.sqf"
POSTINIT = "addon/functions/fn_postInit.sqf"


class CommandedStateTests(unittest.TestCase):
    def test_the_measurement_filter_is_gone(self):
        """THE DEFECT. Blending from the measured velocity every tick is what made the
        aircraft correct the engine instead of flying."""
        src = code(AP)
        self.assertNotIn("_alphaSpeed", src)
        self.assertNotIn("_alphaZ", src)
        self.assertNotIn("(_dt * 1.6) min 0.18", src)

    def test_both_commands_move_by_a_bounded_acceleration(self):
        src = code(AP)
        self.assertIn("private _speedStep = _accelMs2 * _dt;", src)
        self.assertIn("private _vzStep = _vzRateMs2 * _dt;", src)
        self.assertIn("_cmdSpeed = _cmdSpeed + (((_targetGroundSpeedMs - _cmdSpeed) max (-_speedStep)) min _speedStep);", src)
        self.assertIn("_cmdVz = _cmdVz + (((_targetVz - _cmdVz) max (-_vzStep)) min _vzStep);", src)

    def test_the_command_is_what_is_flown(self):
        """Not a blend of the command and the measurement -- the whole point is that the
        commanded trajectory is independent of what the engine did last frame."""
        src = code(AP)
        self.assertIn("private _newGroundSpeed = _cmdSpeed;", src)
        self.assertIn("private _newVz = _cmdVz;", src)

    def test_the_command_is_seeded_from_the_actual_velocity(self):
        """So engaging is continuous. A command seeded from the TARGET would snap exactly
        as hard as the filter it replaced."""
        src = code(AP)
        self.assertIn("if (_cmdSpeed < 0) then {_cmdSpeed = _currentGroundSpeed};", src)
        self.assertIn("if (_cmdVz < -1e8) then {_cmdVz = _vel # 2};", src)

    def test_arming_clears_the_command_rather_than_setting_it(self):
        """Seeding at arm time would go stale if anything changed between the arm and the
        first actuation. The sentinel makes the first tick do it."""
        src = code(ARM)
        self.assertIn("TLB_CARP_state_apCmdSpeedMs = -1;", src)
        self.assertIn("TLB_CARP_state_apCmdVzMs = -1e9;", src)

    def test_the_state_is_initialised_at_load(self):
        """An unset command reads nil, and nil in the arithmetic above throws inside the AP
        on every frame."""
        src = read(POSTINIT)
        self.assertIn("TLB_CARP_state_apCmdSpeedMs = -1;", src)
        self.assertIn("TLB_CARP_state_apCmdVzMs = -1e9;", src)


class RatesAreTunableTests(unittest.TestCase):
    def test_both_rates_are_settings(self):
        """The right numbers are a flying judgement, and Addon Options are not reachable in
        flight -- but these are set before a sortie, not during one, so a setting is the
        right home rather than a panel field."""
        src = read(POSTINIT)
        self.assertIn('["TLB_CARP_setting_apAccelMs2", "SLIDER"', src)
        self.assertIn('["TLB_CARP_setting_apVzRateMs2", "SLIDER"', src)

    def test_the_defaults_are_a_transport_not_a_fighter(self):
        """1.5 m/s2 is roughly a loaded transport shedding speed on idle thrust; 2.5 m/s2 of
        vertical-rate change is a gentle pull rather than a snap."""
        src = read(POSTINIT)
        self.assertIn("[0.3, 6.0, 1.5, 2], 0]", src)
        self.assertIn("[0.5, 8.0, 2.5, 2], 0]", src)

    def test_the_ap_reads_them_with_matching_defaults(self):
        """A setting whose default disagrees with the code's fallback gives two different
        aircraft depending on whether CBA has initialised yet."""
        src = code(AP)
        self.assertIn('getVariable ["TLB_CARP_setting_apAccelMs2", 1.5]', src)
        self.assertIn('getVariable ["TLB_CARP_setting_apVzRateMs2", 2.5]', src)

    def test_they_are_client_settings(self):
        """v0.16.10 MOVED THESE TO CLIENT SCOPE. Every one changes how the autopilot
        FLIES, and the autopilot only ever runs on the machine flying the aircraft.
        Scope 1 put them behind the server tab where a pilot could not reach them --
        reported as "I don't see the sliders", which was correct."""
        src = read(POSTINIT)
        for line in src.splitlines():
            if "TLB_CARP_setting_apAccelMs2" in line or "TLB_CARP_setting_apVzRateMs2" in line:
                if "addSetting" in line:
                    self.assertIn(", 0] call CBA_fnc_addSetting;", line)


class ThrottleTests(unittest.TestCase):
    def test_the_throttle_reads_the_measured_speed(self):
        """It read the COMMANDED speed, which the blend had already pulled to the target, so
        the error was near zero and the throttle did nothing. All the authority came from
        setVelocity -- the forcing that was reported."""
        src = code(AP)
        self.assertIn("private _speedErr = _targetGroundSpeedMs - _currentGroundSpeed;", src)
        # v0.16.8 raised the gain from 0.015 to 1/15 -- HAL's value. At 0.015 a 20 m/s
        # error moved the throttle by 0.3, which was only survivable because setVelocity
        # was doing the real work. In force mode the throttle IS the speed authority.
        self.assertIn("private _throttleCmd = (0.58 + (_speedErr / 15)) max 0.20 min 1.0;", src)
        self.assertNotIn("(_targetGroundSpeedMs - _newGroundSpeed) * 0.015", src)


class InstrumentTests(unittest.TestCase):
    def test_the_half_second_log_is_off_by_default(self):
        """Its period matched the reported symptom exactly and diag_log writes to disk on
        the render thread. Removing it from the normal flight path is free to test."""
        src = code(AP)
        self.assertIn('if ((missionNamespace getVariable ["TLB_CARP_setting_debug", false]) && {(diag_tickTime - (missionNamespace getVariable ["TLB_CARP_state_apTrackLogTick", -1e9])) >= 0.5}) then {', src)

    def test_the_log_still_exists_and_shows_the_new_command(self):
        """Gated, not deleted -- it is still the only instrument on this loop, and it now has
        to show the commanded speed or the new model is invisible in it."""
        src = code(AP)
        self.assertIn("[TLB CARP][AP TRACK]", src)
        self.assertIn("cmdGs=", src)
        self.assertIn("_cmdSpeed toFixed 2", src)

    def test_the_candidate_is_recorded_as_a_candidate(self):
        """This project has adopted a plausible mechanism without a magnitude before. The
        source has to say which this is."""
        src = read(AP)
        self.assertIn("That is a candidate, not a finding", src)


class InvariantsTests(unittest.TestCase):
    def test_setdir_still_precedes_setvelocity(self):
        """v0.3.0: setDir wipes velocity."""
        src = code(AP)
        self.assertLess(src.index("_vehicle setDir _newHeading;"),
                        src.index("_vehicle setVelocity _newVel;"))

    def test_commanded_velocity_is_still_aligned_with_commanded_heading(self):
        """v0.3.2, the reverse-flight fix during large intercepts."""
        src = code(AP)
        self.assertIn("_newGroundSpeed * sin _newHeading", src)
        self.assertIn("_newGroundSpeed * cos _newHeading", src)

    def test_setvelocity_still_runs_on_every_actuation(self):
        """v0.6.3: gating it costs speed authority and fixes nothing. Only the orientation
        write is frame-gated."""
        src = code(AP)
        i = src.index("_vehicle setVelocity _newVel;")
        window = src[max(0, i - 400):i]
        self.assertNotIn("if ((diag_frameNo", window.split("_vehicle setDir")[-1])

    def test_the_turn_rate_schedule_is_untouched(self):
        src = read(AP)
        block = src[src.index("_turnRateDegS = switch"):]
        block = block[:block.index("\n};")]
        found = re.findall(r'case "([A-Z ]+)":\s*\{([0-9.]+)\}', block)
        self.assertEqual(found, [("INTERCEPT", "6"), ("CAPTURE FINAL", "4"), ("FINAL RUN", "2.5"),
                                 ("RELEASE STABLE", "2.0"), ("POST DROP", "2.0")])

    def test_no_position_rail_was_introduced(self):
        src = code(AP)
        self.assertNotIn("setPos", src)
        self.assertNotIn("setPosASL", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)

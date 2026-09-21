"""v0.16.8 -- the autopilot flies the aircraft instead of moving it.

THE REPORT, after v0.16.6 had already smoothed the COMMAND and cured the snap on engage:

    "AP still janky and jittery. I recommend I have in mods folder 2 mods that have AP or 3.
     USAF AC130 Beta has it's own AP, Realistic Auto Pilots mod and Hatchet UH60 mod...
     Can we unpack and figure out how they handle AP so we don't get the jitters?"

Unpacked @Realistic Auto Pilots (HAL, by Blockdude, largely from ITC by BlackHawk). The
answer was in the first file and it is one line long:

    NOT ONE FILE IN THAT MOD CALLS setVelocity OR setDir.

It applies forces and torques -- addForce, addTorque, setAirplaneThrottle -- and lets Arma's
flight model do the flying.

WHY THAT IS THE WHOLE DIFFERENCE

setVelocity and setDir OVERWRITE the engine's own integration. Between two writes Arma flies
the aeroplane properly; the next write throws that away and substitutes the commanded state.
At the measured 15.8 Hz actuation rate that is sixteen discontinuities a second.

This is why v0.16.6 did not fix it. Smoothing the COMMAND makes the substituted state change
gently, but every substitution still discards whatever the flight model just did. The judder
was never in the command -- it was in the act of writing it.

WHAT WAS TAKEN

The structure, not the numbers:

    pitch   a vertical force applied ahead of the centre of gravity, which is a pitching
            moment, driving FLIGHT PATH ANGLE rather than pitch attitude
    roll    bank-to-turn: heading error commands a bank, torque holds the aircraft at it
    yaw     torque proportional to sideslip, so the turn stays coordinated
    trim    an integral term accumulated over 100 samples, because every flight model has a
            standing force deficit and a proportional term alone answers it with a permanent
            small error -- an aircraft that slowly sinks
    mass    every gain scales by getMass, so a C-17 and a Blackfish get proportionate effort

THE HONEST COST, WHICH IS NOT SMALL

A real aircraft turns at g*tan(bank)/V. At 30 degrees of bank and 140 m/s that is about
2.3 deg/s. The old code yawed the nose at up to 6 deg/s, which no transport does at drop
speed. The aircraft will now take noticeably longer to come round onto an intercept, because
that is what an aircraft does.

That is a behaviour change large enough that the old path is kept and selectable. The force
response depends on each airframe's flight model, and CARP flies a C-17, a C-130, a V-44 and
anything else that is kindOf Air -- none of which this has been flown on.
"""
from pathlib import Path
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


def _block(src, start):
    """Return the braced block opening at `start`, by depth.

    NOT by searching for the next "} else {" -- the flight-path-angle lines contain their
    own `else {0}` and a naive search cuts the branch three lines in, which silently makes
    every assertion below it pass or fail for the wrong reason."""
    i = src.index("{", start)
    depth, j = 0, i
    while j < len(src):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
        j += 1
    raise AssertionError("unbalanced block")


def force_branch() -> str:
    src = code(AP)
    return _block(src, src.index("if (_forceMode) then {"))


def legacy_branch() -> str:
    src = code(AP)
    i = src.index("if (_forceMode) then {")
    after = i + len(_block(src, i))
    return _block(src, src.index("else", after))


class ForceModeTests(unittest.TestCase):
    def test_the_force_path_never_writes_the_transform(self):
        """THE ENTIRE POINT. A single setVelocity or setDir in here reintroduces the
        discontinuity this exists to remove."""
        b = force_branch()
        for forbidden in ["setVelocity", "setDir", "setPos", "setPosASL", "setVectorDir"]:
            self.assertNotIn(forbidden, b, forbidden)

    def test_it_applies_force_and_torque(self):
        b = force_branch()
        self.assertIn("_vehicle addForce [_vehicle vectorModelToWorld [0, 0, _pitchForce * _rateComp], [0, 500, 0]];", b)
        self.assertIn("_vehicle addTorque (_vehicle vectorModelToWorld [0, -_bankTorque * _rateComp, 0]);", b)
        # v0.16.10 gave the yaw channel a turn-coordination feedforward alongside the
        # sideslip feedback, so the rudder answers the turn as well as the slip.
        self.assertIn("_vehicle addTorque (_vehicle vectorModelToWorld [0, 0, _yawTorque * _rateComp]);", b)

    def test_the_pitch_channel_drives_flight_path_angle_not_attitude(self):
        """Holding a pitch ATTITUDE lets an aircraft mush up or down at constant attitude.
        Holding the PATH is what altitude hold actually means."""
        b = force_branch()
        self.assertIn("private _targetFpa = if (_currentGroundSpeed > 1) then {(_cmdVz atan2 _currentGroundSpeed)} else {0};", b)
        self.assertIn("private _actualFpa = if (_currentGroundSpeed > 1) then {(_vz atan2 _currentGroundSpeed)} else {0};", b)

    def test_every_gain_scales_with_aircraft_mass(self):
        """A C-17 and a Blackfish differ by an order of magnitude in mass. A fixed force
        would be a nudge on one and a catapult on the other."""
        b = force_branch()
        self.assertIn("private _massMult = (getMass _vehicle) * 0.0001;", b)
        for term in ["_pitchForce = (_targetFpa - _actualFpa) * 1.0 * _massMult",
                     # v0.16.10 added roll-rate damping inside the bank term and folded the
                     # yaw feedforward in with the slip; both still scale by mass.
                     "_rollRate * _rollDamp)) * _massMult",
                     "(_bank * _yawFF)) * _massMult"]:
            self.assertIn(term, b, term)

    def test_the_integral_trim_exists_and_is_bounded(self):
        """Without it the aircraft holds altitude with a permanent small error, which over a
        long run-in is a slow sink. Only accumulated while the error is small, so a genuine
        manoeuvre never poisons the trim."""
        b = force_branch()
        self.assertIn("if ((abs _pitchForce) < 20) then {", b)
        self.assertIn("USAFDC_state_apTrimCount >= 100", b)
        self.assertIn("USAFDC_state_apTrimSum / 100", b)

    def test_the_impulse_is_rate_compensated_and_clamped(self):
        """addForce acts for ONE simulation step, so actuating at 20 Hz on a 60 fps machine
        delivers a third of the intended impulse. The clamp is there because diag_fps is
        smoothed and a wild value would be indistinguishable from the judder this removes."""
        b = force_branch()
        self.assertIn("private _rateComp = ((_dt * (diag_fps max 1)) max 1) min 6;", b)

    def test_bank_is_capped_per_path_state(self):
        """A release run is flown wings-near-level; only an intercept gets real bank. The
        release gate reads |trackError| <= 2 deg, which a banked aircraft cannot hold."""
        b = force_branch()
        for state, cap in [("INTERCEPT", "30"), ("CAPTURE FINAL", "20"), ("FINAL RUN", "8"),
                           ("RELEASE STABLE", "4")]:
            self.assertIn(f'case "{state}": {{{cap}}}', b, state)

    def test_sideslip_is_corrected(self):
        """Left uncorrected the nose hangs outside the turn and the run is flown crabbed,
        which the release gate reads as track error."""
        b = force_branch()
        self.assertIn("private _slip = (_vehicle vectorWorldToModel _vel) # 0;", b)


class LegacyPathTests(unittest.TestCase):
    def test_the_old_path_is_kept_and_reachable(self):
        """The old path is measured and this one is not. A fallback nobody can select is not
        a fallback."""
        src = code(AP)
        self.assertIn('private _forceMode = missionNamespace getVariable ["USAFDC_setting_apForceMode", true];', src)
        self.assertIn('["USAFDC_setting_apForceMode", "CHECKBOX"', read(POSTINIT))

    def test_the_legacy_invariants_still_hold_where_they_apply(self):
        """v0.3.0: setDir wipes velocity so it must come first. v0.6.3: velocity every
        actuation, orientation frame-gated. Both still true inside the legacy branch."""
        b = legacy_branch()
        self.assertLess(b.index("_vehicle setDir _newHeading;"), b.index("_vehicle setVelocity _newVel;"))
        self.assertIn("diag_frameNo - (missionNamespace getVariable [\"USAFDC_state_apLastDirFrame\", -1])) >= 2", b)

    def test_the_default_is_the_new_behaviour(self):
        """Stated explicitly: the crew asked for this, so it ships on."""
        src = code(AP)
        self.assertIn('"USAFDC_setting_apForceMode", true]', src)
        for line in read(POSTINIT).splitlines():
            if '"USAFDC_setting_apForceMode"' in line and "addSetting" in line:
                self.assertIn("], true, 0] call CBA_fnc_addSetting;", line)


class StateTests(unittest.TestCase):
    def test_the_trim_state_is_initialised(self):
        """nil in the accumulator throws inside the AP on every frame."""
        src = read(POSTINIT)
        for v in ["USAFDC_state_apTrimCount = 0;", "USAFDC_state_apTrimSum = 0;",
                  "USAFDC_state_apTrimOffset = 0;"]:
            self.assertIn(v, src, v)

    def test_the_trim_is_cleared_on_arm(self):
        """It belongs to one engagement on one aircraft. Carrying it across arms would apply
        a C-17's standing force deficit to a C-130."""
        src = code(ARM)
        self.assertIn("USAFDC_state_apTrimOffset = 0;", src)


class ThrottleTests(unittest.TestCase):
    def test_the_gain_matches_the_reference(self):
        """HAL uses (target - speed)/15. Ours was 0.015 -- more than four times weaker,
        survivable only because setVelocity was doing the real work. In force mode the
        throttle IS the speed authority."""
        self.assertIn("private _throttleCmd = (0.58 + (_speedErr / 15)) max 0.20 min 1.0;", code(AP))

    def test_the_throttle_is_outside_the_mode_branch(self):
        """Both modes need it, and in force mode it is the only speed authority there is."""
        src = code(AP)
        self.assertGreater(src.index("setAirplaneThrottle"), src.index("_vehicle setVelocity _newVel;"))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TurnDampingTests(unittest.TestCase):
    """v0.16.10 -- the chase between XTRK left and right.

    Flown: "it banks left, but by the time the vector passes it starts to turn back right,
    and by the time it's straight the vector is on the other side." That is a textbook
    proportional-only oscillation, and the diagnosis is in the description: commanded bank
    was k * headingError and nothing else, so at zero error the commanded bank was zero
    while the aircraft was still turning at up to three degrees a second. Nothing in the
    loop knew the aircraft had a turn rate.
    """

    def test_the_bank_command_leads_the_turn(self):
        """Not a damper -- a prediction. A turn rate of w deg/s closes w*lead degrees over
        the lead time, so the aircraft begins rolling out while the needle is still off
        centre, which is what a pilot does."""
        b = force_branch()
        self.assertIn("private _errPredicted = _headingError - (_hdgRate * _leadS);", b)
        self.assertIn("private _targetBank = ((_errPredicted * 1.5) max (-_maxBank)) min _maxBank;", b)

    def test_the_roll_loop_is_damped_too(self):
        """Two undamped loops in series is why the chase never settled: the bank loop
        overshot its own commanded bank as well."""
        b = force_branch()
        self.assertIn("(((_targetBank - _bank) * 300) - (_rollRate * _rollDamp)) * _massMult", b)

    def test_both_rates_are_measured_not_inferred(self):
        """g*tan(bank)/V is right only in a steady coordinated turn -- precisely the state
        the aircraft is NOT in while it is chasing."""
        b = force_branch()
        self.assertIn("_hdgRate = ((((_currentDir - _prevDir) + 540) mod 360) - 180) / _dt;", b)
        self.assertIn("_rollRate = (_bank - _prevBank) / _dt;", b)

    def test_the_first_tick_produces_no_rate(self):
        """A difference needs two samples. Without the guard the first tick reads a rate of
        the whole heading and commands full opposite bank."""
        b = force_branch()
        self.assertIn("if (_prevDir > -1e8) then {", b)

    def test_the_rate_history_is_cleared_on_arm(self):
        """A stale sample across an arm reads as a huge turn rate on the first tick."""
        src = code(ARM)
        self.assertIn("USAFDC_state_apPrevDir = -1e9;", src)
        self.assertIn("USAFDC_state_apPrevBank = -1e9;", src)

    def test_the_rate_history_is_initialised_at_load(self):
        src = read(POSTINIT)
        self.assertIn("USAFDC_state_apPrevDir = -1e9;", src)
        self.assertIn("USAFDC_state_apPrevBank = -1e9;", src)


class YawCoordinationTests(unittest.TestCase):
    """Flown: "I don't see the AP using YAW at all... the tail isn't moving even in roll
    turns." Correct: the only yaw term was proportional to SIDESLIP, and the flight model
    keeps sideslip near zero in a turn, so the rudder had nothing to answer."""

    def test_the_rudder_answers_the_turn_as_well_as_the_slip(self):
        b = force_branch()
        self.assertIn("private _yawTorque = ((_slip * 200) + (_bank * _yawFF)) * _massMult;", b)

    def test_yaw_is_never_driven_by_heading_error(self):
        """THE LINE THAT MUST NOT BE CROSSED. Rudder used to TURN makes the aircraft skid,
        and lateral velocity at release is what the gate punishes hardest -- +1.294 m/s
        measured as about +30 m of miss. Yaw coordinates; bank steers."""
        b = force_branch()
        yaw = b[b.index("private _yawTorque"):]
        yaw = yaw[:yaw.index(";") + 1]
        for forbidden in ["_headingError", "_errPredicted", "_desiredTrackDeg"]:
            self.assertNotIn(forbidden, yaw, forbidden)

    def test_the_coordination_can_be_switched_off(self):
        """Zero leaves the rudder answering sideslip only -- the pre-v0.16.10 behaviour, in
        case the feedforward is wrong on some airframe."""
        src = read(POSTINIT)
        self.assertIn('["USAFDC_setting_apYawCoordination", "SLIDER"', src)
        self.assertIn("[0, 150, 40, 0], 0] call CBA_fnc_addSetting;", src)


class TuningIsReachableTests(unittest.TestCase):
    def test_every_new_term_is_a_setting(self):
        """These are flying judgements on an airframe nobody has flown this on yet. A
        rebuild per guess is not a tuning loop."""
        src = read(POSTINIT)
        # All client scope: they change how the aircraft flies, and the AP runs only on
        # the machine flying it.
        for name, default in [("apTurnLeadS", "[0, 10, 4, 1], 0]"),
                              ("apRollDamping", "[0, 600, 150, 0], 0]"),
                              ("apYawCoordination", "[0, 150, 40, 0], 0]")]:
            self.assertIn(f'["USAFDC_setting_{name}", "SLIDER"', src, name)
            self.assertIn(default, src, name)

    def test_the_ap_defaults_match_the_settings(self):
        b = force_branch()
        self.assertIn('getVariable ["USAFDC_setting_apTurnLeadS", 4]', b)
        self.assertIn('getVariable ["USAFDC_setting_apRollDamping", 150]', b)
        self.assertIn('getVariable ["USAFDC_setting_apYawCoordination", 40]', b)

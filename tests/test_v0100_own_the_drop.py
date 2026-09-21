"""v0.10.0 -- CARP releases its own cargo, and the smoke is a choice.

WHAT CHANGED AND WHY IT IS RISKIER THAN IT LOOKS

Through v0.9.1 a USAF airframe carrying USAF-loaded cargo was handed straight back to
USAF_CARGO_fnc_canDrop. That was deliberate: releaseDelayS = 0.5607 s is not physics, it
is the measured script latency of THAT path, and there was no reason to put a
flown-validated number at risk. The price was a hard dependency -- without the USAF mod
loaded the aircraft CARP was built for could not drop at all, and every behaviour a pilot
saw on a drop belonged to somebody else's code.

Flipping the default means CARP's sequence must now be timing-faithful, not merely
correct. These tests pin the three places where "tidier" would have moved a measured
number:

  THE DOOR WAIT. USAF opens the cargo doors and waits for them in canDrop, BEFORE it
  hands off to dropCargo. Skipping it drops the load through a closed ramp; doing it in
  the wrong place moves it inside or outside the measured latency. It runs on the
  commanding machine, exactly where USAF runs it.

  THE usaf_cargo REMOVAL. USAF clears the array AFTER the detach. CARP cleared it BEFORE
  the attach, which was invisible while USAF's path was the default. fn_sequenceCargo
  paces a stick by waiting for the manifest to shrink -- so clearing it early would fire
  the next release immediately and land a stick measured at 0.588 s apart in one heap.

  THE SEQUENCE FLOOR. That 0.588 s was never enforced, only emergent, and it emerged from
  USAF's ordering. It does not emerge for an ACE or vehicle-in-vehicle load, whose source
  gives up its claim before the load has left. The sequencer now honours the same number
  the solver spaces the release points by.

THE SMOKE

USAF dispatches its smoke loop with `spawn BIS_fnc_MP` and no target, so it runs on every
machine and each one calls createVehicle -- which is global-effect. A four-player server
stacks four shells per load. CARP creates one, on the machine that owns the cargo.

v0.10.1 moved the switch from an Addon Option to a button in the CARP panel and made it
crew intent, because whether a load is marked is a per-drop call and Addon Options are not
reachable in flight. The flag is then PASSED to the release rather than read at the far
end -- fn_releaseCargo runs where the CARGO is local, which on a dedicated server is a
machine that has never had the panel open. That is the same trap guided cargo fell into
with CBA settings in v0.8.0.
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


SELECT = "addon/functions/cargo/fn_releaseSelected.sqf"
RELEASE = "addon/functions/cargo/fn_releaseCargo.sqf"
SEQUENCE = "addon/functions/auto/fn_sequenceCargo.sqf"
# v0.12.0 moved the canopy and everything after it into fn_canopyWatch, so the
# altitude test could leave the script scheduler.
WATCH = "addon/functions/cargo/fn_canopyWatch.sqf"
POSTINIT = "addon/functions/fn_postInit.sqf"
ENHANCE = "addon/functions/ui/fn_ensurePanelEnhancements.sqf"
MODEL = "addon/functions/generated/fn_getModel.sqf"


class DefaultPathTests(unittest.TestCase):
    def test_carp_releases_unless_the_mission_asks_for_usaf(self):
        """The predicate is now positive: take USAF's path only when told to."""
        src = code(SELECT)
        self.assertIn('(missionNamespace getVariable ["USAFDC_setting_useUsafRelease", false])', src)
        self.assertNotIn("!(missionNamespace getVariable [\"USAFDC_setting_useUsafRelease\"", src)

    def test_the_usaf_fallback_still_exists_because_it_is_the_calibration_reference(self):
        """Deleting it would leave no way to measure whether the two paths differ."""
        src = code(SELECT)
        self.assertIn("USAF_CARGO_fnc_canDrop", src)
        self.assertIn("_usafAboard select ((count _usafAboard) - 1)", src)

    def test_the_setting_defaults_off_and_is_server_forced(self):
        """Scope 1. A per-client setting would let two crew disagree about which release
        sequence their shared aircraft uses."""
        lines = [
            ln for ln in read(POSTINIT).splitlines()
            if "USAFDC_setting_useUsafRelease" in ln and "addSetting" in ln
        ]
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].rstrip().endswith("false, 1] call CBA_fnc_addSetting;"), lines[0])


class DoorSequenceTests(unittest.TestCase):
    def test_carps_path_opens_the_cargo_doors(self):
        """Without this the load drops through a closed ramp -- the most visible thing
        USAF's canDrop did that CARP's path never reproduced."""
        src = code(SELECT)
        self.assertIn("USAF_Cargo_Doors", src)
        self.assertIn("_carrier animate [_x, 1]", src)

    def test_the_wait_is_usafs_predicate_poll_included(self):
        """It passes on the first check when the ramp is already open, which on a drop
        run it is -- so reproducing it costs one poll and keeps the two paths
        comparable. A different predicate would move releaseDelayS."""
        src = code(SELECT)
        self.assertIn(
            "waitUntil {sleep 0.01; ({(_carrier animationPhase _x) isEqualTo 1} count _doors) > 0}",
            src,
        )

    def test_the_doors_run_on_the_commanding_machine_the_release_one_hop_away(self):
        """USAF's own split. animate is global-effect so the doors open for everyone;
        the release must reach the machine where the cargo is local."""
        src = code(SELECT)
        doors = src.index("_carrier animate [_x, 1]")
        hop = src.index('remoteExec ["USAFDC_fnc_releaseCargo"')
        self.assertLess(doors, hop, "the doors must be open before the load is dispatched")
        self.assertIn('remoteExec ["USAFDC_fnc_releaseCargo", _cargo]', src)

    def test_usafs_busy_flag_is_set_around_the_door_wait(self):
        """usaf_cargo_loading is what USAF's own load actions read. Leaving it alone
        would let a loadmaster start a load while the ramp is cycling for a drop."""
        src = code(SELECT)
        self.assertIn('_carrier setVariable ["usaf_cargo_loading", true, true]', src)
        self.assertIn('_carrier setVariable ["usaf_cargo_loading", false, true]', src)


class ReleaseOrderingTests(unittest.TestCase):
    def test_usaf_cargo_is_cleared_after_the_detach_not_before_the_attach(self):
        """fn_sequenceCargo paces a stick by the manifest shrinking. Clearing the array
        before the load has left fires the next release immediately."""
        src = code(RELEASE)
        clear = src.index('_carrier setVariable ["usaf_cargo", _list - [_cargo], true]')
        detach = src.index("_cargo setVelocity (velocity _carrier);")
        self.assertLess(detach, clear, "the array must not shrink until the load is away")

    def test_the_timed_sequence_is_unchanged(self):
        """attach, sleep 0.5, detach, inherit velocity -- the constants releaseDelayS was
        fitted against."""
        src = code(RELEASE)
        self.assertIn("_cargo attachTo [_carrier, [_offset # 0, _offset # 1, _offset # 2]];", src)
        attach = src.index("_cargo attachTo [_carrier, [_offset # 0")
        tail = src[attach:attach + 200]
        self.assertIn("sleep 0.5;", tail)
        self.assertIn("detach _cargo;", tail)
        self.assertIn("_cargo setVelocity (velocity _carrier);", tail)

    def test_usafs_own_bookkeeping_on_the_load_is_released(self):
        """USAF's fn_dropCargo clears the GetOut handler and the carrier back-pointer
        last. A load that kept them would still be claiming an aircraft it has left."""
        src = code(RELEASE)
        self.assertIn('_cargo removeEventHandler ["GetOut", _getOutId]', src)
        self.assertIn('_cargo setVariable ["carrier", nil, false]', src)

    def test_the_release_is_still_refused_where_the_cargo_is_not_local(self):
        """detach, setVelocity and attachTo are local-effect. Nothing about owning the
        drop changes that."""
        self.assertIn("if !(local _cargo) exitWith", code(RELEASE))


class SequenceIntervalTests(unittest.TestCase):
    def test_the_sequencer_honours_the_measured_interval(self):
        """The solver spaces a stick's release points by multiCargo.sequenceIntervalS.
        Until now nothing made the releases themselves honour it."""
        src = code(SEQUENCE)
        self.assertIn('_multi getOrDefault ["sequenceIntervalS", 0.588]', src)
        self.assertIn("_notBefore = _simStart + _intervalS", src)

    def test_the_manifest_is_still_the_primary_clock(self):
        """The floor is a floor, not a replacement. A load that takes longer than the
        interval to leave must still be waited for."""
        src = code(SEQUENCE)
        self.assertIn("((_after < _before) && {time >= _notBefore}) || {time > _deadline}", src)

    def test_the_deadline_still_breaks_a_stuck_stick(self):
        self.assertIn("_deadline = time + 3", code(SEQUENCE))

    def test_the_floor_matches_the_number_the_solver_uses(self):
        """One measured value, two consumers. If they drift apart the solver spaces the
        release points for an interval the sequencer does not fly."""
        self.assertIn('["sequenceIntervalS", 0.588]', read(MODEL))
        self.assertIn(
            '_multiCargo getOrDefault ["sequenceIntervalS", 0.53]',
            code("addon/functions/guidance/fn_buildWorldSolution.sqf"),
        )


class SmokeTests(unittest.TestCase):
    """v0.10.1 moved this from an Addon Option to a button in the CARP panel. Whether a
    load is marked is a call the crew makes per drop -- a covert insert and a resupply
    onto a held DZ want opposite answers in the same mission -- and Addon Options are
    not reachable in flight."""

    def test_smoke_is_created_once_not_once_per_machine(self):
        """createVehicle is global-effect. USAF's `spawn BIS_fnc_MP` with no target runs
        the loop everywhere, so a full server stacks a shell per player."""
        src = code(WATCH)
        self.assertIn("createVehicle [_at # 0, _at # 1, 0.2]", src)
        self.assertNotIn("BIS_fnc_MP", src)

    def test_the_flag_is_an_argument_not_state_read_at_the_far_end(self):
        """THE WHOLE POINT. fn_releaseCargo runs where the CARGO is local, which on a
        dedicated server is the server -- a machine that has never had the panel open.
        Reading USAFDC_state_smokeEnabled there gets its power-on default, not the
        crew's choice. Same mistake guided cargo made with CBA settings in v0.8.0."""
        src = code(RELEASE)
        self.assertIn('params ["_carrier", "_cargo", ["_source", ""], ["_smoke", true]]', src)
        # Carried one hop further in v0.12.0: the release hands it to fn_canopyWatch,
        # which is where the shell is actually lit. Neither end may look it up.
        self.assertIn("[_cargo, _carrier, _smoke] call USAFDC_fnc_canopyWatch;", src)
        watch = code(WATCH)
        self.assertIn("if (_smoke) then {", watch)
        for src_text in (src, watch):
            self.assertNotIn("USAFDC_state_smokeEnabled", src_text)
            self.assertNotIn("USAFDC_setting_dropSmoke", src_text)

    def test_the_commanding_machine_reads_it_and_sends_it(self):
        src = code(SELECT)
        self.assertIn('missionNamespace getVariable ["USAFDC_state_smokeEnabled", true]', src)
        self.assertIn(
            '[_carrier, _cargo, _source, _smoke] remoteExec ["USAFDC_fnc_releaseCargo", _cargo]',
            src,
        )

    def test_the_addon_option_is_gone(self):
        """Replaced, not duplicated. Two controls for one behaviour is how a pilot ends
        up unable to explain why the smoke did not match the button."""
        self.assertNotIn("USAFDC_setting_dropSmoke", read(POSTINIT))

    def test_the_button_is_declared_in_the_config(self):
        """WAS: created at runtime, because config.bin could not be regenerated.

        v0.15.0 moved the panel into addon/config.cpp, generated from a layout
        spec by tools/gen_dialog.py. What this used to assert about runtime ctrlCreate is
        now a config declaration, which is the better contract: the generator refuses to
        write if any two control rectangles overlap -- the check v0.11.0 did not have when
        it put four controls on top of the CARGO row and shipped it."""
        cfg = read("addon/config.cpp")
        self.assertIn("idc=9331;", cfg)
        self.assertIn("USAFDC_state_smokeEnabled", cfg)

    def test_toggling_publishes_to_the_other_seat(self):
        """fn_refreshPanel is what publishes crew intent, and it publishes BEFORE it
        paints. Setting the state without going through it would leave the co-pilot on the
        old answer -- as true of a config action as of a runtime one."""
        cfg = read("addon/config.cpp")
        block = cfg[cfg.index("idc=9331;"):]
        # NOT the first "};" -- a colour array ends "1};".
        block = block[:block.index(chr(10) + chr(9) + chr(9) + "};")]
        self.assertIn("USAFDC_state_smokeEnabled=!", block)
        self.assertIn("USAFDC_fnc_refreshPanel", block)

    def test_the_label_follows_the_state(self):
        src = code("addon/functions/ui/fn_updatePanelTelemetry.sqf")
        self.assertIn('[9331, "SMOKE", "USAFDC_state_smokeEnabled", true]', src)
        self.assertIn('ctrlSetText format ["%1: %2", _label,', src)

    def test_it_is_crew_intent_and_the_payload_length_moved_with_it(self):
        """A field added to the snapshot that fn_syncApply does not expect is refused
        wholesale, so both ends must move together."""
        self.assertIn('USAFDC_state_smokeEnabled', code("addon/functions/sync/fn_syncSnapshot.sqf"))
        apply_src = code("addon/functions/sync/fn_syncApply.sqf")
        self.assertIn("(count _payload) isEqualTo 18", apply_src)
        self.assertIn('"_wantGuidance", "_wantAuto", "_smokeEnabled"', apply_src)
        self.assertIn("USAFDC_state_smokeEnabled = _smokeEnabled;", apply_src)

    def test_the_payload_length_matches_the_snapshot(self):
        """The one way these two drift apart is somebody adding a field to one of them,
        and fn_syncApply then refuses every record the crew publishes."""
        snap = code("addon/functions/sync/fn_syncSnapshot.sqf")
        body = snap[snap.index("[", snap.index("*/") if "*/" in snap else 0):]
        depth, fields = 0, 1
        for ch in body:
            if ch in "[(":
                depth += 1
            elif ch in "])":
                depth -= 1
                if depth == 0:
                    break
            elif ch == "," and depth == 1:
                fields += 1
        self.assertEqual(fields, 18, "snapshot field count must match fn_syncApply's 18")

    def test_the_colour_follows_the_side_as_usaf_does(self):
        src = code(WATCH)
        for cls in ["SmokeShellRed", "SmokeShellBlue", "SmokeShellGreen", "SmokeShell"]:
            self.assertIn(cls, src)

    def test_the_loop_relights_the_shell_and_stops_at_the_ground(self):
        """USAF's predicate: between the canopy trigger and the ground, and nobody has
        climbed into the load."""
        src = code(WATCH)
        self.assertIn("waitUntil {sleep 0.5; isNull _shell || {isNull _cargo}}", src)
        # v0.16.4: read through getPosASL. getPos on an ATTACHED object returns its offset
        # from the parent, which opened a canopy at the ramp and destroyed an aircraft.
        # See tests/test_v0164_canopy_altitude.py. The contract here is unchanged.
        self.assertIn("{((ASLToAGL (getPosASL _cargo)) # 2) > 1}", src)
        self.assertIn("{(count (crew _cargo)) isEqualTo 0}", src)

    def test_the_smoke_never_blocks_the_canopy(self):
        """It is spawned, and it now runs AFTER the canopy is attached rather than
        before it. v0.12.0 creates the chute inline on the frame the load crosses the
        trigger, so nothing may sit between the crossing and the chute -- a relight loop
        there would cost the exact frames the whole change was made to recover."""
        src = code(WATCH)
        cross = src.index('_cargo setVariable ["USAFDC_canopyPending", false, false]')
        chute = src.index("private _chute = _chuteClass createVehicle")
        gate = src.index("if (_smoke) then {")
        self.assertNotIn("_smoke", src[cross:chute])
        self.assertGreater(gate, chute, "smoke must not delay the canopy")
        self.assertIn("spawn {", src[gate:])


class CalibrationUntouchedTests(unittest.TestCase):
    def test_release_delay_is_unchanged(self):
        """Reproducing a sequence is not measuring it. The number stays until a flown
        drop says otherwise, and any difference gets its own field."""
        self.assertIn('["releaseDelayS", 0.5607]', read(MODEL))

    def test_the_release_is_still_stamped_in_mission_time(self):
        """The one instrument that can settle whether the two paths differ. Mission time
        is synchronised; diag_tickTime is a machine's uptime and cannot be subtracted
        across a dedicated server."""
        self.assertIn('_cargo setVariable ["USAFDC_releaseSimTime", time, true]', code(RELEASE))
        self.assertIn('_cargo setVariable ["USAFDC_releasePath", "carp", true]', code(RELEASE))


if __name__ == "__main__":
    unittest.main(verbosity=2)

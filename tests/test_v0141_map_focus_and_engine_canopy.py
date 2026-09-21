"""v0.14.1 -- the map is a mouse owner, and the engine brings its own parachute.

TWO FLOWN REPORTS, BOTH FROM v0.14.0.

THE MAP. Arm the autopilot, open the map, move the mouse, and the AP disconnects with
PILOT OVERRIDE.

The obvious fix -- "read only the keys the pilot actually bound" -- does not work, and it
is worth writing down why, because it will be suggested again. `inputAction` ALREADY
reports bound keys; that is what the command is for. The input here is not a key at all.
Aircraft pitch and roll live on the MOUSE AXES, and Arma keeps feeding mouse motion to
those channels while the map is up. There is no binding to exclude, because the thing
generating the input is the mouse the pilot is panning with.

So the map joins the four cases already in fn_inputFocusActive, which are all the same
shape: something else owns the mouse right now.

THE PARACHUTE. A CARP-loaded vehicle dropped from a Blackfish appeared to open a canopy at
the ramp, have it cut, fall ballistic, then open a second one.

Only the second was ours. Unloading vehicle-in-vehicle cargo in flight is a vanilla
behaviour that gives the load ITS OWN parachute -- and the moment fn_releaseCargo attaches
the load to the release offset, that parachute is orphaned and left hanging.

Accuracy was never touched: every load of a four-vehicle stick landed on target. It just
looked broken, which for a build going to the Workshop is enough.

WHY THE SWEEP IS NARROW

Deleting parachutes near a falling load by proximity alone would take the canopy off a load
dropped seconds earlier. So the chutes present BEFORE the unload are recorded, and only
something new can be removed.

It is bounded twice more. After the attach, never before -- deleting a parachute out from
under an object still hanging from it leaves a state nothing downstream can reason about.
And it stops as soon as canopyWatch reports the canopy no longer pending, which is what
protects the case that would otherwise break: a drop from low enough that OUR canopy opens
inside the sweep window.
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


FOCUS = "addon/functions/autopilot/fn_inputFocusActive.sqf"
RELEASE = "addon/functions/cargo/fn_releaseCargo.sqf"
WATCH = "addon/functions/cargo/fn_canopyWatch.sqf"


class MapFocusTests(unittest.TestCase):
    def test_the_map_suppresses_override_detection(self):
        """THE DEFECT. Aircraft pitch and roll are on the mouse axes, and Arma keeps
        feeding them while the map is up."""
        src = code(FOCUS)
        self.assertIn("private _mapOpen = visibleMap;", src)

    def test_the_map_is_part_of_the_returned_predicate(self):
        """Computing it and not returning it is the way this fix fails silently."""
        src = code(FOCUS)
        tail = src[src.rindex("_mapOpen"):]
        self.assertIn("|| {_carpOpen}", tail)
        self.assertIn("|| {_zeusOpen}", tail)

    def test_the_other_four_owners_are_untouched(self):
        """Each cost a flown session to find. The map is a fifth case, not a replacement."""
        src = code(FOCUS)
        for owner in ["findDisplay 9300", "findDisplay 312",
                      "USAFDC_state_apAceInteractOpen", 'inputAction "lookAround"']:
            self.assertIn(owner, src)

    def test_the_grace_period_still_exists(self):
        """Focus ending and the mouse settling are not the same instant."""
        self.assertIn("USAFDC_state_apOverrideInhibitUntil", read("addon/functions/fn_postInit.sqf"))


class EngineCanopyTests(unittest.TestCase):
    def test_only_a_parachute_the_engine_just_made_can_be_deleted(self):
        """Proximity alone would take the canopy off a load dropped seconds earlier."""
        src = code(RELEASE)
        self.assertIn('_chutesBefore = nearestObjects [_cargo, ["ParachuteBase"], 40];', src)
        self.assertIn("if !(_x in _before) then {deleteVehicle _x};", src)

    def test_the_before_list_is_taken_before_the_unload(self):
        src = code(RELEASE)
        before = src.index("_chutesBefore = nearestObjects")
        unload = src.index("objNull setVehicleCargo _cargo")
        self.assertLess(before, unload)

    def test_the_sweep_is_armed_before_the_timed_sequence(self):
        """v0.16.10 MOVED IT, AND THE OLD PLACEMENT WAS THE BUG.

        It used to be spawned AFTER the whole attach / sleep 0.5 / detach sequence, on the
        reasoning that nothing belongs inside the sequence releaseDelayS was fitted
        against. That reasoning is right and is preserved -- but the consequence was the
        engine's canopy being visible for at least half a second, which the crew reported
        as a canopy opening at the ramp, getting cut, and a second opening at 300 m.

        Registering the handler in the viv branch puts it BEFORE the sequence rather than
        after, so the sequence is byte-identical and the sweep is live from the first frame
        the engine's canopy can exist."""
        src = code(RELEASE)
        arm = src.index("CBA_fnc_addPerFrameHandler")
        self.assertLess(arm, src.index("_cargo attachTo [_carrier, [_offset # 0"),
                        "arming must not sit inside the timed sequence")
        self.assertLess(src.index("objNull setVehicleCargo _cargo"), arm)

    def test_it_waits_until_deleting_is_safe(self):
        """The old placement bought safety with lateness. The handler now buys it with a
        test: while the load still hangs from the engine's canopy, deleting that canopy
        leaves a state nothing downstream can reason about, so it does not."""
        src = code(RELEASE)
        self.assertIn("private _parent = attachedTo _cargo;", src)
        self.assertIn('if (!isNull _parent && {_parent isKindOf "ParachuteBase"}) exitWith {};', src)

    def test_it_runs_per_frame_not_on_a_scheduled_poll(self):
        """Same lesson as canopyWatch: a spawned `sleep 0.1` loop shares three milliseconds
        of frame time with every other script, so it checks whenever the scheduler reaches
        it. That is the difference between a canopy nobody sees and one everybody does."""
        src = code(RELEASE)
        self.assertIn("}, 0, [_cargo, _chutesBefore, time + 6]] call CBA_fnc_addPerFrameHandler;", src)
        # Scoped to the sweep: the ACE branch has its own legitimate `sleep 0.1` after
        # handing the unload to ACE's server event, and that one is not this.
        sweep = src[src.index('case "viv":'):src.index("CBA_fnc_addPerFrameHandler")]
        self.assertNotIn("sleep", sweep)

    def test_it_removes_its_own_handler(self):
        """A per-frame handler that never stops is a permanent per-frame nearestObjects
        call for the rest of the mission."""
        self.assertIn("[_pfh] call CBA_fnc_removePerFrameHandler;", code(RELEASE))

    def test_it_only_runs_for_vehicle_in_vehicle_loads(self):
        """No other source hands the engine a reason to make a parachute. Armed inside the
        viv branch of the source switch, so it cannot fire for anything else."""
        src = code(RELEASE)
        viv = src.index('case "viv":')
        arm = src.index("CBA_fnc_addPerFrameHandler")
        self.assertLess(viv, arm)
        self.assertLess(arm, src.index('default {'))

    def test_the_sweep_is_bounded_by_time(self):
        """The engine does not always have it made on the frame the unload returns. Six
        seconds rather than three, because it is now cheap: a per-frame handler that exits
        the moment our own canopy opens costs nothing to leave armed a little longer."""
        self.assertIn("time + 6]", code(RELEASE))

    def test_the_sweep_stops_before_it_could_eat_our_own_canopy(self):
        """THE CASE THAT WOULD OTHERWISE BREAK. A drop from low enough that canopyWatch
        opens ours inside the window."""
        src = code(RELEASE)
        self.assertIn('{!(_cargo getVariable ["USAFDC_canopyPending", true])}', src)
        # The flag the guard reads is the one canopyWatch actually clears.
        self.assertIn('_cargo setVariable ["USAFDC_canopyPending", false, false]', code(WATCH))

    def test_the_default_keeps_the_sweep_alive_before_registration(self):
        """canopyWatch registers half a second into the release, so before that the guard
        reads its default -- which has to be true or the sweep never starts."""
        self.assertIn('getVariable ["USAFDC_canopyPending", true]', code(RELEASE))

    def test_the_timed_release_sequence_is_still_untouched(self):
        """attach, sleep 0.5, detach, inherit velocity -- unchanged by the move. Nothing was
        inserted between the attach and the sleep, which is what would have moved
        releaseDelayS."""
        src = code(RELEASE)
        self.assertIn("_cargo setVelocity (velocity _carrier);", src)
        self.assertEqual(src.count("sleep 0.5;"), 2)
        attach = src.index("_cargo attachTo [_carrier, [_offset # 0")
        window = src[attach:attach + 200]
        for step in ["sleep 0.5;", "detach _cargo;", "_cargo setVelocity (velocity _carrier);"]:
            self.assertIn(step, window, step)
if __name__ == "__main__":
    unittest.main(verbosity=2)

"""v0.16.4 -- a canopy that opened at the ramp, and a load that rode in sideways.

BOTH FLOWN, ONE SORTIE, AND THE FIRST ONE DESTROYED THE AIRCRAFT.

THE CANOPY

    [TLB CARP][RELEASE] carp path sim=430.061 cargo=rhsusf_mrzr4_d source=attached
    [TLB CARP][CANOPY]  open agl=-1 trigger=300 vz=2 sim=430.622
    [TLB CARP][CAL]     chute attachSim=1.15198 cargoPos=[20804.4,16670.1,2841.17]

The load was at 2841 m. The altitude test read about zero, crossed a 300 m trigger 0.56 s
after release, and inflated a canopy a few metres behind the aircraft that had just dropped
it. Expected time to canopy is 23.5 s. The aircraft flew into the load and was destroyed.

`getPos` on an object that is `attachedTo` something returns its offset FROM THAT PARENT,
not its height above the ground. The release sequence attaches the load to the carrier for
half a second, and every consumer in fn_canopyWatch asked `getPos`.

TWO GUARDS, BECAUSE EITHER ALONE LEAVES A HOLE

A load being carried is not falling and cannot need a chute -- so an attached load is never
eligible, whatever any altitude says. That is the meaning, and it also covers the case where
our own canopy is already on. The altitude is then read through getPosASL, which is a real
world position regardless of what the object is attached to.

The same substitution is applied to the four other altitude reads in that function. Three of
them run while the load is riding its own canopy, where getPos returns zero for the entire
descent -- so the smoke relight loop could never start and the touchdown wait would finish
on its first evaluation. Whether those were firing is not established from the log, and the
change cannot regress either way: getPosASL is the true altitude under both readings. The
open line now logs BOTH so the next RPT settles it rather than leaving it to argument.

THE ROTATION

Orientation commands on an ATTACHED object are expressed in the parent's frame.
fn_loadAttach handed setVectorDirAndUp the carrier's WORLD vectors, applying the aircraft's
heading a second time on top of the one the load already had. It rode in square to the
compass and sideways in the hold.
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


WATCH = "addon/functions/cargo/fn_canopyWatch.sqf"
ATTACH = "addon/functions/cargo/fn_loadAttach.sqf"
RELEASE = "addon/functions/cargo/fn_releaseCargo.sqf"


class CanopyGateTests(unittest.TestCase):
    def test_an_attached_load_is_never_eligible(self):
        """THE DEFECT. A load in the release sequence's attachTo is 3000 m up and tests as
        one metre. This guard does not depend on getting the altitude right at all."""
        src = code(WATCH)
        self.assertIn("if !(isNull (attachedTo _cargo)) then {", src)
        gate = src[src.index("if !(isNull (attachedTo _cargo)) then {"):]
        gate = gate[:gate.index("};") + 2]
        self.assertIn("_survivors pushBack _x", gate,
                      "an attached load must stay pending, not be dropped from the list")

    def test_the_guard_precedes_the_altitude_test(self):
        """Order matters: the altitude read is only meaningful once the load is free."""
        src = code(WATCH)
        self.assertLess(src.index("isNull (attachedTo _cargo)"),
                        src.index(">= _triggerAglM"))

    def test_the_trigger_reads_a_real_world_altitude(self):
        src = code(WATCH)
        self.assertIn("if (((ASLToAGL (getPosASL _cargo)) # 2) >= _triggerAglM) then {", src)

    def test_no_altitude_anywhere_is_read_the_ambiguous_way(self):
        """Four more reads ran while the load rides its own canopy, where getPos is its
        offset from the chute -- zero for the whole descent. getPosASL is the true altitude
        under either reading, so this cannot regress."""
        src = code(WATCH)
        self.assertNotIn("(getPos _cargo) # 2) > 1", src)
        self.assertNotIn("(getPos _cargo) # 2) < 1", src)
        self.assertIn("((ASLToAGL (getPosASL _cargo)) # 2) > 1", src)
        self.assertIn("((ASLToAGL (getPosASL _cargo)) # 2) < 1", src)

    def test_the_chute_is_created_where_the_load_actually_is(self):
        """createVehicle at a parent-relative position puts the canopy somewhere the load
        is not."""
        src = code(WATCH)
        self.assertIn("private _openAt = ASLToAGL (getPosASL _cargo);", src)
        self.assertIn("_chuteClass createVehicle _openAt", src)
        self.assertIn("_strobeClass createVehicle _openAt", src)

    def test_the_open_line_logs_both_readings(self):
        """The instrument, so the next RPT establishes what getPos returned here rather
        than leaving it to be argued from memory. This project has twice mistaken an
        instrument for physics."""
        src = code(WATCH)
        self.assertIn("rawGetPosZ=", src)
        self.assertIn("attachedTo=", src)
        line = src[src.index("[TLB CARP][CANOPY] open"):]
        line = line[:line.index("];")]
        self.assertIn("ASLToAGL (getPosASL _cargo)", line)
        self.assertIn("getPos _cargo", line)


class ReleaseSequenceTests(unittest.TestCase):
    def test_the_release_still_attaches_for_half_a_second(self):
        """UNCHANGED ON PURPOSE. That attach / sleep 0.5 / detach is what releaseDelayS was
        measured against. The canopy gate was fixed to tolerate it, not the other way
        round -- moving the sequence would move calibrated release timing."""
        src = code(RELEASE)
        self.assertIn("_cargo attachTo [_carrier, [_offset # 0, _offset # 1, _offset # 2]];", src)
        self.assertIn("sleep 0.5;", src)
        self.assertIn("detach _cargo;", src)

    def test_the_watch_is_armed_after_the_sequence(self):
        src = code(RELEASE)
        self.assertLess(src.index("_cargo setVelocity (velocity _carrier)"),
                        src.index("TLB_CARP_fnc_canopyWatch"))


class RotationTests(unittest.TestCase):
    def test_the_load_is_squared_in_the_carriers_frame(self):
        """Orientation on an ATTACHED object is parent-relative. Passing the carrier's
        world vectors applied its heading twice."""
        src = code(ATTACH)
        self.assertIn("_cargo setVectorDirAndUp [[0, -1, 0], [0, 0, 1]];", src)
        self.assertNotIn("setVectorDirAndUp [vectorDir _carrier, vectorUp _carrier]", src)

    def test_it_faces_the_same_way_usaf_loads_face(self):
        """USAF ends its own load with `setDir 180`. The two can be mixed in one hold, and
        a stick where one vehicle faces the other way looks like a bug even when it is
        harmless."""
        self.assertIn("setDir 180", read(ATTACH))


if __name__ == "__main__":
    unittest.main(verbosity=2)

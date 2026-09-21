"""v0.13.1 -- the vehicle-in-vehicle release used a syntax the command does not have.

FLOWN, v0.13.0, first drop of a CARP-loaded vehicle out of a C-17:

    case "viv": { _carrier |#|setVehicleCargo [_cargo, false]; };
    Error setvehiclecargo: Type Array, expected Object
    fn_releaseCargo.sqf, line 124

THREE RELEASES OF DEAD CODE THAT LOOKED CORRECT

That line landed in v0.8.0 with the cargo-source rework and was never once executed.
Nothing arrived as "viv" cargo, because until v0.13.0 gave CARP its own loader every load
came aboard through USAF, ACE or a mission maker's attachTo. The branch existed, read
plausibly, was covered by tests asserting the branch was PRESENT, and was wrong.

The v0.13.0 loader prefers vanilla vehicle-in-vehicle wherever an airframe supports it --
which the C-17 does -- so the first CARP-loaded drop went straight down a path that had
never run.

THE ENGINE HAS NO UNLOAD COMMAND

Searching arma3_x64.exe for the vehicle-cargo command family returns exactly six:
canVehicleCargo, enableVehicleCargo, getVehicleCargo, isVehicleCargo, setVehicleCargo,
vehicleCargoEnabled. There is no unloadVehicleCargo and no two-argument form.

A load is freed by setting its TRANSPORTER to null, which is what ACE's own dragging
module does:

    if (!isNull isVehicleCargo _target && {!(objNull setVehicleCargo _target)}) then {

That is where the locality also flips. Loading names the CARRIER as its left operand, so
fn_loadViv runs on the carrier's machine; unloading names objNull and acts on the CARGO,
so fn_unloadViv runs on the cargo's.

WHAT THIS SAYS ABOUT THE TESTS

Every test that covered this branch asserted it existed. None could assert it worked,
because the suite reads SQF as text and cannot evaluate a command signature. The lesson is
not "write a better string assertion" -- it is that a branch no flight has ever taken is
untested regardless of what the suite says, and the cargo-source matrix (usaf / ace / viv /
attached / carp-loaded) now needs one flown drop per source rather than one in total.
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


RELEASE = "addon/functions/cargo/fn_releaseCargo.sqf"
UNLOADVIV = "addon/functions/cargo/fn_unloadViv.sqf"
LOADVIV = "addon/functions/cargo/fn_loadViv.sqf"
UNLOAD = "addon/functions/cargo/fn_unloadCargo.sqf"

# Every SQF file, because the wrong form is a plausible-looking thing to write again.
ALL_SQF = sorted((ROOT / "addon" / "functions").rglob("*.sqf"))


class VivSyntaxTests(unittest.TestCase):
    def test_no_array_form_survives_anywhere(self):
        """THE DEFECT. setVehicleCargo takes an Object. The array form threw
        "Type Array, expected Object" on the first drop that ever reached it."""
        offenders = []
        for path in ALL_SQF:
            rel = path.relative_to(ROOT).as_posix()
            if "setVehicleCargo [" in code(rel):
                offenders.append(rel)
        self.assertEqual(offenders, [], f"setVehicleCargo called with an array: {offenders}")

    def test_the_release_frees_the_load_by_nulling_its_transporter(self):
        """The engine ships no unload command, so this is the only way."""
        self.assertIn("objNull setVehicleCargo _cargo", code(RELEASE))

    def test_the_release_checks_the_result(self):
        """It returns false when the engine refuses, and a silent false would strand the
        load inside the aircraft while the rest of the sequence ran as if it had left."""
        src = code(RELEASE)
        self.assertIn("if !(objNull setVehicleCargo _cargo) then {", src)
        self.assertIn("viv unload refused", src)

    def test_the_standalone_unload_uses_the_same_idiom(self):
        self.assertIn("objNull setVehicleCargo _cargo", code(UNLOADVIV))

    def test_loading_still_names_the_carrier(self):
        """The two are not symmetric: loading's left operand is the carrier, unloading's
        is objNull. Making them match would break the load."""
        self.assertIn("_carrier setVehicleCargo _cargo", code(LOADVIV))


class VivLocalityTests(unittest.TestCase):
    def test_loading_runs_where_the_carrier_is_local(self):
        self.assertIn("if !(local _carrier) exitWith", code(LOADVIV))

    def test_unloading_runs_where_the_cargo_is_local(self):
        """It flips with the operand. `objNull setVehicleCargo _cargo` acts on the cargo,
        so the cargo's machine is the one that matters."""
        self.assertIn("if !(local _cargo) exitWith", code(UNLOADVIV))
        self.assertNotIn("local _carrier", code(UNLOADVIV))

    def test_the_dispatch_matches_the_operand(self):
        src = code(UNLOAD)
        self.assertIn('remoteExec ["USAFDC_fnc_unloadViv", _cargo]', src)
        self.assertNotIn('remoteExec ["USAFDC_fnc_unloadViv", _carrier]', src)

    def test_the_release_needs_no_dispatch_at_all(self):
        """fn_releaseCargo already runs where the cargo is local, so the viv branch is
        already on the right machine."""
        self.assertIn("if !(local _cargo) exitWith", code(RELEASE))


class VivTimingTests(unittest.TestCase):
    def test_no_sleep_was_added_to_the_viv_branch(self):
        """The ace branch sleeps 0.1 s, which is 14 m of along-track at 140 m/s. Adding
        one here on a hunch would make a vehicle-in-vehicle drop land differently from a
        USAF one for no measured reason. If the engine turns out to need a frame, that is
        a measurement, not a guess."""
        src = code(RELEASE)
        branch = src[src.index('case "viv": {'):]
        branch = branch[:branch.index("default {")]
        self.assertNotIn("sleep", branch)

    def test_the_timed_sequence_is_still_untouched(self):
        """attach, sleep 0.5, detach, inherit velocity -- what releaseDelayS was fitted
        against, and no source branch may move it."""
        src = code(RELEASE)
        self.assertIn("_cargo attachTo [_carrier, [_offset # 0, _offset # 1, _offset # 2]];", src)
        self.assertIn("_cargo setVelocity (velocity _carrier);", src)
        self.assertEqual(src.count("sleep 0.5;"), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)

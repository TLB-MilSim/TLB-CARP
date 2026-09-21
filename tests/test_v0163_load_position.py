"""v0.16.3 -- the load branch that had never once fired, and the cursor that could not see.

FLOWN REPORT: "I loaded 2 vehicles in c130 with load usaf function and tried the last one
with our function -- the last vehicle was outside the tail. But when I loaded all 3 with
ours it worked."

That pair of observations is the whole diagnosis, and neither half is visible without the
other.

THE CAUSAL CHAIN, EACH LINK CHECKED AGAINST THE SHIPPED MODS

1. USAF_CARGO_fnc_loadCargo begins `_carrier enableVehicleCargo false`. Loading two
   vehicles with USAF's own action therefore switched OFF vehicle-in-vehicle on that
   aircraft.
2. So CARP's first branch, `canVehicleCargo`, returned false -- the engine mechanism it
   would normally have used was disabled by USAF, not by us. That is why loading all three
   with CARP worked: nothing ever disabled VIV.
3. It fell through to the second branch, which read USAF_Cargo_LoadPos. THAT PROPERTY DOES
   NOT EXIST. A scan of every PBO in @USAF Mod - Main and @USAF Mod - Utility finds zero
   occurrences of the string. What USAF publishes is USAF_Cargo_InitPos, initOffset,
   midOffset, endOffset and Max{Width,Length,Height,Weight}. So this branch had never
   fired, on any airframe, since v0.13.0 -- including the C-17.
4. It fell through to the bounding-box derivation, whose aft edge sits at 12% of the total
   model length from the rear extent. On a C-130, whose tail cone is long, that is behind
   the ramp aperture. The RPT recorded it plainly: `method=carp (DERIVED HOLD)`.
5. And the derivation's stacking cursor only recognised loads CARP itself had placed, by
   reading a variable nothing else sets. USAF's two were invisible, so the third was put at
   the aft-most slot as though the hold were empty.

WHAT THE STATIC SUITE COULD AND COULD NOT HAVE CAUGHT

tests/test_v0130_own_the_load.py asserted that fn_canLoadCargo contains the literal
"USAF_Cargo_LoadPos", and passed for three releases. The string was there; the property was
not. A test over our own source can check that we wrote what we meant. It cannot check that
what we meant exists. A config key we do not own has to be read out of the mod that defines
it before it is relied on -- which is why the values below are quoted from the decompiled
config rather than from memory.
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


OFFSET = "addon/functions/cargo/fn_loadModelOffset.sqf"
CAN = "addon/functions/cargo/fn_canLoadCargo.sqf"
LOAD = "addon/functions/cargo/fn_loadCargo.sqf"


class DeadBranchTests(unittest.TestCase):
    def test_the_property_that_does_not_exist_is_gone(self):
        for rel in [OFFSET, CAN, LOAD]:
            self.assertNotIn("USAF_Cargo_LoadPos", code(rel), rel)

    def test_the_properties_usaf_actually_publishes_are_read(self):
        """Verified against the decompiled USAF_C130J_Cargo config:
            USAF_Cargo_endOffset[] = {0, 9, 1.25}
            USAF_Cargo_MaxLength   = 12.1
            USAF_Cargo_MaxWidth    = 4.0999999   (inherited)
            USAF_Cargo_MaxHeight   = 4.3000002   (inherited)
            USAF_Cargo_MaxWeight   = 35900       (inherited)
        """
        src = code(OFFSET)
        for prop in ["USAF_Cargo_endOffset", "USAF_Cargo_MaxWidth", "USAF_Cargo_MaxLength",
                     "USAF_Cargo_MaxHeight", "USAF_Cargo_MaxWeight"]:
            self.assertIn(prop, src, prop)

    def test_length_and_weight_are_accumulated_because_usaf_accumulates_them(self):
        """USAF_CARGO_fnc_canLoad sums both over everything already aboard before
        comparing, so MaxLength is the usable HOLD length and MaxWeight the total payload.
        Width and height are per load. Treating MaxLength as a per-load cap would let a
        C-130 accept an unbounded stack."""
        src = code(OFFSET)
        self.assertIn("(_usedLen + _cargoLen) > _maxL", src)
        self.assertIn("(_usedKg + _mass) > _maxKg", src)
        self.assertIn("_cargoWide > _maxW", src)
        self.assertIn("_cargoTall > _maxH", src)

    def test_a_zero_limit_is_not_read_as_a_refusal(self):
        """USAF_C130J's base class carries MaxLength 0.6. Reading a published-but-zero or
        tiny value as authoritative without the `> 0` guard would refuse every vehicle in
        the game on any airframe that left a field at its default."""
        src = code(OFFSET)
        for guard in ["_maxW > 0", "_maxL > 0", "_maxH > 0", "_maxKg > 0"]:
            self.assertIn(guard, src, guard)

    def test_the_branch_is_one_expression_because_exitwith_is_scoped(self):
        """In SQF `exitWith` leaves the nearest enclosing scope, and `if ... then {}` is
        one. An exitWith inside the then-block returns from the BLOCK and execution falls
        through to the derivation below -- which would place the load twice and return the
        second answer. The branch is a single top-level exitWith for that reason."""
        src = code(OFFSET)
        branch = src[src.index('getArray (_cfg >> "USAF_Cargo_endOffset")'):]
        branch = branch[:branch.index("HOLD_AFT") if "HOLD_AFT" in branch else len(branch)]
        self.assertIn("if ((count _endOffset) >= 3) exitWith {", branch)
        # Inside it, the two outcomes are if/else values, never a nested exitWith.
        body = branch[branch.index("if ((count _endOffset) >= 3) exitWith {"):]
        self.assertNotIn("exitWith", body[len("if ((count _endOffset) >= 3) exitWith {"):])


class OneReaderTests(unittest.TestCase):
    def test_can_and_load_ask_the_same_function(self):
        """They used to read the config key separately, which is how "can I load this" and
        "where does it go" come to disagree."""
        self.assertIn("USAFDC_fnc_loadModelOffset", code(CAN))
        self.assertIn("USAFDC_fnc_loadModelOffset", code(LOAD))

    def test_the_mechanism_name_is_the_offsets_own_answer(self):
        """Relabelled, not recomputed -- so the ACE action's reason string cannot claim a
        USAF hold while the loader uses a derived one."""
        src = code(CAN)
        self.assertIn('case "usafConfig": {["usaf", "USAF HOLD"]};', src)
        self.assertIn('case "override":', src)
        self.assertIn('default {["carp", "DERIVED HOLD"]};', src)

    def test_the_engine_mechanism_is_still_tried_first(self):
        src = code(CAN)
        self.assertLess(src.index("canVehicleCargo"), src.index("USAFDC_fnc_loadModelOffset"))


class CursorTests(unittest.TestCase):
    def test_the_cursor_measures_loads_it_did_not_place(self):
        """THE SECOND HALF OF THE FLOWN BUG. It read USAFDC_loadSlotY, which only this file
        ever sets, so a hold filled by USAF, ACE or a mission maker looked empty."""
        src = code(OFFSET)
        self.assertIn("_carrier worldToModel (getPosWorld _x)", src)

    def test_an_ace_hidden_load_does_not_occupy_the_hold(self):
        """ACE parks its loaded objects about 100 m below the carrier. Counting one as
        present would push every subsequent load forward out of the aircraft -- the same
        failure in the opposite direction."""
        src = code(OFFSET)
        self.assertIn("_inside", src)
        self.assertIn('(abs (_m # 2)) <= (((_cMax # 2) - (_cMin # 2)) + 5)', src)

    def test_both_sources_record_a_slot_so_they_can_be_mixed(self):
        """A hold can hold one of each. Whichever branch places a load, the next one has to
        be able to see it."""
        src = code(OFFSET)
        self.assertEqual(src.count('_cargo setVariable ["USAFDC_loadSlotY"'), 2)

    def test_the_load_is_lifted_onto_the_floor_not_sunk_through_it(self):
        """Both branches subtract the load's own bbMin.z, because a model's origin is not
        its lowest point. USAF's own z arithmetic is not copied -- it mixes an ATL height
        into a world-to-model conversion and does not mean what it looks like."""
        src = code(OFFSET)
        self.assertIn("(_endOffset # 2) - (_gMin # 2)", src)
        self.assertIn("_floorZ - (_gMin # 2)", src)


class DerivationTests(unittest.TestCase):
    """Only reached by airframes that publish no hold at all, now that the USAF branch
    works. Still worth getting right: it is the answer for every non-USAF cargo aircraft."""

    def test_the_floor_scales_with_the_airframe(self):
        """bbMin.z is the bottom of the LANDING GEAR. A flat 0.2 m above it put the load on
        the ground the wheels stand on -- 1.10 m below the C-130J's cargo deck and 1.90 m
        below the C-17's. The two measured floors agree to 0.008 as a fraction of model
        height, which is the only reason this is a fraction."""
        src = code(OFFSET)
        self.assertIn("#define FLOOR_FRACTION 0.115", src)
        self.assertIn("(((_cMax # 2) - (_cMin # 2)) * FLOOR_FRACTION)", src)
        self.assertNotIn("(_cMin # 2) + 0.2;", src)

    def test_the_hold_is_narrower_than_either_airframe_measured(self):
        """CONSERVATIVE, NOT BEST FIT, and deliberately so: this branch only runs where
        nothing can check the answer. Measured aft limits were 0.3993 (C-130J) and 0.3079
        (C-17); fore limits 0.8046 and 0.7059. Taking the tighter end of each refuses loads
        that would have fitted, which is this file's stated trade. A load too far forward is
        still inside the fuselage; too far aft it is hanging in the air."""
        src = code(OFFSET)
        self.assertIn("#define HOLD_AFT 0.40", src)
        self.assertIn("#define HOLD_FORE 0.70", src)

    def test_the_old_aft_limit_is_gone(self):
        """0.12 put the aft limit 8.3 m behind the C-130J's real floor and 10.4 m behind the
        C-17's -- past the tip of an open ramp. That is the flown symptom."""
        self.assertNotIn("#define HOLD_AFT 0.12", code(OFFSET))


class UnchangedTests(unittest.TestCase):
    def test_the_mission_override_still_wins(self):
        self.assertIn('_carrier getVariable ["USAFDC_loadPos", []]', code(OFFSET))

    def test_the_release_offset_is_not_touched_by_any_of_this(self):
        """CLAUDE.md: a derived LOAD position is acceptable because nothing ballistic
        depends on it; a derived RELEASE point would not be. This change stays entirely on
        the load side -- fn_releaseModelOffset is what the solver is calibrated against."""
        self.assertNotIn("USAFDC_fnc_releaseModelOffset", code(OFFSET))
        self.assertNotIn("USAF_Cargo_DropPos", code(OFFSET))


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Dynamic cargo-count selector.

The panel's cargo combo was hardcoded to ALL / 1 / 2. That is wrong in both
directions: it offered "2" with a single vehicle aboard, and gave no way to release
3 or more from a full bay. It must be built from the live usaf_cargo count when the
panel opens.

The combo's onLBSelChanged handler is compiled into the pre-binarized config.bin:
    TLB_CARP_state_cargoCount = parseNumber ((_this#0) lbData (_this#1))
so lbData must stay a numeric string. That handler cannot be changed, which is why
these tests pin the data format rather than the display text.
"""
from pathlib import Path
import unittest

from tests.test_sqf_structure import strip_comments_and_strings

ROOT = Path(__file__).resolve().parents[1]
SRC = "addon/functions/ui/fn_refreshPanel.sqf"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def code(rel: str) -> str:
    return strip_comments_and_strings(read(rel))


class DynamicCargoCountTests(unittest.TestCase):
    def setUp(self):
        self.src = read(SRC)
        self.code = code(SRC)

    def test_count_is_read_from_the_live_cargo_manifest(self):
        """v0.8.0 moved this off usaf_cargo.

        The selector built its list from USAF's array alone, so a bay holding an ACE
        load, a vehicle-in-vehicle load or a mission maker's attachTo showed NO CARGO
        and offered nothing to select. The manifest counts every carriage source, and
        returns exactly usaf_cargo when that is all there is.
        """
        self.assertIn("count ([_cargoVehicle] call TLB_CARP_fnc_getLoadedCargo)", self.src)
        self.assertNotIn('getVariable ["usaf_cargo"', self.src)
        self.assertIn("objectParent player", self.src)

    def test_no_hardcoded_two_entry_list_remains(self):
        self.assertNotIn('[["ALL", -1], ["1", 1], ["2", 2]]', self.src)

    def test_entries_span_one_to_the_available_count(self):
        self.assertIn('for "_n" from 1 to _availableCargo do', self.src)

    def test_all_entry_carries_minus_one_and_shows_the_count(self):
        """-1 is the sentinel fn_triggerAutoDrop and fn_buildWorldSolution both read
        as "every load aboard"."""
        self.assertIn('_cargoEntries pushBack [format ["ALL (%1)", _availableCargo], -1]', self.src)

    def test_empty_bay_offers_a_single_inert_entry(self):
        self.assertIn('_cargoEntries pushBack ["NO CARGO", -1]', self.src)
        self.assertIn("if (_availableCargo <= 0) then", self.src)

    def test_lb_data_stays_a_numeric_string(self):
        """The config.bin handler parseNumbers lbData; display text is not parsed."""
        self.assertIn("_cargoCtrl lbSetData [_i, str (_x # 1)]", self.src)

    def test_stale_selection_falls_back_to_all(self):
        """Silently clamping at drop time would release fewer loads than the pilot
        last selected with no indication -- fn_triggerAutoDrop's `min _available`
        would absorb it.

        v0.7.0 added an ownership term. The reset itself is unchanged; what changed is
        WHO may perform it. Once cargoCount became crew-shared intent, a client whose
        replica of usaf_cargo was merely lagging -- which it is for a full round trip
        after every load and every release -- would reset the count and then publish
        that reset over the pilot's deliberate stick size.
        """
        self.assertIn("TLB_CARP_state_cargoCount > _availableCargo", self.src)
        self.assertIn("local _cargoVehicle", self.src)
        self.assertIn("TLB_CARP_state_cargoCount = -1;", self.src)

    def test_reset_happens_before_the_list_is_built(self):
        self.assertLess(
            self.src.index("TLB_CARP_state_cargoCount = -1;"),
            self.src.index("lbClear _cargoCtrl"),
        )

    def test_something_is_always_selected(self):
        self.assertIn("if ((lbCurSel _cargoCtrl) < 0) then {_cargoCtrl lbSetCurSel 0};", self.src)

    def test_refresh_guard_still_wraps_the_rebuild(self):
        """lbClear/lbAdd fire onLBSelChanged; without the guard the rebuild would
        disarm auto drop and reset the selection on every panel refresh."""
        self.assertIn("TLB_CARP_state_panelRefreshing", self.src)
        self.assertLess(self.src.index("TLB_CARP_state_panelRefreshing"), self.src.index("lbClear _cargoCtrl"))


class PostReleaseSolverThrottleTests(unittest.TestCase):
    """After the cargo is away and the solver has gone invalid, rebuilding the world
    solution every 0.05 s serves no purpose -- nothing reads it and it cannot become
    valid while usaf_cargo is empty.

    Motivation: chute-attach altitude is the dominant flown error. 3 of 7 flown drops
    attached 37-70 m below USAF's ~300 m trigger, and a late attach measured 52.1 m
    radial against 9.76 m for a prompt one. One flown drop with guidance disarmed
    immediately after release attached at 299.7 m. That is a hypothesis with a single
    supporting sample, not a settled result -- but skipping useless work is correct
    regardless."""

    def setUp(self):
        self.src = read("addon/functions/guidance/fn_updateGuidance.sqf")

    def test_solve_is_skipped_only_while_a_package_is_airborne(self):
        self.assertIn('in ["RELEASED", "CHUTE"]', self.src)
        self.assertIn("_skipSolve = _packageAirborne && _lastWasInvalid", self.src)

    def test_skip_requires_the_previous_solution_to_be_invalid(self):
        """Skipping while the solver is still valid would break the live display and
        the release gate."""
        self.assertIn("_lastWasInvalid = !((missionNamespace getVariable", self.src)

    def test_estimate_state_is_not_skipped(self):
        """The ESTIMATE -> RELEASED transition fires from the invalid branch, so a
        package in ESTIMATE must still reach the solver or the tracker never starts
        and the TOT freezes -- the v0.4.2 bug."""
        airborne = self.src[self.src.index("_packageAirborne ="):self.src.index("_lastWasInvalid =")]
        self.assertNotIn("ESTIMATE", airborne)

    def test_skipped_solution_is_marked(self):
        """A skipped tick must be distinguishable from a genuine solver failure."""
        self.assertIn('["solveSkipped", true]', self.src)

    def test_package_timing_still_runs_on_the_skipped_path(self):
        """TOT must keep counting through CHUTE to ARRIVED -- confirmed in flight."""
        self.assertLess(self.src.index("_skipSolve"), self.src.index("TLB_CARP_fnc_updatePackageTiming"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
"""v0.11.1 -- guided cargo is a panel button, and NOTHING the crew sets is unshared.

THE BUTTON. USAFDC_setting_jpadsEnabled was a per-client Addon Option. Two problems in
one: it is not reachable in flight, and being per-client it let the two seats disagree
about whether the load they are both dropping is guided. fn_steerBegin reads it on the
publishing machine, so whose copy won depended on which crew member fn_steerPublisher
happened to elect -- a coin toss the crew could not see.

It is now USAFDC_state_jpadsEnabled, a panel toggle and crew intent.

THE AUDIT. Three releases in a row added a control to the panel, and each time the
question "is it shared?" had to be answered by hand. This module answers it mechanically
instead.

The rule: every USAFDC_state_* a panel control writes is shared, unless it is named in
DELIBERATELY_LOCAL with a reason. Three are -- the autopilot, which the driver alone owns
because sharing it would have two machines commanding one aircraft's transform, and two
that are not intent at all: a derived per-pass latch and a re-entrancy guard. Naming them
is what keeps "not shared" a decision rather than an oversight.

WHY A GENERATED LIST AND NOT A HARDCODED ONE. A hardcoded list of fields is a second copy
of the payload that drifts. These tests read the panel and the sync layer and compare
them, so a control added without a payload entry fails without anybody remembering to
update a list.
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
    """Comments stripped, string literals intact."""
    sys.path.insert(0, str(ROOT / "tools"))
    from strip_sqf_comments import strip_comments

    path = ROOT / rel
    return strip_comments(path.read_text(encoding="utf-8")) if path.exists() else ""


ENHANCE = "addon/functions/ui/fn_ensurePanelEnhancements.sqf"
TELEM = "addon/functions/ui/fn_updatePanelTelemetry.sqf"
PANEL = "addon/functions/ui/fn_refreshPanel.sqf"
SNAPSHOT = "addon/functions/sync/fn_syncSnapshot.sqf"
APPLY = "addon/functions/sync/fn_syncApply.sqf"
POSTINIT = "addon/functions/fn_postInit.sqf"
BEGIN = "addon/functions/jpads/fn_steerBegin.sqf"
BENCH = "addon/functions/debug/fn_parallelDropBench.sqf"

# Written by the panel and deliberately NOT shared. Each one needs a reason, because the
# whole point of the audit is that "not shared" is a decision somebody made rather than a
# thing somebody forgot.
DELIBERATELY_LOCAL = {
    # Driver-only authority: two machines commanding one aircraft's transform is the one
    # thing crew sync must never do. See the developer guide, "Authority".
    "USAFDC_state_apArmed",
    # Derived, not intent. It records that THIS pass has already released, and every
    # intent change clears it locally anyway. Sharing it would let one client's completed
    # pass suppress another's release.
    "USAFDC_state_dropLatched",
    # A re-entrancy guard, live for the duration of one paint. It exists to stop
    # fn_refreshPanel's own lbSetCurSel re-entering the handlers it just fired.
    "USAFDC_state_panelRefreshing",
}


def snapshot_fields() -> set[str]:
    return set(re.findall(r"USAFDC_state_\w+", code(SNAPSHOT)))


def panel_written_state() -> set[str]:
    """Every USAFDC_state_* the panel's own controls set.

    Both forms: a direct `USAFDC_state_x = ...` assignment, and the indirect
    `missionNamespace setVariable [_var, ...]` used by the toggle and field tables, whose
    variable names appear as string literals in those tables.
    """
    found = set()
    for rel in (ENHANCE, PANEL):
        src = code(rel)
        found |= set(re.findall(r"(USAFDC_state_\w+)\s*=", src))
        found |= set(re.findall(r'"(USAFDC_state_\w+)"', src))
    return found


class JpadsToggleTests(unittest.TestCase):
    def test_guided_cargo_is_crew_state_not_a_per_client_option(self):
        """A per-client setting let the two seats disagree about whether the load they are
        both dropping is guided, and which copy won depended on which crew member
        fn_steerPublisher elected."""
        self.assertNotIn("USAFDC_setting_jpadsEnabled", read(POSTINIT))
        self.assertIn("USAFDC_state_jpadsEnabled = false;", read(POSTINIT))

    def test_the_steer_publisher_reads_the_crews_switch(self):
        src = code(BEGIN)
        self.assertIn('missionNamespace getVariable ["USAFDC_state_jpadsEnabled", false]', src)
        self.assertNotIn("USAFDC_setting_jpadsEnabled", src)

    def test_nothing_still_reads_the_removed_setting(self):
        """The bench flipped it around a run and would have silently stopped enabling
        guided cargo for every batch."""
        for rel in (BENCH, BEGIN, ENHANCE, TELEM, PANEL):
            self.assertNotIn("USAFDC_setting_jpadsEnabled", code(rel), rel)

    def test_the_bench_still_restores_what_it_found(self):
        src = code(BENCH)
        self.assertIn('private _jpadsBefore = missionNamespace getVariable ["USAFDC_state_jpadsEnabled", false]', src)
        self.assertIn("USAFDC_state_jpadsEnabled = _jpadsBefore;", src)

    def test_the_button_exists_and_is_labelled_from_the_same_state(self):
        """v0.15.0 moved the panel into addon/config.cpp, generated from a layout
        spec by tools/gen_dialog.py. What this used to assert about runtime ctrlCreate is
        now a config declaration, which is the better contract: the generator refuses to
        write if any two control rectangles overlap -- the check v0.11.0 did not have when
        it put four controls on top of the CARGO row and shipped it."""
        self.assertIn("idc=9336;", read("addon/config.cpp"))
        self.assertIn('[9336, "JPADS", "USAFDC_state_jpadsEnabled", false]', code(TELEM))

    def test_guided_cargo_still_defaults_off(self):
        """A long-standing invariant: nothing steers unless somebody asked for it."""
        self.assertIn("USAFDC_state_jpadsEnabled = false;", read(POSTINIT))
        # The button's own fallback matters as much as the state's: the config action
        # reads the variable with false as its default, so a fresh session toggles ON.
        self.assertIn("'USAFDC_state_jpadsEnabled',false", read("addon/config.cpp"))

    def test_every_toggle_publishes(self):
        """WAS: both toggles share one runtime handler, so neither can forget to publish.

        v0.15.0 moved the panel into addon/config.cpp, generated from a layout
        spec by tools/gen_dialog.py. What this used to assert about runtime ctrlCreate is
        now a config declaration, which is the better contract: the generator refuses to
        write if any two control rectangles overlap -- the check v0.11.0 did not have when
        it put four controls on top of the CARGO row and shipped it.

        A config declares each action separately, so the shared-handler guarantee is gone
        and the property has to be checked per control: every toggle must end by calling
        fn_refreshPanel, which is what publishes to the crew."""
        cfg = read("addon/config.cpp")
        for idc, var in [("9331", "USAFDC_state_smokeEnabled"), ("9336", "USAFDC_state_jpadsEnabled")]:
            block = cfg[cfg.index("idc=" + idc + ";"):]
            # NOT the first "};" -- a colour array ends "1};" and would cut the block
            # short of the action. The class terminator is the one at control indent.
            block = block[:block.index(chr(10) + chr(9) + chr(9) + "};")]
            self.assertIn(var, block, idc)
            self.assertIn("USAFDC_fnc_refreshPanel", block, idc)


class SyncCoverageTests(unittest.TestCase):
    def test_every_panel_control_writes_a_shared_field(self):
        """THE AUDIT. A control added without a payload entry fails here, rather than
        being discovered by a co-pilot who cannot see what the pilot just set."""
        missing = panel_written_state() - snapshot_fields() - DELIBERATELY_LOCAL
        self.assertEqual(missing, set(), f"panel writes these but they are not shared: {sorted(missing)}")

    def test_the_autopilot_is_excluded_on_purpose(self):
        """Driver-only authority, and the one exclusion that is real intent rather than
        derived state. Named so it stays a decision rather than a thing somebody forgot."""
        self.assertIn("USAFDC_state_apArmed", DELIBERATELY_LOCAL)
        self.assertNotIn("USAFDC_state_apArmed", snapshot_fields())

    def test_nothing_is_excluded_without_a_reason_beside_it(self):
        """A bare name added to the set is how a genuinely unshared control gets waved
        through. Every entry carries a comment saying why."""
        src = read("tests/test_v0111_sync_coverage.py")
        block = src[src.index("DELIBERATELY_LOCAL = {"):]
        block = block[:block.index("}")]
        entries = [ln.strip() for ln in block.splitlines() if ln.strip().startswith('"')]
        comments = [ln.strip() for ln in block.splitlines() if ln.strip().startswith("#")]
        self.assertEqual(len(entries), len(DELIBERATELY_LOCAL))
        self.assertGreaterEqual(len(comments), len(entries),
                                "every exclusion needs a reason written beside it")

    def test_every_payload_field_is_consumed(self):
        """A field published, unpacked and then ignored is worse than one never published:
        the record looks complete while the receiving client silently drops it.

        Consumed, not assigned. The DZ and the run-in lock are applied through
        fn_setDZ / fn_unlockRunIn rather than by assignment, because those also redraw
        markers and clear the derived state that depended on the old value."""
        src = code(APPLY)
        block = src[src.index("_payload params ["):]
        names = re.findall(r'"(_\w+)"', block[:block.index("];")])
        body = block[block.index("];"):]
        for name in names:
            self.assertIn(name, body, f"{name} is unpacked from the payload and never used")

    def test_every_snapshot_field_is_initialised(self):
        """An unset state variable reads nil, and a nil in the payload breaks the publish
        for every other field with it."""
        post = read(POSTINIT)
        for field in snapshot_fields():
            self.assertIn(f"{field} = ", post, f"{field} is published but never initialised")

    def test_the_snapshot_and_apply_lengths_agree(self):
        snap = code(SNAPSHOT)
        body = snap[snap.index("["):]
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
        self.assertEqual(fields, 18)
        self.assertIn("(count _payload) isEqualTo 18", code(APPLY))

    def test_the_apply_params_list_matches_the_payload_length(self):
        """params with fewer names than the payload silently drops the tail."""
        src = code(APPLY)
        block = src[src.index("_payload params ["):]
        block = block[:block.index("];")]
        self.assertEqual(len(re.findall(r'"_\w+"', block)), 18)

    def test_the_panel_publishes_before_it_paints(self):
        """Every binarized dialog handler ends by calling fn_refreshPanel, so this is the
        one publish point. Publishing last meant any error in the painting swallowed the
        crew's change."""
        src = code(PANEL)
        publish = src.index("USAFDC_fnc_syncPublish")
        first_paint = src.index("ctrlSetText")
        self.assertLess(publish, first_paint, "fn_refreshPanel must publish before painting")


if __name__ == "__main__":
    unittest.main(verbosity=2)

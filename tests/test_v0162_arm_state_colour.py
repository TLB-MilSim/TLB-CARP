"""v0.16.2 -- ARM AUTO DROP is red when disarmed and green when armed.

Asked for directly: "ARM AUTO DROP button should be red and green if armed just so we stop
forgetting it."

THE ONLY INTERESTING PART IS WHERE IT IS PAINTED.

A colour is worth nothing unless it is TRUE. fn_refreshPanel runs when a human presses
something, and auto drop disarms itself on two paths that are not presses -- after a release,
and on an AP disconnect. A colour set there would sit green on a disarmed button until
somebody happened to touch the panel, which is worse than no colour, because the crew would
now be trusting it.

fn_updatePanelTelemetry runs off the guidance loop, so it repaints live. The LABEL moved
there with the colour: two writers to one control is how the text and the colour come to
disagree, and the button ends up green while reading ARM. Moving it also closed the stale
label, which had the same hole and predates this change.

AND THE STATIC COLOUR IN THE CONFIG HAS TO MATCH THE DISARMED ONE

config.cpp carries a colorText for the frame the control is created on, before the first
repaint. If that is the old amber, every panel open flashes the wrong colour. Two spellings
of one colour is how they drift, so the constant, the config and the SQF are pinned together
here.
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


TELEM = "addon/functions/ui/fn_updatePanelTelemetry.sqf"
REFRESH = "addon/functions/ui/fn_refreshPanel.sqf"
GEN = "tools/gen_dialog.py"
CONFIG = "addon/config.cpp"

RED = "[0.898, 0.302, 0.251, 1]"
GREEN = "[0.365, 0.855, 0.404, 1]"


class ColourTests(unittest.TestCase):
    def test_the_button_is_coloured_from_the_armed_flag(self):
        src = code(TELEM)
        self.assertIn("_autoCtrl ctrlSetTextColor (", src)
        self.assertIn(GREEN, src)
        self.assertIn(RED, src)

    def test_green_is_armed_and_red_is_not(self):
        """Backwards here would be actively dangerous -- it is the whole point of the
        change that a glance tells the truth."""
        src = code(TELEM)
        block = src[src.index("_autoCtrl ctrlSetTextColor ("):]
        block = block[:block.index(");")]
        self.assertLess(block.index(GREEN), block.index(RED),
                        "then{} is the armed branch: green must come first")

    def test_the_colour_reads_this_machines_flag_not_crew_intent(self):
        """Same rule the label already carried. config.bin's handler toggles on
        TLB_CARP_state_autoArmed, so anything else makes the control lie about its action."""
        src = code(TELEM)
        block = src[src.index("private _autoCtrl"):]
        block = block[:block.index("} forEach [")]
        self.assertIn('getVariable ["TLB_CARP_state_autoArmed", false]', block)
        self.assertNotIn("syncWantAuto", block)


class OneWriterTests(unittest.TestCase):
    def test_the_label_and_colour_are_painted_in_the_same_place(self):
        src = code(TELEM)
        block = src[src.index("private _autoCtrl"):]
        block = block[:block.index("} forEach [")]
        self.assertIn("ctrlSetText", block)
        self.assertIn("ctrlSetTextColor", block)

    def test_refresh_panel_no_longer_writes_the_auto_drop_label(self):
        """THE DEFECT THIS AVOIDS. Two writers, one control: refreshPanel paints the text on
        a press, telemetry paints the colour every tick, and after a self-disarm the button
        is red and still reads DISARM."""
        src = code(REFRESH)
        self.assertNotIn("displayCtrl 9311", src)

    def test_refresh_panel_still_drives_the_telemetry_pass(self):
        """So a human press repaints immediately rather than waiting for a guidance tick."""
        self.assertIn("TLB_CARP_fnc_updatePanelTelemetry", code(REFRESH))

    def test_the_telemetry_pass_is_driven_by_the_guidance_loop(self):
        """This is what makes the colour true between presses. Without it the change is
        cosmetic and the stale-green hole is still open."""
        self.assertIn("TLB_CARP_fnc_updatePanelTelemetry", code("addon/functions/guidance/fn_updateGuidance.sqf"))

    def test_the_label_reads_the_state_not_the_action(self):
        """DELIBERATE REVERSAL, asked for by the crew. The button used to be labelled with
        what pressing it would DO ("DISARM AUTO" when armed). It now reads its STATE, which
        makes it consistent with SMOKE and JPADS directly below it -- three adjacent
        controls had meant three different things.

        The half that was a BUG is unchanged and tested above: it must read the same
        variable config.bin's handler toggles on. A state label cannot misdescribe an
        action it no longer claims, but it can still report the wrong machine's state."""
        src = read(TELEM)
        self.assertIn('{"AUTO DROP: ON"} else {"AUTO DROP: OFF"}', src)
        # Scoped to the line that actually paints, not the whole file -- the comment above
        # it quotes the old wording on purpose, to record what was reversed and why.
        paint = [l for l in src.splitlines()
                 if "_autoCtrl ctrlSetText" in l and "ctrlSetTextColor" not in l]
        self.assertEqual(len(paint), 1, "one painter, or the reversal missed a copy")
        self.assertNotIn("DISARM", paint[0])

    def test_the_static_label_is_the_off_state(self):
        """Same reason the static colour is the OFF colour: it is the frame before the
        first repaint. A button that says ON for one frame on every panel open is a lie
        that is hard to catch and impossible to unsee once noticed."""
        cfg = read(CONFIG)
        block = cfg[cfg.index("class AutoDrop: RscButton"):]
        block = block[:block.index("\n\t\t};")]
        self.assertIn('text="AUTO DROP: OFF"', block)


class StaticAndRuntimeAgreeTests(unittest.TestCase):
    @staticmethod
    def _floats(s: str) -> list[float]:
        return [round(float(v), 4) for v in re.findall(r"[0-9.]+", s)]

    def test_the_config_default_is_the_disarmed_colour(self):
        """The frame before the first repaint. Amber here means every panel open flashes a
        colour that means nothing."""
        cfg = read(CONFIG)
        block = cfg[cfg.index("class AutoDrop: RscButton"):]
        block = block[:block.index("\n\t\t};")]
        m = re.search(r"colorText\[\]=\{([^}]*)\}", block)
        self.assertIsNotNone(m, "AutoDrop has no colorText")
        self.assertEqual(self._floats(m.group(1)), self._floats(RED))

    def test_the_generator_constant_matches_the_sqf(self):
        """Two copies of one colour drift. This is the same discipline the AP turn-rate
        schedule gets, for the same reason."""
        gen = read(GEN)
        off = re.search(r'C_ARM_OFF = "\{([^}]*)\}"', gen)
        on = re.search(r'C_ARM_ON = "\{([^}]*)\}"', gen)
        self.assertIsNotNone(off)
        self.assertIsNotNone(on)
        self.assertEqual(self._floats(off.group(1)), self._floats(RED))
        self.assertEqual(self._floats(on.group(1)), self._floats(GREEN))

    def test_the_generator_says_why_the_constants_must_match(self):
        self.assertIn("HAS TO STAY THAT WAY", read(GEN))

    def test_colortext_is_still_the_only_styling_the_button_carries(self):
        """v0.16.1: a property added on the strength of its name shipped a broken panel.
        Recolouring a button is not a licence to restyle it."""
        cfg = read(CONFIG)
        block = cfg[cfg.index("class AutoDrop: RscButton"):]
        block = block[:block.index("\n\t\t};")]
        props = set(re.findall(r"^\t+(\w+)(?:\[\])?=", block, re.M))
        self.assertEqual(props, {"idc", "text", "x", "y", "w", "h", "font", "sizeEx",
                                 "colorText", "tooltip", "action"})


if __name__ == "__main__":
    unittest.main(verbosity=2)

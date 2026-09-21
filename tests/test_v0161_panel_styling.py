"""v0.16.1 -- borderSize is a fraction of the SCREEN, and v0.15.0 set it to 1.

FLOWN, and it made the panel unusable.

Every row containing a button came back with a dark bar bleeding off the left edge of the
screen. The two rows with no button -- MODE and AIRCRAFT -- were the only clean ones, and
that was the tell.

WHAT WENT WRONG, AND WHAT DID NOT

Not the geometry. Every x/y/w/h in the shipped binary was exactly what the layout spec
computed: inside the panel, no overlaps, verified by decompiling config.bin after the fact.
The generator's overlap check did its job.

The defect was a property whose UNITS were never checked. v0.15.0 styled every button with

    colorBackground / colorBackgroundActive / colorFocused / colorBorder / borderSize=1

The config it replaced carried NONE of those -- the old buttons were idc, text, x, y, w, h
and action, inheriting everything else from the game's base classes, which already define
all of it correctly. In an Arma UI config `borderSize` is a fraction of the screen, not a
pixel count, so borderSize=1 asked for a border a full screen wide around each button.

THE LESSON IS NOT "USE A SMALLER BORDER"

It is that a config cannot be rendered from a build script, so a property added on the
strength of what its name suggests has nothing between it and a flown session. The emitter
is now restricted to the property set the previous working config used, plus
font/sizeEx/colorText/colorBackground/tooltip -- ordinary properties that were in the
screenshot that worked. Adding a name to that list means having checked what the property
means, in units, first.
"""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.exists() else ""


CONFIG = "addon/config.cpp"
GEN = "tools/gen_dialog.py"

# The property set the previous, flown config carried, plus the four ordinary ones.
ALLOWED = {
    "idc", "text", "x", "y", "w", "h",
    "font", "sizeEx", "colorText", "colorBackground",
    "tooltip", "action", "onLBSelChanged", "onCheckedChanged",
}


def dialog_block() -> str:
    cfg = read(CONFIG)
    return cfg[cfg.index("class USAFDC_RscDialog"):cfg.index("class RscTitles")]


class NoUnverifiedPropertyTests(unittest.TestCase):
    def test_bordersize_is_nowhere_in_the_dialog(self):
        """THE DEFECT. A fraction of the screen, set to 1, on every button."""
        self.assertNotIn("borderSize", dialog_block())

    def test_none_of_the_styling_that_shipped_broken_is_back(self):
        block = dialog_block()
        for prop in ["colorBorder", "colorBackgroundActive", "colorFocused"]:
            self.assertNotIn(prop, block, prop)

    def test_no_control_carries_a_property_outside_the_verified_set(self):
        """The generator refuses these, but the config is what ships -- so the check that
        matters is against the config, not against the tool that writes it."""
        emitted = set(re.findall(r"^\t+(\w+)(?:\[\])?=", dialog_block(), re.M))
        # idd / movingEnable / enableSimulation / onLoad / onUnload belong to the display
        # itself rather than to a control.
        display = {"idd", "movingEnable", "enableSimulation", "onLoad", "onUnload"}
        stray = sorted(emitted - ALLOWED - display)
        self.assertEqual(stray, [], f"unverified control properties in the config: {stray}")

    def test_the_generator_refuses_them_before_writing(self):
        """Catching it in the config is catching it late. The emitter is where it stops."""
        src = read(GEN)
        self.assertIn("refusing to emit unverified control properties", src)
        self.assertIn("allowed = {", src)

    def test_the_generator_records_why_the_list_exists(self):
        """A bare allowlist gets widened by the next person who wants a border. The reason
        has to travel with it."""
        src = read(GEN)
        self.assertIn("borderSize", src)
        self.assertIn("FRACTION OF THE SCREEN", src)


class ButtonsMatchWhatWorkedTests(unittest.TestCase):
    def test_a_button_carries_only_the_old_set_plus_font_and_colour(self):
        block = dialog_block()
        btn = block[block.index("class ApplyProfile: RscButton"):]
        btn = btn[:btn.index("\n\t\t};")]
        props = set(re.findall(r"^\t+(\w+)(?:\[\])?=", btn, re.M))
        self.assertEqual(props, {"idc", "text", "x", "y", "w", "h", "font", "sizeEx",
                                 "colorText", "action"})

    def test_the_layout_itself_was_never_the_problem_and_is_unchanged(self):
        """Worth pinning: the overlap checker was right, the panel spans 0.315-0.685, and
        nothing about the geometry needed touching to fix this."""
        block = dialog_block()
        xs = [float(m) for m in re.findall(r'x="safeZoneX\+safeZoneW\*([0-9.]+)"', block)]
        ws = [float(m) for m in re.findall(r'w="safeZoneW\*([0-9.]+)"', block)]
        self.assertTrue(xs and ws)
        self.assertGreaterEqual(min(xs), 0.30)
        self.assertLessEqual(max(x + w for x, w in zip(xs, ws)), 0.6951)


if __name__ == "__main__":
    unittest.main(verbosity=2)

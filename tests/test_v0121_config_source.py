"""v0.12.1 -- config.bin stops being frozen, and CARP stops requiring the USAF mod to load.

THE ASSUMPTION THAT WAS NEVER CHECKED

Every design note in this project said addon/config.bin was pre-binarized and could not be
regenerated, and the architecture is shaped around it. The dialog cannot gain controls, so
they are created at runtime with ctrlCreate. New functions cannot be declared in
CfgFunctions, so they go in a compile table. ui/*.hpp is compiled in, so HUD geometry is
written with ctrlSetPosition instead.

Arma 3 Tools ships CfgConvert, which de-rapifies a config.bin to text and rapifies it back.
On this file the round trip is BYTE-IDENTICAL -- 11856 bytes, sha256 d87f8780..., in both
directions, verified before the first edit was made. The constraint was real only while
nobody had the tool.

THE FIRST EDIT, DELIBERATELY THE SMALLEST ONE AVAILABLE

    requiredAddons[] = {"cba_main", "ace_interact_menu", "USAF_Cargo"};

v0.10.0 moved the whole release sequence into fn_releaseCargo, so nothing in CARP needs
USAF at runtime. That line still refused to load the addon without it -- which made "CARP
does not depend on the USAF mod" untrue in the only way a user ever notices.

Removing one array entry changes twelve bytes and touches no behaviour, which is exactly
what a first edit to a file nobody has successfully rebuilt in this project's history
should do. It proves the pipeline in the aircraft at the lowest possible stake.

WHAT THESE TESTS ARE FOR

config.cpp is now the source and config.bin is a build artifact. Nothing else in the suite
would notice them drifting apart: the tests read .sqf text, and the PBO build verifies
config.bin against itself as a source file. So the drift is checked here, by decompiling
the binary that will actually ship and comparing it against the text.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONFIG_CPP = ROOT / "addon" / "config.cpp"
CONFIG_BIN = ROOT / "addon" / "config.bin"


def read(rel: str) -> str:
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.exists() else ""


def cfgconvert() -> Path | None:
    sys.path.insert(0, str(ROOT / "tools"))
    import build_config

    for path in build_config.CANDIDATES:
        if path.is_file():
            return path
    return None


class ConfigSourceTests(unittest.TestCase):
    def test_the_text_source_exists(self):
        """config.bin is a build artifact now. Losing the text would put the project back
        where it started, working around a constraint that no longer exists."""
        self.assertTrue(CONFIG_CPP.is_file(), "addon/config.cpp is the source of truth")
        self.assertTrue(CONFIG_BIN.is_file())

    def test_the_builder_exists_and_refuses_to_clobber_the_source(self):
        src = read("tools/build_config.py")
        self.assertIn("CfgConvert", src)
        self.assertIn("refusing to overwrite the source of truth", src)

    def test_the_rebuild_guard_compares_against_source_not_a_magic_number(self):
        """The first version of this guard used a fixed threshold and failed a build whose
        only difference was twelve bytes of removed dependency. A config is meant to
        change; what must not change silently is its contents."""
        src = read("tools/build_config.py")
        self.assertIn("source.count(what)", src)
        self.assertNotIn("< 60", src)

    def test_usaf_cargo_is_not_required_to_load(self):
        """THE POINT. v0.10.0 removed every runtime dependency on USAF; this line still
        refused to load the addon without it."""
        block = re.search(r"requiredAddons\[\]=\s*\{(.*?)\}", CONFIG_CPP.read_text(encoding="utf-8"), re.S)
        self.assertIsNotNone(block, "requiredAddons not found")
        entries = re.findall(r'"([^"]+)"', block.group(1))
        self.assertNotIn("USAF_Cargo", entries)
        self.assertIn("cba_main", entries, "CBA is a real dependency and must stay")
        self.assertIn("ace_interact_menu", entries, "the ACE action needs it")

    def test_every_remaining_usaf_touchpoint_is_guarded(self):
        """Dropping the hard requirement is only safe because nothing calls into USAF
        without testing for it first. fn_releaseSelected is the one path that still can."""
        sys.path.insert(0, str(ROOT / "tools"))
        from strip_sqf_comments import strip_comments

        src = strip_comments(read("addon/functions/cargo/fn_releaseSelected.sqf"))
        guard = src.index('isNil "USAF_CARGO_fnc_canDrop"')
        call = src.index("spawn USAF_CARGO_fnc_canDrop")
        self.assertLess(guard, call, "the nil test must precede the call")

    def test_the_manifest_reads_usaf_cargo_as_an_object_variable(self):
        """An absent object variable is an empty array, not an error, so the manifest is
        simply empty of USAF entries when USAF is not loaded."""
        sys.path.insert(0, str(ROOT / "tools"))
        from strip_sqf_comments import strip_comments

        src = strip_comments(read("addon/functions/cargo/fn_cargoManifest.sqf"))
        self.assertIn('getVariable ["usaf_cargo", []]', src)


class ConfigBinaryMatchesSourceTests(unittest.TestCase):
    """The binary that ships against the text that is reviewed.

    Skipped where Arma 3 Tools is not installed -- CI and a fresh clone should not fail
    for want of a Steam download -- but it runs on the machine that builds releases, which
    is the one that matters.
    """

    @classmethod
    def setUpClass(cls):
        cls.tool = cfgconvert()
        if cls.tool is None:
            raise unittest.SkipTest("Arma 3 Tools' CfgConvert not installed")

    def _decompiled(self) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "check.cpp"
            proc = subprocess.run(
                [str(self.tool), "-txt", "-dst", str(out), str(CONFIG_BIN)],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return out.read_text(encoding="utf-8", errors="replace")

    def test_the_packed_binary_carries_the_edit(self):
        """config.cpp saying one thing while the PBO ships another is the exact failure
        this whole change could introduce."""
        text = self._decompiled()
        block = re.search(r"requiredAddons\[\]=\s*\{(.*?)\}", text, re.S)
        self.assertIsNotNone(block)
        self.assertNotIn("USAF_Cargo", re.findall(r'"([^"]+)"', block.group(1)))

    def test_nothing_was_lost_rebuilding_it(self):
        """35 controls and 111 classes went in. A rebuild that quietly dropped one would
        fail nowhere else in this suite."""
        text = self._decompiled()
        source = CONFIG_CPP.read_text(encoding="utf-8")
        self.assertEqual(text.count("idc="), source.count("idc="))
        self.assertEqual(text.count("class "), source.count("class "))

    def test_the_dialog_and_its_handlers_survived(self):
        """The 22 handler strings are what make a runtime-built replacement unnecessary.
        Losing them in a rebuild would be silent until a control was clicked."""
        text = self._decompiled()
        self.assertIn("TLB_CARP_RscDialog", text)
        self.assertIn("TLB_CARP_fnc_refreshPanel", text)
        self.assertIn("TLB_CARP_fnc_beginMapDZ", text)
        self.assertGreaterEqual(text.count("TLB_CARP_fnc_"), 15)


if __name__ == "__main__":
    unittest.main(verbosity=2)

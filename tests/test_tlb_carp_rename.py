from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PREFIX = r"\x\tlbcarp\addons\drop_computer"

# Files that name the old prefix ON PURPOSE, each for a stated reason. Everything else
# must be free of it.
#
#   build_release / test_mod_naming / test_v090_crew_access
#       record what SHIPPED under the old name. build_release deletes a legacy PBO left
#       beside the current one, so when the rename swept this name up it became equal to
#       PBO_NAME -- and deploy would have deleted the PBO it had just installed.
#   fn_openPanel
#       reads USAFDC_carpRecord to detect a pre-rename crewmate, who is otherwise
#       completely invisible to this build.
#   pack_pbo
#       its --prefix help names the old addon path, which is the reason the flag exists.
HISTORICAL = {
    ROOT / "tools" / "build_release.py",
    ROOT / "tools" / "pack_pbo.py",
    ROOT / "tests" / "test_mod_naming.py",
    ROOT / "tests" / "test_v090_crew_access.py",
    ROOT / "tests" / "test_tlb_carp_rename.py",
    ROOT / "addon" / "functions" / "ui" / "fn_openPanel.sqf",
}


def source_files():
    for pattern in ("addon/**/*.sqf", "addon/**/*.hpp", "addon/config.cpp",
                    "tools/*.py", "tests/*.py", "testing/*.sqf", "items/config.cpp"):
        for p in ROOT.glob(pattern):
            if p.is_file():
                yield p


class RenameTests(unittest.TestCase):
    def test_no_source_file_still_uses_the_old_symbol_prefix(self):
        # Reported as file:line rather than with assertNotIn, which prints the whole file
        # and buries the one line that matters.
        offenders = []
        for p in source_files():
            if p in HISTORICAL:
                continue
            for number, line in enumerate(
                p.read_text(encoding="utf-8", errors="replace").split("\n"), start=1
            ):
                if "USAFDC" in line or "usafdc" in line:
                    offenders.append(f"{p.relative_to(ROOT)}:{number}: {line.strip()[:70]}")
        self.assertEqual(
            [], offenders,
            "the old prefix survives in:\n  " + "\n  ".join(offenders)
        )

    def test_the_binarised_config_carries_no_old_name(self):
        # config.cpp is the source and config.bin is built from it, so the two drift apart
        # the moment somebody edits the text and does not rebuild. A rename is exactly the
        # change where that would be invisible until the addon is loaded in game.
        blob = (ROOT / "addon" / "config.bin").read_bytes()
        self.assertNotIn(b"USAFDC", blob, "config.bin is stale -- rerun tools/build_config.py")
        self.assertNotIn(b"usafdc", blob, "config.bin is stale -- rerun tools/build_config.py")
        self.assertIn(b"TLB_CARP", blob)

    def test_the_three_copies_of_the_pbo_prefix_agree(self):
        # The addon path lives in three places that have to match exactly, and a mismatch
        # is silent: the PBO simply mounts somewhere CfgFunctions is not looking, and every
        # function is nil at runtime with nothing in the RPT to say why.
        config = (ROOT / "addon" / "config.cpp").read_text(encoding="utf-8")
        postinit = (ROOT / "addon" / "functions" / "fn_postInit.sqf").read_text(encoding="utf-8")
        build = (ROOT / "tools" / "build_release.py").read_text(encoding="utf-8")

        self.assertIn(PREFIX, config, "CfgFunctions does not use the current prefix")
        self.assertIn(PREFIX, postinit, "the compile table does not use the current prefix")
        # build_release spells it for a Python string literal, so backslashes are doubled.
        self.assertIn(PREFIX.lstrip("\\").replace("\\", "\\\\"), build,
                      "build_release.PREFIX does not match the source paths")

        for name, text in (("config.cpp", config), ("fn_postInit.sqf", postinit)):
            others = set(re.findall(r"\\x\\[a-z_]+\\addons\\[a-z_]+", text))
            self.assertLessEqual(
                others, {PREFIX, r"\x\tlbcarp\addons\items"},
                f"{name} references an addon path that is neither the drop computer's "
                f"nor the items addon's: {others}"
            )

    def test_no_compiled_sqfc_survives_anywhere(self):
        # Every .sqfc had the old symbol names compiled in and shadowed the .sqf beside it,
        # so one surviving file would silently run pre-rename code. They were all deleted;
        # the build excludes them from the base PBO, which still lists them.
        stale = sorted(str(p.relative_to(ROOT)) for p in ROOT.glob("addon/**/*.sqfc"))
        self.assertEqual([], stale, "a compiled .sqfc would shadow the renamed source")

        build = (ROOT / "tools" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn("DELETED_SQFC_ENTRIES", build)
        listed = re.findall(r'"(functions\\\\[^"]+\.sqfc)"', build)
        self.assertGreaterEqual(
            len(listed), 20,
            "the exclude list looks short -- pack_pbo fails on a base entry with no source"
        )

    def test_the_addon_declares_itself_under_the_new_name(self):
        config = (ROOT / "addon" / "config.cpp").read_text(encoding="utf-8")
        self.assertIn("class tlb_carp_system", config)
        self.assertIn('tag="TLB_CARP"', config)
        self.assertIn('name="TLB CARP', config)
        self.assertNotIn("USAF CARP", config)

    def test_a_pre_rename_crewmate_is_reported_rather_than_silently_ignored(self):
        # The one genuinely dangerous case: an older client keeps its record under
        # USAFDC_carpRecord, which this build never reads, so both crews see a coherent
        # CARP and never see each other. The version notice cannot catch it because that
        # version travels inside the record.
        panel = (ROOT / "addon" / "functions" / "ui" / "fn_openPanel.sqf").read_text(encoding="utf-8")
        self.assertIn('getVariable "USAFDC_carpRecord"', panel)
        self.assertIn("TLB_CARP_legacyRecordWarned", panel)
        self.assertIn("running an older build", panel)

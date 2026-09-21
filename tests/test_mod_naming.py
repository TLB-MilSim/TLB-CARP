from pathlib import Path
import contextlib
import importlib.util
import io
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load_tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ModNamingTests(unittest.TestCase):
    def setUp(self):
        self.build = load_tool("build_release")

    def write_release(self, path: Path):
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr(f"{self.build.MOD_DIR}/addons/{self.build.PBO_NAME}", b"new pbo")
            zf.writestr(f"{self.build.MOD_DIR}/mod.cpp", b"name = \"test\";")

    def test_pbo_and_mod_folder_are_named_for_the_mod(self):
        self.assertEqual(self.build.PBO_NAME, "TLB_CARP_System.pbo")
        self.assertEqual(self.build.MOD_DIR, "@TLB_CARP_System")
        self.assertIn("usafdc_drop_computer.pbo", self.build.LEGACY_PBO_NAMES)
        self.assertIn("@USAF_CARP_System", self.build.LEGACY_MOD_DIRS)

    def test_deploy_removes_the_pbo_under_its_old_name(self):
        """Both names carry the same CfgPatches class. A deploy over a mod folder that
        still holds the old PBO would otherwise leave Arma loading the addon twice."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release = root / "release.zip"
            self.write_release(release)
            target = root / "mod"
            (target / "addons").mkdir(parents=True)
            legacy = target / "addons" / "usafdc_drop_computer.pbo"
            legacy.write_bytes(b"old pbo")

            with contextlib.redirect_stdout(io.StringIO()):
                self.build.deploy(release, target)

            self.assertFalse(legacy.exists())
            self.assertEqual((target / "addons" / self.build.PBO_NAME).read_bytes(), b"new pbo")
            self.assertEqual(sorted(p.name for p in (target / "addons").iterdir()), [self.build.PBO_NAME])

    def test_deploy_warns_about_the_old_mod_folder_but_leaves_it_alone(self):
        """The old folder may be what the launcher still points at, so deploy never
        deletes it -- but loading both loads the addon twice, so it must say so."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release = root / "release.zip"
            self.write_release(release)
            old = root / "@USAF_CARP_System"
            (old / "addons").mkdir(parents=True)

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.build.deploy(release, root / "@TLB_CARP_System")

            self.assertIn("WARNING", out.getvalue())
            self.assertIn("@USAF_CARP_System", out.getvalue())
            self.assertTrue(old.is_dir())

    def test_rotation_archives_a_release_zip_under_the_old_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "@USAF_CARP_System_v0.8.4-old.zip"
            legacy.write_bytes(b"old release")
            keep = root / "@TLB_CARP_System_v0.8.5-new.zip"
            keep.write_bytes(b"new release")
            archive = root / "releases"

            self.build.rotate_old_releases(root, keep, archive)

            self.assertTrue((archive / legacy.name).is_file())
            self.assertEqual(self.build.release_zips(root), [keep])

    def test_publish_finds_release_zips_under_both_names(self):
        publish = load_tool("publish_release")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "releases").mkdir()
            (root / "releases" / "@USAF_CARP_System_v0.8.4-old.zip").write_bytes(b"")
            (root / "@TLB_CARP_System_v0.8.5-new.zip").write_bytes(b"")
            publish.ROOT = root

            self.assertEqual(publish.asset_for("v0.8.4").name, "@USAF_CARP_System_v0.8.4-old.zip")
            self.assertEqual(publish.asset_for("v0.8.5").name, "@TLB_CARP_System_v0.8.5-new.zip")
            self.assertIsNone(publish.asset_for("v9.9.9"))

    def test_publish_attaches_the_loose_pbos_alongside_the_zip(self):
        """A Workshop upload refreshes a staging folder by copying two files. The ZIP is
        still first in the list -- it is what a player installs."""
        publish = load_tool("publish_release")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "@TLB_CARP_System_v0.16.12-x.zip").write_bytes(b"")
            pbos = root / "releases" / "pbo" / "v0.16.12"
            pbos.mkdir(parents=True)
            (pbos / "TLB_CARP_System.pbo").write_bytes(b"")
            (pbos / "TLB_CARP_Items.pbo").write_bytes(b"")
            publish.ROOT = root

            names = [a.name for a in publish.assets_for("v0.16.12")]
            self.assertEqual(names[0], "@TLB_CARP_System_v0.16.12-x.zip")
            self.assertEqual(sorted(names[1:]),
                             ["TLB_CARP_Items.pbo", "TLB_CARP_System.pbo"])

    def test_a_release_built_before_the_pbo_export_still_publishes(self):
        """Every release through v0.16.12 was built without it. Publishing those must not
        start failing because a folder is missing."""
        publish = load_tool("publish_release")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "@TLB_CARP_System_v0.8.5-new.zip").write_bytes(b"")
            publish.ROOT = root

            self.assertEqual(publish.pbos_for("v0.8.5"), [])
            self.assertEqual([a.name for a in publish.assets_for("v0.8.5")],
                             ["@TLB_CARP_System_v0.8.5-new.zip"])

    def test_the_exported_pbos_keep_their_runtime_names(self):
        """They are copied straight into a mod folder, so a version-qualified filename
        would have to be renamed by hand every release. The VERSION is the folder."""
        build = load_tool("build_release")
        src = (ROOT / "tools" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('pbo_out = archive_dir / "pbo" / f"v{short}"', src)
        self.assertIn("(pbo_out / built.name).write_bytes(body)", src)
        self.assertEqual(build.PBO_NAME, "TLB_CARP_System.pbo")
        self.assertEqual(build.ITEMS_PBO_NAME, "TLB_CARP_Items.pbo")

    def test_the_export_is_verified_against_the_shipped_zip(self):
        """A loose PBO that is not the one inside the ZIP would be worse than none: it
        would deploy to the Workshop while every checksum in the release notes described
        something else."""
        src = (ROOT / "tools" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn("differs from the copy inside", src)

    def test_the_export_does_not_break_the_one_zip_root_rule(self):
        """CLAUDE.md: never leave a loose .pbo at the repo root. The export writes under
        releases/, and the rotate step that enforces the rule runs after it."""
        src = (ROOT / "tools" / "build_release.py").read_text(encoding="utf-8")
        # Order by NAME, not by step number. The numbers shifted when signing was added
        # as step 3, and a test that pins them fails on an unrelated insertion while
        # proving nothing about the rule it is named for.
        self.assertLess(src.index("Export loose PBOs"),
                        src.index("Rotate superseded releases"))
        self.assertLess(src.index("Rotate superseded releases"),
                        src.index("Deploy to Arma mod folder"))



class LicenceTests(unittest.TestCase):
    """The mod travels as a folder, so the licence has to travel with it."""

    def setUp(self):
        self.build = load_tool("build_release")
        self.licence = ROOT / "LICENSE"

    def test_the_licence_is_apl_nd_and_names_this_mod(self):
        self.assertTrue(self.licence.is_file(), "LICENSE is missing")
        text = self.licence.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("TLB CARP"), "LICENSE does not name the mod first")
        self.assertIn("Arma Public License No Derivatives (APL-ND)", text)
        self.assertIn("https://www.bohemia.net/community/licenses/arma-public-license-nd", text)

    def test_the_release_zip_carries_the_licence(self):
        src = (ROOT / "tools" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('zip_members.append((f"{MOD_DIR}/LICENSE", licence.read_bytes()))', src)

    def test_the_readme_points_at_it(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Arma Public License No Derivatives (APL-ND)", readme)
        self.assertIn("(LICENSE)", readme)


if __name__ == "__main__":
    unittest.main()

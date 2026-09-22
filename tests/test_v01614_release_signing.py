"""v0.16.14 -- every release is signed.

THE BLOCKER. A server running `verifySignatures = 2` -- which is the normal setting --
kicks every client that loads an unsigned mod. Until now there was no `.biprivatekey`, no
`.bikey` and no `.bisign` anywhere in the project, and the release ZIP carried only the two
PBOs and mod.cpp. That made TLB CARP undeployable to any unit server with signature checks
on, which is most of them. Found while answering a question about the client/server split;
asked for directly on the way to 1.0.0.

ONE KEY PER VERSION, as of 2026-09-22. This file originally argued the opposite: a
versioned key makes every admin install a new .bikey every release, and that is how a unit
ends up turning signature checking off instead. The owner chose versioned keys to match the
other TLB mods. That cost did not disappear -- it moved into the release notes, which now
have to say the key changed, every time.

THE PRIVATE KEY LIVES OUTSIDE THE REPOSITORY. Anyone holding it can sign a hostile PBO
that passes as TLB CARP, so there must be no path by which it reaches a commit or the
source ZIP. Keeping it out of the tree is that guarantee; the .gitignore entries are a
backstop for a copy made by hand, not the mechanism.

SIGNING HAPPENS BETWEEN THE BUILD AND THE ZIP. That is what puts the .bisign files inside
the release archive. Signing afterwards would leave the ZIP and the mod folder disagreeing
about what shipped, which is the same class of error as a stale .sqfc.

AND IT IS VERIFIED, NOT ASSUMED. DSCheckSignatures runs against the freshly signed PBOs
before the build continues. A signature the engine will reject is worse than no signature
at all, because the build would report the deployment blocker closed.
"""
from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUILD = (ROOT / "tools" / "build_release.py").read_text(encoding="utf-8")


class SigningStepTests(unittest.TestCase):
    def test_the_build_has_a_signing_step(self):
        self.assertIn('step(3, "Sign the PBOs")', BUILD)

    def test_it_runs_before_the_release_zip_is_written(self):
        """THE ORDERING IS THE POINT: it is what puts the .bisign inside the archive."""
        self.assertLess(BUILD.index('step(3, "Sign the PBOs")'),
                        BUILD.index('step(4, "Write release ZIP")'))

    def test_both_pbos_are_signed(self):
        self.assertIn("for built in (pbo_path, items_path):", BUILD)
        self.assertIn("DSSignFile.exe", BUILD)

    def test_the_signatures_are_verified_before_the_build_continues(self):
        """A signature the engine rejects is worse than none -- the build would claim the
        blocker was closed."""
        self.assertIn("DSCheckSignatures.exe", BUILD)
        self.assertIn("DSCheckSignatures rejected the signed PBOs", BUILD)

    def test_the_verdict_is_the_exit_code_and_not_the_output(self):
        """MEASURED AGAINST THE TOOL, not assumed. A good folder prints NOTHING and exits
        0; an unsigned PBO gives exit 1 and a missing public key exit 2, each with a line
        saying which. The first version of this keyed on a "Verified" string and failed
        every good build."""
        self.assertIn("if check.returncode != 0:", BUILD)
        self.assertNotIn('"Verified" not in out', BUILD)

    def test_the_check_runs_against_our_pbos_alone(self):
        """DSCheckSignatures walks every PBO it finds, and the temp dir also holds
        base.pbo -- the previous release, extracted to supply the entry set. That is not
        ours to sign, and it failed the first signed build."""
        self.assertIn('check_dir = tmp_path / "signcheck"', BUILD)

    def test_a_missing_key_fails_the_build_and_says_how_to_make_one(self):
        """Silently shipping unsigned is the failure mode this exists to prevent."""
        self.assertIn("signing key {needed} not found", BUILD)
        self.assertIn("DSCreateKey.exe", BUILD)

    def test_unsigned_is_possible_but_must_be_asked_for_and_says_what_it_costs(self):
        self.assertIn('ap.add_argument("--no-sign"', BUILD)
        self.assertIn("this release is UNSIGNED", BUILD)


class ArchiveLayoutTests(unittest.TestCase):
    def test_the_bisign_sits_beside_the_pbo_it_signs(self):
        self.assertIn('zip_members.append((f"{MOD_DIR}/addons/{name}", body))', BUILD)

    def test_the_public_key_ships_in_keys(self):
        """Where a server admin expects to find it and copy it into the server's Keys
        folder. A mod whose key you have to ask for does not get installed."""
        self.assertIn('zip_members.append((f"{MOD_DIR}/keys/{bikey[0]}", bikey[1]))', BUILD)

    def test_the_loose_export_carries_the_signatures_too(self):
        """A PBO copied into a server's addons folder without its .bisign is exactly as
        unloadable as an unsigned one."""
        self.assertIn("for name, body in signatures:", BUILD)
        self.assertIn("(pbo_out / name).write_bytes(body)", BUILD)


def load_tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class KeySafetyTests(unittest.TestCase):
    def test_the_key_directory_defaults_outside_the_repository(self):
        self.assertIn('DEFAULT_KEY_DIR = os.environ.get("TLB_CARP_SIGNING_DIR", "E:/CARP-SIGNING")', BUILD)
        self.assertNotIn('DEFAULT_KEY_DIR = ROOT', BUILD)

    def test_the_key_name_carries_the_version(self):
        """REVERSED 2026-09-22, deliberately. This test used to assert the opposite, on the
        reasoning that a key admins reinstall every release is a key they stop installing.
        The owner chose versioned keys instead, to match the other TLB mods. The old cost
        did not go away -- it moved into the release notes, which have to say the key
        changed every single time."""
        build = load_tool("build_release")
        self.assertEqual(build.key_name_for("1.1.0.0"), "tlb_carp_v1_1_0")
        self.assertEqual(build.key_name_for("2.0.0.0"), "tlb_carp_v2_0_0")
        # The build number moves for reasons no admin cares about.
        self.assertEqual(build.key_name_for("1.1.0.7"), build.key_name_for("1.1.0.0"))
        # The ASSIGNMENT, not the word: the comment where the constant used to be
        # names it so anyone grepping for it lands on the reason it went.
        self.assertNotIn("DEFAULT_KEY_NAME =", BUILD)

    def test_a_release_cannot_be_signed_with_another_versions_key(self):
        """The derived name is only half of it. Passing --key-name by hand is how you would
        sign v1.2.0 with v1.1.0's key and not notice until a server started kicking
        people."""
        self.assertIn("does not carry version", BUILD)
        self.assertIn("if expected not in key_name:", BUILD)

    def test_git_refuses_key_material(self):
        # The source ZIP does not carry .gitignore, and the suite is re-run from a fresh
        # extraction of it as a release gate. Skipping there is correct rather than
        # lenient: the guarantee that matters in an extracted tree is that no key material
        # is present at all, which the next test asserts unconditionally.
        path = ROOT / ".gitignore"
        if not path.is_file():
            self.skipTest("no .gitignore (source ZIP extraction)")
        ignore = path.read_text(encoding="utf-8")
        self.assertIn("*.biprivatekey", ignore)
        self.assertIn("*.bikey", ignore)

    def test_no_private_key_exists_anywhere_in_the_tree(self):
        """THE ONE THAT MATTERS. A private key in the tree can be committed, can reach the
        source ZIP, and lets anyone sign a hostile PBO that passes as TLB CARP.

        The PUBLIC .bikey is deliberately NOT included here: build_release.py writes it
        into releases/pbo/v<version>/ and into the release ZIP, which is how an admin gets
        it, and publishing a public key is the entire point of one. The first version of
        this test asserted both and failed the moment signing worked."""
        self.assertEqual(list(ROOT.rglob("*.biprivatekey")), [])

    def test_git_tracks_no_key_material_of_either_kind(self):
        """Separate from the filesystem check and stricter about the public key: a .bikey
        belongs in a release, not in the history. Asked of git rather than of .gitignore,
        because .gitignore has no effect on a file already tracked."""
        import subprocess

        out = subprocess.run(["git", "-C", str(ROOT), "ls-files"],
                             capture_output=True, text=True)
        if out.returncode != 0:
            self.skipTest("not a git checkout")
        tracked = out.stdout.splitlines()
        self.assertEqual([f for f in tracked if f.endswith((".bikey", ".biprivatekey"))], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

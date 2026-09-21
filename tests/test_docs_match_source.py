from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WIKI = "https://github.com/TLB-MilSim/TLB-CARP/wiki"

# Everything a player or mission maker reads in this repository.
PLAYER_FACING = [ROOT / "README.md", ROOT / "docs" / "workshop" / "DESCRIPTION.bbcode"]
PLAYER_FACING += sorted((ROOT / "docs" / "guides").glob("*.md"))


class DocsMatchSourceTests(unittest.TestCase):
    def test_no_doc_describes_the_removed_degraded_tier(self):
        # The DEGRADED confidence tier, its five calibration warnings, the amber HUD block
        # and TLB_CARP_setting_allowDegradedAuto were all removed in v0.14.0 --
        # fn_solveRelative says so in as many words. The player-facing docs kept telling
        # people an uncalibrated airframe "reports DEGRADED and says so on the HUD" for
        # several releases after it had stopped doing anything of the sort, which is the
        # worst kind of wrong: specific, confident and checkable.
        #
        # If the tier ever comes back, delete this test as part of that change.
        solver = (ROOT / "addon" / "functions" / "solver" / "fn_solveRelative.sqf")
        self.assertIn(
            "THERE IS NO DEGRADED TIER", solver.read_text(encoding="utf-8"),
            "the solver no longer declares the tier removed -- if it was reinstated, this "
            "test and the documentation both need revisiting"
        )
        for doc in PLAYER_FACING:
            text = doc.read_text(encoding="utf-8")
            for term in ("DEGRADED", "UNCAL AIRFRAME", "allowDegradedAuto"):
                self.assertNotIn(
                    term, text,
                    f"{doc.relative_to(ROOT)} still describes {term}, which the mod removed "
                    f"in v0.14.0"
                )

    def test_the_guides_point_at_the_wiki(self):
        # The guides are deliberately stubs: the wiki is the one copy. They stay in the
        # repository so links made before the move still lead somewhere.
        guides = sorted((ROOT / "docs" / "guides").glob("*.md"))
        self.assertTrue(guides, "docs/guides is empty")
        for guide in guides:
            text = guide.read_text(encoding="utf-8")
            self.assertIn(WIKI, text, f"{guide.name} does not link to the wiki")
            self.assertNotIn(
                "](docs/guides/", text,
                f"{guide.name} links into docs/guides, which is no longer where the "
                f"documentation lives"
            )

    def test_readme_sends_readers_to_the_wiki_not_to_the_stubs(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(WIKI, text)
        # Markdown links AND raw <a href>, because the README's header row is HTML and the
        # first version of this test checked only the former -- which let five stale links
        # through at the top of the page.
        stub_links = re.findall(r"docs/guides/[A-Z_]+\.md", text)
        self.assertEqual(
            [], stub_links,
            "README still links to the guide stubs instead of the wiki pages they point at"
        )

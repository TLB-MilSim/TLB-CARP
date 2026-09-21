from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DESCRIPTION = ROOT / "docs" / "workshop" / "DESCRIPTION.bbcode"
BANNERS = ROOT / "docs" / "workshop" / "banners"

# The repository the published Workshop page fetches its banners from. Renaming the
# repository or moving docs/workshop/banners/ breaks a page that is already live, and
# nothing about that failure is visible from here -- see the test below.
REPO_URL = "https://raw.githubusercontent.com/TLB-MilSim/TLB-CARP/main/docs/workshop/banners/"

# Steam rejects a Workshop description longer than this. It does not truncate and it
# does not explain: the save simply does not take, the page keeps whatever it had
# before, and the obvious reading from the author's chair is "my images are broken".
STEAM_DESCRIPTION_LIMIT = 8000


class WorkshopDescriptionTests(unittest.TestCase):
    def setUp(self):
        self.text = DESCRIPTION.read_text(encoding="utf-8")

    def test_fits_in_steams_description_limit(self):
        # Measured in characters, not bytes -- the em dashes and degree signs in the
        # page are two or three bytes each and Steam does not charge for that.
        self.assertLessEqual(
            len(self.text), STEAM_DESCRIPTION_LIMIT,
            f"{len(self.text)} characters, {len(self.text) - STEAM_DESCRIPTION_LIMIT} over "
            f"Steam's {STEAM_DESCRIPTION_LIMIT}. Shorten the prose rather than dropping a "
            f"banner: Steam refuses the whole save, so nothing you paste will land."
        )

    def test_a_pasted_copy_still_fits_if_newlines_become_crlf(self):
        # Pasting into a browser textarea can turn every LF into CRLF, which Steam then
        # counts. The margin has to survive that or the limit is only nominally met.
        pasted = len(self.text) + self.text.count("\n")
        self.assertLessEqual(pasted, STEAM_DESCRIPTION_LIMIT, f"{pasted} characters as CRLF")

    def test_every_banner_is_linked_from_this_repository_and_exists(self):
        urls = re.findall(r"\[img\]([^\[]+)\[/img\]", self.text)
        self.assertTrue(urls, "the description has no banners at all")
        for url in urls:
            # A URL naming a repository that has since been renamed returns 404 and the
            # page shows broken images, which is how TLB-CARP-System's links failed.
            self.assertTrue(
                url.startswith(REPO_URL),
                f"{url} does not point at {REPO_URL}"
            )
            banner = BANNERS / url[len(REPO_URL):]
            self.assertTrue(banner.is_file(), f"{url} has no file at {banner}")

    def test_no_unrendered_placeholder_survives(self):
        # render_workshop.py refuses to write one of these through; the source page must
        # not carry one either, because Steam would render the braces literally.
        self.assertEqual([], re.findall(r"\{\{[a-z0-9-]+\}\}", self.text))

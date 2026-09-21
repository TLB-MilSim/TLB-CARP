# -*- coding: utf-8 -*-
"""Renders the Steam Workshop description with real banner URLs.

    python tools/render_workshop.py --urls build/banner-urls.txt

docs/workshop/DESCRIPTION.bbcode links its banners straight out of the public repository,
so it is paste-ready as it stands. This is for hosting them somewhere else instead: swap
the links back to {{banner-name}} placeholders, then pass a urls file of one `name=url`
line per banner, where the name is the banner's filename without `.png`:

    what-it-is=https://steamuserimages-a.akamaihd.net/ugc/...

Writes build/workshop/DESCRIPTION.txt, ready to paste into the Workshop editor. It refuses
to write a page with a placeholder left in it, because Steam would render the braces.

    python tools/render_workshop.py --no-banners

renders the same page with [h1] headings in place of the banner images, which is what to
paste when the banners are not hosted anywhere yet. The page reads correctly either way;
the banners are decoration, and a description that cannot be published until twelve images
are uploaded somewhere is a description that does not get published.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "workshop" / "DESCRIPTION.bbcode"
BANNERS = ROOT / "docs" / "workshop" / "banners"
OUT = ROOT / "build" / "workshop" / "DESCRIPTION.txt"

# Written out rather than derived from the slug: "the-run-in" title-cases to "The Run In",
# and a heading that reads like a filename undoes the point of having one.
HEADINGS = {
    "what-it-is": "What it is",
    "what-you-need": "What you need",
    "getting-started": "Getting started",
    "the-run-in": "The run-in",
    "auto-drop": "Auto drop",
    "cargo": "Cargo",
    "guided-cargo": "Guided cargo",
    "jump-run": "The jump run",
    "crew": "Crew",
    "accuracy": "Accuracy",
    "settings": "Settings",
    "support": "Support",
}


def read_urls(path: Path) -> dict[str, str]:
    urls = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise SystemExit(f"{path}:{number}: expected name=url, got {line!r}")
        name, url = line.split("=", 1)
        urls[name.strip()] = url.strip()
    return urls


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--urls", type=Path, help="file of name=url lines")
    ap.add_argument("--no-banners", action="store_true",
                    help="render [h1] headings instead of the banner images, for when they "
                         "are not hosted yet")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    text = SOURCE.read_text(encoding="utf-8")

    if args.no_banners:
        names = sorted(set(re.findall(r"\{\{([a-z0-9-]+)\}\}", text)))
        unknown = [n for n in names if n not in HEADINGS]
        if unknown:
            raise SystemExit("no heading for: " + ", ".join(unknown))
        for name in names:
            # The whole [img] tag, not just the placeholder -- leaving [img][/img] round a
            # heading gives Steam an empty image tag to render.
            text = text.replace(f"[img]{{{{{name}}}}}[/img]", f"[h1]{HEADINGS[name]}[/h1]")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out.relative_to(ROOT)} "
              f"({len(names)} headings, no images, {len(text)} characters)")
        return 0

    if args.urls is None:
        raise SystemExit("pass --urls, or --no-banners to render headings instead")
    urls = read_urls(args.urls)
    wanted = sorted(set(re.findall(r"\{\{([a-z0-9-]+)\}\}", text)))

    missing = [name for name in wanted if name not in urls]
    if missing:
        raise SystemExit("no URL for: " + ", ".join(missing))

    unused = sorted(set(urls) - set(wanted))
    for name in unused:
        print(f"note: {name} is in the urls file but not in the description")

    for name in wanted:
        banner = BANNERS / f"{name}.png"
        if not banner.is_file():
            print(f"note: {banner.relative_to(ROOT)} does not exist; the URL had better be right")
        text = text.replace("{{" + name + "}}", urls[name])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"wrote {args.out.relative_to(ROOT)} ({len(wanted)} banners, {len(text)} characters)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

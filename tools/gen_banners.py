# -*- coding: utf-8 -*-
"""Section banners and the item preview for the Steam Workshop page.

    python tools/gen_banners.py

Steam's description renders one wide column, so a page of plain text reads as a wall.
These banners head each section: 1000x200 PNGs in the mod's colours -- the logo's camo
grey, olive and orange -- with the logo mark on the left and the section title set in
condensed caps. docs/workshop/DESCRIPTION.bbcode names each one where it belongs.

Also writes workshop-preview.png (1280x720), the item's preview image.

Needs Pillow. Output goes to docs/workshop/banners/ and docs/workshop/. The camo shards
are seeded, so the same script always draws the same banners.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "workshop" / "banners"
PREVIEW = ROOT / "docs" / "workshop" / "workshop-preview.png"
LOGO = ROOT / "tools" / "logo_source.png"
SHOT = ROOT / "docs" / "images" / "screenshots" / "hud-run-in.png"

W, H = 1000, 200
INK = (232, 236, 230, 255)
MUTED = (150, 158, 146, 255)
ORANGE = (243, 126, 28, 255)
OLIVE = (108, 124, 72, 255)
BASE = (26, 28, 25, 255)

SECTIONS = [
    ("what-it-is", "WHAT IT IS", "A drop computer that reads the aircraft you are actually flying"),
    ("what-you-need", "WHAT YOU NEED", "CBA and ACE. The USAF mod is supported, not required"),
    ("getting-started", "GETTING STARTED", "Set a drop up in six steps"),
    ("cargo", "CARGO", "Load it, stack it, drop it back to front"),
    ("the-run-in", "THE RUN-IN", "Lock the track you are flying, then fly the needle"),
    ("auto-drop", "AUTOPILOT & AUTO DROP", "It flies the line, and refuses a pass it cannot make"),
    ("guided-cargo", "GUIDED CARGO", "The canopy steers itself onto the drop zone"),
    ("jump-run", "JUMP RUN", "A computed exit point, a countdown and the jumplight"),
    ("crew", "CREW", "One CARP per aircraft, shared by everyone with a computer"),
    ("settings", "SETTINGS", "Addon Options, server-forced where it matters"),
    ("accuracy", "ACCURACY", "Measured on flown drops, not estimated"),
    ("support", "SUPPORT", "Bugs, ideas and the guides"),
]


def font(names, size):
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


TITLE = ("bahnschrift.ttf", "arialbd.ttf")
BODY = ("bahnschrift.ttf", "arial.ttf")


def camo(size, seed):
    """The logo's faceted grey camo, as a background."""
    rng = random.Random(seed)
    img = Image.new("RGBA", size, BASE)
    d = ImageDraw.Draw(img)
    tones = [(34, 36, 32), (44, 47, 41), (54, 58, 50), (30, 32, 28), (62, 66, 56)]
    for _ in range(46):
        cx, cy = rng.uniform(0, size[0]), rng.uniform(0, size[1])
        r = rng.uniform(40, 190)
        pts = []
        for i in range(rng.randint(3, 5)):
            a = rng.uniform(0, math.tau) + i * math.tau / 4
            k = rng.uniform(0.45, 1.0)
            pts.append((cx + r * k * math.cos(a), cy + r * k * math.sin(a)))
        d.polygon(pts, fill=tuple(rng.choice(tones)) + (rng.randint(120, 210),))
    shade = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(shade).rectangle([0, 0, size[0], size[1]], fill=(0, 0, 0, 90))
    return Image.alpha_composite(img.filter(ImageFilter.GaussianBlur(0.6)), shade)


def logo_mark(px):
    src = Image.open(LOGO).convert("RGBA")
    return src.resize((px, px), Image.LANCZOS)


def banner(title, subtitle, seed):
    img = camo((W, H), seed)
    d = ImageDraw.Draw(img)

    # Darker plate behind the text, so the camo never fights the words.
    plate = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(plate).rectangle([170, 0, W, H], fill=(14, 16, 14, 150))
    img = Image.alpha_composite(img, plate.filter(ImageFilter.GaussianBlur(18)))
    d = ImageDraw.Draw(img)

    img.alpha_composite(logo_mark(150), (14, 25))
    d.line([(178, 34), (178, H - 34)], fill=ORANGE, width=4)

    d.text((208, 52), title, font=font(TITLE, 62), fill=INK)
    d.text((211, 128), subtitle, font=font(BODY, 27), fill=MUTED)

    d.rectangle([0, H - 6, W, H], fill=(18, 20, 17, 255))
    for x in range(W):
        k = x / W
        d.line([(x, H - 6), (x, H - 2)], fill=(
            int(ORANGE[0] * (1 - k) + OLIVE[0] * k),
            int(ORANGE[1] * (1 - k) + OLIVE[1] * k),
            int(ORANGE[2] * (1 - k) + OLIVE[2] * k),
            255,
        ))
    d.text((W - 150, 22), "TLB CARP", font=font(BODY, 22), fill=(120, 128, 116, 255))
    return img


def preview():
    size = (1280, 720)
    img = camo(size, 99)

    # The HUD shot sits behind everything, faded, with a dark veil over the whole
    # frame so the text never has to compete with it.
    shot = Image.open(SHOT).convert("RGBA")
    shot = shot.resize((int(shot.width * 720 / shot.height), 720), Image.LANCZOS)
    shot = shot.crop((max(0, shot.width - size[0]), 0, shot.width, 720))
    shot.putalpha(Image.new("L", shot.size, 90))
    img.alpha_composite(shot, (size[0] - shot.width, 0))
    img = Image.alpha_composite(img, Image.new("RGBA", size, (10, 12, 10, 175)))

    veil = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(veil).rectangle([0, 0, 900, size[1]], fill=(10, 12, 10, 180))
    img = Image.alpha_composite(img, veil.filter(ImageFilter.GaussianBlur(60)))
    d = ImageDraw.Draw(img)

    img.alpha_composite(logo_mark(300), (56, 60))
    d.text((392, 116), "TLB CARP", font=font(TITLE, 104), fill=INK)
    d.text((398, 232), "COMPUTED AIR RELEASE POINT", font=font(BODY, 36), fill=ORANGE)
    d.line([(396, 296), (1208, 296)], fill=(90, 98, 86, 255), width=3)

    lines = [
        "Live release point, solved from the aircraft you are flying",
        "Autopilot flies the run-in; auto drop refuses a bad pass",
        "Guided canopies, jump runs, one CARP for the whole crew",
    ]
    for i, line in enumerate(lines):
        d.text((398, 330 + i * 52), line, font=font(BODY, 31), fill=INK)

    d.text((398, 556), "ARMA 3  |  CBA + ACE  |  TLB MILSIM", font=font(BODY, 28), fill=MUTED)
    return img


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for i, (name, title, subtitle) in enumerate(SECTIONS):
        path = OUT / f"{name}.png"
        banner(title, subtitle, 11 + i * 7).convert("RGB").save(path, quality=95)
        print(f"  {path.relative_to(ROOT)}")
    preview().convert("RGB").save(PREVIEW, quality=95)
    print(f"  {PREVIEW.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

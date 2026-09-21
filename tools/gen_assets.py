# -*- coding: utf-8 -*-
"""Generates the mod's images, then converts the in-game ones to PAA.

    python tools/gen_assets.py

- The CARP Computer's inventory icon (items/data/tlb_carp_computer_ca.paa): a rugged
  aircrew tablet in olive polymer with rubber corner bumpers, rendered with lighting,
  surface grain and a slight three-quarter tilt so it reads as a piece of equipment
  rather than a drawing. Its screen shows what CARP computes: the aircraft on its run-in
  over terrain imagery, the release point on that line, and the canopy drifting onto the
  drop zone. Drawn at 4x and downsampled.
- The mod logo, which is artwork (tools/logo_source.png) and is only scaled here: 512 px
  for the README, 256 and 64 px for the launcher (items/data/logo_ca.paa and
  logo_small_ca.paa, referenced from packaging/mod.cpp).

Needs Pillow. Every noise texture is seeded, so the same script always draws the same
icon. PNGs for the README go to docs/images/; intermediate PNGs go to build/icons/
(git-ignored). PAAs are made with Arma 3 Tools' ImageToPAA, which only accepts
power-of-two sizes; without Arma 3 Tools the PNGs are left for converting by hand.
"""
from __future__ import annotations

import math
import random
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
PNG_DIR = ROOT / "build" / "icons"
PAA_DIR = ROOT / "items" / "data"
DOCS = ROOT / "docs" / "images"
ICON = "tlb_carp_computer_ca"
SIZE = 256
SS = 4
W = SIZE * SS

# The device, laid out flat on the 4x canvas before it is tilted.
BODY = (104, 196, 920, 836)
BEZEL = (160, 248, 864, 742)
SCREEN = (178, 266, 846, 724)
# Where the body's corners land once tilted: a slight turn and a little perspective,
# with the far (right) edge shorter and the top edge narrower.
TILTED = [(95, 215), (923, 165), (955, 833), (68, 887)]


# --- drawing helpers ----------------------------------------------------------

def font(names: tuple[str, ...], size: int):
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def inset(box, d):
    return (box[0] + d, box[1] + d, box[2] - d, box[3] - d)


def shifted(box, dx, dy):
    return (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)


def rmask(size, box, radius) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=radius, fill=255)
    return mask


def scaled(mask: Image.Image, factor: float) -> Image.Image:
    return mask.point(lambda v: int(v * factor))


def layer(size, fill, mask: Image.Image) -> Image.Image:
    """fill (a colour or an RGBA image) cut to mask."""
    src = fill.copy() if isinstance(fill, Image.Image) else Image.new("RGBA", size, fill)
    src.putalpha(ImageChops.multiply(src.getchannel("A"), mask))
    return src


def vgradient(size, top, bottom) -> Image.Image:
    ramp = Image.linear_gradient("L").resize(size)
    return Image.composite(Image.new("RGBA", size, bottom), Image.new("RGBA", size, top), ramp)


def hgradient(size, left, right) -> Image.Image:
    ramp = Image.linear_gradient("L").rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT).resize(size)
    return Image.composite(Image.new("RGBA", size, right), Image.new("RGBA", size, left), ramp)


def light_from_top_left(size) -> Image.Image:
    """255 where the light falls, 0 on the far side."""
    return Image.frombytes("L", (2, 2), bytes([255, 150, 150, 0])).resize(size, Image.BILINEAR)


def noise(size, seed) -> Image.Image:
    rng = random.Random(seed)
    return Image.frombytes("L", size, rng.randbytes(size[0] * size[1]))


def fractal(size, seed, octaves=6, base=3) -> Image.Image:
    acc = Image.new("L", size, 0)
    weights = [0.5 ** o for o in range(octaves)]
    total = sum(weights)
    for o, weight in enumerate(weights):
        cells_x = base * 2 ** o
        cells_y = max(2, cells_x * size[1] // size[0])
        octave = noise((cells_x, cells_y), seed + o).resize(size, Image.BICUBIC)
        acc = ImageChops.add(acc, octave.point(lambda v, k=weight / total: int(v * k)))
    return ImageOps.autocontrast(acc)


def grain(img: Image.Image, seed, strength: float) -> Image.Image:
    """Fine surface texture, overlaid so it lightens and darkens around the base tone."""
    n = noise(img.size, seed).point(lambda v: int(128 + (v - 128) * strength))
    rgb = ImageChops.overlay(img.convert("RGB"), Image.merge("RGB", (n, n, n)))
    rgb.putalpha(img.getchannel("A"))
    return rgb


def perspective_coeffs(src, dst):
    """PIL's PERSPECTIVE data mapping the output quad dst back onto the input quad src."""
    rows = []
    for (xs, ys), (xd, yd) in zip(src, dst):
        rows.append([xd, yd, 1, 0, 0, 0, -xs * xd, -xs * yd, xs])
        rows.append([0, 0, 0, xd, yd, 1, -ys * xd, -ys * yd, ys])
    for c in range(8):
        pivot = max(range(c, 8), key=lambda r: abs(rows[r][c]))
        rows[c], rows[pivot] = rows[pivot], rows[c]
        for r in range(8):
            if r != c:
                f = rows[r][c] / rows[c][c]
                rows[r] = [a - f * b for a, b in zip(rows[r], rows[c])]
    return [rows[i][8] / rows[i][i] for i in range(8)]


# --- the display ------------------------------------------------------------------

TRACK = (255, 178, 54)
DZ_GREEN = (110, 255, 160)
DRIFT = (120, 225, 255)
TEXT = (176, 236, 196)
PLANE = [
    (0, -1.0), (0.09, -0.78), (0.09, -0.28), (0.95, 0.12), (0.95, 0.26), (0.09, 0.06),
    (0.07, 0.62), (0.36, 0.84), (0.36, 0.96), (0, 0.88), (-0.36, 0.96), (-0.36, 0.84),
    (-0.07, 0.62), (-0.09, 0.06), (-0.95, 0.26), (-0.95, 0.12), (-0.09, -0.28), (-0.09, -0.78),
]


def terrain(size) -> Image.Image:
    """Satellite-style ground: woodland and farmland tones, field patches, a river, a road."""
    sw, sh = size
    ground = ImageOps.colorize(fractal(size, 31, octaves=7, base=5), (24, 40, 28), (172, 158, 116), mid=(80, 92, 54), midpoint=118)
    ground = ground.filter(ImageFilter.UnsharpMask(radius=3, percent=140, threshold=0)).convert("RGBA")

    fields = Image.new("RGBA", size, (0, 0, 0, 0))
    f = ImageDraw.Draw(fields)
    rng = random.Random(5)
    for _ in range(16):
        cx, cy = rng.uniform(0, sw), rng.uniform(40, sh)
        half_w, half_h = rng.uniform(20, 58), rng.uniform(14, 36)
        turn = math.radians(rng.uniform(-35, 35))
        corners = ((-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h))
        f.polygon(
            [(cx + dx * math.cos(turn) - dy * math.sin(turn), cy + dx * math.sin(turn) + dy * math.cos(turn)) for dx, dy in corners],
            fill=rng.choice([(122, 120, 72), (70, 94, 50), (156, 142, 100), (98, 106, 62)]) + (rng.randint(40, 76),),
        )
    ground = Image.alpha_composite(ground, fields.filter(ImageFilter.GaussianBlur(1.2)))
    ground = ImageEnhance.Brightness(grain(ground, 41, 0.12)).enhance(0.88)

    g = ImageDraw.Draw(ground)
    river = [(x, 360 - 70 * x / sw + 16 * math.sin(x / 41)) for x in range(-10, sw + 12, 6)]
    g.line(river, fill=(18, 34, 44, 255), width=16, joint="curve")
    g.line(river, fill=(46, 84, 108, 255), width=9, joint="curve")
    road = [(150 + 430 * k + 34 * math.sin(k * 8), sh - sh * k) for k in (i / 60 for i in range(61))]
    g.line(road, fill=(34, 34, 28, 255), width=9, joint="curve")
    g.line(road, fill=(158, 150, 126, 255), width=4, joint="curve")
    return ground


def display() -> Image.Image:
    """A moving-map page: terrain imagery with CARP's overlay drawn over it."""
    sw, sh = SCREEN[2] - SCREEN[0], SCREEN[3] - SCREEN[1]
    size = (sw, sh)

    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    o = ImageDraw.Draw(overlay)
    for x in range(0, sw, 76):
        o.line([(x, 0), (x, sh)], fill=(255, 255, 255, 30), width=1)
    for y in range(38, sh, 76):
        o.line([(0, y), (sw, y)], fill=(255, 255, 255, 30), width=1)

    a, b = (56, 420), (650, 118)
    rp = (a[0] + (b[0] - a[0]) * 0.47, a[1] + (b[1] - a[1]) * 0.47)
    dz = (462, 292)

    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).line([a, rp], fill=TRACK + (150,), width=16)
    overlay = Image.alpha_composite(overlay, glow.filter(ImageFilter.GaussianBlur(7)))
    o = ImageDraw.Draw(overlay)
    o.line([a, rp], fill=TRACK + (255,), width=5)
    length = math.hypot(b[0] - rp[0], b[1] - rp[1])
    ux, uy = (b[0] - rp[0]) / length, (b[1] - rp[1]) / length
    d = 0.0
    while d < length:
        e = min(d + 16, length)
        o.line([(rp[0] + ux * d, rp[1] + uy * d), (rp[0] + ux * e, rp[1] + uy * e)], fill=TRACK + (235,), width=4)
        d = e + 11

    ctrl = (rp[0] + 120, rp[1] - 6)
    curve = []
    for i in range(25):
        k = i / 24
        curve.append((
            (1 - k) ** 2 * rp[0] + 2 * (1 - k) * k * ctrl[0] + k * k * dz[0],
            (1 - k) ** 2 * rp[1] + 2 * (1 - k) * k * ctrl[1] + k * k * dz[1],
        ))
    for i in range(0, len(curve) - 1, 2):
        o.line([curve[i], curve[i + 1]], fill=DRIFT + (240,), width=3)

    for r, width in ((30, 3), (12, 3)):
        o.ellipse([dz[0] - r, dz[1] - r, dz[0] + r, dz[1] + r], outline=DZ_GREEN + (255,), width=width)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        o.line([(dz[0] + dx * 18, dz[1] + dy * 18), (dz[0] + dx * 40, dz[1] + dy * 40)], fill=DZ_GREEN + (255,), width=3)

    s = 10
    o.polygon([(rp[0], rp[1] - s), (rp[0] + s, rp[1]), (rp[0], rp[1] + s), (rp[0] - s, rp[1])], fill=TRACK + (255,), outline=(40, 26, 6, 255))

    cx, cy = curve[12]
    o.pieslice([cx - 13, cy - 21, cx + 13, cy + 5], 180, 360, fill=(236, 240, 232, 255))
    for dx in (-12, 0, 12):
        o.line([(cx + dx, cy - 8), (cx, cy + 8)], fill=(220, 226, 218, 255), width=1)
    o.rectangle([cx - 4, cy + 7, cx + 4, cy + 13], fill=(206, 176, 118, 255))

    heading = math.atan2(b[0] - a[0], -(b[1] - a[1]))
    px, py = a[0] + (b[0] - a[0]) * 0.18, a[1] + (b[1] - a[1]) * 0.18
    plane = [(px + 22 * (x * math.cos(heading) - y * math.sin(heading)), py + 22 * (x * math.sin(heading) + y * math.cos(heading))) for x, y in PLANE]
    o.polygon(plane, fill=(244, 246, 240, 255), outline=(16, 22, 20, 255))

    ui = font(("bahnschrift.ttf", "arialbd.ttf"), 17)
    mono = font(("consola.ttf", "cour.ttf"), 15)
    bold = font(("bahnschrift.ttf", "arialbd.ttf"), 23)

    o.text((rp[0] + 14, rp[1] + 8), "RP", font=ui, fill=TRACK + (255,))
    o.text((dz[0] + 34, dz[1] + 16), "DZ ALPHA", font=ui, fill=DZ_GREEN + (255,))

    o.rectangle([0, 0, sw, 34], fill=(6, 14, 12, 215))
    o.line([(0, 34), (sw, 34)], fill=DZ_GREEN + (140,), width=1)
    o.text((12, 4), "CARP", font=bold, fill=DZ_GREEN + (255,))
    o.text((96, 9), "RUN-IN 118    GS 245 KT    ALT 3000 FT    RP 1.2 KM", font=mono, fill=TEXT + (255,))
    o.rectangle([sw - 52, 10, sw - 16, 26], outline=TEXT + (255,), width=2)
    o.rectangle([sw - 16, 14, sw - 12, 22], fill=TEXT + (255,))
    o.rectangle([sw - 49, 13, sw - 26, 23], fill=DZ_GREEN + (255,))
    for i, h in enumerate((5, 9, 13)):
        o.rectangle([sw - 82 + i * 7, 26 - h, sw - 78 + i * 7, 26], fill=TEXT + (255,))

    o.rounded_rectangle([12, 48, 196, 164], radius=6, fill=(4, 12, 10, 185), outline=DZ_GREEN + (110,), width=1)
    for i, row in enumerate(("WIND  270/12 KT", "XTK   +4 M", "DRIFT 38 M", "TOT   14:32:08")):
        o.text((24, 58 + i * 25), row, font=mono, fill=TEXT + (255,))

    o.rounded_rectangle([12, sh - 44, 196, sh - 14], radius=6, fill=(8, 40, 24, 200), outline=DZ_GREEN + (200,), width=2)
    o.text((26, sh - 40), "GUIDANCE ARMED", font=ui, fill=DZ_GREEN + (255,))

    o.line([(sw - 150, sh - 22), (sw - 30, sh - 22)], fill=TEXT + (255,), width=3)
    for x in (sw - 150, sw - 30):
        o.line([(x, sh - 30), (x, sh - 14)], fill=TEXT + (255,), width=3)
    o.text((sw - 106, sh - 48), "1 KM", font=mono, fill=TEXT + (255,))

    screen = Image.alpha_composite(terrain(size), overlay)

    # Glass: darker toward the edges, and a soft reflection across the upper left.
    vignette = Image.radial_gradient("L").resize(size).point(lambda v: int(min(255, v) * 0.5))
    screen = Image.alpha_composite(screen, layer(size, (0, 0, 0, 255), vignette))
    shine = Image.new("L", size, 0)
    ImageDraw.Draw(shine).polygon([(0, 0), (int(sw * 0.62), 0), (int(sw * 0.3), sh), (0, sh)], fill=54)
    screen = Image.alpha_composite(screen, layer(size, (255, 255, 255, 255), shine.filter(ImageFilter.GaussianBlur(40))))
    return screen


# --- the device -------------------------------------------------------------------

def device() -> Image.Image:
    size = (W, W)
    light = light_from_top_left(size)
    img = Image.new("RGBA", size, (0, 0, 0, 0))

    def add(fill, mask):
        nonlocal img
        img = Image.alpha_composite(img, layer(size, fill, mask))

    # Thickness: the lower and right edges of the case, seen from slightly above.
    add(vgradient(size, (30, 31, 27, 255), (10, 10, 9, 255)), rmask(size, shifted(BODY, 10, 28), 64))

    # Stub antenna on the top edge.
    add(hgradient(size, (74, 75, 68, 255), (18, 18, 16, 255)), rmask(size, (704, 138, 750, 214), 16))
    d = ImageDraw.Draw(img)
    for y in range(152, 206, 12):
        d.line([(708, y), (746, y)], fill=(12, 12, 11, 200), width=3)

    # Olive polymer body with a faint mottling and grain.
    body = rmask(size, BODY, 64)
    polymer = vgradient(size, (78, 80, 64, 255), (40, 42, 34, 255))
    mottle = fractal(size, 7, octaves=4, base=6).point(lambda v: int(128 + (v - 128) * 0.35))
    polymer = ImageChops.overlay(polymer.convert("RGB"), Image.merge("RGB", (mottle, mottle, mottle))).convert("RGBA")
    add(grain(polymer, 11, 0.16), body)

    # Moulded edge: lit along the top and left, falling into shadow bottom right.
    ring = ImageChops.subtract(body, rmask(size, inset(BODY, 7), 58))
    add((236, 238, 220, 255), ImageChops.multiply(ring, scaled(light, 0.62)))
    add((0, 0, 0, 255), ImageChops.multiply(ring, scaled(ImageOps.invert(light), 0.7)))
    bevel = ImageChops.subtract(rmask(size, inset(BODY, 7), 58), rmask(size, inset(BODY, 20), 50))
    add((210, 214, 190, 255), ImageChops.multiply(bevel.filter(ImageFilter.GaussianBlur(4)), scaled(light, 0.16)))

    # Grip ridges on the right-hand frame.
    d = ImageDraw.Draw(img)
    for y in range(392, 660, 34):
        d.rounded_rectangle([874, y, 904, y + 12], radius=6, fill=(26, 27, 23, 255))
        d.line([(876, y + 13), (902, y + 13)], fill=(104, 106, 90, 150), width=2)

    # Recessed bezel around the glass.
    bezel = rmask(size, BEZEL, 40)
    add(vgradient(size, (16, 17, 15, 255), (30, 31, 28, 255)), bezel)
    add((0, 0, 0, 255), scaled(ImageChops.subtract(bezel, rmask(size, shifted(BEZEL, 7, 9), 40)).filter(ImageFilter.GaussianBlur(3)), 0.7))
    add((150, 152, 136, 255), scaled(ImageChops.subtract(bezel, rmask(size, shifted(BEZEL, -4, -5), 40)), 0.35))
    add((70, 190, 130, 255), ImageChops.multiply(scaled(rmask(size, inset(SCREEN, -6), 12).filter(ImageFilter.GaussianBlur(16)), 0.22), bezel))

    # Rubber corner bumpers, kept clear of the bezel.
    guard = rmask(size, inset(BEZEL, -16), 48)
    for x0, y0 in ((88, 180), (760, 180), (88, 676), (760, 676)):
        corner = (x0, y0, x0 + 176, y0 + 176)
        bumper = ImageChops.subtract(rmask(size, corner, 60), guard)
        add(grain(vgradient(size, (50, 51, 46, 255), (20, 20, 18, 255)), 23 + x0 + y0, 0.1), bumper)
        edge = ImageChops.subtract(bumper, rmask(size, inset(corner, 5), 55))
        add((150, 152, 140, 255), ImageChops.multiply(edge, scaled(light, 0.45)))
        add((0, 0, 0, 255), ImageChops.multiply(edge, scaled(ImageOps.invert(light), 0.8)))
        d = ImageDraw.Draw(img)
        top = y0 < 400
        for i in range(3):
            ry = (y0 + 24 + i * 16) if top else (y0 + 152 - i * 16)
            d.line([(x0 + 40, ry), (x0 + 136, ry)], fill=(12, 12, 11, 170), width=4)
            d.line([(x0 + 40, ry + 3), (x0 + 136, ry + 3)], fill=(84, 86, 78, 90), width=2)

    # Screws on the frame.
    for sx, sy in ((302, 222), (722, 222), (302, 790), (722, 790)):
        ImageDraw.Draw(img).ellipse([sx - 15, sy - 15, sx + 15, sy + 15], fill=(18, 18, 16, 255))
        head = Image.radial_gradient("L").resize((24, 24)).point(lambda v: 255 - min(255, v))
        cap = Image.new("RGBA", (24, 24), (158, 158, 148, 255))
        cap.putalpha(ImageChops.multiply(head, rmask((24, 24), (0, 0, 23, 23), 12)))
        base = Image.new("RGBA", (24, 24), (62, 62, 58, 255))
        base.putalpha(rmask((24, 24), (0, 0, 23, 23), 12))
        img.alpha_composite(Image.alpha_composite(base, cap), (sx - 12, sy - 12))
        d = ImageDraw.Draw(img)
        d.line([(sx - 6, sy - 6), (sx + 6, sy + 6)], fill=(20, 20, 18, 255), width=3)
        d.line([(sx - 6, sy + 6), (sx + 6, sy - 6)], fill=(20, 20, 18, 255), width=3)

    # Moulded label on the top frame, between the screws.
    label = font(("bahnschrift.ttf", "arialbd.ttf"), 26)
    left = 512 - d.textlength("TLB CARP", font=label) / 2
    d.text((left + 2, 209), "TLB CARP", font=label, fill=(16, 17, 14, 255))
    d.text((left, 207), "TLB CARP", font=label, fill=(110, 112, 96, 255))

    # Hardware keys below the screen, and the status LED.
    for cx in (416, 480, 544, 608):
        add((0, 0, 0, 255), scaled(rmask(size, (cx - 25, 766, cx + 29, 802), 10).filter(ImageFilter.GaussianBlur(3)), 0.6))
        add(vgradient(size, (66, 67, 60, 255), (28, 29, 26, 255)), rmask(size, (cx - 26, 760, cx + 26, 794), 10))
        ImageDraw.Draw(img).line([(cx - 16, 763), (cx + 16, 763)], fill=(128, 130, 118, 170), width=2)
    glow = Image.new("L", size, 0)
    ImageDraw.Draw(glow).ellipse([662, 764, 692, 794], fill=200)
    add((90, 255, 140, 255), glow.filter(ImageFilter.GaussianBlur(9)))
    ImageDraw.Draw(img).ellipse([670, 772, 684, 786], fill=(190, 255, 205, 255))

    # The glass itself, with a thin dark gasket.
    img = Image.alpha_composite(img, layer(size, (4, 5, 5, 255), rmask(size, inset(SCREEN, -4), 14)))
    screen = display()
    img.alpha_composite(layer(screen.size, screen, rmask(screen.size, (0, 0, screen.width - 1, screen.height - 1), 10)), (SCREEN[0], SCREEN[1]))
    return img


def render(flat: Image.Image, size: int) -> Image.Image:
    src = [(BODY[0], BODY[1]), (BODY[2], BODY[1]), (BODY[2], BODY[3]), (BODY[0], BODY[3])]
    tilted = flat.transform((W, W), Image.PERSPECTIVE, perspective_coeffs(src, TILTED), Image.BICUBIC)

    shadow = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    soft = Image.new("RGBA", (W, W), (0, 0, 0, 255))
    soft.putalpha(tilted.getchannel("A").filter(ImageFilter.GaussianBlur(24)).point(lambda v: int(v * 0.55)))
    shadow.alpha_composite(soft, (10, 26))
    out = Image.alpha_composite(shadow, tilted).resize((size, size), Image.LANCZOS)

    rgb = out.convert("RGB").filter(ImageFilter.UnsharpMask(radius=0.8, percent=45, threshold=2))
    rgb.putalpha(out.getchannel("A"))
    return rgb


def icon() -> list[str]:
    flat = device()
    render(flat, SIZE).save(PNG_DIR / f"{ICON}.png")
    render(flat, 512).save(DOCS / "carp-computer.png")
    return [ICON]


# --- Mod logo ----------------------------------------------------------------

def logo() -> list[str]:
    """The mod logo is artwork (tools/logo_source.png), only scaled here to the sizes
    the README and the launcher use."""
    source = ROOT / "tools" / "logo_source.png"
    if not source.is_file():
        print("no tools/logo_source.png -- logo skipped")
        return []
    src = Image.open(source).convert("RGBA")
    side = max(src.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(src, ((side - src.width) // 2, (side - src.height) // 2))
    square.resize((512, 512), Image.LANCZOS).save(DOCS / "logo.png")
    square.resize((256, 256), Image.LANCZOS).save(PNG_DIR / "logo_ca.png")
    square.resize((64, 64), Image.LANCZOS).save(PNG_DIR / "logo_small_ca.png")
    return ["logo_ca", "logo_small_ca"]


# --- PAA conversion ----------------------------------------------------------

def image_to_paa() -> str | None:
    candidates = []
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Bohemia Interactive\ImageToPAA") as key:
            candidates.append(str(Path(winreg.QueryValueEx(key, "path")[0]) / "ImageToPAA.exe"))
    except (ImportError, OSError):
        pass
    candidates.append(r"C:\Program Files (x86)\Steam\steamapps\common\Arma 3 Tools\ImageToPAA\ImageToPAA.exe")
    found = next((c for c in candidates if Path(c).is_file()), None)
    return found or shutil.which("ImageToPAA")


def convert(names: list[str]) -> int:
    tool = image_to_paa()
    if tool is None:
        print("ImageToPAA not found -- PNGs left in", PNG_DIR)
        return 1
    failed = 0
    for name in names:
        dst = PAA_DIR / f"{name}.paa"
        dst.unlink(missing_ok=True)
        subprocess.run([tool, str(PNG_DIR / f"{name}.png"), str(dst)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ok = dst.is_file()
        failed += 0 if ok else 1
        print(f"{name}: {'ok' if ok else 'FAILED'}")
    return 1 if failed else 0


def main() -> int:
    for folder in (PNG_DIR, PAA_DIR, DOCS):
        folder.mkdir(parents=True, exist_ok=True)
    return convert(icon() + logo())


if __name__ == "__main__":
    raise SystemExit(main())

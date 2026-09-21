#!/usr/bin/env python3
"""Generate the CARP panel's dialog block in addon/config.cpp from a layout spec.

    python tools/gen_dialog.py            # rewrite the dialog block in config.cpp
    python tools/gen_dialog.py --check    # verify the block matches the spec, change nothing

WHY THE LAYOUT IS COMPUTED AND NOT TYPED
----------------------------------------
v0.11.0 put four new controls at y 0.480. The dialog already had CARGO, its combo, DEBUG
and SOLVER TEST at 0.485. The labels overprinted each other and a combo's dropdown arrow
showed through an edit box, and it shipped, because nothing could tell that two rectangles
in a text file intersected.

Here every control's rectangle is computed from a cursor that walks down the panel, so
rows cannot collide by construction, and `verify_layout` asserts no two rectangles overlap
before anything is written. The generator is the only thing that should ever set a
position in this dialog.

WHY THE HANDLERS ARE READ BACK OUT OF THE CONFIG
------------------------------------------------
The 22 handler strings are real behaviour -- the DZ list, the mode list, the wind apply,
the arm buttons. Retyping them into a generator is how one of them quietly loses a clause.
So they are PARSED FROM THE EXISTING config.cpp and re-emitted verbatim, and a handler
this script cannot find for a control it is told to keep is a hard error rather than an
empty action.

WHAT THIS REPLACED
------------------
Five controls were created at runtime by fn_ensurePanelEnhancements -- the AP button, the
two toggles and the two jump fields -- because config.bin could not be regenerated. It can
(tools/build_config.py), so they are declared here like everything else, and the runtime
creation is gone. The diagnostics row and the status block, hidden at runtime since
v0.11.2, are simply absent.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "addon" / "config.cpp"

# ---- panel metrics ------------------------------------------------------------------
X0 = 0.315          # left edge, unchanged: the HUD and every screenshot assume it
W = 0.370           # full width, so the right edge stays 0.685
TOP = 0.150

ROW_H = 0.030       # a control
ROW_GAP = 0.006     # between rows inside a section
SEC_H = 0.021       # a section header
SEC_GAP_BEFORE = 0.012
SEC_GAP_AFTER = 0.005
RULE_H = 0.0015
LABEL_W = 0.078
PAD = 0.004         # between controls on the same row

# ---- palette ------------------------------------------------------------------------
# Flat, dark, one accent. Matches the HUD so the two do not read as different products.
C_PANEL = "{0.027,0.043,0.055,0.96}"
C_RULE = "{0.149,0.192,0.223,1}"
C_TEXT = "{0.910,0.929,0.941,1}"
C_LABEL = "{0.780,0.816,0.835,1}"
C_MUTED = "{0.553,0.604,0.639,1}"
C_ACCENT = "{0.341,0.886,0.604,1}"
C_FIELD_BG = "{0.039,0.059,0.071,1}"
C_BTN_BG = "{0.043,0.067,0.082,1}"
C_BTN_ACTIVE = "{0.086,0.129,0.153,1}"
C_BORDER = "{0.149,0.192,0.223,1}"
C_AMBER = "{0.957,0.757,0.365,1}"
C_RED = "{0.949,0.420,0.420,1}"

# AUTO DROP reads its STATE, not its action -- "AUTO DROP: ON" in green, "AUTO DROP: OFF"
# in red -- so it matches SMOKE and JPADS below it instead of being the one imperative in a
# column of readouts. The crew kept forgetting whether it was live.
#
# fn_updatePanelTelemetry paints both the text and the colour every guidance tick, because
# the state changes without a press (auto disarms itself after a release and on an AP
# disconnect) and a stale green is worse than no colour at all.
#
# C_ARM_OFF IS THE SAME RED THAT FUNCTION WRITES, AND HAS TO STAY THAT WAY: it is what the
# button shows on the frame it is created, before the first repaint. Two spellings of one
# colour is how they drift, so a test pins these two against the SQF.
C_ARM_OFF = "{0.898,0.302,0.251,1}"
C_ARM_ON = "{0.365,0.855,0.404,1}"

FONT = "RobotoCondensed"
FONT_BOLD = "RobotoCondensedBold"


class Cursor:
    """Walks down the panel handing out rectangles. Nothing else sets a y."""

    def __init__(self) -> None:
        self.y = TOP + 0.012
        self.rects: list[tuple[str, float, float, float, float]] = []

    def place(self, name: str, x: float, w: float, h: float, y: float | None = None):
        yy = self.y if y is None else y
        self.rects.append((name, x, yy, w, h))
        return (x, yy, w, h)

    def row(self, h: float = ROW_H) -> float:
        y = self.y
        self.y += h + ROW_GAP
        return y

    def section(self) -> float:
        self.y += SEC_GAP_BEFORE
        y = self.y
        self.y += SEC_H + SEC_GAP_AFTER
        return y


def verify_layout(rects):
    """No two rectangles may intersect. This is the check v0.11.0 did not have."""
    problems = []
    for i, (n1, x1, y1, w1, h1) in enumerate(rects):
        if x1 + w1 > X0 + W + 1e-9:
            problems.append(f"{n1} runs past the right edge ({x1 + w1:.4f} > {X0 + W:.4f})")
        if x1 < X0 - 1e-9:
            problems.append(f"{n1} starts left of the panel ({x1:.4f} < {X0:.4f})")
        for n2, x2, y2, w2, h2 in rects[i + 1:]:
            overlap_x = (x1 < x2 + w2 - 1e-9) and (x2 < x1 + w1 - 1e-9)
            overlap_y = (y1 < y2 + h2 - 1e-9) and (y2 < y1 + h1 - 1e-9)
            if overlap_x and overlap_y:
                problems.append(f"{n1} overlaps {n2}")
    return problems


def parse_handlers(text: str) -> dict[str, dict[str, str]]:
    """Read the existing handler strings so they can be re-emitted verbatim."""
    start = text.index("class TLB_CARP_RscDialog")
    end = text.index("class RscTitles")
    block = text[start:end]
    cur = None
    out: dict[str, dict[str, str]] = {}
    for line in block.splitlines():
        m = re.match(r"\s*class (\w+)", line)
        if m:
            cur = m.group(1)
        m2 = re.match(r'\s*(action|onLBSelChanged|onCheckedChanged|onLoad|onUnload)="(.*)";\s*$', line)
        if m2 and cur:
            out.setdefault(cur, {})[m2.group(1)] = m2.group(2)
    return out


def q(v: float) -> str:
    return f"{v:.4f}".rstrip("0").rstrip(".")


def pos(rect) -> str:
    x, y, w, h = rect
    return (f'\t\t\tx="safeZoneX+safeZoneW*{q(x)}";\n'
            f'\t\t\ty="safeZoneY+safeZoneH*{q(y)}";\n'
            f'\t\t\tw="safeZoneW*{q(w)}";\n'
            f'\t\t\th="safeZoneH*{q(h)}";\n')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="verify only, write nothing")
    args = ap.parse_args()

    text = CONFIG.read_text(encoding="utf-8")
    H = parse_handlers(text)

    required = ["TLB_CARP_RscDialog", "DZCombo", "MapDZ", "ClearDZ", "ModeCombo", "ProfileCombo",
                "ManualWind", "ApplyWind", "ApplyProfile", "RunIn", "Guidance", "AutoDrop",
                "CargoCombo", "Close"]
    missing = [c for c in required if c not in H]
    if missing:
        raise SystemExit(f"handlers not found for: {missing} -- refusing to emit empty actions")

    # The mode list handler whitelisted TOUCHDOWN and CHUTE and ignored anything else, which
    # is why v0.9.1 had to bolt a second LBSelChanged on at runtime. The config can be
    # edited now, so the third mode is added here and the bolt-on is removed.
    # Idempotent: the generator reads its own previous output, so the whitelist may already
    # carry JUMP. Refusing in that case made --check fail on a correct config, which is a
    # guard that cries wolf -- and a guard nobody can leave switched on gets switched off.
    mode_handler = H["ModeCombo"]["onLBSelChanged"]
    if "'TOUCHDOWN','CHUTE','JUMP'" not in mode_handler:
        mode_handler = mode_handler.replace(
            "if (_v in ['TOUCHDOWN','CHUTE'])", "if (_v in ['TOUCHDOWN','CHUTE','JUMP'])")
        if "'TOUCHDOWN','CHUTE','JUMP'" not in mode_handler:
            raise SystemExit("mode handler whitelist not found -- refusing to guess at it")

    c = Cursor()
    parts: list[str] = []

    def text_ctrl(name, rect, label, *, font=FONT, size=0.030, colour=C_TEXT, bg=None, style=0):
        s = f"\t\tclass {name}: RscText\n\t\t{{\n\t\t\tidc=-1;\n\t\t\ttext=\"{label}\";\n"
        s += pos(rect)
        # No `style` -- the previous config set none on any RscText and inherited it.
        s += f'\t\t\tfont="{font}";\n\t\t\tsizeEx={size};\n'
        s += f"\t\t\tcolorText[]={colour};\n"
        s += f"\t\t\tcolorBackground[]={bg if bg else '{0,0,0,0}'};\n\t\t}};\n"
        return s

    # ---- chrome ---------------------------------------------------------------------
    title_r = c.place("Title", X0, W, 0.034, c.row(0.034))
    eyebrow_r = c.place("Eyebrow", X0, W, 0.018, c.row(0.018))

    body: list[str] = []

    def section(title: str):
        y = c.section()
        r = c.place(f"Sec_{title.replace(' ', '')}", X0, W, SEC_H, y)
        body.append(text_ctrl(f"Sec{title.replace(' ', '')}", r, title,
                              font=FONT_BOLD, size=0.024, colour=C_MUTED))
        rr = c.place(f"Rule_{title.replace(' ', '')}", X0, W, RULE_H, y + SEC_H + 0.001)
        body.append(text_ctrl(f"Rule{title.replace(' ', '')}", rr, "", bg=C_RULE))

    def field(name, cls, idc, rect, *, text_val=None, extra=""):
        s = f"\t\tclass {name}: {cls}\n\t\t{{\n\t\t\tidc={idc};\n"
        if text_val is not None:
            s += f'\t\t\ttext="{text_val}";\n'
        s += pos(rect)
        s += f'\t\t\tfont="{FONT}";\n\t\t\tsizeEx=0.030;\n'
        # No colorBackground -- RscCombo, RscEdit and RscCheckBox each draw their own and
        # the previous config overrode none of them. See the note on button().
        s += f"\t\t\tcolorText[]={C_TEXT};\n"
        s += extra
        s += "\t\t};\n"
        return s

    def button(name, idc, rect, label, *, colour=C_TEXT, handler="", tooltip=""):
        s = f"\t\tclass {name}: RscButton\n\t\t{{\n\t\t\tidc={idc};\n\t\t\ttext=\"{label}\";\n"
        s += pos(rect)
        s += f'\t\t\tfont="{FONT_BOLD}";\n\t\t\tsizeEx=0.028;\n'
        # ONLY WHAT THE PREVIOUS CONFIG CARRIED, PLUS FONT AND TEXT COLOUR.
        #
        # v0.15.0 also set colorBackground / colorBackgroundActive / colorFocused /
        # colorBorder / borderSize=1 here and shipped it. borderSize in an Arma UI config
        # is a FRACTION OF THE SCREEN, not a pixel count, so borderSize=1 drew a border a
        # full screen wide around every button. The panel came back with a bar bleeding off
        # the left edge of every row that contained one, and the two rows with no button --
        # MODE and AIRCRAFT -- were the only clean ones. That was the tell.
        #
        # The lesson is not "use a smaller border". These controls inherit from the game's
        # base classes, which already define all of those correctly. Overriding a property
        # whose UNITS have not been verified, in a config that cannot be rendered here, is
        # how a panel ships broken.
        s += f"\t\t\tcolorText[]={colour};\n"
        if tooltip:
            s += f'\t\t\ttooltip="{tooltip}";\n'
        if handler:
            s += f'\t\t\taction="{handler}";\n'
        s += "\t\t};\n"
        return s

    # ---- DROP ZONE ------------------------------------------------------------------
    section("DROP ZONE")
    y = c.row()
    body.append(text_ctrl("DZLabel", c.place("DZLabel", X0, LABEL_W, ROW_H, y), "DZ", colour=C_LABEL))
    dz_x = X0 + LABEL_W + PAD
    dz_w = 0.150
    body.append(field("DZCombo", "RscCombo", 9301, c.place("DZCombo", dz_x, dz_w, ROW_H, y),
                      extra=f'\t\t\tonLBSelChanged="{H["DZCombo"]["onLBSelChanged"]}";\n'))
    map_x = dz_x + dz_w + PAD
    map_w = 0.072
    body.append(button("MapDZ", 9302, c.place("MapDZ", map_x, map_w, ROW_H, y), "SET ON MAP",
                       colour=C_ACCENT, handler=H["MapDZ"]["action"]))
    clr_x = map_x + map_w + PAD
    body.append(button("ClearDZ", 9315, c.place("ClearDZ", clr_x, X0 + W - clr_x, ROW_H, y), "CLEAR",
                       colour=C_MUTED, handler=H["ClearDZ"]["action"]))

    # ---- MISSION --------------------------------------------------------------------
    section("MISSION")
    y = c.row()
    body.append(text_ctrl("ModeLabel", c.place("ModeLabel", X0, LABEL_W, ROW_H, y), "MODE", colour=C_LABEL))
    body.append(field("ModeCombo", "RscCombo", 9303,
                      c.place("ModeCombo", dz_x, X0 + W - dz_x, ROW_H, y),
                      extra=f'\t\t\tonLBSelChanged="{mode_handler}";\n'))
    y = c.row()
    body.append(text_ctrl("AircraftLabel", c.place("AircraftLabel", X0, LABEL_W, ROW_H, y), "AIRCRAFT", colour=C_LABEL))
    body.append(field("ProfileCombo", "RscCombo", 9304,
                      c.place("ProfileCombo", dz_x, X0 + W - dz_x, ROW_H, y),
                      extra=f'\t\t\tonLBSelChanged="{H["ProfileCombo"]["onLBSelChanged"]}";\n'))
    y = c.row()
    body.append(text_ctrl("TargetAglLabel", c.place("AglLabel", X0, LABEL_W, ROW_H, y), "AGL m", colour=C_LABEL))
    e1 = X0 + LABEL_W + PAD
    body.append(field("TargetAgl", "RscEdit", 9320, c.place("TargetAgl", e1, 0.060, ROW_H, y), text_val="3000"))
    gs_l = e1 + 0.060 + PAD + 0.006
    body.append(text_ctrl("TargetGsLabel", c.place("GsLabel", gs_l, 0.062, ROW_H, y), "GS km/h", colour=C_LABEL))
    e2 = gs_l + 0.062 + PAD
    body.append(field("TargetGs", "RscEdit", 9321, c.place("TargetGs", e2, 0.055, ROW_H, y), text_val="500"))
    ap_x = e2 + 0.055 + PAD
    body.append(button("ApplyProfile", 9322, c.place("ApplyProfile", ap_x, X0 + W - ap_x, ROW_H, y), "APPLY",
                       colour=C_ACCENT, handler=H["ApplyProfile"]["action"]))

    # ---- ENVIRONMENT ----------------------------------------------------------------
    section("ENVIRONMENT")
    y = c.row()
    body.append(text_ctrl("WindLabel", c.place("WindLabel", X0, LABEL_W, ROW_H, y), "WIND", colour=C_LABEL))
    cb_x = X0 + LABEL_W + PAD
    body.append(field("ManualWind", "RscCheckBox", 9305, c.place("ManualWind", cb_x, 0.022, ROW_H, y),
                      extra=f'\t\t\tonCheckedChanged="{H["ManualWind"]["onCheckedChanged"]}";\n'))
    ws_x = cb_x + 0.022 + PAD
    body.append(field("WindSpeed", "RscEdit", 9306, c.place("WindSpeed", ws_x, 0.055, ROW_H, y), text_val="0"))
    wf_x = ws_x + 0.055 + PAD
    body.append(field("WindFrom", "RscEdit", 9307, c.place("WindFrom", wf_x, 0.055, ROW_H, y), text_val="0"))
    aw_x = wf_x + 0.055 + PAD
    body.append(button("ApplyWind", 9308, c.place("ApplyWind", aw_x, X0 + W - aw_x, ROW_H, y), "APPLY WIND",
                       colour=C_ACCENT, handler=H["ApplyWind"]["action"]))

    # ---- JUMP RUN -------------------------------------------------------------------
    section("JUMP RUN")
    y = c.row()
    body.append(text_ctrl("StickLabel", c.place("StickLabel", X0, 0.050, ROW_H, y), "STICK", colour=C_LABEL))
    s_x = X0 + 0.050 + PAD
    body.append(field("JumpStick", "RscEdit", 9332, c.place("JumpStick", s_x, 0.048, ROW_H, y), text_val="0"))
    o_l = s_x + 0.048 + PAD + 0.006
    body.append(text_ctrl("OpenLabel", c.place("OpenLabel", o_l, 0.056, ROW_H, y), "OPEN m", colour=C_LABEL))
    o_x = o_l + 0.056 + PAD
    body.append(field("JumpOpen", "RscEdit", 9333, c.place("JumpOpen", o_x, 0.048, ROW_H, y), text_val="0"))
    j_x = o_x + 0.048 + PAD
    body.append(button("JumpRun", 9337, c.place("JumpRun", j_x, X0 + W - j_x, ROW_H, y), "ARM JUMP RUN",
                       colour=C_AMBER,
                       tooltip="Arm or disarm the HALO exit cue: computed exit point, audible countdown and the jumplight. Was an ACE interaction until v0.15.0.",
                       handler="if (TLB_CARP_state_jumpArmed) then {['PILOT DISARM'] call TLB_CARP_fnc_disarmJumpRun} else {[] call TLB_CARP_fnc_armJumpRun}; [] call TLB_CARP_fnc_refreshPanel"))

    # ---- CARGO ----------------------------------------------------------------------
    section("CARGO")
    y = c.row()
    body.append(text_ctrl("CargoLabel", c.place("CargoLabel", X0, LABEL_W, ROW_H, y), "DROP", colour=C_LABEL))
    body.append(field("CargoCombo", "RscCombo", 9312, c.place("CargoCombo", dz_x, 0.090, ROW_H, y),
                      extra=f'\t\t\tonLBSelChanged="{H["CargoCombo"]["onLBSelChanged"]}";\n'))
    jp_x = dz_x + 0.090 + PAD
    jp_w = 0.093
    body.append(button("Jpads", 9336, c.place("Jpads", jp_x, jp_w, ROW_H, y), "JPADS: OFF",
                       tooltip="Steer the cargo canopy onto the drop zone after the chute opens. A stick is spread along the run-in rather than steered onto one point. Shared with the crew.",
                       handler="TLB_CARP_state_jpadsEnabled=!(missionNamespace getVariable ['TLB_CARP_state_jpadsEnabled',false]); [] call TLB_CARP_fnc_refreshPanel"))
    sm_x = jp_x + jp_w + PAD
    body.append(button("Smoke", 9331, c.place("Smoke", sm_x, X0 + W - sm_x, ROW_H, y), "SMOKE: ON",
                       tooltip="Mark the released load with a coloured smoke shell under canopy, re-lit as each burns out. Shared with the crew.",
                       handler="TLB_CARP_state_smokeEnabled=!(missionNamespace getVariable ['TLB_CARP_state_smokeEnabled',true]); [] call TLB_CARP_fnc_refreshPanel"))

    # ---- actions --------------------------------------------------------------------
    c.y += SEC_GAP_BEFORE
    rr = c.place("RuleActions", X0, W, RULE_H, c.y)
    body.append(text_ctrl("RuleActions", rr, "", bg=C_RULE))
    c.y += RULE_H + 0.010

    y = c.row(0.034)
    bw = (W - 3 * PAD) / 4
    for i, (name, idc, label, colour, handler, tip) in enumerate([
        ("RunIn", 9309, "RUN-IN", C_TEXT, H["RunIn"]["action"], "Lock the aircraft's current ground track as the required drop heading."),
        ("Guidance", 9310, "GUIDANCE", C_AMBER, H["Guidance"]["action"], "Start solving and drawing the release point."),
        ("Autopilot", 9330, "AP: OFF", C_TEXT,
         "if (missionNamespace getVariable ['TLB_CARP_state_apArmed',false]) then {['USER',false] call TLB_CARP_fnc_disarmAutopilot} else {[] call TLB_CARP_fnc_armAutopilot}; [] call TLB_CARP_fnc_refreshPanel",
         "Fly the locked run-in at the target altitude and speed. Driver only."),
        ("AutoDrop", 9311, "AUTO DROP: OFF", C_ARM_OFF, H["AutoDrop"]["action"], "Release automatically at the computed release point."),
    ]):
        bx = X0 + i * (bw + PAD)
        body.append(button(name, idc, c.place(name, bx, bw, 0.034, y), label, colour=colour, handler=handler, tooltip=tip))

    y = c.row(0.032)
    cw = 0.090
    body.append(button("Close", -1, c.place("Close", X0 + W - cw, cw, 0.032, y), "CLOSE",
                       colour=C_RED, handler=H["Close"]["action"]))

    panel_h = (c.y + 0.010) - TOP

    # ---- no property whose units were never verified ---------------------------------
    #
    # v0.15.0 shipped borderSize=1 on every button. In an Arma UI config borderSize is a
    # FRACTION OF THE SCREEN, so that drew a border a full screen wide around each one and
    # the panel came back unusable. Nothing here could have caught it: the layout checker
    # only knows about x/y/w/h, and a config cannot be rendered from this script.
    #
    # So the emitter is restricted to properties the previous, working config carried, plus
    # font/sizeEx/colorText/colorBackground/tooltip, which are ordinary and were verified in
    # flight. Adding to this list means having checked what the property MEANS, in units,
    # first -- not having assumed it from its name.
    # `body` only -- the chrome (background, title, eyebrow) is emitted by the same
    # text_ctrl helper, so anything it could produce is already covered here, and it
    # is assembled further down.
    body_text = "".join(body)
    emitted = set(re.findall(r"^	+(\w+)(?:\[\])?=", body_text, re.M))
    allowed = {
        "idc", "text", "x", "y", "w", "h",               # what the old config had
        "font", "sizeEx", "colorText", "colorBackground",  # verified in flight
        "tooltip", "action", "onLBSelChanged", "onCheckedChanged",
    }
    stray = sorted(emitted - allowed)
    if stray:
        raise SystemExit(
            "refusing to emit unverified control properties: " + ", ".join(stray)
            + "\n  borderSize=1 shipped a broken panel this way. Verify the UNITS first,"
            + "\n  then add the name to `allowed` in this script with a note saying you did."
        )

    problems = verify_layout(c.rects)
    if problems:
        for p in problems:
            print("  LAYOUT:", p, file=sys.stderr)
        raise SystemExit(f"{len(problems)} layout problem(s) -- nothing written")
    print(f"  {len(c.rects)} controls, no overlaps, panel {q(TOP)} -> {q(TOP + panel_h)}")

    # ---- assemble -------------------------------------------------------------------
    bg = "\tclass controlsBackground\n\t{\n"
    bg += "\t\tclass Background: RscText\n\t\t{\n\t\t\tidc=-1;\n"
    bg += pos((X0 - 0.008, TOP, W + 0.016, panel_h))
    bg += f"\t\t\tcolorBackground[]={C_PANEL};\n\t\t}};\n"
    bg += text_ctrl("Title", title_r, "TLB CARP - COMPUTED AIR RELEASE POINT",
                    font=FONT_BOLD, size=0.036, colour=C_ACCENT)
    bg += text_ctrl("Eyebrow", eyebrow_r, "TLB MISSION SYSTEMS", size=0.022, colour=C_MUTED)
    bg += "\t};\n"

    block = "class TLB_CARP_RscDialog: RscDisplayEmpty\n{\n"
    block += "\tidd=9300;\n\tmovingEnable=0;\n\tenableSimulation=1;\n"
    block += f'\tonLoad="{H["TLB_CARP_RscDialog"]["onLoad"]}";\n'
    block += f'\tonUnload="{H["TLB_CARP_RscDialog"]["onUnload"]}";\n'
    block += bg
    block += "\tclass controls\n\t{\n" + "".join(body) + "\t};\n};\n"

    start = text.index("class TLB_CARP_RscDialog")
    end = text.index("class RscTitles")
    new = text[:start] + block + text[end:]

    if args.check:
        print("  check only" + ("" if new == text else " -- config.cpp DIFFERS from the spec"))
        return 0 if new == text else 1
    CONFIG.write_text(new, encoding="utf-8")
    print(f"  wrote the dialog block into {CONFIG.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""v0.16.13 -- the jump readout moves off the shared hint slot onto CARP's own layer.

FLOWN IN MP, 2026-09-21. Everything else in the session worked. The jump readout was
visible from a seat, including the NO JUMP hold when the aircraft overflew the DZ, then
vanished the instant the jumper stood up on the ramp under the free-fall mod -- and CAME
BACK once their canopy opened.

THAT LAST PART IS THE WHOLE DIAGNOSIS, and it is what made a console probe unnecessary.
Two mechanisms were open:

  1. the roster stopped addressing the client, because the readout targets unit OBJECTS
     and FFR may swap the unit; or
  2. the event arrived fine and something else owned the hint slot.

Mechanism 1 predicts the readout stays gone under canopy: TLB_CARP_state_jumpRoster is a
snapshot taken at arm time and a jumper under canopy is in neither it nor `crew`, so
nothing would start matching again. It came back. Mechanism 2 predicts it returns the
moment the other UI stops drawing, which is exactly when the jumper leaves the ramp.

So the targeting was never broken -- v0.10.1 fixed that half and it still works. The
defect is the CHANNEL. `hintSilent` is one slot shared by every mod in the session and
the last writer wins; a flight instrument cannot live there.

THE FIX. CARP already allocates its own title layer for the HUD (TLB_CARP_HUD_LAYER,
cutRsc). Title layers and the hint box are separate subsystems, so a layer CARP allocates
for itself cannot be taken. The readout now goes to TLB_CARP_JUMP_LAYER with isStructured,
so the markup fn_updateJumpCue already builds renders unchanged and nothing about the
cue, the roster or the phases moved.

AND IT HAS TO BE CLEARED. A title layer holds its last frame forever, where a hint fades.
fn_disarmJumpRun therefore broadcasts an empty string to the same audience BEFORE it wipes
the roster -- after that there is nobody left to address, and the final countdown frame
would sit on the jumpers' screens for the rest of the mission.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.exists() else ""


def code(rel: str) -> str:
    sys.path.insert(0, str(ROOT / "tools"))
    from strip_sqf_comments import strip_comments

    path = ROOT / rel
    return strip_comments(path.read_text(encoding="utf-8")) if path.exists() else ""


POSTINIT = "addon/functions/fn_postInit.sqf"
DISARM = "addon/functions/jump/fn_disarmJumpRun.sqf"
CUE = "addon/functions/jump/fn_updateJumpCue.sqf"


class LayerTests(unittest.TestCase):
    def test_the_readout_no_longer_uses_the_hint_slot(self):
        """THE DEFECT. One slot, every mod in the session, last writer wins."""
        src = code(POSTINIT)
        self.assertNotIn("hintSilent parseText _text;", src)

    def test_it_has_its_own_layer_separate_from_the_hud(self):
        """Sharing the HUD's layer would mean a jump readout and a cargo HUD could not be
        on screen at once, and disarming one would wipe the other."""
        src = code(POSTINIT)
        self.assertIn('TLB_CARP_state_jumpHintLayer = "TLB_CARP_JUMP_LAYER" call BIS_fnc_rscLayer;', src)
        self.assertIn('TLB_CARP_state_hudLayer = "TLB_CARP_HUD_LAYER" call BIS_fnc_rscLayer;', src)

    def test_the_layer_is_allocated_only_where_there_is_a_screen(self):
        """BIS_fnc_rscLayer is a UI allocation. The receiver is registered above the
        hasInterface guard so a server can take the event, so the allocation must sit
        below it and the receiver must tolerate its absence."""
        src = code(POSTINIT)
        guard = src.index("if (!hasInterface) exitWith {")
        self.assertLess(src.index('["TLB_CARP_jumpHint", {'), guard)
        self.assertGreater(src.index('TLB_CARP_state_jumpHintLayer = "TLB_CARP_JUMP_LAYER"'), guard)

    def test_the_receiver_tolerates_a_machine_with_no_layer(self):
        src = code(POSTINIT)
        self.assertIn('if (isNil "TLB_CARP_state_jumpHintLayer") exitWith {};', src)

    def test_the_markup_is_rendered_as_structured_text(self):
        """fn_updateJumpCue builds <t> markup in every branch. Without isStructured the
        jumper would read the tags."""
        src = code(POSTINIT)
        self.assertIn('TLB_CARP_state_jumpHintLayer cutText [_text, "PLAIN", 0, true, true];', src)

    def test_an_empty_string_clears_the_layer(self):
        src = code(POSTINIT)
        self.assertIn('if (_text isEqualTo "") exitWith {TLB_CARP_state_jumpHintLayer cutText ["", "PLAIN"]};', src)

    def test_the_state_is_initialised_so_isnil_means_something(self):
        self.assertIn("TLB_CARP_state_jumpHintLayer = nil;", read(POSTINIT))


class DisarmClearsEveryScreenTests(unittest.TestCase):
    def test_disarm_broadcasts_a_clear(self):
        """A title layer holds its last frame forever, where a hint fades."""
        src = code(DISARM)
        self.assertIn('["TLB_CARP_jumpHint", [""], _clearTargets] call CBA_fnc_targetEvent;', src)

    def test_it_clears_before_the_roster_is_wiped(self):
        """THE ORDERING IS THE POINT. After TLB_CARP_state_jumpRoster = [] there is nobody
        left to address, and the countdown's last frame would stay on the jumpers'
        screens for the rest of the mission."""
        src = code(DISARM)
        self.assertLess(src.index('["TLB_CARP_jumpHint", [""], _clearTargets]'),
                        src.index("TLB_CARP_state_jumpRoster = [];"))

    def test_it_clears_the_same_audience_the_readout_went_to(self):
        """Not `crew`. FFR's fnc_standUp calls moveOut, so crew alone would leave the text
        stuck on exactly the people standing on the ramp -- the ones this release is for."""
        src = code(DISARM)
        self.assertIn("private _clearRoster = (TLB_CARP_state_jumpRoster select {alive _x}) + (crew _aircraft);", src)
        self.assertIn("private _clearTargets = _clearRoster arrayIntersect _clearRoster;", src)


class NothingElseMovedTests(unittest.TestCase):
    def test_the_cue_still_builds_and_targets_exactly_as_before(self):
        """The targeting was never the defect -- v0.10.1 fixed that and the flown evidence
        confirms it still works. Only the channel changed."""
        src = code(CUE)
        self.assertIn("private _roster = (TLB_CARP_state_jumpRoster select {alive _x}) + (crew TLB_CARP_state_jumpAircraft);", src)
        self.assertIn('["TLB_CARP_jumpHint", [_this], _targets] call CBA_fnc_targetEvent;', src)

    def test_the_audio_is_untouched(self):
        src = code(CUE)
        self.assertIn('["TLB_CARP_jumpCue", [_sound], _targets] call CBA_fnc_targetEvent;', src)

    def test_every_phase_still_says_something(self):
        """HOLD and REFUSED exit before the main readout block and each carries its own
        hint. A silent hold looks identical to a stalled system."""
        src = code(CUE)
        self.assertIn("JUMP HOLD", src)
        self.assertIn("NO JUMP", src)

    def test_the_hud_layer_is_not_reused_for_the_readout(self):
        src = code(POSTINIT)
        self.assertNotIn("TLB_CARP_state_hudLayer cutText [_text", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""v0.10.1 -- the jump readout reaches the jumpers, not just whoever armed the run.

REPORTED FROM A FLOWN JUMP: "the JUMP hint showed for the pilot but not the people in the
back of the plane that stood up using the free fall ramp mod."

THE CAUSE, AND WHY IT SURVIVED THE FIRST JUMP-RUN RELEASE

fn_updateJumpCue runs on exactly ONE machine -- the one that armed the jump run, in
practice the pilot's -- from a per-frame handler started by fn_armJumpRun. hintSilent is
local. So every readout it drew (the hold reason, the NO JUMP refusal and the main
phase/range/countdown block) was painted on that machine alone.

The audio was already correct. fn_armJumpRun snapshots a roster because FFR's fnc_standUp
calls moveOut before teleporting the jumper into its hidden dummy -- so a standing jumper
is not in `crew` and has a null objectParent -- and the cue goes out by CBA target event
to that roster unioned with the live crew.

Which is precisely why this was easy to miss: the jumpers could HEAR the countdown working
while seeing nothing at all, so from the pilot's seat the system looked complete.

The readout now goes to the same audience by the same mechanism. These tests pin that the
two audiences cannot drift apart again, because a fix that sent the hint to `crew` would
look right in a single-player test and fail for exactly the people it exists for.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.exists() else ""


def code(rel: str) -> str:
    """Comments stripped, string literals intact."""
    sys.path.insert(0, str(ROOT / "tools"))
    from strip_sqf_comments import strip_comments

    path = ROOT / rel
    return strip_comments(path.read_text(encoding="utf-8")) if path.exists() else ""


CUE = "addon/functions/jump/fn_updateJumpCue.sqf"
ARM = "addon/functions/jump/fn_armJumpRun.sqf"
POSTINIT = "addon/functions/fn_postInit.sqf"


class JumpReadoutAudienceTests(unittest.TestCase):
    def test_no_readout_is_drawn_locally_any_more(self):
        """THE DEFECT. A single surviving hintSilent is a readout one machine sees and
        the rest of the aircraft does not."""
        self.assertNotIn("hintSilent", code(CUE))

    def test_every_readout_goes_through_the_one_broadcast(self):
        """Three of them: the hold reason, the NO JUMP refusal, and the main block. If a
        fourth is added it has to go the same way."""
        self.assertEqual(code(CUE).count("call _hint"), 3)

    def test_the_readout_and_the_audio_share_one_audience(self):
        """Both compute the roster the same way. Anything else and a jumper can hear a
        countdown they cannot see, or the reverse."""
        src = code(CUE)
        self.assertEqual(
            src.count("(USAFDC_state_jumpRoster select {alive _x}) + (crew USAFDC_state_jumpAircraft)"),
            2,
        )
        self.assertEqual(src.count("_roster arrayIntersect _roster"), 2)

    def test_the_audience_is_not_crew(self):
        """FFR's fnc_standUp calls moveOut, so a jumper standing on the ramp is not in
        crew. Targeting crew would make the readout invisible to exactly the people it
        is for, while looking perfectly correct to the pilot."""
        src = code(CUE)
        self.assertIn("USAFDC_state_jumpRoster", src)
        self.assertIn('["USAFDC_jumpHint", [_this], _targets] call CBA_fnc_targetEvent', src)

    def test_the_roster_is_snapshotted_at_arm_time(self):
        """The only record that still knows a standing jumper is aboard."""
        self.assertIn("USAFDC_state_jumpRoster = crew _aircraft;", code(ARM))

    def test_the_hint_closure_exists_before_the_first_readout(self):
        """The hold-reason readout is inside an early exitWith. A closure defined next to
        the audio one, further down, would be undefined there."""
        src = code(CUE)
        self.assertLess(src.index("private _hint ="), src.index("call _hint"))

    def test_the_receiver_is_registered(self):
        """v0.16.13 MOVED THE CHANNEL, not the audience. This test pinned hintSilent, and
        that pin was correct for what v0.10.1 fixed -- the readout reaching the roster at
        all. It was flown in MP on 2026-09-21 and the roster half still works; the hint
        BOX does not, because it is one slot shared with every other mod and the free-fall
        mod's ramp UI takes it. The readout now goes to a title layer CARP allocates for
        itself. See tests/test_v01613_jump_readout_layer.py for the evidence."""
        src = code(POSTINIT)
        self.assertIn('["USAFDC_jumpHint", {', src)
        self.assertIn('USAFDC_state_jumpHintLayer cutText [_text, "PLAIN", 0, true, true];', src)

    def test_the_readout_is_not_gated_on_the_sounds_setting(self):
        """The cue receiver checks USAFDC_setting_sounds. A jumper who turned cue audio
        off still needs to see the countdown."""
        src = code(POSTINIT)
        receiver = src[src.index('["USAFDC_jumpHint", {'):]
        receiver = receiver[:receiver.index("call CBA_fnc_addEventHandler")]
        self.assertNotIn("USAFDC_setting_sounds", receiver)

    def test_an_empty_audience_sends_nothing(self):
        """CBA_fnc_targetEvent with no targets is a broadcast to everyone on some paths.
        A jump run whose roster has emptied must go quiet, not go global."""
        src = code(CUE)
        self.assertEqual(src.count("if ((count _targets) isEqualTo 0) exitWith {};"), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)

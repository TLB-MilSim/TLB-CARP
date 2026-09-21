"""v0.4.2 fixes for defects found in v0.4.1 in-engine validation.

Pass 2  - toggled (double-tap Alt) freelook disconnected the AP.
Pass 4/5 - package PACKAGE/DROP/CHUTE/TOT lines were clipped out of the HUD.
Pass 6  - flight-director caret rendered below the centre post, overlapping the
          HUD block, because only the caret was positioned at runtime while the
          centre post kept its position from the pre-binarized config.bin.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


class FlightDirectorGeometryTests(unittest.TestCase):
    """config.bin cannot be regenerated, so BOTH flight-director controls must
    be positioned from SQF. Editing ui/hud.hpp alone is inert in-engine."""

    def test_centre_post_is_positioned_at_runtime(self):
        text = read("addon/functions/ui/fn_updateHud.sqf")
        self.assertIn("_centerCtrl ctrlSetPosition", text)
        self.assertIn("_centerCtrl ctrlCommit", text)

    def test_caret_sits_above_centre_post(self):
        text = read("addon/functions/ui/fn_updateHud.sqf")
        self.assertIn("_cueY", text)
        self.assertIn("_centerY", text)
        # Both offsets are derived from the HUD block bottom; caret nearer the block.
        # The gap is deliberately tight so the caret tip meets the post tip and the
        # pair reads as one arrow the pilot can line up.
        self.assertIn("_hudBottomY + 0.013", text)
        self.assertIn("_fdGapY", text)
        self.assertIn("_fdGapY = 0.0;", text)

    def test_caret_and_post_no_longer_use_frozen_hardcoded_offsets(self):
        text = read("addon/functions/ui/fn_updateHud.sqf")
        self.assertNotIn("safeZoneH * 0.238", text)


class HudPackageBlockTests(unittest.TestCase):
    """The package/TOT block existed in the format string but was clipped by a
    fixed 0.20 block height, so the pilot could only read TOT in the panel."""

    def test_hud_block_height_is_derived_not_fixed(self):
        text = read("addon/functions/ui/fn_updateHud.sqf")
        self.assertIn("_hudH", text)
        self.assertIn("_hudBottomY", text)
        self.assertNotIn("safeZoneW * 0.33, safeZoneH * 0.20]", text)

    def test_hud_still_renders_package_and_tot_lines(self):
        """These were clipped off the bottom by a fixed 0.20 height, which is why TOT
        used to be panel-only. They must stay on the HUD."""
        text = read("addon/functions/ui/fn_updateHud.sqf")
        for marker in ('"PKG"', '"DROP"', "CHUTE %1", '"TOT"'):
            self.assertIn(marker, text)

    def test_hud_height_is_derived_from_the_rows_actually_rendered(self):
        """Was (0.35 * _scale) min 0.60 -- a constant already raised twice because
        content kept clipping (0.20, then 0.32, then 0.35). A guessed constant cannot
        be right for a variable number of rows at a variable font size, so v0.5.5
        computes the height from the row count instead. That is what makes clipping
        structurally impossible rather than tuned-against."""
        text = read("addon/functions/ui/fn_updateHud.sqf")
        self.assertIn("(_headerRows + (count _rows)) * _rowH", text)
        # The title and status lines render ahead of _rows, so omitting them from the
        # budget under-reports by two and clips the bottom pair.
        self.assertIn("_headerRows = 2", text)
        # 0.0270. Two flown screenshots at STATED hudScale give 20 px per line at
        # 0.70 and 28.5 px at 1.00 on a 1080-tall screen -- both 2.64% of safeZoneH
        # per scale unit.
        #
        # Both earlier values were wrong in opposite directions: 0.0300 was a guess,
        # and 0.0185 came from "measuring" a screenshot assumed to be scale 1.0 that
        # was actually 0.70, so v0.5.6 clipped at BOTH scales and cut the VS row in
        # half. A calibration is only as good as the metadata behind the sample.
        self.assertIn("_rowH = 0.0270 * _scale", text)
        self.assertNotIn("_rowH = 0.0185", text)
        # Comment-stripped: the header legitimately cites the old constant when
        # explaining why it was replaced.
        from tests.test_sqf_structure import strip_comments_and_strings
        self.assertNotIn("0.35 * _scale", strip_comments_and_strings(text))
        # The cap remains, so a pathological row count cannot fill the screen. Raised
        # from 0.60 to 0.72: at 0.60 it bound early enough at hudScale 1.5 to trim the
        # whole package block away, which is worse than a tall panel the pilot asked
        # for. The panel starts at y 0.025 and the flight director sits 0.013 below it,
        # so 0.72 keeps both on screen.
        self.assertIn("#define HUD_MAX_H 0.72", text)
        self.assertIn("min HUD_MAX_H", text)

    def test_content_yields_when_it_cannot_fit_the_cap(self):
        """At hudScale 1.5 with guidance armed, a package live AND a warning present,
        16 rows want 0.75 safeZoneH against the 0.60 cap -- the original clipping bug
        returning at the top of the scale range. Tier 2 is trimmed from its tail
        instead. Tier 1 and the warning are never trimmed: tier 1 is what the pilot
        flies on and a warning must never be silently hidden.
        """
        text = read("addon/functions/ui/fn_updateHud.sqf")
        self.assertIn("_maxRows = floor ((HUD_MAX_H - (_padY * 2) - _cueExtra) / _rowH)", text)
        self.assertIn("_tier2 = _tier2 select [0, _budget]", text)
        # the warning is accounted for in the budget, so it always survives
        self.assertIn("(count _warnRows)", text)
        self.assertLess(text.index("_warnRows pushBack"), text.index("_maxRows = floor"))


class LastCargoPackageTimingTests(unittest.TestCase):
    """Dropping the LAST cargo empties usaf_cargo, which invalidates the live
    solution on the same tick the cargo leaves. The RELEASED transition was
    gated behind solver validity, so the state machine stayed in ESTIMATE, the
    display-refresh branch never saw a tracking state, and TOT froze."""

    def test_release_detection_is_not_gated_on_solver_validity(self):
        text = read("addon/functions/timing/fn_updatePackageTiming.sqf")
        removed = text.index("_removed = _previousCargo")
        guard = text.index("if (!_solutionValid) exitWith")
        self.assertLess(
            removed, guard,
            "cargo-removal detection must run before the invalid-solution bail-out",
        )

    def test_predicted_timings_are_cached_while_estimate_is_valid(self):
        text = read("addon/functions/timing/fn_updatePackageTiming.sqf")
        self.assertIn("USAFDC_state_packageEstimatedChuteAttachTimeS", text)
        self.assertIn("USAFDC_state_packageEstimatedCanopyTimeS", text)

    def test_guidance_invalid_branch_still_runs_timing_from_estimate(self):
        text = read("addon/functions/guidance/fn_updateGuidance.sqf")
        self.assertIn('"ESTIMATE", "RELEASED", "CHUTE", "ARRIVED"', text)
        # The state may transition inside the timing call, so tracking must be
        # re-read afterwards or the HUD refresh is skipped on the release tick.
        timing_call = text.index("USAFDC_fnc_updatePackageTiming")
        tracking = text.index("_trackingPackage = (missionNamespace getVariable")
        self.assertLess(timing_call, tracking)

    def test_release_requires_the_same_carrier(self):
        """Solver validity used to implicitly reject 'cargo vanished because the
        player left the aircraft'. Removing that gate needs an explicit check or
        disembarking latches a release that never happened."""
        text = read("addon/functions/timing/fn_updatePackageTiming.sqf")
        self.assertIn("USAFDC_state_packageCarrier", text)
        self.assertIn("_sameCarrier", text)
        self.assertIn("{_sameCarrier}", text)
        reset = read("addon/functions/timing/fn_resetPackageTiming.sqf")
        self.assertIn("USAFDC_state_packageCarrier = objNull", reset)

    def test_cached_timings_are_initialised_and_reset(self):
        post_init = read("addon/functions/fn_postInit.sqf")
        reset = read("addon/functions/timing/fn_resetPackageTiming.sqf")
        for var in [
            "USAFDC_state_packageEstimatedChuteAttachTimeS",
            "USAFDC_state_packageEstimatedCanopyTimeS",
        ]:
            self.assertIn(var, post_init)
            self.assertIn(var, reset)


class ToggledFreelookTests(unittest.TestCase):
    """`inputAction "lookAroundToggle"` is a momentary pulse, not a state, so a
    latched toggle state is required or freelook reads as pilot input."""

    def test_focus_guard_latches_toggled_freelook_state(self):
        text = read("addon/functions/autopilot/fn_inputFocusActive.sqf")
        self.assertIn("USAFDC_state_apFreelookToggled", text)
        self.assertIn("USAFDC_state_apLookAroundTogglePrev", text)

    def test_focus_guard_still_covers_held_freelook_and_menus(self):
        text = read("addon/functions/autopilot/fn_inputFocusActive.sqf")
        self.assertIn('inputAction "lookAround"', text)
        self.assertIn('inputAction "lookAroundToggle"', text)
        self.assertIn("9300", text)
        self.assertIn("312", text)
        self.assertIn("apAceInteractOpen", text)

    def test_latch_state_is_initialised_and_reset_on_arm(self):
        post_init = read("addon/functions/fn_postInit.sqf")
        self.assertIn("USAFDC_state_apFreelookToggled", post_init)
        self.assertIn("USAFDC_state_apLookAroundTogglePrev", post_init)
        # A stale latch must not survive into a new AP engagement.
        arm = read("addon/functions/autopilot/fn_armAutopilot.sqf")
        self.assertIn("USAFDC_state_apFreelookToggled = false", arm)


class VersionIdentificationTests(unittest.TestCase):
    """The loaded build must identify its own version, in the launcher entry and
    on the HUD, so there is no doubt which one is being flown."""

    def test_mod_cpp_template_stamps_the_version_into_the_launcher_name(self):
        text = read("packaging/mod.cpp")
        self.assertIn("{VERSION}", text)
        self.assertIn('name = "TLB CARP System (Computed Air Release Point) v{VERSION}"', text)

    def test_source_declares_a_version_constant(self):
        text = read("addon/functions/fn_postInit.sqf")
        self.assertIn("USAFDC_VERSION", text)

    def test_hud_header_shows_the_version(self):
        text = read("addon/functions/ui/fn_updateHud.sqf")
        self.assertIn("USAFDC_VERSION", text)

if __name__ == "__main__":
    unittest.main(verbosity=2)

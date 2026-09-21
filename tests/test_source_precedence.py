from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SourcePrecedenceTests(unittest.TestCase):
    def test_changed_runtime_functions_have_no_stale_sqfc_sibling(self):
        for rel in [
            # Added 2026-09-20 with v0.14.0. Its hint told the pilot to paste the
            # calibration record into an AI chatbot; the .sqfc carried that string
            # COMPILED IN and shadowed the .sqf, so editing the source alone would have
            # changed nothing in game. The sibling was deleted and excluded from the PBO.
            "addon/functions/debug/fn_copyLastCalibrationRun.sqf",
            # Added 2026-09-20 with v0.15.0. The recorder was reading usaf_cargo directly
            # and was therefore blind to vehicle-in-vehicle, ACE and CARP-loaded cargo --
            # a Blackfish drop logged "no cargo loaded at cue" with the vehicle in the
            # hold. Its .sqfc was not in the PBO, so the fix landed, but it sat in source
            # next to the file being edited and one careless --include would have
            # resurrected the old behaviour.
            "addon/functions/debug/fn_beginCalibrationRun.sqf",
            "addon/functions/debug/fn_debugDropSeries.sqf",
            "addon/functions/debug/fn_debugDropTest.sqf",
            # Added 2026-09-01. fn_buildDebugDropSolution was parameterised with
            # _aircraftId so the harnesses could fly a C-130, but a stale .sqfc
            # shadowed the edit: the builder kept defaulting to c17 and handed back
            # C-17 door names (5: back_ramp...) for a C-130 spawn (2: ramp_top,
            # ramp_bottom). Every door wait then timed out, USAF's own canDrop spent
            # ~10 s opening the ramp, and all 16 runs released ~1500 m late.
            "addon/functions/debug/fn_buildDebugDropSolution.sqf",
            "addon/functions/auto/fn_sequenceCargo.sqf",
            # Added 2026-09-02. The canopy-attach detection was moved into a
            # per-frame handler here; a stale .sqfc would have shadowed it and the
            # recorder would have kept reporting attach altitudes 46-70 m low.
            "addon/functions/debug/fn_pollCalibrationRun.sqf",
            # Added 2026-09-02. fn_triggerAutoDrop now stamps the drop-command
            # instant; a stale .sqfc would have discarded that silently, exactly as
            # one did for fn_buildDebugDropSolution.
            "addon/functions/auto/fn_triggerAutoDrop.sqf",
            "addon/functions/solver/fn_empiricalCanopyC17.sqf",
            "addon/functions/generated/fn_getModel.sqf",
            "addon/functions/fn_postInit.sqf",
            "addon/functions/guidance/fn_buildWorldSolution.sqf",
            "addon/functions/guidance/fn_updateGuidance.sqf",
            "addon/functions/guidance/fn_disarmGuidance.sqf",
            "addon/functions/guidance/fn_unlockRunIn.sqf",
            "addon/functions/ui/fn_openPanel.sqf",
            "addon/functions/ui/fn_refreshPanel.sqf",
            "addon/functions/guidance/fn_estimatePackageTiming.sqf",
            "addon/functions/guidance/fn_lockRunIn.sqf",
            "addon/functions/dz/fn_setDZ.sqf",
            "addon/functions/dz/fn_clearDZ.sqf",
            "addon/functions/autopilot/fn_armAutopilot.sqf",
            "addon/functions/autopilot/fn_updateAutopilot.sqf",
            "addon/functions/autopilot/fn_inputFocusActive.sqf",
            "addon/functions/path/fn_buildPathSolution.sqf",
            "addon/functions/timing/fn_resetPackageTiming.sqf",
            "addon/functions/timing/fn_updatePackageTiming.sqf",
            "addon/functions/ui/fn_updateHud.sqf",
            "addon/functions/ui/fn_updatePanelTelemetry.sqf",
            # Added 2026-09-15 with the v0.7.0 multiplayer work. All runtime-compiled
            # and none of them has ever had a compiled sibling -- which is exactly the
            # state that must be preserved, because a .sqfc appearing here would
            # silently restore the single-client behaviour these files exist to fix
            # and the symptom would be "multiplayer sync does not work" with no error.
            "addon/functions/sync/fn_syncSnapshot.sqf",
            "addon/functions/sync/fn_syncPublish.sqf",
            "addon/functions/sync/fn_syncApply.sqf",
            "addon/functions/sync/fn_syncReconcile.sqf",
            "addon/functions/sync/fn_syncTick.sqf",
            "addon/functions/jpads/fn_steerCargo.sqf",
            # Added 2026-09-15 with v0.8.1. These three are the whole reason guided
            # cargo works on a dedicated server; a compiled sibling shadowing any of
            # them would restore the client-only behaviour in-engine while the source
            # and the tests both said otherwise.
            "addon/functions/jpads/fn_steerBegin.sqf",
            "addon/functions/jpads/fn_steerTick.sqf",
            "addon/functions/jpads/fn_steerPublisher.sqf",
            "addon/functions/jump/fn_armJumpRun.sqf",
            "addon/functions/jump/fn_disarmJumpRun.sqf",
            "addon/functions/jump/fn_setJumpLight.sqf",
            "addon/functions/jump/fn_updateJumpCue.sqf",
            "addon/functions/jump/fn_buildJumpSolution.sqf",
            # Added 2026-09-15 with the v0.8.0 cargo work. These five all HAD a
            # compiled sibling and it was removed in that release, because each of them
            # carried a hard USAF coupling that the change exists to break -- the
            # usaf_cargo read, the USAF_Cargo_DropPos requirement, the C-17/C-130 class
            # test, the NO USAF CARGO refusal and the confidence line. A .sqfc
            # reappearing beside any of them restores the old behaviour in-engine while
            # the source and the tests both say otherwise, which is the exact trap that
            # cost this project 16 runs of garbage in v0.4.43.
            "addon/functions/aircraft/fn_getLoadedCargo.sqf",
            "addon/functions/aircraft/fn_getAircraftState.sqf",
            "addon/functions/aircraft/fn_resolveAircraftProfile.sqf",
            "addon/functions/auto/fn_validateAutoDrop.sqf",
            "addon/functions/guidance/fn_confidenceReason.sqf",
            "addon/functions/cargo/fn_cargoManifest.sqf",
            "addon/functions/cargo/fn_releaseModelOffset.sqf",
            "addon/functions/cargo/fn_releaseCargo.sqf",
            "addon/functions/cargo/fn_releaseSelected.sqf",
            # Added with v0.9.0: the access rule that every way into CARP asks. It has
            # never had a compiled sibling, and one appearing would let a player without
            # a CARP Computer back in while the source and the tests said otherwise.
            "addon/functions/access/fn_hasComputer.sqf",
            "addon/functions/access/fn_canUseCarp.sqf",
            # The server-side half of the v0.9.0 crew sync. Shadowed, the server would
            # merge nothing and every crew edit would silently stay on its own client.
            "addon/functions/sync/fn_syncMerge.sqf",
        ]:
            sqf = ROOT / rel
            self.assertTrue(sqf.exists(), rel)
            self.assertFalse(sqf.with_suffix(".sqfc").exists(), f"stale compiled sibling shadows {rel}")


if __name__ == "__main__":
    unittest.main(verbosity=2)

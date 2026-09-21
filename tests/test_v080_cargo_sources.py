"""v0.8.0 -- cargo that did not arrive through USAF, on aircraft USAF does not ship.

WHAT WAS ACTUALLY COUPLED

CARP read `usaf_cargo` in six places and `USAF_Cargo_DropPos` in one, and refused any
airframe that was not a C-17 or a C-130 in another. Three expressions, but they reached
everything: the solver, the panel's cargo selector, the package tracker, Auto Drop's
validation, the trigger and the stick sequencer. A vehicle loaded with ACE, with vanilla
vehicle-in-vehicle, or by a mission maker's attachTo did not exist as far as any of them
were concerned, and a Blackfish could not be given a drop solution at all.

WHAT IS DELIBERATELY NOT DECOUPLED

USAF's own release still runs for a USAF airframe carrying USAF-loaded cargo.
releaseDelayS = 0.5607 s is not physics -- it is the measured script latency of that
path, fitted across forty bench batches and confirmed by a flown drop. CARP's release
reproduces the sequence step for step, but reproducing is not measuring, and this
project's rule is that a calibration change is re-measured rather than assumed. So the
calibrated case keeps its flown-validated path at zero risk, and the new path carries
only what the old one could not.

WHY A GENERIC PROFILE RATHER THAN A REFUSAL

An airframe that cannot solve can never be measured. calibrationState
"provisional-borrowed" already existed for exactly this: fn_solveRelative raises a
warning for it, any warning forces DEGRADED, and fn_validateAutoDrop then gates Auto
Drop behind TLB_CARP_setting_allowDegradedAuto. Every guard the C-130 gets, for free.
"""
from pathlib import Path
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def code(rel: str) -> str:
    """Source with comments stripped, string literals intact.

    Every absence assertion here must run against executable code: these files discuss
    at length the couplings they have removed, and a raw-text search would find the
    explanation rather than the call.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    from strip_sqf_comments import strip_comments

    path = ROOT / rel
    if not path.exists():
        return ""
    return strip_comments(path.read_text(encoding="utf-8"))


MANIFEST = "addon/functions/cargo/fn_cargoManifest.sqf"
OFFSET = "addon/functions/cargo/fn_releaseModelOffset.sqf"
RELEASE = "addon/functions/cargo/fn_releaseCargo.sqf"
WATCH = "addon/functions/cargo/fn_canopyWatch.sqf"
SELECT = "addon/functions/cargo/fn_releaseSelected.sqf"
POSTINIT = "addon/functions/fn_postInit.sqf"

CARGO_FILES = [MANIFEST, OFFSET, RELEASE, SELECT]


class CargoModuleRegistrationTests(unittest.TestCase):
    def test_every_cargo_function_exists_and_is_registered(self):
        """config.bin is pre-binarized; the compile table is the only way in."""
        post = read(POSTINIT)
        for rel in CARGO_FILES:
            self.assertTrue((ROOT / rel).exists(), rel)
            name = Path(rel).stem.replace("fn_", "")
            self.assertIn(f'"TLB_CARP_fnc_{name}"', post)
            self.assertIn(Path(rel).name, post)

    def test_no_cargo_function_has_a_compiled_sibling(self):
        for rel in CARGO_FILES:
            self.assertFalse((ROOT / rel).with_suffix(".sqfc").exists(), rel)

    def test_the_compile_table_is_reachable_on_a_dedicated_server(self):
        """The whole remoteExec-to-the-cargo-owner design rests on this.

        On a dedicated server a load placed in Eden, spawned by Zeus or spawned by the
        server is local to the SERVER. If the compile table still sat behind the
        blanket hasInterface guard that v0.7.0 removed, TLB_CARP_fnc_releaseCargo would
        be nil there and the remoteExec would resolve nothing at all -- silently.
        """
        src = code(POSTINIT)
        guard = "if (!hasInterface) exitWith {"
        self.assertIn("fn_releaseCargo.sqf", src[:src.index(guard)])


class ManifestTests(unittest.TestCase):
    def test_all_four_physical_carriage_sources_are_enumerated(self):
        src = code(MANIFEST)
        self.assertIn('getVariable ["usaf_cargo", []]', src)
        self.assertIn('getVariable ["ace_cargo_loaded", []]', src)
        self.assertIn("getVehicleCargo _carrier", src)
        self.assertIn("attachedObjects _carrier", src)

    def test_ace_string_entries_are_excluded(self):
        """ACE stores loaded OBJECTS, and separately virtual CLASS NAMES. A string has
        no object behind it, so listing one would offer the pilot a load that cannot be
        dropped."""
        src = code(MANIFEST)
        self.assertIn("_x isEqualType objNull", src)

    def test_usaf_entries_come_first(self):
        """Order is load-bearing. With only USAF cargo aboard, the last element of the
        manifest must be the last element of usaf_cargo, because that is the one
        USAF_CARGO_fnc_canDrop selects for itself regardless of what it is handed."""
        src = code(MANIFEST)
        self.assertLess(src.index("usaf_cargo"), src.index("ace_cargo_loaded"))
        self.assertLess(src.index("ace_cargo_loaded"), src.index("getVehicleCargo"))
        self.assertLess(src.index("getVehicleCargo"), src.index("attachedObjects"))

    def test_the_source_is_stamped_on_the_object_and_broadcast(self):
        """The release may run on another machine, so the source has to travel with the
        object rather than in a parallel array on this one."""
        self.assertIn('setVariable ["TLB_CARP_cargoSource", _source, true]', code(MANIFEST))

    def test_attached_objects_are_filtered_to_droppable_types(self):
        src = code(MANIFEST)
        for kind in ["LandVehicle", "Ship", "ThingX", "ReammoBox_F"]:
            self.assertIn(kind, src)

    def test_every_former_usaf_cargo_read_now_goes_through_the_manifest(self):
        """Six call sites. Missing one leaves that subsystem blind to non-USAF cargo,
        and the symptom is subtle: the panel offers a load the tracker never sees leave.
        """
        offenders = []
        allowed = {
            # The manifest itself must read the raw array.
            MANIFEST,
            # The config-declared wrapper keeps a direct-read fallback for the window
            # before the compile table has registered the manifest.
            "addon/functions/aircraft/fn_getLoadedCargo.sqf",
            # The release removes the load from USAF's own bookkeeping.
            RELEASE,
            # And the unload puts it back, for the same reason and in the same way. Both
            # are WRITES to USAF's array dressed as a read -- you cannot remove an entry
            # from an array without first reading it -- which is a different thing from
            # asking "what is aboard", and that question still goes through the manifest.
            "addon/functions/cargo/fn_unloadCargo.sqf",
            # The path predicate has to ask "is this USAF's last one".
            SELECT,
        }
        for path in (ROOT / "addon" / "functions").rglob("*.sqf"):
            rel = path.relative_to(ROOT).as_posix()
            if rel in allowed or rel.startswith("addon/functions/debug/"):
                continue
            if 'getVariable ["usaf_cargo"' in code(rel):
                offenders.append(rel)
        self.assertEqual(offenders, [], f"still reading usaf_cargo directly: {offenders}")


class ManifestCostTests(unittest.TestCase):
    def test_the_source_tag_is_broadcast_only_when_it_changes(self):
        """fn_updatePackageTiming rebuilds the manifest on every guidance tick -- 20 Hz,
        on every client with guidance armed. An unconditional public setVariable put one
        network write per load per tick on the wire for a value that changes at most once
        in a load's life."""
        src = code(MANIFEST)
        guard = 'if !((_obj getVariable ["TLB_CARP_cargoSource", ""]) isEqualTo _source) then {'
        self.assertIn(guard, src)
        self.assertLess(src.index(guard), src.index('setVariable ["TLB_CARP_cargoSource", _source, true]'))

    def test_an_empty_manifest_can_still_be_explained_on_demand(self):
        """WAS on the panel: naming the vehicles that are present but held by nothing, so
        "NO CARGO ABOARD" next to a visible car did not read as a broken detector.
        v0.11.2 removed the panel status block (control 9314) on a flown request and took the explanation with it.

        The explanation still exists, in the debug-console diagnostic, which reports all
        four carriage mechanisms raw next to what the manifest made of them and lists
        what is sitting in the hold that nothing is carrying. It has to be asked for now
        rather than being in front of the loadmaster, which is the cost."""
        src = read("testing/mp_carp_diagnostic.sqf")
        self.assertIn("UNCLAIMED near aircraft", src)
        self.assertIn("attachedTo", src)
        self.assertIn("isVehicleCargo", src)

    def test_the_loose_scan_never_runs_on_the_guidance_path(self):
        """nearestObjects is not free. It belongs on the panel, and only when there is
        nothing to report otherwise."""
        self.assertNotIn("nearestObjects", code(MANIFEST))
        self.assertNotIn("nearestObjects", code("addon/functions/timing/fn_updatePackageTiming.sqf"))


class ReleaseOffsetTests(unittest.TestCase):
    def test_priority_is_override_then_config_then_derivation(self):
        src = code(OFFSET)
        self.assertLess(src.index("TLB_CARP_dropPos"), src.index("USAF_Cargo_DropPos"))
        self.assertLess(src.index("USAF_Cargo_DropPos"), src.index("boundingBoxReal _carrier"))

    def test_a_usaf_airframe_still_gets_its_configured_value(self):
        """The calibration was fitted with the config value in the loop. If the
        derivation ever took priority over it, every calibrated drop would move."""
        src = code(OFFSET)
        config_branch = src[src.index("USAF_Cargo_DropPos"):src.index("boundingBoxReal _carrier")]
        self.assertIn("exitWith", config_branch)

    def test_the_derivation_reproduces_the_c17_margins(self):
        """The rule gives [0, -30.02, -4.86] against USAF's hand-placed [0, -30, -5] --
        2 cm along and 14 cm vertically. That agreement is the reason to trust it."""
        src = code(OFFSET)
        self.assertIn("(_bbMin # 1) - 6", src)
        self.assertIn("(_bbMin # 2) - 1.5", src)

    def test_the_bounding_box_top_is_added_on_every_branch(self):
        """USAF adds it so the attach point sits under the load rather than through it.
        A branch that forgot it would bury the load in the airframe."""
        src = code(OFFSET)
        self.assertEqual(src.count("_bboxTop"), 4)  # one definition, three branches

    def test_the_source_is_reported_so_the_panel_can_show_it(self):
        src = code(OFFSET)
        for tag in ['"override"', '"config"', '"bbox"']:
            self.assertIn(tag, src)
        self.assertIn("dropPosSource", code("addon/functions/aircraft/fn_getAircraftState.sqf"))


class CarpReleaseTests(unittest.TestCase):
    def test_it_refuses_to_run_where_the_cargo_is_not_local(self):
        """detach, setVelocity and attachTo are all local-effect commands."""
        self.assertIn("if !(local _cargo) exitWith", code(RELEASE))

    def test_it_is_dispatched_to_the_cargo_owner(self):
        self.assertIn('remoteExec ["TLB_CARP_fnc_releaseCargo", _cargo]', code(SELECT))

    def test_it_spawns_so_the_sleeps_are_legal(self):
        """remoteExec does not guarantee a scheduled environment, and the whole
        sequence is built on timing."""
        self.assertIn("spawn {", code(RELEASE))

    def test_the_release_sequence_matches_usaf_step_for_step(self):
        """releaseDelayS = 0.5607 s is the measured latency of this exact order.
        Changing it to something tidier moves a number fitted over forty batches."""
        src = code(RELEASE)
        # Anchor past the source-specific unload branches: the ACE branch legitimately
        # detaches the load from its -100 m hiding place before any of this begins.
        src = src[src.index("disableCollisionWith _carrier"):]
        order = [
            "disableCollisionWith _carrier",
            "attachTo [_carrier",
            "sleep 0.5",
            "detach _cargo",
            "setVelocity (velocity _carrier)",
            "enableCollisionWith _carrier",
        ]
        last = -1
        for token in order:
            idx = src.index(token)
            self.assertGreater(idx, last, f"{token} out of order")
            last = idx

    def test_the_canopy_opens_at_usafs_altitude_not_on_a_timer(self):
        """ace_cargo_fnc_paradropItem opens its canopy 0.7 s after release with no
        altitude test at all -- a canopy at aircraft altitude, which is exactly what
        the developer guide warns about. CARP uses the 300 m AGL gate USAF uses.

        v0.12.0 moved the canopy and everything after it into fn_canopyWatch, so the
        altitude test could leave the script scheduler, where the
        test is a per-frame comparison against the trigger rather than a scheduled poll.
        The RULE is unchanged and this test still enforces it: an altitude, never a
        timer."""
        src = code(WATCH)
        self.assertIn("_triggerAglM", src)
        self.assertIn('["_triggerAglM", 300]', src)
        # v0.16.4: read through getPosASL. getPos on an ATTACHED object returns its offset
        # from the parent, which opened a canopy at the ramp and destroyed an aircraft.
        # See tests/test_v0164_canopy_altitude.py. The contract here is unchanged.
        self.assertIn("((ASLToAGL (getPosASL _cargo)) # 2) >= _triggerAglM", src)
        self.assertNotIn("0.7", src)

    def test_the_canopy_geometry_matches_usafs(self):
        """zeroWorldM was fitted against this attach geometry; a different one moves it."""
        src = code(WATCH)
        self.assertIn('_chute attachTo [_cargo, [0, 0, 0]]', src)
        self.assertIn('_strobe attachTo [_cargo, [0, -2, 0.5]]', src)
        self.assertIn('isKindOf "ReammoBox_F"', src)
        self.assertIn("sleep 5", src)
        self.assertIn("setVectorUp [0, 0, 1]", src)

    def test_release_time_is_stamped_in_mission_time_not_uptime(self):
        """The command stamp records diag_tickTime on the PILOT's client, which is that
        machine's uptime and means nothing on the machine that performs the release. A
        dedicated-server drop could never be measured end to end without a synchronised
        clock at both ends."""
        src = code(RELEASE)
        self.assertIn('setVariable ["TLB_CARP_releaseSimTime", time, true]', src)
        self.assertIn('setVariable ["TLB_CARP_releasePath", "carp", true]', src)

    def test_a_busy_flag_is_raised_across_the_release(self):
        src = code(RELEASE)
        self.assertIn('setVariable ["TLB_CARP_releaseInProgress", true, true]', src)
        self.assertIn('setVariable ["TLB_CARP_releaseInProgress", false, true]', src)
        self.assertIn("TLB_CARP_releaseInProgress", code("addon/functions/auto/fn_validateAutoDrop.sqf"))

    def test_ace_bookkeeping_follows_aces_own_order(self):
        """ACE reads the space left AFTER removing the item and then adds its size back.
        Doing it the other way round double-counts and the vehicle slowly gains capacity.
        """
        src = code(RELEASE)
        self.assertIn("ace_cargo_loaded", src)
        self.assertIn("ace_cargo_space", src)
        self.assertLess(src.index("_loaded deleteAt"), src.index("getCargoSpaceLeft"))

    def test_ace_loads_are_unhidden_through_aces_own_server_event(self):
        """ACE hides loaded objects and attaches them 100 m below the carrier. Its own
        event does the unhide, the reposition and the damage unblock in the order it
        documents as required."""
        self.assertIn('"ace_cargo_serverUnload"', code(RELEASE))

    def test_ace_integration_is_guarded_so_carp_runs_without_ace(self):
        src = code(RELEASE)
        self.assertIn('isNil "ace_cargo_fnc_getSizeItem"', src)
        self.assertIn('isNil "ace_cargo_fnc_getCargoSpaceLeft"', src)


class ReleasePathSplitTests(unittest.TestCase):
    def test_a_usaf_airframe_with_usaf_cargo_still_uses_usafs_own_release(self):
        src = code(SELECT)
        self.assertIn("USAF_CARGO_fnc_canDrop", src)
        self.assertIn('_source isEqualTo "usaf"', src)
        self.assertIn("USAF_Cargo_DropPos", src)

    def test_the_last_element_test_is_present(self):
        """canDrop selects `_cargos select (count _cargos - 1)` itself and ignores what
        it is handed. With a mixed manifest, asking it to drop a USAF load that is not
        last would release a different object than the one the solver computed for."""
        self.assertIn("_usafAboard select ((count _usafAboard) - 1)", code(SELECT))

    def test_the_split_can_be_overridden_for_measurement(self):
        """v0.10.0 inverted this. CARP's release is the default and USAF's is the
        fallback, but the fallback is kept BECAUSE it is the calibration reference --
        it is how a difference between the two paths gets measured rather than argued
        about. Deleting it would remove the only instrument for that."""
        src = code(SELECT)
        self.assertIn("TLB_CARP_setting_useUsafRelease", src)
        self.assertIn("TLB_CARP_setting_useUsafRelease", read(POSTINIT))
        self.assertNotIn("forceCarpRelease", src)

    def test_a_dry_run_reports_the_path_without_taking_it(self):
        """So the panel can show the pilot which release will run without a second copy
        of the predicate drifting out of step with this one."""
        src = code(SELECT)
        self.assertIn("_dryRun", src)
        self.assertIn('if (_dryRun) exitWith {"carp"}', src)
        self.assertIn("if (!_dryRun) then {[_carrier] spawn USAF_CARGO_fnc_canDrop}", src)

    def test_the_manifest_the_offset_and_the_path_are_still_reportable(self):
        """WAS on the panel. v0.11.2 removed the panel status block (control 9314) on a flown request.
        The dry-run predicate that let the panel show which release path would run is
        deliberately KEPT in fn_releaseSelected even with no caller in the UI: it is the
        only way to answer the question without a second copy of the predicate, and the
        console diagnostic uses the manifest the same way."""
        self.assertIn("_dryRun", code(SELECT))
        self.assertIn("TLB_CARP_fnc_getLoadedCargo", read("testing/mp_carp_diagnostic.sqf"))


class GenericProfileTests(unittest.TestCase):
    def setUp(self):
        self.model = json.loads((ROOT / "calibration" / "model.json").read_text(encoding="utf-8"))

    def test_any_aircraft_resolves_to_a_profile(self):
        src = code("addon/functions/aircraft/fn_resolveAircraftProfile.sqf")
        self.assertIn('_vehicle isKindOf "USAF_C17"', src)
        self.assertIn('_vehicle isKindOf "USAF_C130J"', src)
        self.assertIn('if (_vehicle isKindOf "Air") exitWith {"generic"}', src)

    def test_the_generic_profile_reports_good_like_any_other(self):
        """WAS: provisional-borrowed forces DEGRADED and gates Auto Drop.

        v0.14.0 removed the DEGRADED tier on the project owner's flown evidence: the C-17
        model held against the C-17, the C-130 and the V-44 Blackfish, and guided cargo
        absorbs the residual. A warning that fired on every drop of every airframe was
        furniture, not information.

        The NUMBERS never changed and that is the point: releaseDelayS and canopyRef in
        this profile were always the C-17's. Only what it called them changed."""
        generic = self.model["aircraft"]["generic"]
        self.assertEqual(generic["calibrationState"], "ready")
        self.assertEqual(generic["releaseDelayS"], self.model["aircraft"]["c17"]["releaseDelayS"])
        self.assertEqual(generic["canopyRef"], "empiricalC17")

    def test_the_generic_profile_carries_no_drop_position(self):
        """A dropPos here would silently hand a C-17's geometry to an airframe of any
        size. The bounding-box derivation must supply it instead."""
        self.assertNotIn("dropPos", self.model["aircraft"]["generic"])

    def test_the_generic_profile_records_who_decided_and_on_what_evidence(self):
        """A loosening of what CARP claims to know is exactly the kind of change that
        looks unexplained a year later. The note has to carry the decision, the date, the
        evidence, and what would count as a reason to reverse it."""
        note = self.model["aircraft"]["generic"]["profileSource"]
        self.assertIn("2026-09-20", note)
        self.assertIn("empiricalC17", note)
        self.assertIn("Blackfish", note)
        self.assertIn("OWNER-APPROVED", note)
        self.assertIn("measure it into its own profile", note)

    def test_the_generated_model_carries_it(self):
        """Never hand-edited: model.json is the source and the generator rewrites this."""
        self.assertIn('"generic"', read("addon/functions/generated/fn_getModel.sqf"))

    def test_the_calibrated_profiles_are_untouched(self):
        for key, state, canopy in [("c17", "ready", "empiricalC17"), ("c130", "zero-wind-measured", "empiricalC130")]:
            self.assertEqual(self.model["aircraft"][key]["calibrationState"], state)
            self.assertEqual(self.model["aircraft"][key]["canopyRef"], canopy)
            self.assertEqual(self.model["aircraft"][key]["releaseDelayS"], 0.5607)


class ConfidenceLineTests(unittest.TestCase):
    def test_the_borrowed_profile_warning_fits_the_hud(self):
        """"GENERIC PROFILE PROVISIONAL - CANOPY TABLE BORROWED - UNVERIFIED FOR THIS
        AIRFRAME" is 79 characters against the HUD's 26, so it truncated to "GENERIC
        PROFILE PROVISION" -- which reads as a status, not a warning."""
        src = code("addon/functions/guidance/fn_confidenceReason.sqf")
        self.assertIn("UNCAL AIRFRAME - EST ONLY", src)
        self.assertLessEqual(len("UNCAL AIRFRAME - EST ONLY"), 26)
        self.assertIn("WIND TABLES BORROWED", src)

    def test_nothing_phrases_a_confidence_reason_any_more(self):
        """WAS: fn_confidenceReason's wind branch must match the string the solver raises.

        v0.14.0 removed the DEGRADED tier on the project owner's flown evidence: the C-17
        model held against the C-17, the C-130 and the V-44 Blackfish, and guided cargo
        absorbs the residual. A warning that fired on every drop of every airframe was
        furniture, not information.

        fn_confidenceReason turned a warning into one short HUD line. With no warnings to
        phrase it is no longer called. It is left in the PBO rather than cut from a
        pre-binarized CfgFunctions in the same release that changes solver behaviour --
        dead code is cheaper than two risky changes at once."""
        self.assertNotIn(
            "TLB_CARP_fnc_confidenceReason",
            code("addon/functions/guidance/fn_buildWorldSolution.sqf"),
        )


class NoCargoWordingTests(unittest.TestCase):
    def test_a_pilot_with_an_ace_load_is_not_told_he_has_no_usaf_cargo(self):
        for rel in [
            "addon/functions/auto/fn_validateAutoDrop.sqf",
            "addon/functions/guidance/fn_buildWorldSolution.sqf",
        ]:
            src = code(rel)
            self.assertNotIn("NO USAF CARGO", src)
            self.assertIn("NO CARGO ABOARD", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)

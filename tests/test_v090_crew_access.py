"""v0.9.0 -- crew sync that cannot quietly stop, and a CARP Computer to use it with.

A field report said pilot and co-pilot never saw each other's CARP changes, in either
direction, after v0.7.0 and v0.8.4 had both set out to fix exactly that. Tracing the
v0.7.0 sync turned up five ways it could stop working with nothing on screen:

1. fn_refreshPanel published as its LAST statement, after painting every list and the
   whole telemetry block. Any script error while painting ended the call first, and
   nothing ever retried the change.
2. The same kind of error inside fn_syncApply's repaint left TLB_CARP_state_syncApplying
   raised for good, and fn_syncPublish refuses to run while it is.
3. A record was adopted only if its sequence number beat a counter each client kept for
   itself. Two crew editing at once, or Zeus moving a player between aircraft, could
   leave that counter ahead of the aircraft, after which every record the crew
   published was ignored.
4. Every publish wrote all fourteen fields from the publisher's own copy, so a client
   that had missed an update erased the crew's other settings, and of two simultaneous
   edits only the last write to reach the server survived.
5. A crew member on a different build neither sent nor received, and nothing said so.

The contracts below are static assertions over source, like the rest of the suite.
ProtocolModelTests re-implements the new rules in Python -- the way
empirical_reference.py does for the canopy maths -- to show they converge where the old
ones did not. None of it proves the sync works across a real network;
docs/validation/V090_RUNTIME_VALIDATION.md is what does.
"""
from pathlib import Path
import contextlib
import hashlib
import importlib.util
import io
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]

POSTINIT = "addon/functions/fn_postInit.sqf"
SNAPSHOT = "addon/functions/sync/fn_syncSnapshot.sqf"
PUBLISH = "addon/functions/sync/fn_syncPublish.sqf"
MERGE = "addon/functions/sync/fn_syncMerge.sqf"
APPLY = "addon/functions/sync/fn_syncApply.sqf"
TICK = "addon/functions/sync/fn_syncTick.sqf"
REFRESH = "addon/functions/ui/fn_refreshPanel.sqf"
OPEN = "addon/functions/ui/fn_openPanel.sqf"
TELEMETRY = "addon/functions/ui/fn_updatePanelTelemetry.sqf"
CAN_USE = "addon/functions/access/fn_canUseCarp.sqf"
HAS_COMPUTER = "addon/functions/access/fn_hasComputer.sqf"
ITEMS_CONFIG = "items/config.cpp"
ICON = "items/data/tlb_carp_computer_ca.paa"
GUARD = "if (!hasInterface) exitWith {"


def read(rel: str) -> str:
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.exists() else ""


def code(rel: str) -> str:
    """Source with comments stripped, string literals intact."""
    sys.path.insert(0, str(ROOT / "tools"))
    from strip_sqf_comments import strip_comments

    return strip_comments((ROOT / rel).read_text(encoding="utf-8"))


def load_tool(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def handler(src: str, event: str) -> str:
    body = src[src.index(f'["{event}", {{'):]
    return body[:body.index("call CBA_fnc_addEventHandler")]


class PublishBeforePaintTests(unittest.TestCase):
    """Defect 1: a painting error must not be able to swallow the change."""

    def test_refresh_publishes_before_it_paints_anything(self):
        src = code(REFRESH)
        publish = src.index("TLB_CARP_fnc_syncPublish")
        self.assertLess(publish, src.index("TLB_CARP_state_panelRefreshing = true;"))
        self.assertLess(publish, src.index("lbClear"))
        self.assertLess(publish, src.index("TLB_CARP_fnc_updatePanelTelemetry"))
        self.assertEqual(src.count("call TLB_CARP_fnc_syncPublish"), 1)

    def test_the_owner_cargo_reset_is_decided_before_the_publish(self):
        src = code(REFRESH)
        self.assertLess(src.index("TLB_CARP_state_cargoCount = -1;"), src.index("TLB_CARP_fnc_syncPublish"))

    def test_refresh_never_runs_scheduled(self):
        """config.bin's onLoad spawns the refresh; suspended half way, it left the panel's
        lists deaf and let a record arrive in the middle of a publish."""
        src = code(REFRESH)
        self.assertIn("if (canSuspend) exitWith {", src)
        self.assertIn("[{[] call TLB_CARP_fnc_refreshPanel}] call CBA_fnc_execNextFrame;", src)
        self.assertLess(src.index("canSuspend"), src.index("TLB_CARP_fnc_syncPublish"))


class StrandedGuardTests(unittest.TestCase):
    """Defect 2: a flag left raised by a script error must not last."""

    def test_the_tick_lowers_both_guards_before_anything_else(self):
        src = code(TICK)
        first = src.index("objectParent player")
        self.assertLess(src.index("TLB_CARP_state_syncApplying = false;"), first)
        self.assertLess(src.index("TLB_CARP_state_panelRefreshing = false;"), first)

    def test_apply_marks_the_record_adopted_before_any_side_effect(self):
        src = code(APPLY)
        marked = max(src.index("TLB_CARP_state_syncRev = _rev;"), src.index("TLB_CARP_state_syncUid = _uid;"))
        for side_effect in [
            "TLB_CARP_fnc_setDZ", "TLB_CARP_fnc_clearDZ", "TLB_CARP_fnc_unlockRunIn",
            "TLB_CARP_fnc_syncReconcile", "TLB_CARP_fnc_refreshPanel",
        ]:
            self.assertLess(marked, src.index(side_effect), side_effect)


class AdoptionTests(unittest.TestCase):
    """Defect 3: the aircraft's record is the arbiter, not a counter on the client."""

    def test_the_tick_adopts_any_record_that_is_not_the_one_it_holds(self):
        src = code(TICK)
        self.assertIn('_aircraft getVariable ["TLB_CARP_carpRecord", []]', src)
        self.assertIn("!([_record # 0, _record # 1] isEqualTo [TLB_CARP_state_syncRev, TLB_CARP_state_syncUid])", src)

    def test_no_client_side_counter_is_left_to_veto_a_record(self):
        for rel in (PUBLISH, MERGE, APPLY, TICK, POSTINIT, OPEN, REFRESH):
            src = code(rel)
            self.assertNotIn("TLB_CARP_state_syncSeq", src, rel)
            self.assertNotIn("_incomingSeq", src, rel)
            self.assertNotIn("TLB_CARP_state_syncLastPayload", src, rel)

    def test_the_doorbell_only_ever_moves_a_client_forward(self):
        body = handler(code(POSTINIT), "TLB_CARP_carpRecordChanged")
        self.assertIn('(_record # 0) > (missionNamespace getVariable ["TLB_CARP_state_syncRev", -1])', body)
        self.assertIn("TLB_CARP_fnc_canUseCarp", body)
        self.assertIn("TLB_CARP_fnc_syncApply", body)

    def test_changing_aircraft_forgets_what_was_adopted(self):
        src = code(TICK)
        self.assertIn('!(_aircraft isEqualTo (missionNamespace getVariable ["TLB_CARP_state_syncAircraft", objNull]))', src)

    def test_opening_the_panel_adopts_before_the_display_exists(self):
        src = code(OPEN)
        self.assertLess(src.index("TLB_CARP_fnc_syncTick"), src.index("createDisplay"))


class ServerMergeTests(unittest.TestCase):
    """Defect 4: only changed fields travel, and one machine writes the record."""

    def test_publish_sends_only_the_fields_changed_here(self):
        src = code(PUBLISH)
        self.assertIn('missionNamespace getVariable ["TLB_CARP_state_syncBase", []]', src)
        self.assertIn("_changes pushBack [_forEachIndex, _x];", src)
        self.assertIn("if ((count _changes) isEqualTo 0) exitWith {false};", src)
        self.assertIn("TLB_CARP_state_syncBase = +_local;", src)

    def test_publish_hands_the_patch_to_the_server(self):
        src = code(PUBLISH)
        self.assertIn("private _patch = [_aircraft, _changes, _local, _uid, name player, TLB_CARP_VERSION];", src)
        self.assertIn('["TLB_CARP_carpPatch", _patch] call CBA_fnc_serverEvent;', src)

    def test_without_carp_on_the_server_the_client_merges_and_says_so(self):
        src = code(PUBLISH)
        self.assertIn('missionNamespace getVariable ["TLB_CARP_serverVersion", ""]', src)
        self.assertIn("_patch call TLB_CARP_fnc_syncMerge;", src)
        self.assertIn("the server is not running TLB CARP", src)

    def test_only_the_merge_writes_the_record(self):
        writers = []
        for path in (ROOT / "addon" / "functions").rglob("*.sqf"):
            rel = path.relative_to(ROOT).as_posix()
            if 'setVariable ["TLB_CARP_carpRecord"' in code(rel):
                writers.append(rel)
        self.assertEqual(writers, [MERGE])

    def test_the_merge_lands_each_change_on_the_record_as_it_stands(self):
        src = code(MERGE)
        self.assertIn('private _record = _aircraft getVariable ["TLB_CARP_carpRecord", []];', src)
        self.assertIn("private _payload = if (_hasRecord) then {+(_record # 4)} else {+_senderPayload};", src)
        self.assertIn("if (_index >= 0 && {_index < (count _payload)}) then {_payload set [_index, _value]};", src)
        self.assertIn("private _rev = (if (_hasRecord) then {_record # 0} else {0}) + 1;", src)
        self.assertIn("private _newRecord = [_rev, _uid, _author, _version, _payload];", src)
        self.assertIn('_aircraft setVariable ["TLB_CARP_carpRecord", _newRecord, true];', src)
        self.assertIn('["TLB_CARP_carpRecordChanged", [_aircraft, _newRecord], crew _aircraft] call CBA_fnc_targetEvent;', src)

    def test_the_server_half_is_registered_where_the_server_runs(self):
        post = code(POSTINIT)
        head = post[:post.index(GUARD)]
        self.assertIn('["TLB_CARP_fnc_syncMerge", "\\x\\tlbcarp\\addons\\drop_computer\\functions\\sync\\fn_syncMerge.sqf"]', head)
        body = handler(head, "TLB_CARP_carpPatch")
        self.assertIn("if (!isServer) exitWith {};", body)
        self.assertIn("_this call TLB_CARP_fnc_syncMerge;", body)
        self.assertIn('if (isServer) then {missionNamespace setVariable ["TLB_CARP_serverVersion", TLB_CARP_VERSION, true]};', head)

    def test_the_payload_length_agrees_between_snapshot_and_apply(self):
        snapshot = code(SNAPSHOT)
        payload = snapshot[snapshot.index("["):snapshot.rindex("]") + 1]
        depth, fields = 0, 1
        for ch in payload[1:-1]:
            if ch in "[(":
                depth += 1
            elif ch in "])":
                depth -= 1
            elif ch == "," and depth == 0:
                fields += 1
        # Eighteen since v0.11.1. See the note in test_v070_multiplayer: the count
        # itself is arbitrary, its agreement with fn_syncApply is not.
        self.assertEqual(fields, 18)
        self.assertIn("(count _payload) isEqualTo 18", code(APPLY))


class VersionTests(unittest.TestCase):
    """Defect 5: a mismatched build has to announce itself."""

    def test_the_record_carries_its_author_version_and_apply_checks_it(self):
        src = code(APPLY)
        self.assertIn('_record params ["_rev", "_uid", "_author", "_version", "_payload"];', src)
        self.assertIn("if !(_version isEqualTo TLB_CARP_VERSION) then {", src)
        self.assertIn("TLB_CARP_state_syncVersionWarned", src)

    def test_a_crew_member_on_the_old_sync_is_named(self):
        src = code(TICK)
        self.assertIn('_aircraft getVariable ["TLB_CARP_carpIntent", []]', src)
        self.assertIn("TLB_CARP_state_syncLegacyWarned", src)

    def test_nothing_writes_the_old_record_any_more(self):
        for path in (ROOT / "addon" / "functions").rglob("*.sqf"):
            rel = path.relative_to(ROOT).as_posix()
            self.assertNotIn('setVariable ["TLB_CARP_carpIntent"', code(rel), rel)

    def test_which_record_each_seat_holds_is_still_reportable(self):
        """WAS on the panel as the CREW line. v0.11.2 removed the panel status block (control 9314) on a flown request.

        Sync is now checked the better way, and the way the acceptance list asks for: by
        watching the CONTROLS change on the other seat's panel, which is the thing that
        actually has to work. A revision number agreeing proves the record arrived; a DZ
        appearing in the other combo proves it was applied.

        The console diagnostic still reports the revision, the author and the version on
        every machine, which is what settles a disagreement."""
        diag = read("testing/mp_carp_diagnostic.sqf")
        self.assertIn("TLB_CARP_state_syncRev", diag)
        self.assertIn("TLB_CARP_carpRecord", diag)
        self.assertIn("TLB_CARP_fnc_hasComputer", diag)


class AccessTests(unittest.TestCase):
    """The CARP Computer, and CARP offered from the airframe rather than the player."""

    def test_the_rule_is_inside_the_aircraft_supported_and_carrying_the_computer(self):
        src = code(CAN_USE)
        self.assertIn("if !((objectParent _unit) isEqualTo _aircraft) exitWith {false};", src)
        self.assertIn("TLB_CARP_fnc_resolveAircraftProfile", src)
        self.assertIn('!(missionNamespace getVariable ["TLB_CARP_setting_requireComputer", true]) || {[_unit] call TLB_CARP_fnc_hasComputer}', src)
        self.assertIn('"TLB_CARP_Computer"', code(HAS_COMPUTER))

    def test_every_way_in_asks_the_same_rule(self):
        post = code(POSTINIT)
        self.assertIn("[player, _vehicle] call TLB_CARP_fnc_canUseCarp", code(OPEN))
        self.assertIn("[player, _aircraft] call TLB_CARP_fnc_canUseCarp", code(PUBLISH))
        self.assertIn("[player, _aircraft] call TLB_CARP_fnc_canUseCarp", code(TICK))
        self.assertIn("TLB_CARP_fnc_canUseCarp", handler(post, "TLB_CARP_carpRecordChanged"))

    def test_the_access_functions_are_registered_above_the_interface_guard(self):
        post = code(POSTINIT)
        head = post[:post.index(GUARD)]
        prefix = "\\x\\tlbcarp\\addons\\drop_computer\\functions\\access\\"
        for name in ("hasComputer", "canUseCarp"):
            self.assertIn(f'["TLB_CARP_fnc_{name}", "{prefix}fn_{name}.sqf"]', head)

    def test_the_requirement_is_a_server_forced_setting_that_defaults_on(self):
        lines = [ln for ln in code(POSTINIT).splitlines() if "TLB_CARP_setting_requireComputer" in ln and "CBA_fnc_addSetting" in ln]
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].rstrip().endswith('["TLB CARP", "Access"], true, 1] call CBA_fnc_addSetting;'))

    def test_the_panel_is_offered_from_the_aircraft_not_from_the_player(self):
        """Inside a vehicle the interaction key renders that vehicle's ACE_SelfActions
        (ace_interact_menu fnc_renderActionPoints), so that is where it belongs."""
        post = code(POSTINIT)
        self.assertIn('["Air", 1, ["ACE_SelfActions"], _openAction, true] call ace_interact_menu_fnc_addActionToClass;', post)
        self.assertNotIn('["CAManBase", 1, ["ACE_SelfActions"], _openAction, true]', post)
        action = post[post.index('"TLB_CARP_Open"'):post.index("call ace_interact_menu_fnc_createAction", post.index('"TLB_CARP_Open"'))]
        self.assertIn("[_player, _target] call TLB_CARP_fnc_canUseCarp", action)
        self.assertIn('"\\x\\tlbcarp\\addons\\items\\data\\tlb_carp_computer_ca.paa"', action)

    def test_losing_access_closes_the_panel(self):
        src = code(TICK)
        lost = src[src.index("if (isNull _aircraft || {!([player, _aircraft] call TLB_CARP_fnc_canUseCarp)}) exitWith {"):]
        lost = lost[:lost.index("};") + 2]
        self.assertIn("closeDisplay 2", lost)


class ItemsAddonTests(unittest.TestCase):
    def setUp(self):
        self.config = (ROOT / ITEMS_CONFIG).read_text(encoding="utf-8")
        self.build = load_tool("build_release")

    def test_the_item_is_a_cba_misc_item_with_the_class_the_rule_checks(self):
        self.assertIn("class TLB_CARP_Computer: CBA_MiscItem {", self.config)
        self.assertIn('weapons[] = {"TLB_CARP_Computer"};', self.config)
        self.assertIn('requiredAddons[] = {"cba_common"};', self.config)

    def test_the_icon_path_resolves_inside_the_items_pbo(self):
        picture = f'picture = "\\{self.build.ITEMS_PREFIX}\\data\\tlb_carp_computer_ca.paa";'
        self.assertIn(picture, self.config)
        icon = ROOT / ICON
        self.assertTrue(icon.is_file())
        self.assertGreater(icon.stat().st_size, 1000)

    def test_the_model_is_the_vanilla_rugged_tablet(self):
        self.assertIn('model = "\\a3\\props_f_exp_a\\Military\\Equipment\\Tablet_02_F.p3d";', self.config)

    def test_the_launcher_logo_ships_in_the_items_pbo(self):
        """mod.cpp points into TLB_CARP_Items.pbo, so every path it names has to be a
        file under items/, or the launcher shows a blank tile."""
        mod = (ROOT / "packaging/mod.cpp").read_text(encoding="utf-8")
        prefix = "\\" + self.build.ITEMS_PREFIX
        for key, name in (("picture", "logo_ca"), ("logo", "logo_ca"), ("logoOver", "logo_ca"), ("logoSmall", "logo_small_ca")):
            self.assertIn(f'{key} = "{prefix}\\data\\{name}.paa";', mod)
            self.assertTrue((ROOT / "items" / "data" / f"{name}.paa").is_file(), name)
        self.assertIn('action = "https://github.com/TLB-MilSim/TLB-CARP-System";', mod)
        self.assertTrue((ROOT / "docs" / "images" / "logo.png").is_file())

    def test_the_items_addon_ships_and_is_verified_with_the_release(self):
        src = (ROOT / "tools/build_release.py").read_text(encoding="utf-8")
        self.assertIn("items", self.build.SOURCE_TREES)
        self.assertIn('(f"{MOD_DIR}/addons/{ITEMS_PBO_NAME}", items_bytes)', src)
        self.assertIn("pack_pbo.pack_directory(ROOT / ITEMS_SOURCE, ITEMS_PREFIX, args.version)", src)
        self.assertIn("(items_path, ROOT / ITEMS_SOURCE)", src)


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.pack = load_tool("pack_pbo")
        self.build = load_tool("build_release")

    def test_pack_directory_is_deterministic_and_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "items"
            (src / "data").mkdir(parents=True)
            (src / "config.cpp").write_bytes(b"class CfgPatches {};")
            (src / "data" / "icon_ca.paa").write_bytes(b"PAA")
            first = self.pack.pack_directory(src, "x\\tlbcarp\\addons\\items", "0.9.0.0")
            self.assertEqual(first, self.pack.pack_directory(src, "x\\tlbcarp\\addons\\items", "0.9.0.0"))
            self.assertEqual(first[-20:], hashlib.sha1(first[:-21]).digest())

            pbo = Path(tmp) / "items.pbo"
            pbo.write_bytes(first)
            props, entries = self.pack.parse_pbo_header(pbo)
            self.assertEqual(dict(props), {"prefix": "x\\tlbcarp\\addons\\items", "version": "0.9.0.0"})
            self.assertEqual([e["name"] for e in entries], ["config.cpp", "data\\icon_ca.paa"])
            self.assertEqual(self.build.verify_pbo_against_source(pbo, "0.9.0.0", src), [])

    def test_the_base_pbo_is_taken_by_name_not_by_position(self):
        """Release ZIP entries are sorted, so TLB_CARP_Items.pbo now comes first."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release = root / "release.zip"
            with zipfile.ZipFile(release, "w") as zf:
                zf.writestr(f"{self.build.MOD_DIR}/addons/{self.build.ITEMS_PBO_NAME}", b"items")
                zf.writestr(f"{self.build.MOD_DIR}/addons/{self.build.PBO_NAME}", b"drop computer")
            self.assertEqual(self.build.extract_base_pbo(release, root / "a.pbo").read_bytes(), b"drop computer")

            legacy = root / "legacy.zip"
            with zipfile.ZipFile(legacy, "w") as zf:
                zf.writestr("@USAF_CARP_System/addons/usafdc_drop_computer.pbo", b"old drop computer")
            self.assertEqual(self.build.extract_base_pbo(legacy, root / "b.pbo").read_bytes(), b"old drop computer")

    def test_deploy_lands_every_pbo_in_the_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release = root / "release.zip"
            with zipfile.ZipFile(release, "w") as zf:
                zf.writestr(f"{self.build.MOD_DIR}/addons/{self.build.PBO_NAME}", b"drop computer")
                zf.writestr(f"{self.build.MOD_DIR}/addons/{self.build.ITEMS_PBO_NAME}", b"items")
                zf.writestr(f"{self.build.MOD_DIR}/mod.cpp", b'name = "test";')
            target = root / "mod"
            with contextlib.redirect_stdout(io.StringIO()):
                self.build.deploy(release, target)
            addons = target / "addons"
            self.assertEqual((addons / self.build.PBO_NAME).read_bytes(), b"drop computer")
            self.assertEqual((addons / self.build.ITEMS_PBO_NAME).read_bytes(), b"items")


class ProtocolModelTests(unittest.TestCase):
    """The v0.9.0 rules, re-implemented in Python, against the failures they replace.

    Server.merge is fn_syncMerge, Client.edit is a panel handler followed by
    fn_syncPublish, Client.tick is fn_syncTick's adoption, Client.doorbell is the
    TLB_CARP_carpRecordChanged handler, and Client.apply is fn_syncApply's bookkeeping.
    """

    DEFAULTS = ["", "", "TOUCHDOWN", "", False, 0, 0, 3000, 500, -1, False, 0, False, False]
    DZ, AGL = 1, 7

    class Server:
        def __init__(self):
            self.record = None

        def merge(self, patch):
            changes, sender_payload, uid = patch
            payload = list(self.record["payload"]) if self.record else list(sender_payload)
            for index, value in changes:
                payload[index] = value
            self.record = {"rev": (self.record["rev"] if self.record else 0) + 1, "uid": uid, "payload": payload}
            return self.record

    class Client:
        def __init__(self, uid, defaults):
            self.uid = uid
            self.local = list(defaults)
            self.base = None
            self.rev, self.author = -1, ""

        def apply(self, record):
            self.rev, self.author = record["rev"], record["uid"]
            self.local = list(record["payload"])
            self.base = list(self.local)

        def tick(self, record):
            if record is not None and (record["rev"], record["uid"]) != (self.rev, self.author):
                self.apply(record)
            elif record is None and self.base is None:
                self.base = list(self.local)

        def doorbell(self, record):
            if record["rev"] > self.rev:
                self.apply(record)

        def edit(self, index, value):
            self.local[index] = value
            changes = [(i, v) for i, v in enumerate(self.local) if self.base is None or v != self.base[i]]
            self.base = list(self.local)
            return (changes, list(self.local), self.uid) if changes else None

    def crew(self):
        server = self.Server()
        pilot, copilot = self.Client("pilot", self.DEFAULTS), self.Client("copilot", self.DEFAULTS)
        for client in (pilot, copilot):
            client.tick(server.record)
        return server, pilot, copilot

    def ring(self, record, *clients):
        for client in clients:
            client.doorbell(record)

    def test_two_fields_edited_in_the_same_instant_both_survive(self):
        server, pilot, copilot = self.crew()
        dz_patch = pilot.edit(self.DZ, "DZ ALPHA")
        agl_patch = copilot.edit(self.AGL, 2500)
        # Either patch may reach the server first.
        self.ring(server.merge(agl_patch), pilot, copilot)
        self.ring(server.merge(dz_patch), pilot, copilot)
        for client in (pilot, copilot):
            client.tick(server.record)
            self.assertEqual(client.local[self.DZ], "DZ ALPHA")
            self.assertEqual(client.local[self.AGL], 2500)

    def test_the_same_field_edited_at_once_settles_on_one_value_everywhere(self):
        server, pilot, copilot = self.crew()
        first = pilot.edit(self.AGL, 1800)
        second = copilot.edit(self.AGL, 2200)
        self.ring(server.merge(second), pilot, copilot)
        self.ring(server.merge(first), pilot, copilot)
        for client in (pilot, copilot):
            client.tick(server.record)
        self.assertEqual(pilot.local, copilot.local)
        self.assertEqual(pilot.local[self.AGL], server.record["payload"][self.AGL])

    def test_a_client_that_missed_an_update_cannot_erase_it(self):
        server, pilot, copilot = self.crew()
        record = server.merge(pilot.edit(self.DZ, "DZ ALPHA"))
        pilot.doorbell(record)
        # The co-pilot never hears about it, and edits the AGL on top of stale state.
        server.merge(copilot.edit(self.AGL, 2500))
        for client in (pilot, copilot):
            client.tick(server.record)
            self.assertEqual(client.local[self.DZ], "DZ ALPHA")
            self.assertEqual(client.local[self.AGL], 2500)

    def test_a_client_holding_a_higher_revision_from_another_aircraft_still_adopts(self):
        """v0.7.0 dropped every record numbered below its own counter."""
        server, pilot, copilot = self.crew()
        copilot.rev, copilot.author = 50, "elsewhere"
        record = server.merge(pilot.edit(self.DZ, "DZ ALPHA"))
        copilot.doorbell(record)
        self.assertNotEqual(copilot.local[self.DZ], "DZ ALPHA")
        copilot.tick(server.record)
        self.assertEqual(copilot.local[self.DZ], "DZ ALPHA")

    def test_a_late_doorbell_never_rolls_a_client_back(self):
        server, pilot, copilot = self.crew()
        older = server.merge(pilot.edit(self.AGL, 1800))
        newer = server.merge(pilot.edit(self.AGL, 2200))
        copilot.doorbell(newer)
        copilot.doorbell(older)
        self.assertEqual(copilot.local[self.AGL], 2200)

    def test_opening_the_panel_after_adopting_sends_nothing(self):
        server, pilot, copilot = self.crew()
        record = server.merge(pilot.edit(self.DZ, "DZ ALPHA"))
        copilot.tick(record)
        changes = [(i, v) for i, v in enumerate(copilot.local) if v != copilot.base[i]]
        self.assertEqual(changes, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

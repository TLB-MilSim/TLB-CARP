"""v0.13.0 -- CARP loads cargo as well as dropping it, on any aircraft.

v0.10.0 took the release in house. This takes the other half.

Until now a load had to arrive through USAF's load action, ACE cargo, vanilla
vehicle-in-vehicle or a mission maker's attachTo. A vehicle Zeus merely placed in the
fuselage was carried by nothing, so droppable by nothing -- which is exactly what a field
report said, twice: "loaded 1 car into C130 with Zeus and it doesn't show in CARP".

THREE MECHANISMS, AND THE ORDER IS THE DESIGN

"Any cargo aircraft from any mod" cannot be one mechanism, because Arma has no shared idea
of a cargo hold. It has three partial ones, and the right answer is to use the most
supported one each airframe offers rather than to impose ours on all of them.

  viv   The aircraft declares VehicleTransport and the engine does everything -- ramp,
        capacity, bookkeeping. Any mod that configured it gets its author's behaviour.
  usaf  The airframe has USAF_Cargo_LoadPos. We use the POSITION, not the function:
        hand-placed coordinates beat anything derivable, and USAF need not be installed.
  carp  Neither, so the hold is derived from the bounding box.

WHY A DERIVED HOLD IS ACCEPTABLE HERE AND A DERIVED RELEASE POINT WOULD NOT BE

Nothing ballistic depends on where a load sits in the hold. It rides attached until
release, and the RELEASE offset -- which reproduces the C-17's hand-placed value to within
two centimetres -- is what the solver is calibrated against. The load position only has to
look like the inside of an aircraft and ride with it.

LOCALITY IS THE PART THAT FAILS SILENTLY

setVehicleCargo wants the CARRIER's machine; attachTo is local-effect on the object being
attached, so it wants the CARGO's machine. On a dedicated server with a Zeus-spawned truck
and a player-flown aircraft those are different machines, and getting it wrong does
nothing at all -- which is how guided cargo failed for a whole release.
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


CAN = "addon/functions/cargo/fn_canLoadCargo.sqf"
LOAD = "addon/functions/cargo/fn_loadCargo.sqf"
VIV = "addon/functions/cargo/fn_loadViv.sqf"
ATTACH = "addon/functions/cargo/fn_loadAttach.sqf"
OFFSET = "addon/functions/cargo/fn_loadModelOffset.sqf"
NEAREST = "addon/functions/cargo/fn_nearestLoader.sqf"
UNLOAD = "addon/functions/cargo/fn_unloadCargo.sqf"
UNATTACH = "addon/functions/cargo/fn_unloadAttach.sqf"
MANIFEST = "addon/functions/cargo/fn_cargoManifest.sqf"
POSTINIT = "addon/functions/fn_postInit.sqf"


class MechanismChoiceTests(unittest.TestCase):
    def test_the_engines_own_mechanism_is_preferred(self):
        """Any mod that configured VehicleTransport gets the behaviour its author
        intended -- ramp animation, declared capacity, engine bookkeeping. Imposing ours
        over the top would be worse on every airframe that did the work."""
        src = code(CAN)
        viv = src.index("canVehicleCargo")
        derived = src.index("TLB_CARP_fnc_loadModelOffset")
        self.assertLess(viv, derived)

    def test_the_position_is_asked_for_once(self):
        """v0.16.3. THIS TEST USED TO PIN THE BUG.

        It asserted that fn_canLoadCargo contains the literal USAF_Cargo_LoadPos -- and it
        passed for three releases, because the string was there. The property was not:
        a scan of every PBO in both USAF mods finds zero occurrences of it anywhere. So the
        usaf branch never fired on any airframe, every load fell through to the bounding-box
        derivation, and a flown C-130 put a vehicle behind its own tail.

        A static test can only ever check that our source says what we meant. It cannot
        check that what we meant exists. The lesson is not "test harder" -- it is that a
        config key we do not own has to be read out of the mod that defines it before it is
        relied on.

        What is pinned now is the structural half, which a static test CAN hold: one reader
        for the position. canLoadCargo and loadCargo both ask fn_loadModelOffset, so "can I
        load this" and "where does it go" cannot give different answers."""
        can, load = code(CAN), code(LOAD)
        self.assertIn("TLB_CARP_fnc_loadModelOffset", can)
        self.assertIn("TLB_CARP_fnc_loadModelOffset", load)
        self.assertNotIn("USAF_Cargo_LoadPos", can)
        self.assertNotIn("USAF_Cargo_LoadPos", load)
        # Neither may read hold geometry out of the config itself any more.
        self.assertNotIn("USAF_Cargo_endOffset", can)
        self.assertNotIn("USAF_Cargo_endOffset", load)

    def test_usafs_positions_are_used_without_usafs_code(self):
        """Hand-placed coordinates beat anything derivable, and reading a config entry
        does not require the mod that defines it to be loaded.

        The properties are the ones USAF actually publishes, verified against the shipped
        PBOs: endOffset is where its own loadCargo stacks from, and Max* are the limits its
        canLoad enforces -- length and weight CUMULATIVELY, which is what makes MaxLength
        the usable hold length rather than a per-load cap."""
        off = code(OFFSET)
        self.assertIn("USAF_Cargo_endOffset", off)
        for limit in ["USAF_Cargo_MaxWidth", "USAF_Cargo_MaxLength",
                      "USAF_Cargo_MaxHeight", "USAF_Cargo_MaxWeight"]:
            self.assertIn(limit, off)
        self.assertNotIn("USAF_CARGO_fnc", code(CAN))
        self.assertNotIn("USAF_CARGO_fnc", code(LOAD))
        self.assertNotIn("USAF_CARGO_fnc", off)

    def test_refusing_is_a_result_not_an_error(self):
        """A jet that will not take a truck is correct behaviour, and the reason string
        is what the interaction menu shows."""
        src = code(CAN)
        for reason in ["NOT AN AIRCRAFT", "ALREADY ABOARD", "WILL NOT FIT", "NOT A LOADABLE TYPE"]:
            self.assertIn(reason, src)

    def test_only_types_the_manifest_can_see_are_loadable(self):
        """A load CARP cannot find is a load CARP cannot drop, so the two type sets have
        to be the same one."""
        can, manifest = code(CAN), code(MANIFEST)
        for kind in ["LandVehicle", "Ship", "ThingX", "ReammoBox_F"]:
            self.assertIn(kind, can)
            self.assertIn(kind, manifest)

    def test_a_load_already_held_by_something_is_refused(self):
        src = code(CAN)
        self.assertIn("isNull (attachedTo _cargo)", src)
        self.assertIn("isNull (isVehicleCargo _cargo)", src)
        self.assertIn("TLB_CARP_fnc_getLoadedCargo", src)

    def test_the_menu_predicate_and_the_action_ask_the_same_function(self):
        """Offering Load and then refusing it is worse than not offering it."""
        self.assertIn("TLB_CARP_fnc_canLoadCargo", code(NEAREST))
        self.assertIn("TLB_CARP_fnc_nearestLoader", code(POSTINIT))


class LocalityTests(unittest.TestCase):
    def test_vehicle_in_vehicle_runs_where_the_carrier_is_local(self):
        self.assertIn('remoteExec ["TLB_CARP_fnc_loadViv", _carrier]', code(LOAD))
        self.assertIn("if !(local _carrier) exitWith", code(VIV))

    def test_the_attach_runs_where_the_cargo_is_local(self):
        """attachTo is local-effect on the object being attached. On a dedicated server a
        Zeus-spawned truck belongs to the server, not to the player who asked."""
        self.assertIn('remoteExec ["TLB_CARP_fnc_loadAttach", _cargo]', code(LOAD))
        self.assertIn("if !(local _cargo) exitWith", code(ATTACH))

    def test_the_unload_splits_the_same_way(self):
        """v0.13.1 corrected the viv half: the unload idiom is `objNull setVehicleCargo
        _cargo`, so the CARGO is the operand whose locality matters, not the carrier.
        Loading is the asymmetric case -- its left operand IS the carrier."""
        src = code(UNLOAD)
        self.assertIn('remoteExec ["TLB_CARP_fnc_unloadViv", _cargo]', src)
        self.assertIn('remoteExec ["TLB_CARP_fnc_unloadAttach", _cargo]', src)
        self.assertIn("if !(local _cargo) exitWith", code(UNATTACH))

    def test_every_new_function_is_registered(self):
        """config.bin declares functions now, but the compile table is still what these
        use -- and a remoteExec to a name that resolves to nil does nothing, silently."""
        post = read(POSTINIT)
        for name in ["loadModelOffset", "canLoadCargo", "loadCargo", "loadViv", "loadAttach",
                     "nearestLoader", "unloadCargo", "unloadViv", "unloadAttach"]:
            self.assertIn(f"TLB_CARP_fnc_{name}", post, name)
            self.assertIn(f"fn_{name}.sqf", post, name)


class HoldDerivationTests(unittest.TestCase):
    def test_the_derivation_refuses_rather_than_clipping(self):
        """Better to refuse a load that would have fitted than to put a truck through a
        wing. boundingBoxReal includes the wings; there is no interior volume to ask."""
        src = code(OFFSET)
        self.assertIn("if (_cargoWide > _holdWide || {_cargoTall > _holdTall}) exitWith {[]}", src)
        self.assertIn("exitWith {[]}", src)

    def test_a_mission_can_override_the_derivation(self):
        """The same escape hatch TLB_CARP_dropPos gives the release."""
        self.assertIn('_carrier getVariable ["TLB_CARP_loadPos", []]', code(OFFSET))

    def test_the_load_is_lifted_by_its_own_origin_offset(self):
        """The model origin is not the bottom of the model. Without this a tall vehicle is
        buried to its axles in the floor."""
        self.assertIn("_floorZ - (_gMin # 2)", code(OFFSET))

    def test_loads_stack_forward_and_the_order_is_load_bearing(self):
        """The manifest is last-in-first-out at release, so stacking forward means the
        load nearest the ramp leaves first -- which is what a loadmaster expects and what
        makes the guided stick spacing match how the aircraft was packed."""
        src = code(OFFSET)
        self.assertIn("TLB_CARP_loadSlotY", src)
        self.assertIn("TLB_CARP_fnc_getLoadedCargo", src)


class LoadStateTests(unittest.TestCase):
    def test_the_load_is_squared_to_the_aircraft(self):
        """attachTo keeps the object's world orientation, so a truck driven up at an angle
        stays at that angle inside the hold."""
        # v0.16.4: read through getPosASL. getPos on an ATTACHED object returns its offset
        # from the parent, which opened a canopy at the ramp and destroyed an aircraft.
        # See tests/test_v0164_canopy_altitude.py. The contract here is unchanged.
        self.assertIn("setVectorDirAndUp [[0, -1, 0], [0, 0, 1]]", code(ATTACH))

    def test_collision_is_disabled_both_ways_at_load_time(self):
        """An attached vehicle inside a fuselage is interpenetrating it by definition.
        USAF disables it at release; doing it at load means the load is not fighting the
        airframe for the whole flight."""
        src = code(ATTACH)
        self.assertIn("_cargo disableCollisionWith _carrier;", src)
        self.assertIn("_carrier disableCollisionWith _cargo;", src)

    def test_the_load_is_visible_not_hidden(self):
        """ACE hides its loaded objects 100 m below the carrier. Visible is better and it
        is free here -- the load rides in the hold where a loadmaster can see it."""
        src = code(ATTACH)
        self.assertNotIn("hideObject", src)
        self.assertNotIn("setPos", src)

    def test_the_manifest_sees_a_carp_loaded_vehicle_without_changes(self):
        """It is attached to the carrier and of a type the manifest already accepts, so it
        is found as the "attached" source with no special case anywhere."""
        self.assertIn('_cargo setVariable ["TLB_CARP_cargoSource", "attached", true]', code(ATTACH))
        self.assertIn('[_x, "attached"] call _add', code(MANIFEST))


class UnloadTests(unittest.TestCase):
    def test_unloading_refuses_in_the_air(self):
        """THE POINT OF HAVING OUR OWN. ACE's Unload on an airborne aircraft can open the
        canopy at altitude, which the developer guide has warned about since v0.4.x. The drop
        only way cargo leaves a flying aircraft."""
        src = code(UNLOAD)
        self.assertIn("if (_aglM > 3) exitWith", src)
        self.assertIn("land first", src)

    def test_the_menu_entry_is_also_gated_on_the_ground(self):
        """Refusing after the click is worse than not offering it."""
        self.assertIn("((getPos _target) # 2) <= 3", code(POSTINIT))

    def test_it_undoes_whichever_mechanism_loaded_it(self):
        """A load put aboard by USAF's own action before CARP was involved still unloads,
        because the manifest records what is carrying it."""
        src = code(UNLOAD)
        for source in ['case "viv"', 'case "usaf"', 'case "ace"', "default"]:
            self.assertIn(source, src)

    def test_the_load_is_set_down_beside_the_aircraft_not_inside_it(self):
        """Detaching in place leaves the vehicle inside the fuselage with collisions
        disabled, and re-enabling them there throws it out at speed."""
        src = code(UNATTACH)
        self.assertIn("_carrier modelToWorld [-8, 0, 0]", src)
        self.assertIn("_cargo enableCollisionWith _carrier;", src)
        self.assertIn("_cargo setVelocity [0, 0, 0];", src)


class MenuPlacementTests(unittest.TestCase):
    def test_load_sits_on_the_cargo_and_unload_on_the_aircraft(self):
        """ACE puts Load on the object being loaded and that is the right place: a
        loadmaster walks up to the truck, not to the wing. It also answers "which
        aircraft" without asking."""
        src = code(POSTINIT)
        self.assertIn('[_x, 0, ["ACE_MainActions"], _loadAction, true]', src)
        self.assertIn('["Air", 0, ["ACE_MainActions"], _unloadAction, true]', src)

    def test_loading_is_a_main_action_not_a_self_action(self):
        """It is done from OUTSIDE the aircraft. The jump run is the opposite case, which
        is why the two sit in different menus."""
        src = code(POSTINIT)
        load = src.index("_loadAction = [")
        self.assertIn("ACE_MainActions", src[load:load + 1800])

    def test_the_condition_puts_the_cheap_tests_first(self):
        """The expensive one walks nearby aircraft and derives a hold, and interaction
        conditions run every time the menu is opened."""
        src = code(POSTINIT)
        cond = src.index("(alive _target) && {isNull (attachedTo _target)}")
        nearest = src.index("TLB_CARP_fnc_nearestLoader", cond)
        self.assertLess(cond, nearest)


if __name__ == "__main__":
    unittest.main(verbosity=2)

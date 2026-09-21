/*
    TLB_CARP_fnc_loadCargo

    Load a vehicle into an aircraft, by whichever mechanism that airframe supports.

        [_carrier, _cargo] call TLB_CARP_fnc_loadCargo  ->  "viv" | "usaf" | "carp" | ""

    CARP CAN NOW LOAD AS WELL AS DROP, AND NEITHER NEEDS THE USAF MOD

    v0.10.0 took the release in house. This takes the other half: until now a load had to
    arrive through USAF's load action, ACE cargo, vanilla vehicle-in-vehicle or a mission
    maker's attachTo, and a vehicle Zeus merely placed in the fuselage was a car standing
    on the floor of a flying building -- carried by nothing, so droppable by nothing.

    TLB_CARP_fnc_canLoadCargo picks the mechanism and explains itself; this executes it.

    WHERE EACH MECHANISM HAS TO RUN, WHICH IS NOT THE SAME PLACE

    setVehicleCargo is global in effect but wants the CARRIER's machine. attachTo is
    local-effect on the object being attached, so it wants the CARGO's machine. On a
    dedicated server with a Zeus-spawned truck and a player-flown aircraft those are two
    different machines, and getting it wrong is silent -- the command simply does nothing,
    which is exactly how guided cargo failed for a whole release.

    So each branch remoteExecs to the object whose locality it needs, and this function is
    safe to call from anywhere.

    THE LOAD IS NOT MADE INVISIBLE

    ACE hides its loaded objects and parks them 100 m below the carrier; USAF leaves them
    attached and visible. Visible is the better behaviour and it is free here: the load
    rides in the hold where a loadmaster can see it, and the release detaches it from
    there. Collisions with the carrier are disabled for the same reason USAF disables them
    at release -- an attached vehicle otherwise fights the airframe it is sitting in.
*/

params ["_carrier", "_cargo"];
if (isNull _carrier || {isNull _cargo}) exitWith {""};

([_carrier, _cargo] call TLB_CARP_fnc_canLoadCargo) params ["_method", "_reason"];
if (_method isEqualTo "") exitWith {
    diag_log format ["[TLB CARP][LOAD] refused carrier=%1 cargo=%2 reason=%3",
        typeOf _carrier, typeOf _cargo, _reason];
    ""
};

switch (_method) do {
    // ---- the engine's own, on the carrier's machine ---------------------------------
    case "viv": {
        [_carrier, _cargo] remoteExec ["TLB_CARP_fnc_loadViv", _carrier];
    };

    // ---- ours, on the cargo's machine, because attachTo is local-effect -------------
    default {
        // One source for the position, whichever mechanism canLoadCargo named. It used to
        // branch here and read USAF_Cargo_LoadPos directly -- a property that does not
        // exist anywhere in the USAF mod, so the branch was dead and the load fell through
        // to the derivation with nothing saying so.
        private _offset = [_carrier, _cargo] call TLB_CARP_fnc_loadModelOffset;
        if ((count _offset) < 3) exitWith {};
        [_carrier, _cargo, _offset] remoteExec ["TLB_CARP_fnc_loadAttach", _cargo];
    };
};

diag_log format ["[TLB CARP][LOAD] carrier=%1 cargo=%2 method=%3 (%4) sim=%5",
    typeOf _carrier, typeOf _cargo, _method, _reason, time];
_method

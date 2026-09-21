/*
    TLB_CARP_fnc_loadViv

    The vanilla vehicle-in-vehicle load, run where the CARRIER is local.

        [_carrier, _cargo] call TLB_CARP_fnc_loadViv

    Dispatched by fn_loadCargo rather than called directly. It is its own function only
    because remoteExec needs a name to resolve, and it is registered on every machine in
    fn_postInit's compile table -- which is above the hasInterface guard, so a dedicated
    server can resolve it too.

    setVehicleCargo does the whole job: the engine animates the ramp, enforces the
    aircraft's declared capacity and keeps the load in its own bookkeeping, which
    getVehicleCargo then reports and TLB_CARP_fnc_cargoManifest reads as the "viv" source.
    Nothing here needs to reproduce any of that.
*/

params ["_carrier", "_cargo"];
if (isNull _carrier || {isNull _cargo}) exitWith {false};
if !(local _carrier) exitWith {
    diag_log format ["[TLB CARP][LOAD] viv refused: carrier %1 is not local here", _carrier];
    false
};
_carrier setVehicleCargo _cargo

/*
    USAFDC_fnc_unloadViv -- vanilla vehicle-in-vehicle unload, where the CARGO is local.

    THERE IS NO UNLOAD COMMAND. The engine ships canVehicleCargo, enableVehicleCargo,
    getVehicleCargo, isVehicleCargo, setVehicleCargo and vehicleCargoEnabled, and nothing
    else. A load is freed by setting its TRANSPORTER to null, which is the idiom ACE's own
    dragging module uses:

        if (!isNull isVehicleCargo _target && {!(objNull setVehicleCargo _target)})

    So the object that matters here is the CARGO, not the carrier -- which is why this
    runs on the cargo's machine while fn_loadViv runs on the carrier's. Loading names the
    carrier as its left operand; unloading names objNull.

    Its own function only because remoteExec needs a name to resolve.
*/
params ["_carrier", "_cargo"];
if (isNull _cargo) exitWith {false};
if !(local _cargo) exitWith {false};
objNull setVehicleCargo _cargo

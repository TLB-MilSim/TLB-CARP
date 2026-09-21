/*
    USAFDC_fnc_unloadCargo

    Put a load back on the ground. The counterpart to fn_loadCargo, NOT to the release.

        [_carrier, _cargo] call USAFDC_fnc_unloadCargo  ->  true/false

    THIS IS THE GROUND OPERATION AND fn_releaseCargo IS THE AIRBORNE ONE

    They must not be confused, and ACE's own Unload action is the reason this function
    exists at all: using it on an airborne aircraft can open the canopy at altitude, which
    is the behaviour the developer guide has warned about since v0.4.x. So this refuses
    outright
    above a walking height rather than doing something clever, and the drop is the only
    way cargo leaves a flying aircraft.

    It undoes whichever mechanism loaded the object, which is not always the one CARP
    would choose today -- a load put aboard by USAF's own action before CARP was involved
    still unloads correctly, because the manifest records what is carrying it.
*/

params ["_carrier", "_cargo"];
if (isNull _carrier || {isNull _cargo}) exitWith {false};

private _aglM = ((getPos _carrier) # 2);
if (_aglM > 3) exitWith {
    hint "TLB CARP: land first -- use the drop to release cargo in flight";
    false
};

private _source = _cargo getVariable ["USAFDC_cargoSource", "attached"];
switch (_source) do {
    case "viv": {
        // To the CARGO, not the carrier: the unload idiom is `objNull setVehicleCargo
        // _cargo`, so the cargo is the operand whose locality matters. fn_loadViv is the
        // other way round because loading names the carrier.
        [_carrier, _cargo] remoteExec ["USAFDC_fnc_unloadViv", _cargo];
    };
    case "usaf": {
        private _list = _carrier getVariable ["usaf_cargo", []];
        _carrier setVariable ["usaf_cargo", _list - [_cargo], true];
        if ((count _list) <= 1) then {_carrier enableVehicleCargo true};
        [_carrier, _cargo] remoteExec ["USAFDC_fnc_unloadAttach", _cargo];
    };
    case "ace": {
        private _loaded = _carrier getVariable ["ace_cargo_loaded", []];
        if (_cargo in _loaded) then {
            _loaded deleteAt (_loaded find _cargo);
            _carrier setVariable ["ace_cargo_loaded", _loaded, true];
        };
        // ACE's own server event does the unhide, the reposition and the damage unblock
        // in the order ACE requires. Worth using rather than reimplementing.
        ["ace_cargo_serverUnload", [_cargo, ASLToAGL (getPosASL _carrier)]] call CBA_fnc_serverEvent;
    };
    default {
        [_carrier, _cargo] remoteExec ["USAFDC_fnc_unloadAttach", _cargo];
    };
};

diag_log format ["[TLB CARP][UNLOAD] carrier=%1 cargo=%2 source=%3 sim=%4",
    typeOf _carrier, typeOf _cargo, _source, time];
true

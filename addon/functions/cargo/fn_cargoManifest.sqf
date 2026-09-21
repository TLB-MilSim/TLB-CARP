/*
    USAFDC_fnc_cargoManifest

    Everything droppable that is currently aboard this aircraft, however it got there.

    [_carrier] call USAFDC_fnc_cargoManifest  ->  [object, object, ...]

    CARP read `usaf_cargo` directly in six places, which tied the whole system to one
    mod's loading action. This is the single place that question is answered now, and
    every one of those six call sites goes through it.

    FIVE WAYS CARGO GETS ABOARD, AND WHAT EACH ONE ACTUALLY IS

      usaf      USAF's own load. Objects exist and are attachTo'd inside the bay.
                The array is broadcast (fn_forceLoadCargo does
                setVariable ["usaf_cargo", ..., true]), so every machine sees it.

      ace       ACE cargo. ACE does NOT delete the object -- fnc_loadItem hides it and
                attaches it 100 m below the carrier, damage-blocked. The array is
                broadcast. Releasing one therefore means detach plus a server-side
                hideObjectGlobal false, not a createVehicle.

      viv       Vanilla vehicle-in-vehicle. The engine holds the object and replicates
                it. Note USAF actively fights this: its fn_loadCargo calls
                `_carrier enableVehicleCargo false` and its fn_canLoad refuses to load
                while getVehicleCargo is non-empty, so in practice a carrier has one or
                the other, not both.

      attached  A mission maker's or Zeus's plain attachTo. Nothing records it anywhere,
                so it is found by filtering attachedObjects to the same type set USAF
                itself uses when deciding what may be loaded.

    ORDER MATTERS AND IS NOT ARBITRARY. USAF entries come first, so that when only USAF
    cargo is aboard the last element of this list is the last element of usaf_cargo --
    which is the one USAF_CARGO_fnc_canDrop selects for itself and ignores whatever it
    was handed. That alignment is what lets fn_releaseSelected hand a pure-USAF load
    back to USAF's own flown-validated release path unchanged.

    WHAT IS DELIBERATELY NOT HERE

      ACE VIRTUAL CARGO. Entries in ace_cargo_loaded that are class-name STRINGS have
      no object behind them; dropping one means creating a vehicle in mid-air on the
      server first. That is a separate piece of work with its own failure modes, and a
      manifest that silently listed something it cannot drop would be worse than one
      that does not list it.

      CARGO SEATS. fullCrew returns people, not droppable objects.

    Everything read here is already replicated, so every client computes the same
    manifest from its own copy and no broadcast of our own is needed.
*/

params ["_carrier"];
if (isNull _carrier) exitWith {[]};

private _out = [];
private _add = {
    params ["_obj", "_source"];
    if (isNull _obj) exitWith {};
    if (_obj in _out) exitWith {};
    // Stamped on the object, not held in a parallel array, so the source survives being
    // handed to a release running on another machine -- but ONLY WHEN IT CHANGES.
    //
    // This function is rebuilt from fn_updatePackageTiming on every guidance tick, which
    // is 20 Hz, on every client with guidance armed. An unconditional public setVariable
    // here put one network write per load per tick on the wire for the whole sortie, for
    // a value that changes at most once in a load's life. The compare is free; the
    // broadcast was not.
    if !((_obj getVariable ["USAFDC_cargoSource", ""]) isEqualTo _source) then {
        _obj setVariable ["USAFDC_cargoSource", _source, true];
    };
    _out pushBack _obj;
};

{[_x, "usaf"] call _add} forEach (_carrier getVariable ["usaf_cargo", []]);

{
    // Objects only. A string here is ACE's virtual cargo and has nothing to drop.
    if (_x isEqualType objNull) then {[_x, "ace"] call _add};
} forEach (_carrier getVariable ["ace_cargo_loaded", []]);

{[_x, "viv"] call _add} forEach (getVehicleCargo _carrier);

{
    // The same type set USAF's own fn_canLoad accepts, plus ammo boxes, which are the
    // other thing this system is routinely asked to drop.
    if (
        _x isKindOf "LandVehicle" || {_x isKindOf "Ship"}
        || {_x isKindOf "ThingX"} || {_x isKindOf "ReammoBox_F"}
    ) then {
        [_x, "attached"] call _add;
    };
} forEach (attachedObjects _carrier);

_out

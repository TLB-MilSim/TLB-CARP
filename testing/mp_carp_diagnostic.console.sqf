USAFDC_diag = {
    private _out = [];
    private _add = {_out pushBack _this; systemChat _this};

    private _v = objectParent player;
    if (isNull _v) then {

        _v = ((player nearEntities [["Air"], 300]) select {alive _x}) param [0, objNull];
    };

    format ["CARP %1 | iface %2 | server %3 | me %4",
        missionNamespace getVariable ["USAFDC_VERSION", "*** NOT LOADED ***"],
        hasInterface, isServer, name player
    ] call _add;

    private _missing = [
        "cargoManifest", "getLoadedCargo", "syncPublish", "syncApply", "syncTick",
        "syncReconcile", "steerTick", "steerBegin", "releaseSelected", "steerPublisher",
        "hasComputer", "canUseCarp"
    ] select {isNil (format ["USAFDC_fnc_%1", _x])};
    format ["fns missing: %1",
        if ((count _missing) isEqualTo 0) then {"none"} else {_missing}
    ] call _add;

    format ["syncPfh %1 | adopted rev %2 by %3 (%4) | wantGuid %5 | wantAuto %6",
        missionNamespace getVariable ["USAFDC_state_syncPfh", -99],
        missionNamespace getVariable ["USAFDC_state_syncRev", -99],
        missionNamespace getVariable ["USAFDC_state_syncAuthor", "?"],
        missionNamespace getVariable ["USAFDC_state_syncUid", "?"],
        missionNamespace getVariable ["USAFDC_state_syncWantGuidance", "?"],
        missionNamespace getVariable ["USAFDC_state_syncWantAuto", "?"]
    ] call _add;

    format ["access: computer %1 | required %2 | can use %3",
        if (isNil "USAFDC_fnc_hasComputer") then {"?"} else {[player] call USAFDC_fnc_hasComputer},
        missionNamespace getVariable ["USAFDC_setting_requireComputer", "?"],
        if (isNil "USAFDC_fnc_canUseCarp" || {isNull _v}) then {"?"} else {[player, _v] call USAFDC_fnc_canUseCarp}
    ] call _add;

    format ["MY state: dz %1 | mode %2 | agl %3 | gs %4 | runIn %5 @ %6 | guidance %7",
        missionNamespace getVariable ["USAFDC_state_dzName", "?"],
        missionNamespace getVariable ["USAFDC_state_mode", "?"],
        round (missionNamespace getVariable ["USAFDC_state_targetAglM", -1]),
        round (missionNamespace getVariable ["USAFDC_state_targetGroundSpeedKmh", -1]),
        missionNamespace getVariable ["USAFDC_state_runInLocked", "?"],
        round (missionNamespace getVariable ["USAFDC_state_runInDeg", -1]),
        missionNamespace getVariable ["USAFDC_state_guidanceArmed", "?"]
    ] call _add;

    if (isNull _v) exitWith {
        "no aircraft found -- get in one, or within 300 m" call _add;
        copyToClipboard (_out joinString endl);
        _out
    };

    format ["server CARP: %1",
        missionNamespace getVariable ["USAFDC_serverVersion", "NOT RUNNING -- clients merge for themselves"]
    ] call _add;

    private _record = _v getVariable ["USAFDC_carpRecord", []];
    format ["AIRCRAFT %1 | local %2 | driver %3",
        typeOf _v, local _v, if (isNull (driver _v)) then {"-"} else {name (driver _v)}
    ] call _add;
    format ["SHARED record: %1",
        if ((count _record) < 5) then {"NONE ON THIS AIRFRAME"} else {
            private _p = _record # 4;
            format ["rev %1 by %2 on v%3 | dz %4 | agl %5 | gs %6 | runIn %7 @ %8",
                _record # 0, _record # 2, _record # 3,
                _p # 1, round (_p # 7), round (_p # 8),
                _p # 10, round (_p # 11)]
        }
    ] call _add;
    private _intent = _v getVariable ["USAFDC_carpIntent", []];
    if ((count _intent) >= 16) then {
        format ["LEGACY intent from %1 (seq %2) -- that player is on a CARP older than v0.9.0", _intent # 1, _intent # 0] call _add;
    };

    private _names = {_this apply {if (_x isEqualType "") then {_x + " (virtual)"} else {typeOf _x}}};

    private _usaf = _v getVariable ["usaf_cargo", []];
    private _ace  = _v getVariable ["ace_cargo_loaded", []];
    private _viv  = getVehicleCargo _v;
    private _att  = attachedObjects _v;

    format ["usaf_cargo       %1 %2", count _usaf, _usaf call _names] call _add;
    format ["ace_cargo_loaded %1 %2", count _ace,  _ace  call _names] call _add;
    format ["getVehicleCargo  %1 %2", count _viv,  _viv  call _names] call _add;
    format ["attachedObjects  %1 %2", count _att,  _att  call _names] call _add;

    private _manifest = if (isNil "USAFDC_fnc_getLoadedCargo") then {[]} else {
        [_v] call USAFDC_fnc_getLoadedCargo
    };
    format ["CARP MANIFEST    %1 %2", count _manifest, _manifest call _names] call _add;
    {
        format ["   %1 source=%2", typeOf _x, _x getVariable ["USAFDC_cargoSource", "?"]] call _add;
    } forEach _manifest;

    private _unclaimed = (nearestObjects [_v, ["LandVehicle", "Ship", "ThingX", "ReammoBox_F"], 40])
        - [_v] - _manifest - _usaf - _viv - _att;
    format ["UNCLAIMED near aircraft: %1", count _unclaimed] call _add;
    {
        private _m = _v worldToModel (getPosASL _x);
        format ["   %1 at model [%2,%3,%4] attachedTo %5 isVehicleCargo %6",
            typeOf _x, round (_m # 0), round (_m # 1), round (_m # 2),
            if (isNull (attachedTo _x)) then {"none"} else {typeOf (attachedTo _x)},
            if (isNull (isVehicleCargo _x)) then {"none"} else {typeOf (isVehicleCargo _x)}
        ] call _add;
    } forEach _unclaimed;

    copyToClipboard (_out joinString endl);
    systemChat "-- copied to clipboard --";
    _out
};

USAFDC_diag2 = USAFDC_diag;
systemChat "CARP diagnostic loaded. Run:  [] call USAFDC_diag;";
true

if (TLB_CARP_state_mapClickEh >= 0) then {
    removeMissionEventHandler ["MapSingleClick", TLB_CARP_state_mapClickEh];
    TLB_CARP_state_mapClickEh = -1;
};

openMap true;
TLB_CARP_state_mapClickEh = addMissionEventHandler ["MapSingleClick", {
    params ["_units", "_pos", "_alt", "_shift"];
    private _terrainAsl = getTerrainHeightASL _pos;
    private _posASL = [_pos # 0, _pos # 1, _terrainAsl];
    [_posASL, "MAP DZ"] call TLB_CARP_fnc_setDZ;
    if (TLB_CARP_state_mapClickEh >= 0) then {
        removeMissionEventHandler ["MapSingleClick", TLB_CARP_state_mapClickEh];
        TLB_CARP_state_mapClickEh = -1;
    };
    openMap false;
}];
true

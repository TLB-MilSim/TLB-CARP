if (USAFDC_state_mapClickEh >= 0) then {
    removeMissionEventHandler ["MapSingleClick", USAFDC_state_mapClickEh];
    USAFDC_state_mapClickEh = -1;
};

openMap true;
USAFDC_state_mapClickEh = addMissionEventHandler ["MapSingleClick", {
    params ["_units", "_pos", "_alt", "_shift"];
    private _terrainAsl = getTerrainHeightASL _pos;
    private _posASL = [_pos # 0, _pos # 1, _terrainAsl];
    [_posASL, "MAP DZ"] call USAFDC_fnc_setDZ;
    if (USAFDC_state_mapClickEh >= 0) then {
        removeMissionEventHandler ["MapSingleClick", USAFDC_state_mapClickEh];
        USAFDC_state_mapClickEh = -1;
    };
    openMap false;
}];
true

params ["_vehicle"];
if (isNull _vehicle) exitWith {
    createHashMapFromArray [["valid", false], ["reason", "NO AIRCRAFT"]]
};

private _profileId = [_vehicle] call USAFDC_fnc_resolveAircraftProfile;
if (_profileId isEqualTo "") exitWith {
    createHashMapFromArray [["valid", false], ["reason", "UNSUPPORTED AIRCRAFT"], ["class", typeOf _vehicle]]
};

private _cfg = configFile >> "CfgVehicles" >> typeOf _vehicle;
private _doors = getArray (_cfg >> "USAF_Cargo_Doors");

private _vel = velocity _vehicle;
private _vx = _vel # 0;
private _vy = _vel # 1;
private _vz = _vel # 2;
private _groundSpeed = sqrt ((_vx * _vx) + (_vy * _vy));
private _track = if (_groundSpeed > 0.5) then {((_vx atan2 _vy) + 360) mod 360} else {getDir _vehicle};
private _cargoList = [_vehicle] call USAFDC_fnc_getLoadedCargo;
private _cargo = if ((count _cargoList) > 0) then {_cargoList # ((count _cargoList) - 1)} else {objNull};
private _bboxTop = if (isNull _cargo) then {0} else {((0 boundingBoxReal _cargo) # 1) # 2};
// The release offset used to be USAF_Cargo_DropPos read straight off the config, and a
// missing entry invalidated the whole aircraft state -- which is what refused every
// airframe USAF does not ship. It now resolves through a mission override, then that
// same config entry, then a derivation from the carrier's bounding box, so a calibrated
// C-17 gets exactly the value it always got and an unknown airframe gets a usable one.
([_vehicle, _cargo] call USAFDC_fnc_releaseModelOffset) params ["_offX", "_offY", "_offZ", "_offSource"];
private _dropPos = [_offX, _offY, _offZ - _bboxTop];
private _releaseModelOffset = [_offX, _offY, _offZ];

private _logKey = format ["USAFDC_profileLogged_%1", typeOf _vehicle];
if !(missionNamespace getVariable [_logKey, false]) then {
    missionNamespace setVariable [_logKey, true];
    diag_log format ["[TLB CARP][PROFILE] class=%1 profile=%2 dropPos=%3 doors=%4", typeOf _vehicle, _profileId, _dropPos, _doors];
};

createHashMapFromArray [
    ["valid", true],
    ["profileId", _profileId],
    ["class", typeOf _vehicle],
    ["vehicle", _vehicle],
    ["posASL", getPosASL _vehicle],
    ["velocity", _vel],
    ["groundSpeedMs", _groundSpeed],
    ["verticalSpeedMs", _vz],
    ["trackDeg", _track],
    ["dropPos", +_dropPos],
    ["doors", +_doors],
    ["loadedCargo", +_cargoList],
    ["cargoCount", count _cargoList],
    ["selectedCargo", _cargo],
    ["cargoBBoxTopM", _bboxTop],
    ["releaseModelOffset", _releaseModelOffset],
    ["dropPosSource", _offSource]
]

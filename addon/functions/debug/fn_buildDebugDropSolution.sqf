params [
    ["_headingDeg", 0, [0]],
    ["_aglM", 3000, [0]],
    ["_groundSpeedKmh", 500, [0]],
    ["_verticalSpeedMs", 0, [0]],
    ["_cargoClass", "rhsusf_mrzr4_d", [""]],
    ["_cargoObject", objNull, [objNull]],
    ["_aircraftId", "c17", [""]]
];

private _invalid = {
    params ["_reason"];
    createHashMapFromArray [
        ["valid", false],
        ["reason", _reason]
    ]
};

if (isMultiplayer) exitWith {["DEBUG HARNESS IS EDEN / SINGLE PLAYER ONLY"] call _invalid};
if ((count TLB_CARP_state_dzPosASL) < 3) exitWith {["NO DZ"] call _invalid};
if (_aglM <= 300) exitWith {["TEST AGL MUST BE ABOVE 300 M"] call _invalid};
if (_groundSpeedKmh <= 0) exitWith {["TEST GROUND SPEED MUST BE POSITIVE"] call _invalid};
// Carrier class comes from the profile, so the harness can drop from any calibrated
// or provisionally-borrowed airframe rather than only the C-17. getModel is called
// here because _model is not resolved until later in this file.
private _profileForClass = (([] call TLB_CARP_fnc_getModel) getOrDefault ["aircraft", createHashMap]) getOrDefault [_aircraftId, createHashMap];
private _carrierClass = ((_profileForClass getOrDefault ["classNames", []]) param [0, ""]);
if (_carrierClass isEqualTo "") exitWith {[format ["NO CLASSNAME FOR PROFILE: %1", _aircraftId]] call _invalid};
if !(isClass (configFile >> "CfgVehicles" >> _carrierClass)) exitWith {[format ["%1 CLASS MISSING", _carrierClass]] call _invalid};
if !(isClass (configFile >> "CfgVehicles" >> _cargoClass)) exitWith {[format ["CARGO CLASS MISSING: %1", _cargoClass]] call _invalid};
if (isNil "USAF_CARGO_fnc_canDrop") exitWith {["USAF_CARGO_fnc_canDrop MISSING"] call _invalid};

_headingDeg = ((_headingDeg % 360) + 360) % 360;
private _groundSpeedMs = _groundSpeedKmh / 3.6;
private _forward = [sin _headingDeg, cos _headingDeg, 0];
private _right = [cos _headingDeg, -sin _headingDeg, 0];
private _velocity = [
    _groundSpeedMs * (_forward # 0),
    _groundSpeedMs * (_forward # 1),
    _verticalSpeedMs
];

private _cfg = configFile >> "CfgVehicles" >> _carrierClass;
private _dropPos = getArray (_cfg >> "USAF_Cargo_DropPos");
private _doors = getArray (_cfg >> "USAF_Cargo_Doors");
private _initPos = getArray (_cfg >> "USAF_Cargo_InitPos");
if ((count _dropPos) < 3) exitWith {["USAF C-17 DROP POSITION MISSING"] call _invalid};
if ((count _initPos) < 3) then {_initPos = +_dropPos};

private _bboxTop = 0;
if (!isNull _cargoObject) then {
    private _bbox = 0 boundingBoxReal _cargoObject;
    if ((count _bbox) >= 2 && {(count (_bbox # 1)) >= 3}) then {
        _bboxTop = ((_bbox # 1) # 2) max 0;
    };
};
private _releaseModelOffset = [_dropPos # 0, _dropPos # 1, (_dropPos # 2) + _bboxTop];
private _releaseOffsetAlongM = _releaseModelOffset # 1;
private _releaseOffsetRightM = _releaseModelOffset # 0;
private _releaseVerticalOffsetM = _releaseModelOffset # 2;

private _windVector = +wind;
private _wx = _windVector # 0;
private _wy = _windVector # 1;
private _windSpeedMs = sqrt ((_wx * _wx) + (_wy * _wy));
private _windFromDeg = 0;
if (_windSpeedMs > 0.01) then {
    private _windToDeg = ((_wx atan2 _wy) + 360) % 360;
    _windFromDeg = (_windToDeg + 180) % 360;
};

private _model = [] call TLB_CARP_fnc_getModel;
private _aircraftProfiles = _model get "aircraft";
private _profile = _aircraftProfiles getOrDefault [_aircraftId, createHashMap];
if ((count _profile) isEqualTo 0) exitWith {["C-17 PROFILE MISSING"] call _invalid};
// A provisionally-borrowed profile must be measurable -- that is the entire point of
// the state -- so the harness accepts it. Its solutions carry a DEGRADED confidence
// and an explicit warning from fn_solveRelative.
private _harnessCalState = _profile getOrDefault ["calibrationState", ""];
// Must accept every state fn_solveRelative accepts, or a profile becomes solvable in
// flight but unmeasurable on the bench. v0.4.45 added "zero-wind-measured" to the
// solver and not here, and all 16 C-130 runs failed with SOLVE FAILED.
// tests/test_v050_stick_drops.py cross-checks the two lists against model.json.
if !(_harnessCalState in ["ready", "zero-wind-measured", "provisional-borrowed"]) exitWith {
    [format ["%1 PROFILE NOT CALIBRATED (%2)", toUpper _aircraftId, _harnessCalState]] call _invalid
};
_profile set ["dropPos", +_dropPos];

private _dz = +TLB_CARP_state_dzPosASL;
private _dzTerrainAslM = _dz # 2;
private _input = createHashMapFromArray [
    ["aircraft", _aircraftId],
    ["mode", "TOUCHDOWN"],
    ["actionAltitudeAslM", _dzTerrainAslM + _aglM],
    ["openingTerrainAslM", _dzTerrainAslM],
    ["dzTerrainAslM", _dzTerrainAslM],
    ["groundSpeedMs", _groundSpeedMs],
    ["velocityAlongMs", _groundSpeedMs],
    ["velocityRightMs", 0],
    ["verticalSpeedMs", _verticalSpeedMs],
    ["releaseOffsetAlongM", _releaseOffsetAlongM],
    ["releaseOffsetRightM", _releaseOffsetRightM],
    ["releaseVerticalOffsetM", _releaseVerticalOffsetM],
    ["runInDeg", _headingDeg],
    ["windSpeedMs", _windSpeedMs],
    ["windFromDeg", _windFromDeg]
];

private _reference = createHashMap;
private _solveFailed = false;
for "_pass" from 0 to 4 do {
    _reference = [_input, _model, _dz] call TLB_CARP_fnc_solveWorldReference;
    if !(_reference getOrDefault ["valid", false]) exitWith {_solveFailed = true};
    private _rp = _reference get "rpPosASL";
    private _actionTerrainAslM = getTerrainHeightASL [_rp # 0, _rp # 1];
    _input set ["actionAltitudeAslM", _actionTerrainAslM + _aglM];
};
if (_solveFailed || {!(_reference getOrDefault ["valid", false])}) exitWith {
    private _badRelative = _reference getOrDefault ["relative", createHashMap];
    private _warnings = _badRelative getOrDefault ["warnings", ["INVALID TEST SOLUTION"]];
    [if ((count _warnings) > 0) then {_warnings # 0} else {"INVALID TEST SOLUTION"}] call _invalid
};

// Re-solve once with the altitude tied to terrain under the final action point.
private _lastRp = _reference get "rpPosASL";
_input set ["actionAltitudeAslM", (getTerrainHeightASL [_lastRp # 0, _lastRp # 1]) + _aglM];
_reference = [_input, _model, _dz] call TLB_CARP_fnc_solveWorldReference;
if !(_reference getOrDefault ["valid", false]) exitWith {["FINAL TEST SOLUTION INVALID"] call _invalid};

private _rp = +(_reference get "rpPosASL");
private _spawnTerrainAslM = getTerrainHeightASL [_rp # 0, _rp # 1];
private _spawnPosASL = [_rp # 0, _rp # 1, _spawnTerrainAslM + _aglM];
private _relative = _reference get "relative";
private _solution = createHashMapFromArray [
    ["valid", true],
    ["mode", "TOUCHDOWN"],
    ["relative", _relative],
    ["runInDeg", _headingDeg],
    ["dzPosASL", +_dz],
    ["rpPosASL", +_rp],
    ["liveRpPosASL", +_rp],
    ["plannedRpPosASL", +_rp],
    ["chutePosASL", +(_reference get "chutePosASL")],
    ["openingTerrainAslM", _reference get "openingTerrainAslM"],
    ["windVector", +_windVector],
    ["windFromDeg", _windFromDeg],
    ["signedRpM", 0],
    ["crossTrackM", 0],
    ["trackErrorDeg", 0],
    ["confidence", _relative getOrDefault ["confidence", "INVALID"]],
    ["warnings", +(_relative getOrDefault ["warnings", []])],
    ["desiredTrackDeg", _headingDeg],
    ["interceptAngleDeg", 0],
    ["guidanceState", "DEBUG HARNESS"],
    ["finalRunLineOffsetM", 0],
    ["targetAglM", _aglM],
    ["targetGroundSpeedKmh", _groundSpeedKmh],
    ["actualAglM", _aglM],
    ["actualGroundSpeedKmh", _groundSpeedKmh]
];

createHashMapFromArray [
    ["valid", true],
    ["reason", ""],
    ["headingDeg", _headingDeg],
    ["aglM", _aglM],
    ["groundSpeedKmh", _groundSpeedKmh],
    ["groundSpeedMs", _groundSpeedMs],
    ["verticalSpeedMs", _verticalSpeedMs],
    ["cargoClass", _cargoClass],
    ["dropPos", +_dropPos],
    ["initPos", +_initPos],
    ["doors", +_doors],
    ["cargoBBoxTopM", _bboxTop],
    ["releaseModelOffset", _releaseModelOffset],
    ["releaseOffsetAlongM", _releaseOffsetAlongM],
    ["releaseOffsetRightM", _releaseOffsetRightM],
    ["releaseVerticalOffsetM", _releaseVerticalOffsetM],
    ["velocity", _velocity],
    ["forward", _forward],
    ["right", _right],
    ["spawnPosASL", _spawnPosASL],
    ["actionRpPosASL", +_rp],
    ["solution", _solution]
]

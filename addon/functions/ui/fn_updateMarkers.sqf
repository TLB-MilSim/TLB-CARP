if (!hasInterface) exitWith {false};
private _owned = ["USAFDC_LOCAL_RP", "USAFDC_LOCAL_PLANNED_RP", "USAFDC_LOCAL_CHUTE", "USAFDC_LOCAL_TOUCH", "USAFDC_LOCAL_RUNIN", "USAFDC_LOCAL_INTERCEPT", "USAFDC_LOCAL_CAPTURE"];
if (!USAFDC_state_guidanceArmed || {!((USAFDC_state_solution) getOrDefault ["valid", false])}) exitWith {
    {deleteMarkerLocal _x} forEach _owned;
    false
};

private _s = USAFDC_state_solution;
private _rp = _s getOrDefault ["liveRpPosASL", _s get "rpPosASL"];
private _plannedRp = _s getOrDefault ["plannedRpPosASL", _rp];
private _chute = _s get "chutePosASL";
private _touch = _s get "touchdownPosASL";
private _dz = _s get "dzPosASL";
private _capture = _s getOrDefault ["capturePosASL", _rp];
private _stableAnchor = _s getOrDefault ["finalRunLineAnchorASL", _plannedRp];
private _forward = _s get "forward";
private _aircraftState = _s get "aircraftState";
private _airPos = _aircraftState get "posASL";

if ((markerShape "USAFDC_LOCAL_RP") isEqualTo "") then {createMarkerLocal ["USAFDC_LOCAL_RP", _rp]};
"USAFDC_LOCAL_RP" setMarkerPosLocal _rp;
"USAFDC_LOCAL_RP" setMarkerShapeLocal "ICON";
"USAFDC_LOCAL_RP" setMarkerTypeLocal "mil_dot";
"USAFDC_LOCAL_RP" setMarkerColorLocal "ColorOrange";
"USAFDC_LOCAL_RP" setMarkerAlphaLocal 1;
"USAFDC_LOCAL_RP" setMarkerTextLocal format ["LIVE RP %1 m", round (abs (_s get "signedRpM"))];

if (!USAFDC_setting_mapTrajectory) exitWith {
    {deleteMarkerLocal _x} forEach ["USAFDC_LOCAL_PLANNED_RP", "USAFDC_LOCAL_CHUTE", "USAFDC_LOCAL_TOUCH", "USAFDC_LOCAL_RUNIN", "USAFDC_LOCAL_INTERCEPT", "USAFDC_LOCAL_CAPTURE"];
    true
};

if ((markerShape "USAFDC_LOCAL_PLANNED_RP") isEqualTo "") then {createMarkerLocal ["USAFDC_LOCAL_PLANNED_RP", _plannedRp]};
"USAFDC_LOCAL_PLANNED_RP" setMarkerPosLocal _plannedRp;
"USAFDC_LOCAL_PLANNED_RP" setMarkerShapeLocal "ICON";
"USAFDC_LOCAL_PLANNED_RP" setMarkerTypeLocal "mil_circle";
"USAFDC_LOCAL_PLANNED_RP" setMarkerColorLocal "ColorWhite";
"USAFDC_LOCAL_PLANNED_RP" setMarkerAlphaLocal 0.45;
"USAFDC_LOCAL_PLANNED_RP" setMarkerTextLocal "PLANNED RP";

if ((markerShape "USAFDC_LOCAL_CHUTE") isEqualTo "") then {createMarkerLocal ["USAFDC_LOCAL_CHUTE", _chute]};
"USAFDC_LOCAL_CHUTE" setMarkerPosLocal _chute;
"USAFDC_LOCAL_CHUTE" setMarkerShapeLocal "ICON";
"USAFDC_LOCAL_CHUTE" setMarkerTypeLocal "mil_circle";
"USAFDC_LOCAL_CHUTE" setMarkerColorLocal "ColorBlue";
"USAFDC_LOCAL_CHUTE" setMarkerTextLocal "CHUTE";

if ((markerShape "USAFDC_LOCAL_TOUCH") isEqualTo "") then {createMarkerLocal ["USAFDC_LOCAL_TOUCH", _touch]};
"USAFDC_LOCAL_TOUCH" setMarkerPosLocal _touch;
"USAFDC_LOCAL_TOUCH" setMarkerShapeLocal "ICON";
"USAFDC_LOCAL_TOUCH" setMarkerTypeLocal "mil_dot";
"USAFDC_LOCAL_TOUCH" setMarkerColorLocal "ColorGreen";
"USAFDC_LOCAL_TOUCH" setMarkerTextLocal "TOUCH";

if ((markerShape "USAFDC_LOCAL_CAPTURE") isEqualTo "") then {createMarkerLocal ["USAFDC_LOCAL_CAPTURE", _capture]};
"USAFDC_LOCAL_CAPTURE" setMarkerPosLocal _capture;
"USAFDC_LOCAL_CAPTURE" setMarkerShapeLocal "ICON";
"USAFDC_LOCAL_CAPTURE" setMarkerTypeLocal "mil_dot";
"USAFDC_LOCAL_CAPTURE" setMarkerColorLocal "ColorYellow";
"USAFDC_LOCAL_CAPTURE" setMarkerTextLocal "CAPTURE";

private _setLine = {
    params ["_name", "_start", "_end", "_color", "_alpha"];
    private _dx = (_end # 0) - (_start # 0);
    private _dy = (_end # 1) - (_start # 1);
    private _length = _start distance2D _end;
    if (_length < 5) exitWith {deleteMarkerLocal _name};
    private _mid = [((_start # 0) + (_end # 0)) * 0.5, ((_start # 1) + (_end # 1)) * 0.5, 0];
    private _dir = ((_dx atan2 _dy) + 360) mod 360;
    if ((markerShape _name) isEqualTo "") then {createMarkerLocal [_name, _mid]};
    _name setMarkerPosLocal _mid;
    _name setMarkerShapeLocal "RECTANGLE";
    _name setMarkerBrushLocal "Solid";
    _name setMarkerColorLocal _color;
    _name setMarkerAlphaLocal _alpha;
    _name setMarkerSizeLocal [2.5, (_length * 0.5) max 2];
    _name setMarkerDirLocal _dir;
};

private _toDz = [(_dz # 0) - (_stableAnchor # 0), (_dz # 1) - (_stableAnchor # 1)];
private _toDzAlongM = (((_toDz # 0) * (_forward # 0)) + ((_toDz # 1) * (_forward # 1))) max 250;
private _stableRunEnd = [
    (_stableAnchor # 0) + ((_forward # 0) * _toDzAlongM),
    (_stableAnchor # 1) + ((_forward # 1) * _toDzAlongM),
    0
];
_stableRunEnd set [2, getTerrainHeightASL _stableRunEnd];

["USAFDC_LOCAL_INTERCEPT", _airPos, _capture, "ColorYellow", 0.45] call _setLine;
["USAFDC_LOCAL_RUNIN", _capture, _stableRunEnd, "ColorOrange", 0.30] call _setLine;
true

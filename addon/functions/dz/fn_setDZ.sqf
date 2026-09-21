params ["_posASL", ["_displayName", "MAP DZ"]];
if ((count _posASL) < 3) exitWith {false};

if !(isNil "USAFDC_fnc_disarmAutoDrop") then {[] call USAFDC_fnc_disarmAutoDrop};
USAFDC_state_dzPosASL = +_posASL;
USAFDC_state_dzName = _displayName;
USAFDC_state_dropLatched = false;
// A missed pass belongs to the previous attempt, not this one.
USAFDC_state_passMissed = false;
USAFDC_state_lastSignedRpM = 1e9;
USAFDC_state_pathSolution = createHashMap;
if !(isNil "USAFDC_fnc_resetPackageTiming") then {[] call USAFDC_fnc_resetPackageTiming};

if ((markerType "USAFDC_LOCAL_DZ") isEqualTo "") then {
    createMarkerLocal ["USAFDC_LOCAL_DZ", _posASL];
    "USAFDC_LOCAL_DZ" setMarkerTypeLocal "mil_dot";
    "USAFDC_LOCAL_DZ" setMarkerColorLocal "ColorYellow";
};
"USAFDC_LOCAL_DZ" setMarkerPosLocal _posASL;
"USAFDC_LOCAL_DZ" setMarkerTextLocal format ["DZ %1", _displayName];

if !(isNil "USAFDC_fnc_updateMarkers") then {[] call USAFDC_fnc_updateMarkers};

// The map-click path (fn_beginMapDZ) sets a DZ without ever going through the panel,
// so fn_refreshPanel's publish would not fire. Publishing here covers it; the publish
// is a no-op when this call is itself the result of applying somebody else's intent.
if !(isNil "USAFDC_fnc_syncPublish") then {[] call USAFDC_fnc_syncPublish};
true

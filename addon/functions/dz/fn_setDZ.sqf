params ["_posASL", ["_displayName", "MAP DZ"]];
if ((count _posASL) < 3) exitWith {false};

if !(isNil "TLB_CARP_fnc_disarmAutoDrop") then {[] call TLB_CARP_fnc_disarmAutoDrop};
TLB_CARP_state_dzPosASL = +_posASL;
TLB_CARP_state_dzName = _displayName;
TLB_CARP_state_dropLatched = false;
// A missed pass belongs to the previous attempt, not this one.
TLB_CARP_state_passMissed = false;
TLB_CARP_state_lastSignedRpM = 1e9;
TLB_CARP_state_pathSolution = createHashMap;
if !(isNil "TLB_CARP_fnc_resetPackageTiming") then {[] call TLB_CARP_fnc_resetPackageTiming};

if ((markerType "TLB_CARP_LOCAL_DZ") isEqualTo "") then {
    createMarkerLocal ["TLB_CARP_LOCAL_DZ", _posASL];
    "TLB_CARP_LOCAL_DZ" setMarkerTypeLocal "mil_dot";
    "TLB_CARP_LOCAL_DZ" setMarkerColorLocal "ColorYellow";
};
"TLB_CARP_LOCAL_DZ" setMarkerPosLocal _posASL;
"TLB_CARP_LOCAL_DZ" setMarkerTextLocal format ["DZ %1", _displayName];

if !(isNil "TLB_CARP_fnc_updateMarkers") then {[] call TLB_CARP_fnc_updateMarkers};

// The map-click path (fn_beginMapDZ) sets a DZ without ever going through the panel,
// so fn_refreshPanel's publish would not fire. Publishing here covers it; the publish
// is a no-op when this call is itself the result of applying somebody else's intent.
if !(isNil "TLB_CARP_fnc_syncPublish") then {[] call TLB_CARP_fnc_syncPublish};
true

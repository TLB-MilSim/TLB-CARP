if (!hasInterface) exitWith {false};
private _vehicle = objectParent player;
if (isNull _vehicle) exitWith {hint "TLB CARP: enter a supported aircraft first"; false};
if (([_vehicle] call TLB_CARP_fnc_resolveAircraftProfile) isEqualTo "") exitWith {hint "TLB CARP: unsupported aircraft"; false};
// The keybind reaches this without the ACE action's condition, so the access rule is
// checked here as well. fn_canUseCarp is the one rule for both ways in.
if !([player, _vehicle] call TLB_CARP_fnc_canUseCarp) exitWith {hint "TLB CARP: you need a CARP Computer to use the drop computer"; false};

// A PRE-RENAME CLIENT IS INVISIBLE, NOT BROKEN -- SAY SO.
//
// Everything CARP shares moved from USAFDC_ to TLB_CARP_, including the record on the
// aircraft. An older client writes USAFDC_carpRecord, which this build never reads, so
// two crews can sit in one aircraft each seeing a perfectly coherent CARP and never see
// each other. The existing mismatched-version notice cannot catch this, because that
// version number travels INSIDE the record that is no longer being read.
//
// Checked here rather than in fn_syncTick: this costs two getVariable calls when a human
// opens the panel, instead of ten a second on a path that has to stay cheap.
private _legacyRecord = _vehicle getVariable "USAFDC_carpRecord";
private _currentRecord = _vehicle getVariable "TLB_CARP_carpRecord";
if (!isNil "_legacyRecord" && {isNil "_currentRecord"}) then {
    if !(_vehicle getVariable ["TLB_CARP_legacyRecordWarned", false]) then {
        _vehicle setVariable ["TLB_CARP_legacyRecordWarned", true];
        systemChat "TLB CARP: somebody in this aircraft is running an older build. CARP is not shared between you until everyone updates.";
    };
};

private _existing = findDisplay 9300;
if (!isNull _existing) exitWith {true};

private _parent = findDisplay 46;
if (isNull _parent) exitWith {hint "TLB CARP: gameplay display unavailable"; false};

// CATCH UP WITH THE AIRCRAFT BEFORE OPENING, SO OPENING THE PANEL NEVER PUBLISHES.
//
// config.bin's onLoad does `[] spawn {uiSleep 0.01; [] call TLB_CARP_fnc_refreshPanel}`,
// and fn_refreshPanel publishes -- so merely opening the panel could look exactly like
// a human changing something. v0.8.4 kept it quiet by seeding the last-published payload
// with whatever this client held, which also hid the crew's record from a client that
// had not adopted it yet. Running the sync tick here adopts the aircraft's record first,
// so the refresh about to run finds nothing of this client's own to send, while a real
// edit a moment later still publishes normally.
if !(isNil "TLB_CARP_fnc_syncTick") then {[] call TLB_CARP_fnc_syncTick};

private _display = _parent createDisplay "TLB_CARP_RscDialog";

if (!isNull _display && {!(isNil "TLB_CARP_fnc_ensurePanelEnhancements")}) then {
    [_display] call TLB_CARP_fnc_ensurePanelEnhancements;
    if !(isNil "TLB_CARP_fnc_updatePanelTelemetry") then {[] call TLB_CARP_fnc_updatePanelTelemetry};
};
!(isNull _display)

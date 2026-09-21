if (!hasInterface) exitWith {false};
private _vehicle = objectParent player;
if (isNull _vehicle) exitWith {hint "TLB CARP: enter a supported aircraft first"; false};
if (([_vehicle] call USAFDC_fnc_resolveAircraftProfile) isEqualTo "") exitWith {hint "TLB CARP: unsupported aircraft"; false};
// The keybind reaches this without the ACE action's condition, so the access rule is
// checked here as well. fn_canUseCarp is the one rule for both ways in.
if !([player, _vehicle] call USAFDC_fnc_canUseCarp) exitWith {hint "TLB CARP: you need a CARP Computer to use the drop computer"; false};

private _existing = findDisplay 9300;
if (!isNull _existing) exitWith {true};

private _parent = findDisplay 46;
if (isNull _parent) exitWith {hint "TLB CARP: gameplay display unavailable"; false};

// CATCH UP WITH THE AIRCRAFT BEFORE OPENING, SO OPENING THE PANEL NEVER PUBLISHES.
//
// config.bin's onLoad does `[] spawn {uiSleep 0.01; [] call USAFDC_fnc_refreshPanel}`,
// and fn_refreshPanel publishes -- so merely opening the panel could look exactly like
// a human changing something. v0.8.4 kept it quiet by seeding the last-published payload
// with whatever this client held, which also hid the crew's record from a client that
// had not adopted it yet. Running the sync tick here adopts the aircraft's record first,
// so the refresh about to run finds nothing of this client's own to send, while a real
// edit a moment later still publishes normally.
if !(isNil "USAFDC_fnc_syncTick") then {[] call USAFDC_fnc_syncTick};

private _display = _parent createDisplay "USAFDC_RscDialog";

if (!isNull _display && {!(isNil "USAFDC_fnc_ensurePanelEnhancements")}) then {
    [_display] call USAFDC_fnc_ensurePanelEnhancements;
    if !(isNil "USAFDC_fnc_updatePanelTelemetry") then {[] call USAFDC_fnc_updatePanelTelemetry};
};
!(isNull _display)

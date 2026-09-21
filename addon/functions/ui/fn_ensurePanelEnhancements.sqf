/*
    USAFDC_fnc_ensurePanelEnhancements

    Attaches the two edit-field commit handlers the config cannot declare.

    THIS FUNCTION USED TO BUILD HALF THE PANEL, AND v0.15.0 GAVE THAT BACK TO THE CONFIG.

    Until config.bin could be regenerated, anything the binarized dialog did not already
    contain had to be created here at runtime: the autopilot button, the SMOKE and JPADS
    toggles, the STICK and OPEN fields with their labels, a second LBSelChanged bolted onto
    the mode list because the config handler whitelisted two modes and ignored the third,
    ctrlSetPosition calls to move controls the config had put in the wrong place, and
    ctrlShow false over the diagnostics row and the status block to hide controls that
    could not be deleted.

    All of that was a workaround for a constraint that stopped being true when Arma 3
    Tools' CfgConvert turned out to round-trip config.bin byte for byte. The panel is now
    declared in addon/config.cpp, generated from a layout spec by tools/gen_dialog.py --
    which computes every rectangle from a cursor and refuses to write if any two overlap,
    because hand-typed coordinates are what put four controls on top of the CARGO row in
    v0.11.0 and shipped it.

    WHAT IS LEFT, AND WHY IT IS STILL HERE

    An RscEdit has no config-side "the user finished typing" event. The two jump fields
    have to commit somewhere, and it cannot be per keystroke: the commit calls
    fn_refreshPanel, which publishes to the rest of the crew and repaints the panel, so
    doing it per character would fight the typist and flood the crew record.

    KillFocus is the event that means "finished", and it can only be attached at runtime.
    That is the whole of this function now.
*/

params [["_display", findDisplay 9300]];
if (isNull _display) exitWith {false};

private _commitJump = {
    params ["_ctrl"];
    private _value = parseNumber (ctrlText _ctrl);
    if (_value < 0) then {_value = 0};
    missionNamespace setVariable [_ctrl getVariable ["USAFDC_jumpField", ""], round _value];
    [] call USAFDC_fnc_refreshPanel;
};

{
    _x params ["_idc", "_var"];
    private _ctrl = _display displayCtrl _idc;
    // Guarded because this runs on every refresh. Without it the handler stacks and fires
    // once per refresh the panel has ever seen.
    if (!isNull _ctrl && {!(_ctrl getVariable ["USAFDC_commitBound", false])}) then {
        _ctrl setVariable ["USAFDC_commitBound", true];
        _ctrl setVariable ["USAFDC_jumpField", _var];
        _ctrl ctrlAddEventHandler ["KillFocus", _commitJump];
    };
} forEach [
    [9332, "USAFDC_state_jumpPlannedStick"],
    [9333, "USAFDC_state_jumpOpenAglM"]
];

true

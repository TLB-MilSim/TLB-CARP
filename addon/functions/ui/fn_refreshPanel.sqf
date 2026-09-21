// ALWAYS UNSCHEDULED. config.bin's onLoad reaches this through
// `[] spawn {uiSleep 0.01; [] call USAFDC_fnc_refreshPanel}`, and scheduled code can be
// suspended half way through: with USAFDC_state_panelRefreshing raised, so every list on
// the panel ignores input until it resumes, and with a crew record free to arrive in the
// middle of a publish. Re-dispatching makes every refresh atomic, which is also what
// lets fn_syncTick treat a flag still raised at its own start as stranded.
if (canSuspend) exitWith {
    [{[] call USAFDC_fnc_refreshPanel}] call CBA_fnc_execNextFrame;
    false
};

private _display = findDisplay 9300;
if (isNull _display) exitWith {false};

// Cargo count selector, built from what is actually aboard.
//
// Was hardcoded to ALL / 1 / 2, which is wrong in both directions: it offered 2 with
// a single vehicle loaded, and could not select 3+ with a full bay. The combo's
// onLBSelChanged handler is compiled into the pre-binarized config.bin and does
//     USAFDC_state_cargoCount = parseNumber ((_this#0) lbData (_this#1))
// so any numeric lbData works and no config change is needed -- the entries just
// have to be built at runtime, which is the only option available here anyway.
private _cargoVehicle = objectParent player;
private _availableCargo = if (isNull _cargoVehicle) then {0} else {
    count ([_cargoVehicle] call USAFDC_fnc_getLoadedCargo)
};

// A selection that no longer exists must fall back to ALL rather than silently
// clamping at drop time: releasing 2 when the pilot last picked 4 and then unloaded
// would be a surprise, and fn_triggerAutoDrop's `min _available` would hide it.
// Only the machine that owns the aircraft may act on this. usaf_cargo is replicated,
// so on any other client "more selected than available" is as likely to mean the
// replica has not caught up as it is to mean somebody unloaded -- and since cargoCount
// is crew-shared intent, resetting it here would publish the pilot's stick size away.
// Worked out before the publish below, so a reset the owner makes goes out with it.
if (USAFDC_state_cargoCount > _availableCargo && {!isNull _cargoVehicle} && {local _cargoVehicle}) then {
    USAFDC_state_cargoCount = -1;
};

// PUBLISH FIRST, PAINT SECOND (v0.9.0).
//
// This is the only place every panel change passes through. config.bin is
// pre-binarized, so the control handlers cannot be edited, and several of them assign
// the intent globals directly --
//     USAFDC_state_mode=_v
//     USAFDC_state_cargoCount=parseNumber ((_this#0) lbData (_this#1))
//     USAFDC_state_targetAglM=(parseNumber ctrlText ...) max 300
// -- so there is no function to hook for those values. What every handler DOES do is end
// with a call to this function.
//
// The publish used to be the last line, after every list, edit box and the whole
// telemetry block had been painted. A script error anywhere in that painting ended the
// call before it got there: the change stayed on this machine, nothing ever retried it,
// and in multiplayer, where script errors are not shown, nobody could see why the crew
// never received it. The handler has already written the globals by the time this
// runs, so publishing first loses nothing.
//
// Publishing only where a human just acted is also what makes the diff trustworthy: a
// polling publisher cannot tell "this crew member changed something" from "this crew
// member failed to apply what somebody else changed", and sending the second one
// clobbers the author.
if !(isNil "USAFDC_fnc_syncPublish") then {[] call USAFDC_fnc_syncPublish};

USAFDC_state_panelRefreshing = true;

private _dzCtrl = _display displayCtrl 9301;
lbClear _dzCtrl;
private _idx = _dzCtrl lbAdd "SELECT DZ_*";
_dzCtrl lbSetData [_idx, ""];
private _selectedDz = 0;
private _dzs = [] call USAFDC_fnc_getMissionDZs;
{
    private _i = _dzCtrl lbAdd format ["%1 (%2)", _x # 1, _x # 0];
    _dzCtrl lbSetData [_i, _x # 0];
    if ((USAFDC_state_dzName isEqualTo (_x # 1)) || {USAFDC_state_dzName isEqualTo (_x # 0)}) then {_selectedDz = _i};
} forEach _dzs;
_dzCtrl lbSetCurSel _selectedDz;

private _modeCtrl = _display displayCtrl 9303;
lbClear _modeCtrl;
{
    private _i = _modeCtrl lbAdd (_x # 0);
    _modeCtrl lbSetData [_i, _x # 1];
    if (USAFDC_state_mode isEqualTo (_x # 1)) then {_modeCtrl lbSetCurSel _i};
} forEach [["TOUCHDOWN ON DZ", "TOUCHDOWN"], ["CHUTE ON DZ", "CHUTE"], ["HALO JUMP", "JUMP"]];

private _profileCtrl = _display displayCtrl 9304;
lbClear _profileCtrl;
{
    private _i = _profileCtrl lbAdd (_x # 0);
    _profileCtrl lbSetData [_i, _x # 1];
    if (USAFDC_state_profileOverride isEqualTo (_x # 1)) then {_profileCtrl lbSetCurSel _i};
} forEach [["AUTO DETECT", ""], ["C-17 OVERRIDE", "c17"], ["C-130 OVERRIDE", "c130"]];

(_display displayCtrl 9305) cbSetChecked USAFDC_state_manualWind;
(_display displayCtrl 9306) ctrlSetText str USAFDC_state_manualWindMs;
(_display displayCtrl 9307) ctrlSetText str USAFDC_state_manualWindFromDeg;
(_display displayCtrl 9306) ctrlEnable USAFDC_state_manualWind;
(_display displayCtrl 9307) ctrlEnable USAFDC_state_manualWind;
(_display displayCtrl 9308) ctrlEnable USAFDC_state_manualWind;
// The jump fields are created at runtime by fn_ensurePanelEnhancements, so they may not
// exist yet on the first paint. Never repainted while focused: this function runs on
// every crew change and rewriting the box under the typist would eat what they are
// entering.
{
    _x params ["_idc", "_value"];
    private _ctrl = _display displayCtrl _idc;
    if (!isNull _ctrl && {!((focusedCtrl _display) isEqualTo _ctrl)}) then {
        _ctrl ctrlSetText str (round _value);
    };
} forEach [
    [9332, missionNamespace getVariable ["USAFDC_state_jumpPlannedStick", 0]],
    [9333, missionNamespace getVariable ["USAFDC_state_jumpOpenAglM", 0]]
];

(_display displayCtrl 9320) ctrlSetText str round USAFDC_state_targetAglM;
(_display displayCtrl 9321) ctrlSetText str round USAFDC_state_targetGroundSpeedKmh;

private _cargoCtrl = _display displayCtrl 9312;
private _cargoEntries = [];
if (_availableCargo <= 0) then {
    _cargoEntries pushBack ["NO CARGO", -1];
} else {
    // "ALL (n)" so the pilot can see the bay count without leaving the panel.
    _cargoEntries pushBack [format ["ALL (%1)", _availableCargo], -1];
    for "_n" from 1 to _availableCargo do {_cargoEntries pushBack [str _n, _n]};
};

lbClear _cargoCtrl;
{
    private _i = _cargoCtrl lbAdd (_x # 0);
    _cargoCtrl lbSetData [_i, str (_x # 1)];
    if (USAFDC_state_cargoCount isEqualTo (_x # 1)) then {_cargoCtrl lbSetCurSel _i};
} forEach _cargoEntries;
if ((lbCurSel _cargoCtrl) < 0) then {_cargoCtrl lbSetCurSel 0};

(_display displayCtrl 9309) ctrlSetText format ["RUN-IN: %1", if (USAFDC_state_runInLocked) then {"LOCKED"} else {"LIVE"}];
(_display displayCtrl 9310) ctrlSetText (if (USAFDC_state_guidanceArmed) then {"DISARM GUIDANCE"} else {"ARM GUIDANCE"});
// AUTO DROP (9311) IS DELIBERATELY NOT PAINTED HERE.
//
// Its label and its red/green colour both live in fn_updatePanelTelemetry, which runs off
// the guidance loop and therefore tracks a state that changes without anybody pressing
// anything -- auto drop disarms itself after a release and on an AP disconnect. Painting
// the label here as well would be a second writer to the same control, which is how the
// text and the colour come to disagree. The telemetry pass is called at the end of this
// function, so a human press still repaints immediately.
//
// The rule it carries, recorded here because this is where it was learned: THE LABEL MUST
// READ WHAT THE BUTTON WILL DO. config.bin's handler toggles on USAFDC_state_autoArmed, so
// painting from `autoArmed || syncWantAuto` made the button read DISARM AUTO and arm
// whenever those disagreed. Crew intent belongs in the status line, never on the control
// whose behaviour it contradicts.
if !(isNil "USAFDC_fnc_ensurePanelEnhancements") then {[_display] call USAFDC_fnc_ensurePanelEnhancements};
if !(isNil "USAFDC_fnc_updatePanelTelemetry") then {[] call USAFDC_fnc_updatePanelTelemetry};

USAFDC_state_panelRefreshing = false;
true

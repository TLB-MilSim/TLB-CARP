/*
    USAFDC_fnc_syncReconcile

    Close the gap between what the crew asked for and what this machine has managed to
    do about it.

    Guidance arming can fail on any given tick: fn_armGuidance needs a valid world
    solution, and that needs a DZ, a resolvable profile and cargo aboard, any of which
    may arrive a moment later than the intent that referenced them. Retrying here means
    a co-pilot whose solver was briefly invalid comes up on his own a fraction of a
    second later, instead of sitting with a blank HUD until he touches the panel.

    The seen-markers at the bottom are updated alongside every change, because
    fn_syncPublish reads a change in the live armed flag as evidence that a human just
    pressed the button. Without them, a successful retry would be published back out as
    a fresh intent by the next panel interaction.
*/

if (!hasInterface) exitWith {false};
private _aircraft = objectParent player;
if (isNull _aircraft) exitWith {false};

private _wantGuidance = missionNamespace getVariable ["USAFDC_state_syncWantGuidance", false];
if (_wantGuidance) then {
    if (!USAFDC_state_guidanceArmed) then {
        // Probe first. fn_armGuidance hints its failure reason, and a client retrying
        // several times a second would paper the screen with it.
        private _probe = [_aircraft] call USAFDC_fnc_buildWorldSolution;
        if (_probe getOrDefault ["valid", false]) then {[] call USAFDC_fnc_armGuidance};
    };
} else {
    if (USAFDC_state_guidanceArmed) then {[] call USAFDC_fnc_disarmGuidance};
};

private _wantAuto = missionNamespace getVariable ["USAFDC_state_syncWantAuto", false];
if (!_wantAuto) then {
    if (USAFDC_state_autoArmed) then {[] call USAFDC_fnc_disarmAutoDrop};
    // Cleared here so the next arm intent is attempted afresh.
    USAFDC_state_syncAutoAttempted = false;
} else {
    // Arming auto drop is attempted ONCE per intent, never retried. fn_armAutoDrop is
    // a one-shot check against the geometry at the instant it runs and refuses an RP
    // already behind the aircraft, so retrying it every tick would hint that refusal
    // several times a second all the way down the run.
    if (!USAFDC_state_autoArmed && {!(missionNamespace getVariable ["USAFDC_state_syncAutoAttempted", false])}) then {
        USAFDC_state_syncAutoAttempted = true;
        [] call USAFDC_fnc_armAutoDrop;
    };
};

USAFDC_state_syncSeenGuidance = USAFDC_state_guidanceArmed;
USAFDC_state_syncSeenAuto = USAFDC_state_autoArmed;
true

/*
    TLB_CARP_fnc_syncReconcile

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

private _wantGuidance = missionNamespace getVariable ["TLB_CARP_state_syncWantGuidance", false];
if (_wantGuidance) then {
    if (!TLB_CARP_state_guidanceArmed) then {
        // Probe first. fn_armGuidance hints its failure reason, and a client retrying
        // several times a second would paper the screen with it.
        private _probe = [_aircraft] call TLB_CARP_fnc_buildWorldSolution;
        if (_probe getOrDefault ["valid", false]) then {[] call TLB_CARP_fnc_armGuidance};
    };
} else {
    if (TLB_CARP_state_guidanceArmed) then {[] call TLB_CARP_fnc_disarmGuidance};
};

private _wantAuto = missionNamespace getVariable ["TLB_CARP_state_syncWantAuto", false];
if (!_wantAuto) then {
    if (TLB_CARP_state_autoArmed) then {[] call TLB_CARP_fnc_disarmAutoDrop};
    // Cleared here so the next arm intent is attempted afresh.
    TLB_CARP_state_syncAutoAttempted = false;
} else {
    // Arming auto drop is attempted ONCE per intent, never retried. fn_armAutoDrop is
    // a one-shot check against the geometry at the instant it runs and refuses an RP
    // already behind the aircraft, so retrying it every tick would hint that refusal
    // several times a second all the way down the run.
    if (!TLB_CARP_state_autoArmed && {!(missionNamespace getVariable ["TLB_CARP_state_syncAutoAttempted", false])}) then {
        TLB_CARP_state_syncAutoAttempted = true;
        [] call TLB_CARP_fnc_armAutoDrop;
    };
};

TLB_CARP_state_syncSeenGuidance = TLB_CARP_state_guidanceArmed;
TLB_CARP_state_syncSeenAuto = TLB_CARP_state_autoArmed;
true

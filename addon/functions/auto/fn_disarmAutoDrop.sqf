/*
    USAFDC_fnc_disarmAutoDrop

    Auto drop is over: the pass was flown, the DZ moved, the mode changed, the solution
    went invalid, or a human pressed the button. All of those END the crew's intent, so
    they clear the shared want flag as well as the local armed flag.

    THE ASYMMETRY IS THE WHOLE POINT, AND IT IS WHY THIS IS NOT IN fn_armAutoDrop.

    A client that FAILS to arm -- fn_armAutoDrop refusing because the RP is already
    behind the aircraft, say -- sets USAFDC_state_autoArmed = false directly and never
    comes through here. That is deliberate: "I could not arm" must not disarm the rest of
    the crew, or one co-pilot's bad geometry would cancel the pilot's pass.

    WHY THE WANT FLAG HAD TO BE CLEARED HERE AT ALL

    fn_syncPublish detects a human's intent by watching the armed flag change since
    USAFDC_state_syncSeenAuto. But fn_syncReconcile re-points that marker at the live
    flag on every tick, 5 Hz -- so a change this function made was erased 200 ms later,
    long before anyone could open the panel, and the publisher saw nothing to publish.
    The want flag then stayed true for the rest of the sortie with auto genuinely off:
    the button read DISARM AUTO, the go-around did not drop, and pressing the button
    called fn_armAutoDrop, which answered "AUTO DROP ARMED".

    Clearing it at the source is what makes the transition detector unnecessary here --
    the state and the intent end together, in one place, for every reason auto can end.
*/

if (missionNamespace getVariable ["USAFDC_state_autoArmed", false]) then {
    diag_log format ["[TLB CARP][AUTO] disarmed sim=%1", time];
};
USAFDC_state_autoArmed = false;
USAFDC_state_dropLatched = false;

// The crew's intent ends with the pass. syncAutoAttempted is released too, so a
// deliberate re-arm later is tried afresh rather than being suppressed as "already
// attempted" -- which is what kept the go-around from ever re-arming.
USAFDC_state_syncWantAuto = false;
USAFDC_state_syncSeenAuto = false;
USAFDC_state_syncAutoAttempted = false;
true

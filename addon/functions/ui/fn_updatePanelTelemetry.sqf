/*
    TLB_CARP_fnc_updatePanelTelemetry

    Repaints the panel controls whose text follows live state: the autopilot button and
    the two toggles.

    IT USED TO DRAW THE STATUS BLOCK AS WELL, AND v0.11.2 REMOVED IT.

    Roughly two hundred lines here built an eight-line readout into control 9314 --
    mission, air state, cargo manifest, wind, flight director, package timing, solution
    and a diagnostics tail. It was removed on a flown request to clean the panel up,
    together with the DEBUG / SOLVER TEST / COPY DEBUG / CAL REC / COPY LAST RUN buttons
    it sat under.

    WHAT SURVIVED AND WHAT DID NOT, CHECKED RATHER THAN ASSUMED.

    Still on the HUD: TOT and the package lifecycle (RELEASED / CHUTE / ARRIVED), the
    flight director, the run-in error, DEGRADED, and the guided-cargo phase including
    JPADS REMOTE and UNSTEERED - NO OWNER.

    Gone from the aircraft entirely, and this is the price: the cargo MANIFEST detail
    (how many are aboard, which load is next, which release path it will take), the CREW
    record readout, and the notice that this client is only OBSERVING because it is not
    in the pilot seat. testing/mp_carp_diagnostic.console.sqf reports all three on demand
    and in more detail than the panel did, but it has to be asked.

    Crew sync is now checked the better way -- by watching the CONTROLS change on the
    other seat's panel, which is the thing that actually has to work.

    The whole block lives in git history if any of it is ever wanted back.
*/

private _display = findDisplay 9300;
if (isNull _display) exitWith {false};

private _vehicle = objectParent player;
private _apArmed = missionNamespace getVariable ["TLB_CARP_state_apArmed", false];
private _apState = missionNamespace getVariable ["TLB_CARP_state_apState", "OFF"];

private _apCtrl = _display displayCtrl 9330;
if (!isNull _apCtrl) then {
    _apCtrl ctrlSetText format ["AP: %1", if (_apArmed) then {_apState} else {"OFF"}];
    private _canArm = _apArmed || {
        TLB_CARP_state_guidanceArmed && {TLB_CARP_state_runInLocked} && {!isNull _vehicle} && {((driver _vehicle) isEqualTo player)}
    };
    _apCtrl ctrlEnable _canArm;
};

// AUTO DROP IS PAINTED HERE, NOT IN fn_refreshPanel, AND THE COLOUR IS WHY.
//
// The crew asked for red/green on this button because they kept forgetting whether it was
// armed. A colour is only worth anything if it is TRUE, and fn_refreshPanel runs when a
// human presses something -- auto drop disarms itself after a release and on an AP
// disconnect, neither of which is a press. A colour set there would sit green on a disarmed
// button until somebody happened to touch the panel, which is worse than no colour at all.
//
// This function runs off the guidance loop, so it repaints live. The LABEL moved here with
// it: text and colour must come from one read on one tick, or the button ends up green
// while reading OFF. That also fixed the stale label, which had the same hole and predates
// this.
//
// IT READS ITS STATE, NOT ITS ACTION, AND THAT IS A DELIBERATE REVERSAL.
//
// This button used to be labelled with what pressing it would DO -- "DISARM AUTO" when
// armed. The crew asked for "AUTO DROP: ON / OFF" instead, and they are right: it now
// matches SMOKE and JPADS immediately below it, which have always been state readouts, so
// three adjacent controls stop meaning three different things. With the colour carrying
// the same fact, a glance answers "is it armed" without anyone parsing an imperative.
//
// WHAT DID NOT CHANGE IS THE HALF THAT WAS A BUG. The label must read the SAME variable
// config.bin's handler toggles on -- TLB_CARP_state_autoArmed -- never the crew's sync
// intent. Painting it from `autoArmed || syncWantAuto` is what once made the control read
// DISARM AUTO and then arm. A state label cannot misdescribe an action it no longer
// claims, but it can still report the wrong machine's state, so the rule stands.
// Crew intent that differs from this machine's belongs in the status line.
private _autoCtrl = _display displayCtrl 9311;
if (!isNull _autoCtrl) then {
    private _autoArmed = missionNamespace getVariable ["TLB_CARP_state_autoArmed", false];
    _autoCtrl ctrlSetText (if (_autoArmed) then {"AUTO DROP: ON"} else {"AUTO DROP: OFF"});
    _autoCtrl ctrlSetTextColor (
        if (_autoArmed) then {[0.365, 0.855, 0.404, 1]} else {[0.898, 0.302, 0.251, 1]}
    );
};

{
    _x params ["_idc", "_label", "_var", "_default"];
    private _ctrl = _display displayCtrl _idc;
    if (!isNull _ctrl) then {
        _ctrl ctrlSetText format ["%1: %2", _label,
            if (missionNamespace getVariable [_var, _default]) then {"ON"} else {"OFF"}];
    };
} forEach [
    [9331, "SMOKE", "TLB_CARP_state_smokeEnabled", true],
    [9336, "JPADS", "TLB_CARP_state_jpadsEnabled", false]
];

// The jump run reads differently from the two toggles above: ARM / DISARM rather than
// ON / OFF, because it is an action and they are states. It is labelled from the AIRCRAFT's
// claim, not this client's flag -- TLB_CARP_jumpArmedBy is public, so a co-pilot sees that
// the run is armed and by whom even though only one machine runs the cue handler.
private _jumpCtrl = _display displayCtrl 9337;
if (!isNull _jumpCtrl) then {
    private _armedBy = if (isNull _vehicle) then {objNull} else {_vehicle getVariable ["TLB_CARP_jumpArmedBy", objNull]};
    _jumpCtrl ctrlSetText (
        if (!isNull _armedBy) then {"DISARM JUMP"} else {"ARM JUMP RUN"}
    );
    _jumpCtrl ctrlSetTooltip (
        if (!isNull _armedBy) then {format ["Jump run armed by %1.", name _armedBy]}
        else {"Arm the HALO exit cue: computed exit point, audible countdown and the jumplight."}
    );
};

true

/*
    USAFDC_fnc_syncTick

    Keep this client on its aircraft's crew record, and reconciled with it.

    Runs on its own low-rate per-frame handler rather than inside the guidance loop,
    because it has to work BEFORE guidance is armed -- that is exactly when a co-pilot
    needs to pick up the pilot's DZ -- and it has to keep working when the guidance loop
    is not running at all.

    The aircraft's record, not the CBA doorbell, is what makes this correct. The event
    can be missed: fired while a client is still loading, or to a crew list that did not
    yet include somebody who had just boarded. Reading the record off the airframe every
    tick means a missed event costs a fraction of a second, a player who boards
    mid-flight adopts the current state without anyone republishing, and a player who
    changes aircraft picks up whatever that airframe knows.

    A RECORD IS ADOPTED WHEN IT IS DIFFERENT, NOT WHEN IT IS NEWER (v0.9.0)

    v0.7.0 adopted a record only when its sequence number beat a counter this client kept
    for itself, and that counter was reset only on leaving the aircraft. Once it ran ahead
    of the aircraft -- two crew editing in the same instant, or Zeus moving a player
    straight from one airframe into another -- every record the crew published after
    that was dropped without a word, in one direction, for the rest of the flight. The
    aircraft is now the arbiter: a record that is not the one this client last adopted
    gets adopted.

    THE TWO GUARD FLAGS HEAL HERE

    fn_syncApply raises USAFDC_state_syncApplying and fn_refreshPanel raises
    USAFDC_state_panelRefreshing while they run. Both run unscheduled (fn_refreshPanel
    re-dispatches itself when it is not), so neither can be half way through when this
    handler starts. A flag still raised here was stranded by a script error, and left
    alone it would stop this client publishing, or freeze every list on its panel, for
    the rest of the session.
*/

if (!hasInterface) exitWith {false};
USAFDC_state_syncApplying = false;
USAFDC_state_panelRefreshing = false;

private _aircraft = objectParent player;
if (isNull _aircraft || {!([player, _aircraft] call USAFDC_fnc_canUseCarp)}) exitWith {
    // Out of the aircraft, or no CARP Computer: forget what was adopted, so boarding --
    // or picking the computer back up -- adopts that airframe's record afresh.
    USAFDC_state_syncAircraft = objNull;
    USAFDC_state_syncRev = -1;
    USAFDC_state_syncUid = "";
    USAFDC_state_syncBase = [];
    private _display = findDisplay 9300;
    if (!isNull _display) then {_display closeDisplay 2};
    false
};

if !(_aircraft isEqualTo (missionNamespace getVariable ["USAFDC_state_syncAircraft", objNull])) then {
    USAFDC_state_syncAircraft = _aircraft;
    USAFDC_state_syncRev = -1;
    USAFDC_state_syncUid = "";
    USAFDC_state_syncBase = [];
};

// A crew member still on v0.7.0-v0.8.x writes the old record and cannot read this one.
// From either seat that looks exactly like broken sync, so say who it is, once.
private _legacy = _aircraft getVariable ["USAFDC_carpIntent", []];
if ((count _legacy) >= 16 && {!((_legacy # 1) in USAFDC_state_syncLegacyWarned)}) then {
    USAFDC_state_syncLegacyWarned pushBack (_legacy # 1);
    systemChat format ["TLB CARP: %1 is running an older CARP. Crew sync needs everyone on v%2.", _legacy # 1, USAFDC_VERSION];
};

private _record = _aircraft getVariable ["USAFDC_carpRecord", []];
if ((count _record) >= 5 && {!([_record # 0, _record # 1] isEqualTo [USAFDC_state_syncRev, USAFDC_state_syncUid])}) exitWith {
    [_aircraft, _record] call USAFDC_fnc_syncApply
};

// Nothing on this airframe yet: this client's own settings are its baseline, so its
// first edit publishes what it changed rather than everything it holds.
if ((count _record) < 5 && {(count USAFDC_state_syncBase) isEqualTo 0}) then {
    USAFDC_state_syncBase = [] call USAFDC_fnc_syncSnapshot;
};

// Nothing new arrived, but this client may still be behind on what it was already
// told: guidance that could not arm a moment ago, for instance.
[] call USAFDC_fnc_syncReconcile;
true

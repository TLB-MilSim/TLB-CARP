if (!TLB_CARP_state_autoArmed) exitWith {false};

// THE RELEASE BELONGS TO THE DRIVER ALONE.
//
// Once auto drop is crew-shared intent, every crew member's guidance loop holds the
// same valid armed solution and every one of them crosses its own signedRpM within a
// few tens of milliseconds of the others. Each would then spawn USAF_CARGO_fnc_canDrop,
// and canDrop takes the LAST element of usaf_cargo each time it runs -- so a second
// caller releases a second load the crew never asked for. It cannot be caught by the
// usaf_cargo_loading flag either: canDrop only raises that after a scheduled door
// animation, long after a second caller has passed the check.
//
// Non-drivers still latch the drop in fn_updateGuidance and still get the cue, the
// sound and the HUD. They just do not command the aircraft to let go of anything.
private _vehicle = objectParent player;
if (isNull _vehicle || {!((driver _vehicle) isEqualTo player)}) exitWith {
    [] call TLB_CARP_fnc_disarmAutoDrop;
    false
};

private _check = [true] call TLB_CARP_fnc_validateAutoDrop;
if !(_check getOrDefault ["valid", false]) exitWith {
    [] call TLB_CARP_fnc_disarmAutoDrop;
    hint format ["TLB CARP AUTO INHIBITED: %1\nMANUAL DROP REQUIRED", _check getOrDefault ["reason", "NOT READY"]];
    false
};

private _carrier = _check get "carrier";
if (isNull _carrier) exitWith {[] call TLB_CARP_fnc_disarmAutoDrop; false};
private _manifest = [_carrier] call TLB_CARP_fnc_getLoadedCargo;
private _available = count _manifest;
private _requested = if (TLB_CARP_state_cargoCount < 0) then {_available} else {(TLB_CARP_state_cargoCount min _available) max 1};
// Stamp the command instant so the recorder need not infer it from the cue.
// beginCalibrationRun and triggerAutoDrop are one tick apart in fn_updateGuidance,
// but "one tick apart" is an assumption, and the cue-to-release distances measured
// in v0.5.2 (34-57 m, i.e. 0.24-0.41 s at 140 m/s) cannot be reconciled with the
// hardcoded `sleep 0.5` in USAF fn_dropCargo.sqf. Measure both ends instead.
TLB_CARP_state_autoDropCommand = [time, diag_tickTime, getPosASL _carrier];

// How many loads this pass drops, stamped where it is known. fn_steerBegin spreads a
// guided stick across this many slots, and it has no other way to find out: by the time
// it runs, the load has already left the manifest and what remains aboard is whatever the
// crew chose NOT to drop. Counting that instead put a single load out of a five-load hold
// in slot 1 of 5 and steered it 70 m off the DZ -- flown, v0.11.2.
_carrier setVariable ["TLB_CARP_stickTotal", _requested, false];
_carrier setVariable ["TLB_CARP_stickIndex", -1, false];

diag_log format ["[TLB CARP][AUTO] start sim=%1 real=%2 posASL=%3 velocity=%4 wind=%5 requested=%6 solution=%7", time, diag_tickTime, getPosASL _carrier, velocity _carrier, wind, _requested, TLB_CARP_state_solution];
[] call TLB_CARP_fnc_disarmAutoDrop;
if (_requested > 1) then {
    [_carrier, _requested] spawn TLB_CARP_fnc_sequenceCargo;
    hint format ["TLB CARP AUTO RELEASED - %1 CARGO SEQUENCE", _requested];
} else {
    // Not USAF_CARGO_fnc_canDrop directly any more. fn_releaseSelected still hands a
    // USAF airframe carrying USAF-loaded cargo straight back to it -- that is the path
    // releaseDelayS was measured against -- and only takes CARP's own release for the
    // loads and airframes USAF cannot serve.
    private _path = [_carrier, _manifest select ((count _manifest) - 1)] call TLB_CARP_fnc_releaseSelected;
    hint format ["TLB CARP AUTO RELEASED (%1)", toUpper _path];
};
true

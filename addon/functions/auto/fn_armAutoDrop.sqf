// Both outcomes are logged. A flown "it did not drop" splits immediately into "it was
// never armed", "arming was refused and said why", and "it was armed and something later
// stopped it" -- and before 2026-09-20 the RPT could not tell those three apart.
private _check = [] call USAFDC_fnc_validateAutoDrop;
if !(_check getOrDefault ["valid", false]) exitWith {
    USAFDC_state_autoArmed = false;
    USAFDC_state_dropLatched = false;
    hint format ["TLB CARP AUTO: %1", _check getOrDefault ["reason", "NOT READY"]];
    false
};

private _solution = _check get "solution";
private _signed = _solution get "signedRpM";
if !(_signed > 0) exitWith {
    USAFDC_state_autoArmed = false;
    USAFDC_state_dropLatched = false;
    USAFDC_state_lastSignedRpM = _signed;
    hint "TLB CARP AUTO: RP already passed - fly a fresh approach";
    false
};

USAFDC_state_dropLatched = false;
USAFDC_state_autoArmed = true;
diag_log format ["[TLB CARP][AUTO] armed sim=%1 carrier=%2 signedRp=%3 cargo=%4",
    time,
    if (isNull (objectParent player)) then {"none"} else {typeOf (objectParent player)},
    _signed,
    count ([objectParent player] call USAFDC_fnc_getLoadedCargo)];
// Rebuild after arming so multi-cargo centering shifts the first-release RP upstream.
private _autoSolution = [objectParent player] call USAFDC_fnc_buildWorldSolution;
if !(_autoSolution getOrDefault ["valid", false]) exitWith {
    USAFDC_state_autoArmed = false;
    hint "TLB CARP AUTO: multi-cargo solution unavailable";
    false
};
private _autoSigned = _autoSolution get "signedRpM";
if !(_autoSigned > 0) exitWith {
    USAFDC_state_autoArmed = false;
    USAFDC_state_lastSignedRpM = _autoSigned;
    hint "TLB CARP AUTO: first-release RP already passed - fly a fresh approach";
    false
};
USAFDC_state_solution = _autoSolution;
USAFDC_state_lastSignedRpM = _autoSigned;
private _warnings = _autoSolution getOrDefault ["warnings", []];
hint (if ((count _warnings) > 0) then {
    format ["AUTO DROP ARMED\n%1", _warnings joinString "\n"]
} else {
    "AUTO DROP ARMED"
});
true

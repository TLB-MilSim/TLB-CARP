params ["_relative", "_airState", "_model", "_windSpeedMs"];
private _warnings = _relative getOrDefault ["warnings", []];
private _confidence = _relative getOrDefault ["confidence", "INVALID"];
if (_confidence isEqualTo "GOOD") exitWith {""};
if (_confidence isEqualTo "INVALID") exitWith {_warnings param [0, "INVALID SOLUTION"]};

private _cfg = _model get "confidence";
private _kmh = (_airState getOrDefault ["groundSpeedMs", 0]) * 3.6;
if ("SPEED OUTSIDE CALIBRATED RANGE" in _warnings) exitWith {
    if (_kmh > (_cfg get "normalSpeedKmhMax")) then {
        format ["GS %1 km/h > CAL %2", round _kmh, round (_cfg get "normalSpeedKmhMax")]
    } else {
        format ["GS %1 km/h < CAL %2", round _kmh, round (_cfg get "normalSpeedKmhMin")]
    }
};
// The string is "WIND ABOVE EMPIRICAL RANGE". fn_solveRelative has pushed that wording
// since the empirical tables replaced the analytic ones, so this branch tested a
// sentence nobody writes and the wind case fell through to the raw warning instead of
// its formatted message.
if ("WIND ABOVE EMPIRICAL RANGE" in _warnings) exitWith {
    format ["WIND %1 m/s > TESTED %2", _windSpeedMs toFixed 1, (_cfg get "testedWindMsMax") toFixed 1]
};
// The borrowed-profile warnings are whole sentences -- "GENERIC PROFILE PROVISIONAL -
// CANOPY TABLE BORROWED - UNVERIFIED FOR THIS AIRFRAME" is 79 characters against the
// HUD's 26, so it would truncate to "GENERIC PROFILE PROVISION", which reads as a
// status rather than a warning. Matched on substring, so the aircraft id in front does
// not matter, and the full text still goes to the CARP panel.
if ((_warnings findIf {(_x find "CANOPY TABLE BORROWED") >= 0}) >= 0) exitWith {"UNCAL AIRFRAME - EST ONLY"};
if ((_warnings findIf {(_x find "WIND TABLES BORROWED") >= 0}) >= 0) exitWith {"WIND TABLES BORROWED"};
if ("LOW-ENERGY CANOPY PROFILE NOT FULLY CALIBRATED" in _warnings) exitWith {"LOW-ENERGY CANOPY PROFILE"};
_warnings param [0, "DEGRADED SOLUTION"]

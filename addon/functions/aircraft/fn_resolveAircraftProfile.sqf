params ["_vehicle"];
if (USAFDC_state_profileOverride in ["c17", "c130"]) exitWith {USAFDC_state_profileOverride};
if (isNull _vehicle) exitWith {""};
if (_vehicle isKindOf "USAF_C17") exitWith {"c17"};
if (_vehicle isKindOf "USAF_C130J") exitWith {"c130"};
// Anything else that flies resolves to the uncalibrated profile rather than being
// refused. It solves, but calibrationState "provisional-borrowed" makes
// fn_solveRelative used to raise a warning that forced DEGRADED, and Auto Drop was then
// gated behind USAFDC_setting_allowDegradedAuto -- the same treatment the C-130 gets.
// Refusing outright was the reason an airframe could never BE measured.
if (_vehicle isKindOf "Air") exitWith {"generic"};
""

params ["_signedRpM"];

if (_signedRpM <= 800) exitWith {0};
if (_signedRpM <= 1500) exitWith {linearConversion [800, 1500, _signedRpM, 0, 5, true]};
if (_signedRpM <= 3000) exitWith {linearConversion [1500, 3000, _signedRpM, 5, 10, true]};
if (_signedRpM <= 5000) exitWith {linearConversion [3000, 5000, _signedRpM, 10, 20, true]};
20

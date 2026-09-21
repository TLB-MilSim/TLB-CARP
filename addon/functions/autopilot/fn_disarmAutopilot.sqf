params [["_reason", "USER"], ["_announce", true]];

private _wasArmed = missionNamespace getVariable ["USAFDC_state_apArmed", false];
USAFDC_state_apArmed = false;
USAFDC_state_apState = "OFF";
USAFDC_state_apOverrideSince = -1;
USAFDC_state_apDisconnectReason = _reason;

if (_wasArmed && {_announce}) then {
    if (missionNamespace getVariable ["USAFDC_setting_sounds", true]) then {playSound "FD_Finish_F"};
    hint format ["TLB CARP AP DISCONNECT: %1", _reason];
    diag_log format ["[TLB CARP][AP] disconnect reason=%1 sim=%2 real=%3", _reason, time, diag_tickTime];
};
true

private _text = missionNamespace getVariable ["TLB_CARP_state_lastCalibrationText", ""];
if (_text isEqualTo "") exitWith {
    hint "NO CALIBRATION RUN RECORDED YET";
    false
};
copyToClipboard _text;
diag_log format ["[TLB CARP][CAL] copied run=%1", (missionNamespace getVariable ["TLB_CARP_state_lastCalibrationRun", createHashMap]) getOrDefault ["runId", -1]];
hint "LAST CALIBRATION RUN COPIED\nPasted to your clipboard as JSON";
true

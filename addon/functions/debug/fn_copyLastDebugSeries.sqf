if ((count TLB_CARP_state_debugSeriesResults) isEqualTo 0) exitWith {
    hint "TLB CARP DEBUG SERIES\nNo completed series to copy";
    false
};

private _text = TLB_CARP_state_debugSeriesResults joinString "\n\n";
TLB_CARP_state_lastDebugSeriesText = _text;
copyToClipboard _text;
diag_log format ["[TLB CARP][HARNESS] copied debug series records=%1 chars=%2", count TLB_CARP_state_debugSeriesResults, count _text];
hint format ["TLB CARP DEBUG SERIES\nCopied %1 CAL records", count TLB_CARP_state_debugSeriesResults];
true

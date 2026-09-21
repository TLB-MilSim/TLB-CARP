/*
    USAFDC_fnc_logLong

    diag_log a string that is longer than Arma will write on one line.

        [_tag, _text] call USAFDC_fnc_logLong

    WHY THIS EXISTS

    Arma truncates a diag_log string at about a kilobyte. It does not warn, it does not
    wrap, and it does not mark the cut -- the line simply stops. Flown 2026-09-20: every
    USAFDC_CAL_V3 record in the RPT ends mid-field at `interceptAngleDeg`, and every
    [TLB CARP][DROP] line is exactly 1031 bytes and stops inside an array.

    What was lost is precisely what the record exists for: the release geometry, the chute
    event, the impact position, the computed along/right miss -- and commandToReleaseS,
    which CLAUDE.md names as the ONLY trustworthy source for release timing ("never infer
    release timing from positions again; read the stamp"). The stamp was being written and
    silently thrown away, so the question "are we landing short" had no instrument behind
    it at all.

    HOW IT SPLITS

    On the record's own line breaks where it can, by length where it cannot, so a wrapped
    line is still a whole field wherever possible. Every part carries the tag and its own
    index, so a grep for the tag reassembles the record in order:

        [TLB CARP][CAL 1/4] USAFDC_CAL_V3
        [TLB CARP][CAL 2/4] ...

    A single-part record still prints its 1/1, because a reader that special-cases the
    common shape is a reader that breaks on the uncommon one.
*/

params ["_tag", "_text"];
if (isNil "_text") exitWith {false};
if !(_text isEqualType "") then {_text = str _text};

// Comfortably inside the engine's limit once the tag and part marker are added. The exact
// cap is not documented and has not been measured, so this does not sit near it.
#define CHUNK 820

private _nl = toString [13, 10];
private _parts = [];
private _current = "";

// Split on the record's own line breaks first. splitString treats its argument as a SET
// of separator characters and drops empty results, so a CRLF separator splits cleanly
// rather than leaving a blank token between the two characters. A field whose own VALUE
// contained a bare CR or LF would split too -- none do, because every one of them is a
// formatted number, string or array.
{
    private _line = _x;
    if ((count _line) > CHUNK) then {
        // One field longer than a whole chunk -- a long array, usually. Flush what is
        // pending, then cut the field itself.
        if (_current isNotEqualTo "") then {_parts pushBack _current; _current = ""};
        private _rest = _line;
        while {(count _rest) > CHUNK} do {
            _parts pushBack (_rest select [0, CHUNK]);
            _rest = _rest select [CHUNK];
        };
        _current = _rest;
    } else {
        if (((count _current) + (count _line) + 1) > CHUNK) then {
            _parts pushBack _current;
            _current = _line;
        } else {
            _current = if (_current isEqualTo "") then {_line} else {_current + _nl + _line};
        };
    };
} forEach (_text splitString _nl);
if (_current isNotEqualTo "") then {_parts pushBack _current};
if ((count _parts) isEqualTo 0) then {_parts = [""]};

private _total = count _parts;
{
    diag_log format ["[TLB CARP][%1 %2/%3] %4", _tag, _forEachIndex + 1, _total, _x];
} forEach _parts;

_total

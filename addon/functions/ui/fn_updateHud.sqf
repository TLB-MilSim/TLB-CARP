// TLB CARP HUD.
//
// Reads as an avionics MFD: a monospace label/value grid, dim labels against bright
// values, groups separated by short rules, and one reserved slot for the drop cue.
//
// THREE HARD CONSTRAINTS, all from ui/hud.hpp being compiled into the pre-binarized
// config.bin:
//   1. Only three controls exist -- 9401 (this panel, with a real translucent
//      background), 9402 (the moving ^) and 9403 (the fixed |). None can be added,
//      so the whole panel is ONE structured-text block and there are no spare
//      controls to draw real rules or a frame with.
//   2. Every position must be set here via ctrlSetPosition. Editing hud.hpp has no
//      in-engine effect; a v0.4.1 fix went in there and shipped broken.
//   3. Layout inside the block is limited to <t size/color/align/font> and <br/>.
//      There are no tab stops, so columns come from a monospace font plus padding.
//
// WHAT THIS FIXES
//   The cue (STANDBY / DROP / NO DROP) and the flight-director glyphs used hardcoded
//   font sizes -- 1.20, 1.45, 1.25, 1.35 -- while every body row multiplied by
//   hudScale. At hudScale 0.7 the body shrank to 0.55 while DROP stayed at 1.45,
//   nearly 3x the body, and overflowed a container that had shrunk with the scale.
//   That is the reported "text pushed out of view". Now every size derives from one
//   scale, and the panel height is computed from the rows actually rendered instead
//   of a guessed constant.
//
// If columns ever look ragged, PAD_CHAR is the single thing to change: Arma's
// structured text should preserve runs of plain spaces, and "&#160;" is the
// non-breaking fallback if a build turns out to collapse them.

if (!hasInterface) exitWith {false};
if (!TLB_CARP_state_guidanceArmed || {!TLB_CARP_setting_hudEnabled}) exitWith {
    if !(isNil "TLB_CARP_state_hudLayer") then {TLB_CARP_state_hudLayer cutText ["", "PLAIN"]};
    false
};

private _liveSolution = missionNamespace getVariable ["TLB_CARP_state_solution", createHashMap];
private _displaySolution = missionNamespace getVariable ["TLB_CARP_state_displaySolution", createHashMap];
private _solution = if (_liveSolution getOrDefault ["valid", false]) then {_liveSolution} else {_displaySolution};
private _packageTrackingOnly = _solution getOrDefault ["packageTrackingOnly", false];
if ((count _solution) isEqualTo 0) exitWith {false};
if (!(_solution getOrDefault ["valid", false]) && {!_packageTrackingOnly}) exitWith {false};

private _display = uiNamespace getVariable ["TLB_CARP_HUD_display", displayNull];
if (isNull _display) then {
    TLB_CARP_state_hudLayer cutRsc ["TLB_CARP_HUD", "PLAIN", 0, false];
    _display = uiNamespace getVariable ["TLB_CARP_HUD_display", displayNull];
};
if (isNull _display) exitWith {false};

// ---- palette -----------------------------------------------------------------
// Five roles, each meaning one thing. The previous HUD used green for the title,
// amber for warnings, amber again for PACKAGE and white for body, which left colour
// carrying no state information at all.
#define C_LABEL "#7e929f"
#define C_VALUE "#dce6ec"
#define C_RULE  "#5c6b75"
#define C_GOOD  "#5fd39b"
#define C_WARN  "#f0b429"
#define C_ALERT "#e8523f"

#define PAD_CHAR " "
// Panel height ceiling. The panel starts at y 0.025 and the flight director sits
// 0.013 below its bottom edge, so 0.72 leaves both comfortably on screen. At 0.60 the
// cap bound early enough at hudScale 1.5 to trim the whole package block away, which
// is worse than a tall panel the pilot deliberately asked for.
#define HUD_MAX_H 0.72
#define MONO "EtelkaMonospacePro"

// ---- smoothed geometry -------------------------------------------------------
private _rawRp = _solution getOrDefault ["signedRpM", 0];
private _rawXtk = _solution getOrDefault ["crossTrackM", 0];
private _alpha = 0.25;
if (isNil "TLB_CARP_state_displayRpM") then {TLB_CARP_state_displayRpM = _rawRp};
if (isNil "TLB_CARP_state_displayXtkM") then {TLB_CARP_state_displayXtkM = _rawXtk};
if (!_packageTrackingOnly) then {
    TLB_CARP_state_displayRpM = TLB_CARP_state_displayRpM + ((_rawRp - TLB_CARP_state_displayRpM) * _alpha);
    TLB_CARP_state_displayXtkM = TLB_CARP_state_displayXtkM + ((_rawXtk - TLB_CARP_state_displayXtkM) * _alpha);
};

private _rp = TLB_CARP_state_displayRpM;
private _rpValue = if ((abs _rp) >= 1000) then {format ["%1", ((abs _rp) / 1000) toFixed 2]} else {format ["%1", round (abs _rp)]};
private _rpUnit = if ((abs _rp) >= 1000) then {"km"} else {"m"};
// Keep the unit when passed. "RP 18.85 PASSED" gave no way to tell 18.85 m from
// 18.85 km, and the difference matters rather a lot on a run-in.
private _rpNote = if (_rp < 0) then {format ["%1 PASSED", _rpUnit]} else {_rpUnit};

private _xtk = TLB_CARP_state_displayXtkM;
private _xtkCentered = (abs _xtk) < 1;
private _xtkValue = if (_xtkCentered) then {"0"} else {format ["%1", round (abs _xtk)]};
private _xtkNote = if (_xtkCentered) then {"CENTRE"} else {if (_xtk > 0) then {"m LEFT"} else {"m RIGHT"}};

private _desiredTrackDeg = _solution getOrDefault ["desiredTrackDeg", _solution getOrDefault ["runInDeg", 0]];
private _steeringErrorDeg = _solution getOrDefault ["steeringErrorDeg", 0];
private _guidanceState = _solution getOrDefault ["guidanceState", "INTERCEPT"];
private _releaseStable = _solution getOrDefault ["releaseStable", true];
private _turnNote = if ((abs _steeringErrorDeg) < 0.8) then {
    "HOLD"
} else {
    format ["%1 %2", if (_steeringErrorDeg > 0) then {"RIGHT"} else {"LEFT"}, (abs _steeringErrorDeg) toFixed 1]
};

// ---- status line -------------------------------------------------------------
// The one line that answers "what should I be doing". Kept short so it never wraps.
private _statusText = "CORRECT TO RUN-IN";
private _statusColor = C_WARN;
if (_packageTrackingOnly) then {
    _statusText = "TRACKING PACKAGE";
    _statusColor = C_LABEL;
} else {
    if (_guidanceState isEqualTo "ON RUN-IN") then {
        _statusText = "ON RUN-IN";
        _statusColor = C_GOOD;
    };
    if (_guidanceState isEqualTo "UNSTABLE RUN-IN") then {
        _statusText = "GO AROUND";
        _statusColor = C_ALERT;
    };
};

// ---- drop cue ----------------------------------------------------------------
// Its own reserved row, ALWAYS rendered. When idle it holds a single space, so the
// rows below never move and the panel never changes height when the cue appears --
// which is what used to push the package block out of view.
private _cueText = PAD_CHAR;
private _cueColor = C_LABEL;
if (!_packageTrackingOnly) then {
    if (_guidanceState isEqualTo "UNSTABLE RUN-IN") then {
        _cueText = "NO DROP";
        _cueColor = C_ALERT;
    } else {
        if (time <= TLB_CARP_state_dropCueUntil) then {
            _cueText = "DROP";
            _cueColor = C_WARN;
        } else {
            if ((_rawRp > 0) && {_rawRp <= 250} && {_releaseStable}) then {
                _cueText = "STANDBY";
                _cueColor = C_WARN;
            };
        };
    };
};

// ---- remaining telemetry -----------------------------------------------------
private _targetAgl = _solution getOrDefault ["targetAglM", TLB_CARP_state_targetAglM];
private _targetGs = _solution getOrDefault ["targetGroundSpeedKmh", TLB_CARP_state_targetGroundSpeedKmh];
private _actualAgl = _solution getOrDefault ["actualAglM", 0];
private _actualGs = _solution getOrDefault ["actualGroundSpeedKmh", 0];
private _apState = missionNamespace getVariable ["TLB_CARP_state_apState", "OFF"];
private _preChute = _solution getOrDefault ["preChuteLateralDriftM", 0];
private _commandVerticalSpeedMs = _solution getOrDefault ["commandVerticalSpeedMs", 0];
private _dropT = _solution getOrDefault ["dropTMinusText", "T---:--"];
private _chuteT = _solution getOrDefault ["chuteTMinusText", "T---:--"];
private _totT = _solution getOrDefault ["totTMinusText", "T---:--"];
private _totClock = _solution getOrDefault ["totClockText", "--:--:--"];
private _pathState = _solution getOrDefault ["pathState", _guidanceState];
private _altitudePathState = _solution getOrDefault ["altitudePathState", "ALT --"];
private _packageState = _solution getOrDefault ["packageState", _solution getOrDefault ["timingState", "ESTIMATE"]];
private _confidence = _solution getOrDefault ["confidence", "INVALID"];
private _confidenceReason = _solution getOrDefault ["confidenceReason", ""];

private _pathColor = if (_pathState in ["FINAL RUN", "RELEASE STABLE", "POST DROP"]) then {C_GOOD} else {C_WARN};
private _altColor = if (_altitudePathState isEqualTo "ALT CAPTURED") then {C_GOOD} else {C_WARN};
private _packageColor = switch (_packageState) do {
    case "ARRIVED": {C_GOOD};
    case "LOST": {C_ALERT};
    default {C_WARN};
};

private _scale = TLB_CARP_setting_hudScale max 0.7 min 1.5;

// ---- type scale --------------------------------------------------------------
// Three steps, ratio ~1.4 apart, and EVERY one multiplied by _scale. That last part
// is the whole bug: a hardcoded cue size does not survive a scale change.
private _fLabel = 0.66 * _scale;
private _fData = 0.94 * _scale;
private _fCue = 1.28 * _scale;

// ---- height budget -----------------------------------------------------------
// Derived from the rows actually rendered, not a constant. The old height was
// (0.35 * _scale) min 0.60, a value already raised twice -- 0.20, then 0.32, then
// 0.35 -- because content kept clipping. A constant cannot be right for a variable
// row count at a variable font size.
// 0.0270, measured properly this time.
//
// Two flown screenshots at STATED hudScale give 20 px per line at 0.70 and 28.5 px at
// 1.00 on a 1080-tall screen -- both 2.64% of safeZoneH per scale unit.
//
// History, because both earlier values were wrong in opposite directions and for the
// same reason: 0.0300 was an outright guess (panel ~15% too tall). 0.0185 came from
// "measuring" a screenshot I assumed was scale 1.0 -- it was actually 0.70, so the
// derived figure was 30% too small and v0.5.6 clipped at BOTH scales, cutting the VS
// row in half. Never calibrate against a screenshot whose scale is assumed.
private _rowH = 0.0270 * _scale;
private _padY = 0.010 * _scale;
private _cueExtra = (_fCue - _fData) * 0.0270;
// The title and status lines are rendered ahead of _rows in the format string, so
// they must be counted or the budget under-reports by two and clips the bottom pair.
private _headerRows = 2;

// ---- row builders ------------------------------------------------------------
private _pad = {
    params ["_n"];
    private _s = "";
    for "_i" from 1 to (_n max 0) do {_s = _s + PAD_CHAR};
    _s
};

// A data row is stored UNFORMATTED and laid out later, once the widest label and the
// widest value among the rows actually rendered are known. Formatting each row on its
// own cannot align them: a fixed column with a minimum gap, "(6 - count _value) max 2",
// puts the note at column 7 for a 5-character value and column 6 for every shorter
// one, which is why "RP 16.02  km PASSED" sat one character right of every note below
// it at hudScale 1.00. Deriving the columns from the content aligns any content.
//
// The minimum gaps that fix earlier collisions are preserved as FLOORS in the layout
// pass, not here. Flight testing without them produced "AP    INTERCEPTINTERCEPT",
// "DROP T-01:20CHUTE T-01:39", "TOT 18:37:46T-02:09" and "DRIFT-73.0".
private _cell = {
    params ["_label", "_value", "_note", ["_valueColor", C_VALUE], ["_noteColor", C_LABEL]];
    [_label, _value, _note, _valueColor, _noteColor]
};

// A short fixed rule, deliberately narrower than the panel so it can never wrap at
// any scale. There is no spare control to draw a real 1px rule with.
private _rule = format ["<t color='%1'>%2</t>", C_RULE, "------------------------"];

// ---- assemble ----------------------------------------------------------------
// Tier 1 is always present. Tier 2 rows appear only when they mean something, which
// roughly halves the resting height and stops the panel reading as a wall of text.
private _rows = [];

_rows pushBack ([ "RP", _rpValue, _rpNote ] call _cell);
_rows pushBack ([ "XTK", _xtkValue, _xtkNote, if (_xtkCentered) then {C_GOOD} else {C_VALUE} ] call _cell);
_rows pushBack ([ "TRK", format ["%1", round _desiredTrackDeg], _turnNote ] call _cell);
// The cue slot. Centred, on its own line, ALWAYS rendered so nothing below it moves.
// Bracketed by ONE rule, not two: an empty slot between two rules left a conspicuous
// void mid-panel at high hudScale.
_rows pushBack _rule;
_rows pushBack format ["<t size='%1' align='center' color='%2'>%3</t>", _fCue, _cueColor, _cueText];
_rows pushBack ([ "ALT", format ["%1", round _actualAgl], format ["-> %1 AGL", round _targetAgl], _altColor ] call _cell);
_rows pushBack ([ "GS", format ["%1", round _actualGs], format ["-> %1 km/h", round _targetGs] ] call _cell);

private _vsArrow = if (_commandVerticalSpeedMs < -0.5) then {"DESC"} else {if (_commandVerticalSpeedMs > 0.5) then {"CLIMB"} else {"HOLD"}};

private _tier2 = [];
if (!_packageTrackingOnly) then {
    _tier2 pushBack ([
        "AP", _apState,
        if (_apState isEqualTo _pathState) then {""} else {_pathState},
        _pathColor, _pathColor
    ] call _cell);
    _tier2 pushBack ([ "VS", format ["%1", (abs _commandVerticalSpeedMs) toFixed 1], format ["%1  %2", _vsArrow, _altitudePathState], C_VALUE, _altColor ] call _cell);
    // preChuteLateralDriftM is one of the three release-gate terms (|crossTrack| <= 25 m,
    // |trackError| <= 2 deg, |drift| <= 15 m). When the gate refuses a pass the pilot has
    // to be able to see WHICH term failed, so this stays on the HUD -- the first draft of
    // this redesign dropped it, which would have made a NO DROP unexplainable in the
    // cockpit. Coloured against the gate limit rather than shown as a bare number.
    private _driftColor = if ((abs _preChute) > 15) then {C_ALERT} else {
        if ((abs _preChute) > 8) then {C_WARN} else {C_VALUE}
    };
    _tier2 pushBack ([ "DRFT", format ["%1", _preChute toFixed 1], "m PRE-CHUTE  LIM 15", _driftColor ] call _cell);
};
private _stickCount = _solution getOrDefault ["cargoSequenceCount", 1];
private _stickLength = _solution getOrDefault ["stickLengthM", 0];
if (_stickCount > 1) then {
    // WHAT THE PATTERN WILL BE, NOT WHAT IT WOULD HAVE BEEN UNGUIDED.
    //
    // This row read the ballistic stick length and compared it against a hardcoded 50,
    // which meant it went amber on every multi-cargo pass -- at any speed in the
    // calibrated band the ballistic figure for two loads is already over 50. Guided cargo
    // replaces that spread with a slot pattern jpadsStickSpacingM wide, so the row was
    // describing a pass that could not happen, all the way down the run-in.
    //
    // stickLengthM is still exported and still drives release geometry; it is simply not
    // what a pilot should be reading. Falling back to it keeps this correct for an
    // unguided stick and for any solution built before these keys existed.
    private _footprint = _solution getOrDefault ["predictedFootprintM", _stickLength];
    private _guided = _solution getOrDefault ["guidedSlots", false];
    private _limit = _solution getOrDefault ["stickWarningLengthM", 50];
    private _stickColor = if (_footprint > _limit) then {C_WARN} else {C_VALUE};
    _tier2 pushBack ([
        "STK", format ["%1", _stickCount],
        // Saying which kind of footprint it is makes an amber row self-explaining --
        // otherwise "65 m" and "35 m" look like the same measurement changing its mind.
        format ["x  %1 m %2", round _footprint, if (_guided) then {"PATTERN"} else {"STICK"}],
        _stickColor, _stickColor
    ] call _cell);
};
if (!(_packageState isEqualTo "IDLE")) then {
    // Guided cargo: the closing error while it is being flown, and the PHASE otherwise.
    // Showing only the error meant every state that is not STEERING looked identical to
    // an unguided load -- including UNSTEERED - NO OWNER, which is the one state that
    // says guided cargo is switched on, a canopy is open, and no machine anywhere is
    // flying it. That is the difference between working and appearing to work, and it
    // had nowhere to appear.
    private _jpadsPhase = missionNamespace getVariable ["TLB_CARP_state_jpadsPhase", "IDLE"];
    private _jpads = if (missionNamespace getVariable ["TLB_CARP_state_jpadsActive", false]) then {
        format ["JPADS %1 m", round (missionNamespace getVariable ["TLB_CARP_state_jpadsErrorM", 0])]
    } else {
        if (_jpadsPhase in ["IDLE", "RELEASED"]) then {""} else {format ["JPADS %1", _jpadsPhase]}
    };
    _tier2 pushBack ([ "PKG", _packageState, _jpads, _packageColor ] call _cell);
    // chuteTMinusText is a countdown BEFORE the chute event and a state word after
    // it, so the literal prefix rendered "DROP RELEASED  CHUTE CHUTE" once the canopy
    // was out. Prefix only while it is still a time.
    private _chuteNote = if (_chuteT isEqualTo "CHUTE") then {_chuteT} else {format ["CHUTE %1", _chuteT]};
    _tier2 pushBack ([ "DROP", _dropT, _chuteNote ] call _cell);
    _tier2 pushBack ([ "TOT", _totClock, _totT ] call _cell);
};
// THE AMBER WARNING BLOCK IS GONE. It only ever carried the DEGRADED tier, which only
// ever carried calibration confidence, and that question is closed -- the C-17 model is
// flown across every airframe this unit uses. A solution is now GOOD or it does not
// exist, and "does not exist" is already said by the tier-1 rows.
private _warnRows = [];
if (false) then {
    // Short form only. The full warning used to wrap to two title-sized lines and
    // take the top of the panel -- the loudest thing on screen and the least
    // actionable. The complete text stays in the CARP panel.
    private _reason = _confidenceReason;
    // Budgeted against the line width the panel actually has. Measured off a flown
    // screenshot at hudScale 1.00: "VS   0.0    HOLD  ALT UNAVAILABLE" is 32
    // characters spanning 485 px in a 635 px box, so ~15.2 px per character and ~41
    // characters usable before the internal inset. "DEGRADED" plus its 2-space gap
    // plus the ellipsis takes 13, leaving 26 -- which puts the longest line in the
    // panel at 39 characters and keeps a real margin.
    //
    // 22 was set when the box width did not scale and cut the longest reason to
    // "DIAGONAL WIND COMPONEN..." with a third of the line empty. 30 was the first
    // correction and overshot: it made this the widest line in the panel at 43
    // characters, against a capacity I had estimated rather than measured.
    if ((count _reason) > 26) then {_reason = (_reason select [0, 26]) + "..."};
    _warnRows pushBack _rule;
    _warnRows pushBack format [
        "<t color='%1'>%2</t>  <t color='%3'>%4</t>",
        C_WARN, _confidence, C_LABEL, _reason
    ];
};
// The panel is height-capped, so at large hudScale the content has to yield rather
// than overflow. At scale 1.5 with guidance armed, a package live AND a warning
// present, the full 16 rows want 0.75 safeZoneH against a 0.60 cap -- which is the
// original clipping bug returning at the top of the scale range.
//
// Tier 1 and the warning are never trimmed: tier 1 is what the pilot flies on, and a
// warning is the one thing that must not be silently hidden. Tier 2 is trimmed from
// its tail, which is why it is ordered most-important-first (AP, then package
// timing, then the AP diagnostics).
private _maxRows = floor ((HUD_MAX_H - (_padY * 2) - _cueExtra) / _rowH);
private _reserved = _headerRows + (count _rows) + (count _warnRows);
private _budget = (_maxRows - _reserved) max 0;
if ((count _tier2) > _budget) then {
    _tier2 = _tier2 select [0, _budget];
};
if ((count _tier2) > 0) then {
    _rows pushBack _rule;
    _rows append _tier2;
};
if ((count _warnRows) > 0) then {
    _rows append _warnRows;
};

// ---- lay the columns out -----------------------------------------------------
// The value column is sized by the values that are NUMBERS, and only those. Sizing it
// by every value is what the first cut of this did, and it is worse than the bug it
// replaced: "AP RELEASE STABLE" is a 14-character value, so a column wide enough for
// it pushed "RP 4.82" twelve spaces from its own note and left the numeric scan-column
// -- the entire point of the grid -- floating in the middle of the panel.
//
// So: values up to VALUE_CEIL drive the column and align exactly; anything longer
// overflows past it on a minimum 2-space gap, which is what AP, PKG, DROP and TOT
// already did and looked correct doing. The numbers a pilot reads down -- RP, XTK,
// TRK, ALT, GS, VS, DRFT -- all fit inside the ceiling.
//
// Floors of 4 and 5 with the "max" gaps below reproduce exactly the guarantee the old
// fixed columns gave: >=1 space after the label, >=2 after the value, always.
#define VALUE_CEIL 6
private _labelW = 4;
private _valueW = 5;
{
    if (_x isEqualType []) then {
        _labelW = _labelW max (count (_x select 0));
        private _vw = count (_x select 1);
        if (_vw <= VALUE_CEIL) then {_valueW = _valueW max _vw};
    };
} forEach _rows;
// if/then/else, NOT "exitWith" -- exitWith exits the innermost enclosing scope and
// its behaviour inside an apply block is not something to rely on. A branch yields
// the value of whichever arm runs, which is all this needs.
private _lines = _rows apply {
    if (_x isEqualType "") then {_x} else {
        _x params ["_label", "_value", "_note", "_valueColor", "_noteColor"];
        format [
            "<t color='%5'>%1</t>%2<t color='%6'>%3</t>%4<t color='%7'>%8</t>",
            _label,
            [(_labelW + 1 - (count _label)) max 1] call _pad,
            _value,
            [(_valueW + 2 - (count _value)) max 2] call _pad,
            C_LABEL, _valueColor, _noteColor, _note
        ]
    }
};

// ---- height from content, not from a guess -----------------------------------
// The old height was (0.35 * scale) min 0.60 -- a constant that had already been
// raised twice because content kept clipping. Deriving it from the rows actually
// rendered means it cannot clip at any scale. The cue row is taller than a data row,
// so it is counted at its real weight.
private _hudTopY = 0.025;
private _hudH = ((_padY * 2) + ((_headerRows + (count _rows)) * _rowH) + _cueExtra) min HUD_MAX_H;
private _hudBottomY = _hudTopY + _hudH;

private _ctrl = _display displayCtrl 9401;
// Width scales with hudScale like every other dimension. It was a bare
// safeZoneW * 0.33 -- the ONE dimension that never scaled -- so at hudScale 0.70 the
// box stood nearly twice as wide as its own text, and above ~1.3 the longest rows
// would have run out through the right edge of the background they sit on. Scaling it
// also keeps the character capacity of a line roughly constant, which is what makes a
// fixed truncation budget mean anything. Capped so the box cannot leave the screen at
// the top of the scale range. The top-left corner stays put; the box grows rightward.
// The flight director is anchored to screen centre, not to this box, so a wider panel
// cannot move the caret or the centre post.
private _hudW = (0.33 * _scale) min 0.60;
_ctrl ctrlSetPosition [safeZoneX + safeZoneW * 0.335, safeZoneY + safeZoneH * _hudTopY, safeZoneW * _hudW, safeZoneH * _hudH];
_ctrl ctrlCommit 0;

// Title carries the identity; the version sits beside it at label weight so it stops
// competing with the data. DZ name follows on the same line rather than being
// right-aligned, because there are no tab stops to right-align against.
_ctrl ctrlSetStructuredText parseText format [
    "<t font='%1' size='%2' color='%3'>TLB CARP</t><t font='%1' size='%4' color='%5'>  v%6  %7</t><br/><t font='%1' size='%4' color='%8'>%9</t><br/><t font='%1' size='%10'>%11</t>",
    MONO,
    _fData, C_GOOD,
    _fLabel, C_LABEL,
    missionNamespace getVariable ["TLB_CARP_VERSION", "?"],
    // A DZ named "MAP DZ" rendered as "DZ MAP DZ". Only add the prefix when the name
    // does not already carry it.
    if (TLB_CARP_state_dzName isEqualTo "") then {"DZ CUSTOM"} else {
        if ("DZ" in (toUpper TLB_CARP_state_dzName splitString " ")) then {TLB_CARP_state_dzName}
        else {format ["DZ %1", TLB_CARP_state_dzName]}
    },
    _statusColor, _statusText,
    _fData,
    _lines joinString "<br/>"
];

// Flight-director geometry is explicit: the moving ^ above the fixed center |, both
// clear of the panel. The center post used to keep its config.bin position -- the
// same y as the panel bottom -- which put | above ^ and overlapped the block, and the
// v0.4.1 hud.hpp edit could never take effect.
// Zero gap on purpose: caret and post share the same box top so the apex of ^ is
// inline with the top of |, and the post's stroke runs down out of it. The pair then
// reads as one arrow to line up rather than two glyphs. Both use the same size so
// their line boxes match, and BOTH now scale -- they were hardcoded at 1.35.
private _fdGapY = 0.0;
private _fGlyph = 1.28 * _scale;
private _cueW = safeZoneW * 0.025;
private _cueY = _hudBottomY + 0.013;
private _centerY = _cueY + _fdGapY;
private _glyphH = safeZoneH * (0.026 * _scale);
private _steerCtrl = uiNamespace getVariable ["TLB_CARP_HUD_STEER", controlNull];
private _centerCtrl = _display displayCtrl 9403;
if (!isNull _steerCtrl) then {
    _steerCtrl ctrlShow (!_packageTrackingOnly);
    if (!_packageTrackingOnly) then {
        private _steerNorm = ((_steeringErrorDeg / 30) max -1) min 1;
        private _cueX = safeZoneX + (safeZoneW * 0.5) + (_steerNorm * safeZoneW * 0.12) - (_cueW * 0.5);
        _steerCtrl ctrlSetPosition [_cueX, safeZoneY + safeZoneH * _cueY, _cueW, _glyphH];
        _steerCtrl ctrlCommit 0;
        _steerCtrl ctrlSetStructuredText parseText format ["<t align='center' size='%1' color='%2'>^</t>", _fGlyph, C_GOOD];
    };
};
if (!isNull _centerCtrl) then {
    _centerCtrl ctrlShow (!_packageTrackingOnly);
    if (!_packageTrackingOnly) then {
        _centerCtrl ctrlSetPosition [
            safeZoneX + (safeZoneW * 0.5) - (_cueW * 0.5),
            safeZoneY + safeZoneH * _centerY,
            _cueW,
            _glyphH
        ];
        _centerCtrl ctrlCommit 0;
        _centerCtrl ctrlSetStructuredText parseText format ["<t align='center' size='%1' color='%2'>|</t>", _fGlyph, C_VALUE];
    };
};
true

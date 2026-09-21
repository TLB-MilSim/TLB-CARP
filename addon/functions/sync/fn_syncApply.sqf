/*
    USAFDC_fnc_syncApply

    Adopt an aircraft's crew record on this client.

        [aircraft, record] call USAFDC_fnc_syncApply

    record: [rev, authorUid, authorName, authorVersion, payload], where payload is the
    fourteen intent fields from fn_syncSnapshot, in that order.

    APPLIED BY CALLING THE REAL FUNCTIONS, NOT BY WRITING THE GLOBALS.

    Each intent value has side effects that live in its own function, and a raw write
    would skip every one of them. fn_setDZ clears the latched miss, resets the package
    tracker and moves the local DZ marker. fn_unlockRunIn drops the smoothed track so
    the next lock does not inherit the old line. fn_armGuidance starts this client's
    own per-frame solver, which is the entire mechanism by which a co-pilot's HUD,
    markers and 3D cue come alive.

    THE RUN-IN IS APPLIED AS A NUMBER, NOT BY RE-RUNNING THE CAPTURE.

    fn_lockRunIn captures this client's own view of the aircraft ground track. On a
    dedicated server the aircraft is local to the pilot, so a co-pilot's velocity read
    is the replicated copy sampled at a different instant. Two clients capturing
    independently would hold different final lines, and the release gate allows two
    degrees of track error, which is the same order as the disagreement. Whoever locks
    owns the number, and everyone else flies it.

    THE RECORD IS MARKED ADOPTED BEFORE ANY SIDE EFFECT RUNS (v0.9.0)

    The sequence number used to be written after fn_setDZ, the reconcile and the panel
    repaint. A script error in any of them left the record un-adopted, so the next tick
    applied it again and failed again, forever -- and left USAFDC_state_syncApplying
    raised, which silently stopped this client publishing anything at all. Marking first
    means a failing side effect costs that one apply, and fn_syncTick lowers the
    stranded guard on its next run.
*/

params [["_aircraft", objNull, [objNull]], ["_record", [], [[]]]];
if (!hasInterface || {isNull _aircraft}) exitWith {false};
if ((count _record) < 5) exitWith {false};
_record params ["_rev", "_uid", "_author", "_version", "_payload"];
// Exact, not a minimum. A crew member on a build with a different payload length is
// not merely missing a field -- every index after the difference means something else
// -- so refusing outright and letting the version warning fire is the safe answer.
if !((_payload isEqualType []) && {(count _payload) isEqualTo 18}) exitWith {false};

_payload params [
    "_dz", "_dzName", "_mode", "_profileOverride",
    "_manualWind", "_manualWindMs", "_manualWindFromDeg",
    "_targetAglM", "_targetGroundSpeedKmh", "_cargoCount",
    "_runInLocked", "_runInDeg",
    "_wantGuidance", "_wantAuto", "_smokeEnabled",
    "_jumpPlannedStick", "_jumpOpenAglM", "_jpadsEnabled"
];

USAFDC_state_syncApplying = true;
USAFDC_state_syncAircraft = _aircraft;
USAFDC_state_syncRev = _rev;
USAFDC_state_syncUid = _uid;
USAFDC_state_syncAuthor = _author;
USAFDC_state_syncAdoptedAt = diag_tickTime;

// A crew member on a different build. Say so once per person and version: a mismatch
// otherwise looks exactly like sync being broken.
if !(_version isEqualTo USAFDC_VERSION) then {
    private _key = format ["%1|%2", _uid, _version];
    if !(_key in USAFDC_state_syncVersionWarned) then {
        USAFDC_state_syncVersionWarned pushBack _key;
        systemChat format ["TLB CARP: %1 is running v%2 and you are running v%3. Crew sync needs everyone on the same version.", _author, _version, USAFDC_VERSION];
    };
};

// Scalars first: everything below re-solves and must read the new values.
USAFDC_state_mode = _mode;
USAFDC_state_profileOverride = _profileOverride;
USAFDC_state_manualWind = _manualWind;
USAFDC_state_manualWindMs = _manualWindMs;
USAFDC_state_manualWindFromDeg = _manualWindFromDeg;
USAFDC_state_targetAglM = _targetAglM;
USAFDC_state_targetGroundSpeedKmh = _targetGroundSpeedKmh;
USAFDC_state_cargoCount = _cargoCount;
USAFDC_state_smokeEnabled = _smokeEnabled;
USAFDC_state_jumpPlannedStick = _jumpPlannedStick;
USAFDC_state_jumpOpenAglM = _jumpOpenAglM;
USAFDC_state_jpadsEnabled = _jpadsEnabled;

if ((count _dz) >= 3) then {
    if (!(_dz isEqualTo USAFDC_state_dzPosASL) || {!(_dzName isEqualTo USAFDC_state_dzName)}) then {
        [_dz, _dzName] call USAFDC_fnc_setDZ;
    };
} else {
    if ((count USAFDC_state_dzPosASL) >= 3) then {[] call USAFDC_fnc_clearDZ};
};

if (_runInLocked) then {
    if (!USAFDC_state_runInLocked || {!(_runInDeg isEqualTo USAFDC_state_runInDeg)}) then {
        USAFDC_state_runInDeg = _runInDeg;
        USAFDC_state_runInLocked = true;
        USAFDC_state_dropLatched = false;
        USAFDC_state_passMissed = false;
        USAFDC_state_pathSolution = createHashMap;
        USAFDC_state_smoothedDesiredTrackDeg = nil;
    };
} else {
    if (USAFDC_state_runInLocked) then {[] call USAFDC_fnc_unlockRunIn};
};

USAFDC_state_syncWantGuidance = _wantGuidance;
USAFDC_state_syncWantAuto = _wantAuto;
// What this client is now synced to. fn_syncPublish diffs against it to find the
// fields a human changes here next.
USAFDC_state_syncBase = [] call USAFDC_fnc_syncSnapshot;

// Reconciling the armed flags is fn_syncReconcile's job, so a client that cannot arm
// right now keeps trying instead of losing the crew's intent on one bad tick.
[] call USAFDC_fnc_syncReconcile;

// The panel paints its widgets once, when something happens on THIS client. Without
// this a co-pilot watching the pilot move the DZ sees the old values until he clicks
// something. Safe to re-enter: fn_refreshPanel raises USAFDC_state_panelRefreshing and
// every binarized control handler tests it before acting, so a repaint cannot re-fire
// the handlers and echo back out.
//
// THE APPLY GUARD STAYS UP ACROSS THE REPAINT. fn_refreshPanel publishes before it
// paints, and it also clamps the cargo selection against this client's replica of the
// cargo manifest. A co-pilot's replica lags the pilot's for a full round trip after a
// load or a release, so a repaint landing in that window would reset cargoCount to ALL
// and publish the reset back over the pilot's deliberate stick size.
if !(isNull (findDisplay 9300)) then {[] call USAFDC_fnc_refreshPanel};
USAFDC_state_syncApplying = false;
true

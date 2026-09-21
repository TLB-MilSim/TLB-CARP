// Parallel drop bench: run many independent C-17 cargo drops simultaneously.
//
// Why this exists alongside TLB_CARP_fnc_debugDropSeries:
//   The series harness is hard-serialised. TLB_CARP_state_debugHarnessActive admits
//   one run at a time, and the calibration recorder is a singleton (it logs
//   "recorder already active; ignoring new cue" if a second cue arrives). A batch
//   of 20 runs therefore takes 20 descents back to back. Time acceleration is not
//   an answer either: the carrier kinematic pin uses real-time uiSleep, so
//   accelerating degrades exactly the release window the measurement depends on.
//
// This function bypasses the recorder entirely and measures the two things the
// accuracy analysis needs -- where the canopy opened and where the load settled --
// writing one [PBENCH] line per run to the RPT. Wall-clock cost is one descent
// regardless of batch size.
//
// Each run gets its own VIRTUAL DZ on a grid around the real one, so loads cannot
// collide and every measurement is independent. Terrain elevation is logged per
// run, because a virtual DZ can land on a slope or in water and that run must be
// discarded rather than silently skewing the batch.
//
// Solving is serial but instant (pure computation, no waiting); only the descents
// run in parallel. TLB_CARP_state_dzPosASL is swapped during the solve phase and
// restored before anything is spawned.
//
// Concurrency is bounded by waves. The carrier pin window is only about a second,
// so launching in waves a couple of seconds apart keeps only one wave's carriers
// pinned at a time while every descent still overlaps. Staggering by a fraction of
// a second would NOT help: all loads take ~50 s to fall, so a 0.5 s launch stagger
// is a 0.5 s landing stagger, and against a single DZ they would land on top of
// each other before their settled positions are sampled.
//
// spacingM = 0 selects the alternative: one REAL DZ, with each wave allowed to land
// and be cleaned up before the next launches. Slower (one descent per wave) but it
// measures against the actual DZ and needs no virtual grid.
//
// Usage:
//   [[0,90,180,270], 3000, 500, 0, "rhsusf_mrzr4_d", "ZERO", [0,0], 500] spawn TLB_CARP_fnc_parallelDropBench;
//
// Argument order (a bool in the wrong slot raises "Type Bool, expected Number"):
//    1 headings          2 aglM             3 groundSpeedKmh   4 verticalSpeedMs
//    5 cargoClass        6 windMode         7 windVector       8 spacingM
//    9 waveSize         10 waveGapS        11 jpads (bool)    12 spawnStaggerS
//   13 aircraftId ("c17" | "c130")
//
// Guided, 8 headings, zero wind, waves of 4:
//   [[0,45,90,135,180,225,270,315], 3000, 500, 0, "rhsusf_mrzr4_d", "ZERO", [0,0], 300, 4, 3, true] spawn TLB_CARP_fnc_parallelDropBench;

params [
    ["_headings", [], [[]]],
    ["_aglM", 3000, [0]],
    ["_groundSpeedKmh", 500, [0]],
    ["_verticalSpeedMs", 0, [0]],
    ["_cargoClass", "rhsusf_mrzr4_d", [""]],
    ["_windMode", "LIVE", [""]],
    ["_windVector", [0, 0], [[]]],
    ["_spacingM", 500, [0]],
    ["_waveSize", 5, [0]],
    ["_waveGapS", 2, [0]],
    ["_jpads", false, [false]],
    ["_spawnStaggerS", 0.35, [0]],
    ["_aircraftId", "c17", [""]]
];

_windMode = toUpper _windMode;

if (isMultiplayer) exitWith {hint "PARALLEL BENCH\nEden / Single Player only"; false};
if ((count _headings) isEqualTo 0) exitWith {hint "PARALLEL BENCH\nNo headings supplied"; false};
if !(_windMode in ["LIVE", "ZERO", "FIXED"]) exitWith {hint "PARALLEL BENCH\nwindMode must be LIVE, ZERO or FIXED"; false};
if (TLB_CARP_state_debugHarnessActive) exitWith {hint "PARALLEL BENCH\nThe series harness is running"; false};
if (missionNamespace getVariable ["TLB_CARP_state_pbenchActive", false]) exitWith {hint "PARALLEL BENCH\nAlready running"; false};
if ((count TLB_CARP_state_dzPosASL) < 3) exitWith {hint "PARALLEL BENCH\nSelect a CARP DZ first"; false};
if (isNil "TLB_CARP_fnc_buildDebugDropSolution") exitWith {hint "PARALLEL BENCH\nDiagnostics build required"; false};

// Grid spacing has to clear BOTH constraints, because one number sets spawn and
// landing separation: a C-17 is ~52 m span / ~53 m long, and observed misses reach
// ~40 m radial so neighbouring cells must not overlap. Below this the carriers
// spawn inside each other and the loads land on one another mid-measurement.
private _minSpacingM = 200;
if (_spacingM > 0 && {_spacingM < _minSpacingM}) then {
    diag_log format ["[PBENCH] spacing %1 m raised to %2 m: a C-17 is ~52 m span and misses reach ~40 m, so tighter grids collide", _spacingM, _minSpacingM];
    _spacingM = _minSpacingM;
};

// Resolve the carrier class from the profile so a batch can fly any supported
// airframe. Refuse early and clearly rather than spawning nothing.
private _carrierProfile = (([] call TLB_CARP_fnc_getModel) getOrDefault ["aircraft", createHashMap]) getOrDefault [_aircraftId, createHashMap];
private _carrierClass = ((_carrierProfile getOrDefault ["classNames", []]) param [0, ""]);
if (_carrierClass isEqualTo "") exitWith {hint format ["PARALLEL BENCH
Unknown aircraft profile: %1", _aircraftId]; false};
if !(isClass (configFile >> "CfgVehicles" >> _carrierClass)) exitWith {hint format ["PARALLEL BENCH
Missing class: %1", _carrierClass]; false};

TLB_CARP_state_pbenchActive = true;
// Guided mode. fn_steerCargo refuses to run unless the CBA setting is on, so drive
// it from the batch argument and restore it afterwards, exactly as with wind.
private _jpadsBefore = missionNamespace getVariable ["TLB_CARP_state_jpadsEnabled", false];
if (_jpads) then {TLB_CARP_state_jpadsEnabled = true};
TLB_CARP_state_pbenchJpads = _jpads;
TLB_CARP_state_pbenchSteer = [];
private _realDz = +TLB_CARP_state_dzPosASL;
private _windBefore = +(wind);
private _gustsBefore = gusts;
private _aceWindWasDefined = !(isNil "ace_weather_disableWindSimulation");
private _aceWindBefore = missionNamespace getVariable ["ace_weather_disableWindSimulation", false];

// Commanding the wind is not the same as having it, and the gap is FRAMES.
//
// v0.4.23 called setWind and then solved all 20 runs in the same frame. Arma's
// `wind` does not update until the next simulation step, so every run was solved
// against the PREVIOUS wind -- and the batch header logged the previous wind for
// the same reason, which is why it read wind=ZERO [-3.437,-2.414,0]. The whole
// batch then showed heading-dependent residuals, which zero wind cannot produce:
// along/right are defined in each run's own heading frame, so a heading-invariant
// error must decompose to one world vector, and those decomposed to four.
//
// This is the sequence from fn_debugDropSeries, which has in-engine evidence
// behind it, rather than a fresh invention. Verified against ACE 3.21.2.113:
// ace_weatherunctionsnc_updateWind.sqf line 19 reads exactly this flag --
//     if (missionNamespace getVariable ["ace_weather_disableWindSimulation", false]) exitWith {};
// -- so setting it does stop ACE re-driving the wind. The flag was never the
// problem; the missing frame wait was.
private _windTarget = [0, 0];
private _windControlToleranceMs = 0.05;
if !(_windMode isEqualTo "LIVE") then {
    _windTarget = if (_windMode isEqualTo "ZERO") then {[0, 0]} else {[_windVector # 0, _windVector # 1]};
    ace_weather_disableWindSimulation = true;
    0 setGusts 0;

    // ACE can complete one more already-scheduled wind update just after the flag
    // changes, so re-assert continuously for a full second rather than once.
    private _aceSettleDeadline = diag_tickTime + 1;
    waitUntil {
        setWind [_windTarget # 0, _windTarget # 1, true];
        0 setGusts 0;
        uiSleep 0.05;
        diag_tickTime >= _aceSettleDeadline
    };
    setWind [_windTarget # 0, _windTarget # 1, true];

    // Frames, not seconds: this is the step v0.4.23 was missing entirely.
    private _settleFrame = diag_frameNo + 3;
    waitUntil {
        uiSleep 0.01;
        diag_frameNo >= _settleFrame
    };

    private _achieved = +(wind);
    private _dE = (_achieved # 0) - (_windTarget # 0);
    private _dN = (_achieved # 1) - (_windTarget # 1);
    private _errMs = sqrt ((_dE * _dE) + (_dN * _dN));
    if (_errMs > _windControlToleranceMs) exitWith {
        diag_log format [
            "[PBENCH] ABORT wind never converged: requested %1 %2, engine reports %3, error %4 m/s. Every run would be solved against a wind that is not flying.",
            _windMode, _windTarget, _achieved, _errMs toFixed 3
        ];
        TLB_CARP_state_pbenchActive = false;
        hint format ["PARALLEL BENCH ABORTED
Wind would not settle
wanted %1
got %2", _windTarget, _achieved];
    };
    diag_log format ["[PBENCH] wind settled: requested %1 %2, engine reports %3 (error %4 m/s) gusts=%5",
        _windMode, _windTarget, _achieved, _errMs toFixed 3, gusts];
};

// The exitWith above only leaves the wind block, not the function, so the abort has
// to be re-checked here or the batch would carry on with an unverified wind.
if (!(_windMode isEqualTo "LIVE") && {!TLB_CARP_state_pbenchActive}) exitWith {false};

private _batchId = round (time * 10);
diag_log format [
    "[PBENCH] batch=%1 runs=%2 agl=%3 gs=%4 vz=%5 cargo=%6 wind=%7 %8 spacing=%9 dz=%10",
    _batchId, count _headings, _aglM, _groundSpeedKmh, _verticalSpeedMs,
    _cargoClass, _windMode, +(wind), _spacingM, _realDz
];
diag_log format ["[PBENCH] batch=%1 aircraft=%2 class=%3 calibrationState=%4", _batchId, _aircraftId, _carrierClass,
    _carrierProfile getOrDefault ["calibrationState", "?"]];
diag_log format ["[PBENCH] batch=%1 jpads=%2", _batchId, _jpads];

// ---- Phase 1: solve every run (serial, instant) -----------------------------
private _plans = [];
private _perRow = ceil sqrt (count _headings);
{
    private _index = _forEachIndex;
    private _col = _index mod _perRow;
    private _row = floor (_index / _perRow);
    private _offE = ((_col - ((_perRow - 1) / 2)) * _spacingM);
    private _offN = ((_row - ((_perRow - 1) / 2)) * _spacingM);
    if (_spacingM <= 0) then {_offE = 0; _offN = 0};
    private _vdz = [(_realDz # 0) + _offE, (_realDz # 1) + _offN, 0];
    _vdz set [2, getTerrainHeightASL [_vdz # 0, _vdz # 1]];

    // A grid cell can land in the sea. v0.4.12 put run 9 on terrain -18.6 m.
    //
    // This MUST be an if/else, not exitWith: exitWith inside a forEach block exits
    // the ENTIRE loop, not the iteration. v0.4.13 used exitWith here, run index 4
    // hit water, and runs 5-19 were never solved at all -- 4 results from a 20-run
    // batch, with the early COMPLETE looking like success.
    // Skipping water cells shrank the batch. Walk outward from the nominal cell
    // until land is found, and log the nudge so the geometry stays auditable.
    private _dzUsable = true;
    if (_spacingM > 0) then {
        private _tries = 0;
        while {(surfaceIsWater [_vdz # 0, _vdz # 1] || {(_vdz # 2) < 0.5}) && {_tries < 24}} do {
            _tries = _tries + 1;
            private _ang = (_tries * 137) mod 360;
            private _rad = 120 * (ceil (_tries / 8));
            _vdz set [0, (_realDz # 0) + _offE + (_rad * (sin _ang))];
            _vdz set [1, (_realDz # 1) + _offN + (_rad * (cos _ang))];
            _vdz set [2, getTerrainHeightASL [_vdz # 0, _vdz # 1]];
        };
        _dzUsable = !(surfaceIsWater [_vdz # 0, _vdz # 1] || {(_vdz # 2) < 0.5});
        if (_tries > 0 && {_dzUsable}) then {
            diag_log format ["[PBENCH] batch=%1 run=%2 virtual DZ nudged %3 attempts to land terrain=%4",
                _batchId, _index, _tries, (_vdz # 2) toFixed 1];
        };
    };

    if (!_dzUsable) then {
        diag_log format ["[PBENCH] batch=%1 run=%2 SKIPPED hdg=%3 no land found near cell terrain=%4",
            _batchId, _index, _x, (_vdz # 2) toFixed 1];
    } else {
        TLB_CARP_state_dzPosASL = +_vdz;
        // Same reason as the run spawn below: [0,0,200] is the map corner and
        // destroys the probe, which is audible even though the probe is discarded.
        private _probe = createVehicle [_cargoClass, [_vdz # 0, _vdz # 1, 0], [], 0, "NONE"];
        private _build = [_x, _aglM, _groundSpeedKmh, _verticalSpeedMs, _cargoClass, _probe, _aircraftId] call TLB_CARP_fnc_buildDebugDropSolution;
        deleteVehicle _probe;

        if (_build getOrDefault ["valid", false]) then {
            _plans pushBack [_index, _x, +_vdz, _build];
        } else {
            diag_log format ["[PBENCH] batch=%1 run=%2 SOLVE FAILED hdg=%3 reason=%4",
                _batchId, _index, _x, _build getOrDefault ["reason", "?"]];
        };
    };
} forEach _headings;

TLB_CARP_state_dzPosASL = +_realDz;
diag_log format ["[PBENCH] batch=%1 solved %2 of %3 requested runs", _batchId, count _plans, count _headings];

if ((count _plans) isEqualTo 0) exitWith {
    TLB_CARP_state_pbenchActive = false;
    hint "PARALLEL BENCH\nEvery run failed to solve";
    false
};

// ---- Phase 2: spawn and drop every run at once ------------------------------
TLB_CARP_state_pbenchPending = count _plans;
TLB_CARP_state_pbenchObjects = [];
TLB_CARP_state_pbenchPins = [];
TLB_CARP_state_pbenchChuteWatch = [];
TLB_CARP_state_pbenchPinEh = addMissionEventHandler ["EachFrame", {
    private _keep = [];
    {
        _x params ["_pinCarrier", "_pinCargo", "_pinOrigin", "_pinT0", "_pinVel", "_pinFwd"];
        if (!isNull _pinCarrier) then {
            if (_pinCargo in (_pinCarrier getVariable ["usaf_cargo", []])) then {
                private _e = (time - _pinT0) max 0;
                _pinCarrier setPosASL [
                    (_pinOrigin # 0) + ((_pinVel # 0) * _e),
                    (_pinOrigin # 1) + ((_pinVel # 1) * _e),
                    (_pinOrigin # 2) + ((_pinVel # 2) * _e)
                ];
                _pinCarrier setVectorDirAndUp [_pinFwd, [0, 0, 1]];
                _pinCarrier setVelocity _pinVel;
                // The pinned-flight window was previously unobserved, so damage
                // taken here was misattributed to the release frame.
                private _pinDmg = damage _pinCargo;
                if (_pinDmg > 0) then {
                    if ((_pinCarrier getVariable ["TLB_CARP_pbenchDmgPinnedAgl", -1]) < 0) then {
                        _pinCarrier setVariable ["TLB_CARP_pbenchDmgPinnedAgl", (getPosATL _pinCargo) # 2, false];
                    };
                    _pinCargo setDamage 0;
                };
                _keep pushBack _x;
            } else {
                _pinCarrier setVariable ["TLB_CARP_pbenchReleased", true, false];
            };
        };
    } forEach TLB_CARP_state_pbenchPins;
    TLB_CARP_state_pbenchPins = _keep;

    // Canopy open MUST be detected per frame. v0.4.22 detected it inside each run's
    // own waitUntil {uiSleep 0.05} loop; with 20 of those competing for Arma's
    // ~3 ms/frame scheduler budget the later waves were starved, and the lag shows
    // up directly in the data: chuteAgl should be a fixed ~300 m (USAF's trigger)
    // but ranged 238-300, and the four runs that detected below 280 m averaged
    // openAlong +36.5 m against +16.1 m for the promptly-detected ones.
    //
    // That is fatal for this bench specifically. The load is still doing ~100 m/s
    // horizontally at canopy open, so 0.76 s of detection lag manufactures ~76 m of
    // phantom openAlong -- and openAlong is the quantity the canopy table is fitted
    // from. Settle detection can stay in the scheduled loop because a load at rest
    // does not move while the loop is starved; canopy open cannot.
    private _watching = [];
    {
        if (!isNull _x) then {
            private _att = attachedTo _x;
            if (!isNull _att && {_att isKindOf "ParachuteBase"}) then {
                _x setVariable ["TLB_CARP_pbenchChuteTime", time, false];
                _x setVariable ["TLB_CARP_pbenchChutePos", getPosASL _x, false];
                _x setVariable ["TLB_CARP_pbenchChuteAgl", (getPosATL _x) # 2, false];
                if (TLB_CARP_state_pbenchJpads) then {TLB_CARP_state_pbenchSteer pushBack _x};
            } else {
                _watching pushBack _x;
            };
        };
    } forEach TLB_CARP_state_pbenchChuteWatch;
    TLB_CARP_state_pbenchChuteWatch = _watching;

    // Guided steering, per frame, per load. fn_steerCargo is the SAME function the
    // live package uses -- called with explicit [cargo, dz] so many loads can be
    // steered at once without touching each other's state or the pilot's HUD.
    // Per-frame is mandatory: at the 0.05 s guidance interval the parachute's own
    // physics reasserted between calls and only 41% of commanded steering survived.
    if (TLB_CARP_state_pbenchJpads) then {
        private _keepSteer = [];
        {
            if (!isNull _x) then {
                private _sdz = _x getVariable ["TLB_CARP_pbenchDz", []];
                if ((count _sdz) >= 3) then {[_x, _sdz] call TLB_CARP_fnc_steerCargo};
                _keepSteer pushBack _x;
            };
        } forEach TLB_CARP_state_pbenchSteer;
        TLB_CARP_state_pbenchSteer = _keepSteer;
    };
}];

private _launch = {
    params ["_plan", "_cargoClass", "_batchId", "_aglM", "_groundSpeedKmh", "_carrierClass"];
    _plan params ["_index", "_headingDeg", "_vdz", "_build"];
    [_index, _headingDeg, _vdz, _build, _cargoClass, _batchId, _aglM, _groundSpeedKmh, _carrierClass] spawn {
        params ["_index", "_headingDeg", "_vdz", "_build", "_cargoClass", "_batchId", "_aglM", "_groundSpeedKmh", "_carrierClass"];

        private _spawnPosASL = +(_build get "spawnPosASL");
        private _forward = +(_build get "forward");
        private _velocity = +(_build get "velocity");
        private _exactHeading = _build get "headingDeg";

        // Spawn the load at the carrier's XY, not [0,0,200]. dmgSpawn instrumentation
        // in v0.4.22 returned 1.00 on all 20 runs with every later window clean: the
        // load was being destroyed by createVehicle at the map corner, before it ever
        // reached the aircraft. setDamage 0 repaired it a line later so the
        // trajectory was never affected -- but it is what made the cook-off audible,
        // and a "destroyed then repaired" test article is not worth defending.
        // The carrier's own createVehicle already uses this position and is never
        // damaged, which is the evidence this location is safe.
        private _cargo = createVehicle [_cargoClass, [_spawnPosASL # 0, _spawnPosASL # 1, 0], [], 0, "NONE"];
        private _carrier = createVehicle [_carrierClass, [_spawnPosASL # 0, _spawnPosASL # 1, 0], [], 0, "FLY"];
        TLB_CARP_state_pbenchObjects append [_cargo, _carrier];

        // Test articles are indestructible. A destroyed load cannot be measured, and
        // destruction is not what this bench measures.
        //
        // allowDamage false alone was NOT enough in v0.4.17 -- the loads still blew
        // up. setDamage explicitly ignores allowDamage false, and HandleDamage is
        // not raised by setDamage either, so whatever is destroying them (USAF's
        // drop path, or landing) gets through both. The only reliable guard is to
        // keep resetting damage, which the tracking loop below does every tick.
        // Damage at settle time is logged so a destroyed load can never be mistaken
        // for a clean measurement.
        _cargo allowDamage false;
        _carrier allowDamage false;
        _cargo addEventHandler ["HandleDamage", {0}];
        _carrier addEventHandler ["HandleDamage", {0}];

        // Kept because uncoupling the two bodies is harmless and correct in
        // principle, but note it did NOT stop the damage: v0.4.20 shipped this and
        // 19 of 20 loads still reported damage.
        //
        // The reason it looked like a release collision was a defect in this
        // harness, not in the game. dmgFirstAgl was only ever sampled by the
        // post-release tracking loop, so the earliest AGL it could possibly report
        // was the release altitude -- ~3000 m on every run, by construction. It
        // measured when damage was first LOOKED FOR, not when it occurred.
        // The spawn window and the entire pinned-flight window were unobserved.
        // dmgSpawn / dmgLoaded / dmgPinnedAgl below close both of them.
        _carrier disableCollisionWith _cargo;
        _cargo disableCollisionWith _carrier;

        private _dmgSpawn = damage _cargo;
        if (_dmgSpawn > 0) then {_cargo setDamage 0};

        _carrier setPosASL _spawnPosASL;
        _carrier setDir _exactHeading;
        _carrier setVectorDirAndUp [_forward, [0, 0, 1]];
        _carrier setVelocity _velocity;
        // Doors must be FULLY open before the drop is commanded, and this is the
        // measured reason bench and flown release timing disagreed.
        //
        // v0.4.30 logged the real lag from canDrop to the cargo leaving usaf_cargo:
        // 0.594 s running a single run alone, 0.619-0.722 s at 8 concurrent. Load
        // costs only ~0.07 s, so the scheduler was NOT the cause -- my concurrency
        // hypothesis was wrong. Flown drops measured 0.167-0.300 s. The difference
        // is that the bench commanded the doors open in the same frame it called
        // canDrop, so USAF's drop path waited on the animation; a pilot has been
        // flying with them open for minutes.
        //
        // Waiting here makes the bench's release state match the flown one. The wait
        // happens BEFORE the pin is registered, so it costs no path fidelity.
        private _doors = (_build getOrDefault ["doors", []]) select {_x isEqualType ""};
        // Drive BOTH animate and animateSource. On the C-17 the ramp is an
        // animation; on the C-130 ramp_top/ramp_bottom are AnimationSources and
        // `animate` does nothing at all -- a v0.4.42 C-130 batch logged
        // phases=["0.00" x5] after 20 s, so USAF's own canDrop then spent ~10 s
        // opening them and every load released 10.5 s late, ~2800 m downrange.
        {
            _carrier animate [_x, 1, true];
            _carrier animateSource [_x, 1, true];
        } forEach _doors;
        if ((count _doors) > 0) then {
            private _doorDeadline = diag_tickTime + 20;
            waitUntil {
                uiSleep 0.05;
                private _open = true;
                // Either channel counts as open: animationPhase for an animation,
                // animationSourcePhase for a source.
                {
                    if (((_carrier animationPhase _x) < 0.99) && {(_carrier animationSourcePhase _x) < 0.99}) then {_open = false};
                } forEach _doors;
                _open || {diag_tickTime >= _doorDeadline} || {isNull _carrier}
            };
            private _phases = _doors apply {format ["%1/%2", (_carrier animationPhase _x) toFixed 2, (_carrier animationSourcePhase _x) toFixed 2]};
            if (diag_tickTime >= _doorDeadline) then {
                diag_log format ["[PBENCH] batch=%1 run=%2 DOORS NOT FULLY OPEN after 20 s phases=%3 -- release timing will not match flown",
                    _batchId, _index, _phases];
            };
        };

        [_carrier, _cargo, 0, false] call USAF_CARGO_fnc_forceLoadCargo;
        if !(_cargo in (_carrier getVariable ["usaf_cargo", []])) exitWith {
            diag_log format ["[PBENCH] batch=%1 run=%2 LOAD FAILED", _batchId, _index];
            deleteVehicle _carrier; deleteVehicle _cargo;
            TLB_CARP_state_pbenchPending = TLB_CARP_state_pbenchPending - 1;
        };

        private _dmgLoaded = damage _cargo;
        if (_dmgLoaded > 0) then {_cargo setDamage 0};

        // Hand the carrier to the shared per-frame pin. v0.4.12 pinned from inside
        // each run's own scheduled loop; with 20 concurrent loops on uiSleep 0.01
        // none of them got per-frame slices, the carriers bled airspeed, and 9 of
        // 14 loads were released at ~0 m/s instead of 139 m/s (they fell straight
        // down, landing ~3400 m short). One EachFrame handler over a registry is
        // guaranteed every frame regardless of batch size.
        TLB_CARP_state_pbenchPins pushBack [_carrier, _cargo, getPosASL _carrier, time, _velocity, _forward];
        TLB_CARP_state_pbenchChuteWatch pushBack _cargo;
        // Each load carries its own aim point, so guided runs on the virtual grid
        // steer to their own cell rather than all converging on the real DZ.
        _cargo setVariable ["TLB_CARP_pbenchDz", +_vdz, false];

        // Capture the drop COMMAND instant. releaseDelayS is not a physical
        // constant -- it is the script latency between canDrop being called and the
        // cargo detaching, and it scales with scheduler load. A single flown
        // aircraft measured 0.211 s; this bench runs 8 carriers at once and its
        // latency is longer, which is why the bench looked correct on the old
        // 0.5285 s value while every flown drop landed 44 m short. Log the real
        // lag per run so the two are never conflated again.
        private _cmdSimTime = time;
        private _cmdPosASL = getPosASL _carrier;
        [_carrier] spawn USAF_CARGO_fnc_canDrop;

        private _pinDeadline = diag_tickTime + 15;
        waitUntil {
            uiSleep 0.05;
            (_carrier getVariable ["TLB_CARP_pbenchReleased", false]) || {isNull _carrier} || {diag_tickTime >= _pinDeadline}
        };
        private _released = _carrier getVariable ["TLB_CARP_pbenchReleased", false];

        private _relRealTime = diag_tickTime;
        private _relSimTime = time;
        private _fpsAtRelease = diag_fps;
        private _lagS = time - _cmdSimTime;
        private _lagM = (_cmdPosASL distance2D (getPosASL _carrier));
        private _dmgPinnedAgl = _carrier getVariable ["TLB_CARP_pbenchDmgPinnedAgl", -1];
        private _releasePos = getPosASL _carrier;
        private _releaseVel = velocity _cargo;
        private _windAtRelease = +(wind);
        private _releaseSimTime = time;
        deleteVehicle _carrier;

        if (!_released) exitWith {
            diag_log format ["[PBENCH] batch=%1 run=%2 NO RELEASE", _batchId, _index];
            deleteVehicle _cargo;
            TLB_CARP_state_pbenchPending = TLB_CARP_state_pbenchPending - 1;
        };

        // Track to canopy open, then to rest.
        private _chuteSimTime = -1;
        private _chuteAgl = -1;
        private _chutePos = [];
        private _airborne = false;
        private _groundSince = -1;
        private _deadline = diag_tickTime + 300;
        private _peakDamage = 0;
        // peakDamage came back 1.00 on EVERY run in v0.4.18 -- the loads are all
        // being destroyed, not occasionally colliding. Record the AGL at which
        // damage first appears: at ~0 m it is a landing artefact and the measured
        // positions are clean, but anything mid-air means the trajectory itself was
        // disturbed and the numbers cannot be trusted.
        private _damageFirstAgl = -1;
        waitUntil {
            uiSleep 0.05;
            if (isNull _cargo) exitWith {true};
            private _dmg = damage _cargo;
            private _agl = (getPosATL _cargo) # 2;
            if (_dmg > 0) then {
                if (_dmg > _peakDamage) then {_peakDamage = _dmg};
                if (_damageFirstAgl < 0) then {_damageFirstAgl = _agl};
                _cargo setDamage 0;
            };
            if (_agl >= 10) then {_airborne = true};
            if (_chuteSimTime < 0) then {
                // Read the per-frame handler's reading; do not re-detect here.
                private _ct = _cargo getVariable ["TLB_CARP_pbenchChuteTime", -1];
                if (_ct >= 0) then {
                    _chuteSimTime = _ct;
                    _chuteAgl = _cargo getVariable ["TLB_CARP_pbenchChuteAgl", -1];
                    _chutePos = _cargo getVariable ["TLB_CARP_pbenchChutePos", []];
                };
            };
            if (_airborne && {isTouchingGround _cargo} && {_agl <= 2}) then {
                if (_groundSince < 0) then {_groundSince = time};
            } else {
                _groundSince = -1;
            };
            ((_groundSince > 0) && {(time - _groundSince) >= 0.5}) || {diag_tickTime >= _deadline}
        };

        // Sim time advancing slower than real time means Arma could not keep up.
        // Physics stays consistent in sim time, but the EachFrame pin applies fewer
        // velocity corrections per sim second, and USAF's own chute-attach check is
        // starved -- which shows up as chuteAgl well below its ~300 m trigger.
        // Logged per run so degraded runs can be excluded rather than averaged in.
        private _simElapsedS = time - _relSimTime;
        private _realElapsedS = diag_tickTime - _relRealTime;
        private _timeRatio = if (_realElapsedS > 0.001) then {_simElapsedS / _realElapsedS} else {-1};

        private _settled = getPosASL _cargo;
        // SQF trig takes DEGREES, so no conversion is needed here.
        private _fwd = [sin _exactHeading, cos _exactHeading];
        private _rgt = [cos _exactHeading, -sin _exactHeading];
        private _dE = (_settled # 0) - (_vdz # 0);
        private _dN = (_settled # 1) - (_vdz # 1);
        private _along = (_dE * (_fwd # 0)) + (_dN * (_fwd # 1));
        private _right = (_dE * (_rgt # 0)) + (_dN * (_rgt # 1));

        // chutePosASL lives in the NESTED solution hashmap, not at the top level of
        // _build. Reading the wrong path returned nil, and in SQF assigning nil
        // DELETES the variable -- which is why v0.4.12 raised "Undefined variable
        // in expression: _openalong" and logged two blank fields.
        private _predChute = (_build getOrDefault ["solution", createHashMap]) getOrDefault ["chutePosASL", []];
        private _openAlong = -9999;
        private _openRight = -9999;
        if ((count _chutePos) >= 2 && {(count _predChute) >= 2}) then {
            private _pE = (_chutePos # 0) - (_predChute # 0);
            private _pN = (_chutePos # 1) - (_predChute # 1);
            _openAlong = (_pE * (_fwd # 0)) + (_pN * (_fwd # 1));
            _openRight = (_pE * (_rgt # 0)) + (_pN * (_rgt # 1));
        };

        // USAF attaches the chute at a fixed ~300 m AGL. A materially lower value
        // means its own check was starved while this load was in freefall, and the
        // load then travelled further before the canopy opened. Those runs are not
        // measurements of the model and must not be averaged in with good ones:
        // in v0.4.33 batch 812, seven runs attached at 296.5-299.1 m and gave
        // openAlong +4.8 to +9.3 m, while the one that attached at 263.3 m gave
        // +45.5 m. Marked in the log rather than silently dropped, so the exclusion
        // is always visible and reversible.
        private _degraded = [];
        if (_chuteAgl >= 0 && {_chuteAgl < 290}) then {_degraded pushBack "LATE_CHUTE_ATTACH"};
        if (_timeRatio >= 0 && {_timeRatio < 0.9}) then {_degraded pushBack "SIM_BEHIND_REAL"};
        if ((count _degraded) > 0) then {
            diag_log format ["[PBENCH] batch=%1 run=%2 DEGRADED %3 chuteAgl=%4 timeRatio=%5 -- exclude from fits",
                _batchId, _index, _degraded joinString "+", _chuteAgl toFixed 1, _timeRatio toFixed 3];
        };

        diag_log format [
            "[PBENCH] batch=%1 run=%2 hdg=%3 dzTerrain=%4 chuteAgl=%5 chuteT=%6 canopyS=%7 openAlong=%8 openRight=%9 settledAlong=%10 settledRight=%11 radial=%12 lagS=%20 lagM=%21 fps=%22 timeRatio=%23 degraded=%24 windRel=%19 peakDamage=%14 dmgPostRelAgl=%15 dmgSpawn=%16 dmgLoaded=%17 dmgPinnedAgl=%18 releaseVel=%13",
            _batchId, _index, _exactHeading toFixed 1, (_vdz # 2) toFixed 1,
            _chuteAgl toFixed 1, (_chuteSimTime - _releaseSimTime) toFixed 3,
            (time - _chuteSimTime) toFixed 3,
            _openAlong toFixed 2, _openRight toFixed 2,
            _along toFixed 2, _right toFixed 2,
            (sqrt ((_along * _along) + (_right * _right))) toFixed 2,
            _releaseVel,
            _peakDamage toFixed 2,
            _damageFirstAgl toFixed 1,
            _dmgSpawn toFixed 2,
            _dmgLoaded toFixed 2,
            _dmgPinnedAgl toFixed 1,
            _windAtRelease,
            _lagS toFixed 3,
            _lagM toFixed 2,
            _fpsAtRelease toFixed 1,
            _timeRatio toFixed 3,
            if ((count _degraded) > 0) then {_degraded joinString "+"} else {"-"}
        ];

        TLB_CARP_state_pbenchPending = TLB_CARP_state_pbenchPending - 1;
    };
};

// Real-DZ mode is inherently serial. Every run shares the DZ, so runs with the
// same heading share an RP, and the carrier spawns directly above its RP: a wave
// of them materialises inside itself, the carriers shove each other off the pinned
// path, and the loads are released off-course or destroyed. Observed in v0.4.14.
// The virtual grid is what makes concurrency safe, because it gives every run its
// own spawn point as well as its own landing site.
private _effectiveWave = if (_spacingM > 0) then {_waveSize max 1} else {1};
if (_spacingM <= 0 && {(_waveSize max 1) > 1}) then {
    diag_log format ["[PBENCH] batch=%1 real-DZ mode forces waveSize 1 (requested %2): shared RP means shared spawn point", _batchId, _waveSize];
};

[_plans, _launch, _cargoClass, _batchId, _aglM, _groundSpeedKmh, _effectiveWave, _waveGapS, _spacingM, _spawnStaggerS, _carrierClass] spawn {
    params ["_plans", "_launch", "_cargoClass", "_batchId", "_aglM", "_groundSpeedKmh", "_waveSize", "_waveGapS", "_spacingM", "_spawnStaggerS", "_carrierClass"];
    private _wave = 0;
    private _i = 0;
    while {_i < (count _plans)} do {
        private _end = ((_i + _waveSize) min (count _plans)) - 1;
        private _remainingAfterWave = (count _plans) - (_end + 1);
        diag_log format ["[PBENCH] batch=%1 wave=%2 launching runs %3..%4", _batchId, _wave, _i, _end];
        // Spawn stagger. Creating several C-17s in a single frame is a large hitch
        // on any machine: v0.4.31 batch 372 spawned 8 at once and two runs attached
        // their chute at 270.1 m and 282.9 m instead of ~298 m, which cost them the
        // worst openAlong of the batch (78.3 m and 64.8 m). Freefall lasts ~23 s, so
        // spreading the spawns over a fraction of a second does not measurably
        // change how much the descents overlap -- it only removes the hitch.
        for "_k" from _i to _end do {
            [(_plans # _k), _cargoClass, _batchId, _aglM, _groundSpeedKmh, _carrierClass] call _launch;
            if (_k < _end) then {uiSleep _spawnStaggerS};
        };
        _i = _end + 1;
        _wave = _wave + 1;
        if (_i < (count _plans)) then {
            if (_spacingM > 0) then {
                uiSleep _waveGapS;
            } else {
                waitUntil {uiSleep 0.5; TLB_CARP_state_pbenchPending <= _remainingAfterWave};
                {if (!isNull _x) then {deleteVehicle _x}} forEach (missionNamespace getVariable ["TLB_CARP_state_pbenchObjects", []]);
                TLB_CARP_state_pbenchObjects = [];
                uiSleep _waveGapS;
            };
        };
    };
};

hint format ["PARALLEL BENCH
%1 runs, waves of %2", count _plans, (_waveSize max 1)];

// ---- Restore environment once every run has reported ------------------------
[_batchId, _windBefore, _gustsBefore, _aceWindWasDefined, _aceWindBefore, _windMode, _jpadsBefore] spawn {
    params ["_batchId", "_windBefore", "_gustsBefore", "_aceWasDef", "_aceBefore", "_windMode", "_jpadsBefore"];
    waitUntil {uiSleep 0.5; (TLB_CARP_state_pbenchPending <= 0)};
    if !(_windMode isEqualTo "LIVE") then {
        setWind [_windBefore # 0, _windBefore # 1, true];
        0 setGusts _gustsBefore;
        if (_aceWasDef) then {
            missionNamespace setVariable ["ace_weather_disableWindSimulation", _aceBefore];
        } else {
            missionNamespace setVariable ["ace_weather_disableWindSimulation", nil];
        };
    };
    {if (!isNull _x) then {deleteVehicle _x}} forEach (missionNamespace getVariable ["TLB_CARP_state_pbenchObjects", []]);
    TLB_CARP_state_pbenchObjects = [];
    TLB_CARP_state_pbenchPins = [];
    TLB_CARP_state_pbenchChuteWatch = [];
    TLB_CARP_state_pbenchSteer = [];
    TLB_CARP_state_pbenchJpads = false;
    TLB_CARP_state_jpadsEnabled = _jpadsBefore;
    if ((missionNamespace getVariable ["TLB_CARP_state_pbenchPinEh", -1]) >= 0) then {
        removeMissionEventHandler ["EachFrame", TLB_CARP_state_pbenchPinEh];
        TLB_CARP_state_pbenchPinEh = -1;
    };
    TLB_CARP_state_pbenchActive = false;
    // Expect one "Undefined variable in expression: _id" error per run from
    // USAF_Cargounctions\Cargon_dropCargo.sqf line 75. It is theirs, not ours,
    // and it is harmless -- it fires long after the load has landed and been
    // measured. Cause: line 71 of that file parks on
    //   waitUntil {count (crew _obj) > 0 || !(_pos1 isEqualTo getPosVisual _obj)}
    // which a settled unmanned load never satisfies, so the script is still
    // suspended there when this cleanup deletes the cargo. getVariable on a null
    // object then returns nil, and assigning nil DELETES _id in SQF, so line 75
    // sees it undefined.
    diag_log format ["[PBENCH] batch=%1 COMPLETE (expect one harmless USAF fn_dropCargo.sqf _id error per run; see comment)", _batchId];
    hint "PARALLEL BENCH\nBatch complete";
};

true

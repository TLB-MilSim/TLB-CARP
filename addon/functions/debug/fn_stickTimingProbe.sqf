// Stick timing probe: measure the real interval between consecutive cargo releases.
//
// Why this exists separately from the parallel bench:
//   fn_buildWorldSolution centres a stick on the DZ by moving the RP upstream by
//   half the predicted stick length, where
//       spacingM   = groundSpeedMs * multiCargo.sequenceIntervalS
//       stickLength = spacingM * (count - 1)
//   so sequenceIntervalS is the single number that decides whether a stick lands
//   centred. It is currently 0.53 s and flagged calibrationState "provisional".
//
//   The interval is a SCRIPT TIMING property, not a ballistic one:
//   fn_sequenceCargo commands canDrop, waits for that load to leave usaf_cargo, then
//   commands the next. USAF's fn_dropCargo.sqf contains a hardcoded `sleep 0.5`
//   before it detaches and updates usaf_cargo, and the single-drop lag measures
//   0.601 s on the bench across two airspeeds. If the true interval is ~0.61 rather
//   than 0.53, a 5-load stick is about 45 m longer than predicted and mis-centred by
//   roughly 22 m.
//
//   Measuring that needs neither a descent nor a landing, so this probe does not
//   wait for either. It reports in a couple of seconds per run.
//
// Usage:
//   [5] spawn TLB_CARP_fnc_stickTimingProbe;                       // 5 loads, defaults
//   [5, 3000, 500, "rhsusf_mrzr4_d", 3] spawn TLB_CARP_fnc_stickTimingProbe;  // 3 reps

params [
    ["_cargoCount", 5, [0]],
    ["_aglM", 3000, [0]],
    ["_groundSpeedKmh", 500, [0]],
    ["_cargoClass", "rhsusf_mrzr4_d", [""]],
    ["_repeats", 1, [0]],
    ["_aircraftId", "c17", [""]]
];

if (isMultiplayer) exitWith {hint "STICK PROBE\nEden / Single Player only"; false};
if (_cargoCount < 2) exitWith {hint "STICK PROBE\nNeed at least 2 loads to measure an interval"; false};
if (isNil "TLB_CARP_fnc_sequenceCargo") exitWith {hint "STICK PROBE\nsequenceCargo not available"; false};

// Carrier class from the profile, so the interval can be confirmed per airframe.
// It should be airframe-independent -- the cost is USAF's hardcoded `sleep 0.5` in
// fn_dropCargo.sqf, the same code for every aircraft -- but that is a prediction, and
// the point of this probe is that predictions about timing get measured.
private _carrierProfile = (([] call TLB_CARP_fnc_getModel) getOrDefault ["aircraft", createHashMap]) getOrDefault [_aircraftId, createHashMap];
private _carrierClass = ((_carrierProfile getOrDefault ["classNames", []]) param [0, ""]);
if (_carrierClass isEqualTo "") exitWith {hint format ["STICK PROBE: unknown aircraft profile %1", _aircraftId]; false};
if !(isClass (configFile >> "CfgVehicles" >> _carrierClass)) exitWith {hint format ["STICK PROBE: missing class %1", _carrierClass]; false};
if (missionNamespace getVariable ["TLB_CARP_state_stickProbeActive", false]) exitWith {
    hint "STICK PROBE\nAlready running"; false
};

TLB_CARP_state_stickProbeActive = true;
private _probeId = round (time * 10);
private _groundSpeedMs = _groundSpeedKmh / 3.6;

diag_log format ["[STICKPROBE] probe=%1 aircraft=%8 class=%9 loads=%2 agl=%3 gs=%4 cargo=%5 repeats=%6 modelInterval=%7",
    _probeId, _cargoCount, _aglM, _groundSpeedKmh, _cargoClass, _repeats,
    ((([player] call TLB_CARP_fnc_getModel) getOrDefault ["multiCargo", createHashMap]) getOrDefault ["sequenceIntervalS", 0.53]),
    _aircraftId, _carrierClass
];

private _allIntervals = [];

// Rep 0 is a discarded warm-up. The probe's very first invocation runs measurably
// slower -- the 2026-09-01 12-gap first run averaged 0.760 s with its reps trending
// 0.788 -> 0.765 -> 0.728, while a settled 39-gap run averaged 0.588 s at sd 0.0159
// against 0.0646. That contaminated sample was shipped as sequenceIntervalS in
// v0.4.40 and had to be corrected in v0.4.41, so the warm-up is discarded here
// rather than left for the reader to notice.
for "_rep" from 0 to _repeats do {
    private _isWarmup = (_rep isEqualTo 0);
    // Somewhere empty and high, well away from anything the mission owns.
    private _base = getPosASL player;
    private _spawnPosASL = [(_base # 0) + 2500, (_base # 1) + 2500, (getTerrainHeightASL [(_base # 0) + 2500, (_base # 1) + 2500]) + _aglM];
    private _forward = [0, 1, 0];
    private _velocity = [0, _groundSpeedMs, 0];

    private _carrier = createVehicle [_carrierClass, [_spawnPosASL # 0, _spawnPosASL # 1, 0], [], 0, "FLY"];
    _carrier allowDamage false;
    _carrier setPosASL _spawnPosASL;
    _carrier setDir 0;
    _carrier setVectorDirAndUp [_forward, [0, 0, 1]];
    _carrier setVelocity _velocity;

    private _cargos = [];
    for "_n" from 1 to _cargoCount do {
        private _c = createVehicle [_cargoClass, [_spawnPosASL # 0, _spawnPosASL # 1, 0], [], 0, "NONE"];
        _c allowDamage false;
        _c setDamage 0;
        [_carrier, _c, 0, false] call USAF_CARGO_fnc_forceLoadCargo;
        _cargos pushBack _c;
    };
    private _loaded = count (_carrier getVariable ["usaf_cargo", []]);
    if (_loaded < _cargoCount) then {
        diag_log format ["[STICKPROBE] probe=%1 rep=%2 LOAD INCOMPLETE loaded=%3 of %4", _probeId, _rep, _loaded, _cargoCount];
    };

    // Doors fully open before commanding, so the measured interval is the sequencing
    // cost and not the door animation. This is the same correction the parallel bench
    // needed: commanding in the same frame as the animate added ~0.1 s.
    private _doors = getArray (configFile >> "cfgVehicles" >> _carrierClass >> "USAF_Cargo_Doors");
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
    };

    // Per-frame pin plus per-frame release stamping. The stamp MUST be per frame:
    // a scheduled poll at 0.05 s would quantise a ~0.6 s interval by up to 8%, which
    // is the same order as the discrepancy being measured.
    TLB_CARP_state_stickProbePin = [_carrier, _cargos, getPosASL _carrier, time, _velocity, _forward];
    TLB_CARP_state_stickProbeStamps = [];
    TLB_CARP_state_stickProbeEh = addMissionEventHandler ["EachFrame", {
        private _pin = missionNamespace getVariable ["TLB_CARP_state_stickProbePin", []];
        if ((count _pin) < 6) exitWith {};
        _pin params ["_pinCarrier", "_pinCargos", "_origin", "_t0", "_vel", "_fwd"];
        if (isNull _pinCarrier) exitWith {};
        private _e = (time - _t0) max 0;
        _pinCarrier setPosASL [
            (_origin # 0) + ((_vel # 0) * _e),
            (_origin # 1) + ((_vel # 1) * _e),
            (_origin # 2) + ((_vel # 2) * _e)
        ];
        _pinCarrier setVectorDirAndUp [_fwd, [0, 0, 1]];
        _pinCarrier setVelocity _vel;
        private _aboard = _pinCarrier getVariable ["usaf_cargo", []];
        {
            if (!(_x in _aboard) && {isNil {_x getVariable "TLB_CARP_stickReleaseTime"}}) then {
                _x setVariable ["TLB_CARP_stickReleaseTime", time, false];
                TLB_CARP_state_stickProbeStamps pushBack [_x, time];
            };
        } forEach _pinCargos;
    }];

    private _cmdTime = time;
    [_carrier, _cargoCount] spawn TLB_CARP_fnc_sequenceCargo;

    // Generous: each load costs at least USAF's hardcoded 0.5 s.
    private _deadline = diag_tickTime + 10 + (_cargoCount * 3);
    waitUntil {
        uiSleep 0.05;
        ((count (_carrier getVariable ["usaf_cargo", []])) <= 0) || {diag_tickTime >= _deadline} || {isNull _carrier}
    };

    private _stamps = +(missionNamespace getVariable ["TLB_CARP_state_stickProbeStamps", []]);
    removeMissionEventHandler ["EachFrame", TLB_CARP_state_stickProbeEh];
    TLB_CARP_state_stickProbeEh = -1;
    TLB_CARP_state_stickProbePin = [];

    private _times = _stamps apply {_x # 1};
    _times sort true;
    if ((count _times) < 2) then {
        diag_log format ["[STICKPROBE] probe=%1 rep=%2 INCOMPLETE only %3 releases detected", _probeId, _rep, count _times];
    } else {
        private _intervals = [];
        for "_i" from 1 to ((count _times) - 1) do {
            _intervals pushBack ((_times # _i) - (_times # (_i - 1)));
        };
        if (!_isWarmup) then {_allIntervals append _intervals};
        private _sum = 0;
        {_sum = _sum + _x} forEach _intervals;
        private _mean = _sum / (count _intervals);
        diag_log format ["[STICKPROBE] probe=%1 rep=%2%9 releases=%3 firstLagS=%4 intervals=%5 meanIntervalS=%6 spacingM=%7 stickLengthM=%8",
            _probeId, _rep, count _times, ((_times # 0) - _cmdTime) toFixed 3,
            _intervals apply {_x toFixed 3}, _mean toFixed 4,
            (_mean * _groundSpeedMs) toFixed 1,
            (_mean * _groundSpeedMs * (_cargoCount - 1)) toFixed 1,
            if (_isWarmup) then {" [WARMUP - DISCARDED]"} else {""}
        ];
    };

    deleteVehicle _carrier;
    {if (!isNull _x) then {deleteVehicle _x}} forEach _cargos;
    uiSleep 1;
};

if ((count _allIntervals) > 0) then {
    private _sum = 0;
    {_sum = _sum + _x} forEach _allIntervals;
    private _mean = _sum / (count _allIntervals);
    private _var = 0;
    {_var = _var + ((_x - _mean) ^ 2)} forEach _allIntervals;
    private _sd = if ((count _allIntervals) > 1) then {sqrt (_var / ((count _allIntervals) - 1))} else {0};
    private _model = (([player] call TLB_CARP_fnc_getModel) getOrDefault ["multiCargo", createHashMap]) getOrDefault ["sequenceIntervalS", 0.53];
    diag_log format ["[STICKPROBE] probe=%1 SUMMARY n=%2 meanIntervalS=%3 sdS=%4 modelIntervalS=%5 errorS=%6 stickErrorM_per_gap=%7",
        _probeId, count _allIntervals, _mean toFixed 4, _sd toFixed 4, _model,
        (_mean - _model) toFixed 4, ((_mean - _model) * _groundSpeedMs) toFixed 1];
    hint format ["STICK PROBE COMPLETE\n%1 gaps measured\nmean %2 s (model %3 s)", count _allIntervals, _mean toFixed 3, _model];
} else {
    diag_log format ["[STICKPROBE] probe=%1 SUMMARY no intervals measured", _probeId];
    hint "STICK PROBE\nNo intervals measured - check RPT";
};

TLB_CARP_state_stickProbeActive = false;
true

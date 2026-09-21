params ["_carrier", ["_targetCount", -1]];
if (isNull _carrier) exitWith {false};

private _initial = [_carrier] call USAFDC_fnc_getLoadedCargo;
private _available = count _initial;
private _countToDrop = if (_targetCount < 0) then {_available} else {_targetCount min _available};
if (_countToDrop <= 0) exitWith {false};

// Stamped here too, not only in fn_triggerAutoDrop, because the sequencer is also driven
// directly by the bench and by a mission script.
_carrier setVariable ["USAFDC_stickTotal", _countToDrop, false];
_carrier setVariable ["USAFDC_stickIndex", -1, false];

for "_index" from 1 to _countToDrop do {
    private _beforeList = [_carrier] call USAFDC_fnc_getLoadedCargo;
    private _before = count _beforeList;
    if (_before <= 0) exitWith {};
    private _cargo = _beforeList # (_before - 1);
    private _cargoClass = if (isNull _cargo) then {"<null>"} else {typeOf _cargo};
    private _simStart = time;
    private _realStart = diag_tickTime;
    diag_log format ["[TLB CARP][AUTO] sequence=%1/%2 invoke sim=%3 real=%4 cargo=%5 count=%6", _index, _countToDrop, _simStart, _realStart, _cargoClass, _before];

    [_carrier, _cargo] call USAFDC_fnc_releaseSelected;
    private _deadline = time + 3;
    private _after = _before;
    // The manifest shrinking is the primary clock and always has been: it means this
    // load is physically away and the next one may go.
    //
    // The floor underneath it is new in v0.10.0. multiCargo.sequenceIntervalS = 0.588 s
    // is a MEASURED inter-release interval and the solver spaces this stick's release
    // points by it, but nothing ever made the sequencer honour it -- the interval was
    // emergent, out of USAF's attach/sleep/detach ordering, and it only held because
    // the manifest happened not to shrink until the detach. That is true for a USAF
    // load and false for an ACE or vehicle-in-vehicle one, where the source releases
    // its claim before the load has left. Without the floor those release back to back
    // and a stick the solver spaced by 0.588 s lands in one heap.
    private _model = if (isNil "USAFDC_fnc_getModel") then {createHashMap} else {call USAFDC_fnc_getModel};
    private _multi = _model getOrDefault ["multiCargo", createHashMap];
    private _intervalS = _multi getOrDefault ["sequenceIntervalS", 0.588];
    private _notBefore = _simStart + _intervalS;
    waitUntil {
        sleep 0.01;
        _after = count ([_carrier] call USAFDC_fnc_getLoadedCargo);
        ((_after < _before) && {time >= _notBefore}) || {time > _deadline}
    };
    if (time > _deadline && {_after >= _before}) exitWith {
        diag_log format ["[TLB CARP][AUTO] cargo sequence timeout sequence=%1/%2 sim=%3 real=%4 cargo=%5 count=%6", _index, _countToDrop, time, diag_tickTime, _cargoClass, _after];
    };
    diag_log format ["[TLB CARP][AUTO] sequence=%1/%2 cleared sim=%3 real=%4 cargo=%5 count=%6 elapsed=%7", _index, _countToDrop, time, diag_tickTime, _cargoClass, _after, time - _simStart];
};
true

/*
    USAFDC_fnc_steerCargo -- the guided-cargo control law, and nothing else.

    [_cargo, _dzPosASL, _glideMs, _scatterM, _releaseAglM, _engageVzMs, _stickOffset] call USAFDC_fnc_steerCargo

    Returns a hashMap describing what it did this frame:
        ["steering", bool] ["phase", string] ["errorM"] ["closingMs"] ["groundMs"] ["timeRemainingS"]

    Everything is passed in. This function reads no CARP state and no CBA setting except
    as a default, which is what lets it run on a machine that has neither.

    WHY THAT MATTERS: THE CANOPY IS USUALLY NOT THE PILOT'S

    setVelocity is a local-effect command. USAF's fn_canDrop ends with

        [_carrier, _cargo] remoteExec ["USAF_CARGO_fnc_dropCargo", _cargo]

    so the release, and the createVehicle of the parachute inside it, happen on the
    machine where the CARGO is local. On a dedicated server that is normally the server:
    cargo placed in Eden, spawned by Zeus, or spawned by a mission script belongs to it,
    and neither attachTo nor USAF's loading transfers ownership. Every steering command
    the pilot's client issued was therefore discarded in silence while the HUD reported a
    closing error, which is how guided cargo came to be "not working on the server".

    So the steering has to run on whichever machine owns the canopy, and that machine has
    none of the pilot's context: USAFDC_state_packageTimingState and
    USAFDC_state_dzPosASL are client-local, and every USAFDC_setting_jpads* is a
    CBA scope-0 setting that reads its default on a server. The pilot's client packages
    all of it into a steer job (USAFDC_fnc_steerBegin) and this function is handed the
    contents.

    THREE FINDINGS FROM FLIGHT ARE BUILT INTO THIS AND MUST NOT BE REMOVED

    1. Do not steer during canopy inflation. The load decelerates 140 -> ~2 m/s over
       about five seconds and that IS the forward throw the release point was computed
       around; steering there deleted ~70 m of along travel, more than the error being
       corrected. Instantaneous agl/|vz| is also useless as a time-to-ground estimate
       while decelerating from -230 m/s: at t=0.5 s it reads ~3 s remaining when 26 s
       actually remain.
    2. It must run EVERY frame. At the 0.05 s guidance interval the parachute's own
       physics reasserted between calls and only 41% of the commanded closing speed
       survived -- 8.0 m/s commanded, 3.28 m/s achieved.
    3. The command is wind + clamp(requiredGroundVelocity - wind, glide), NOT
       wind + direction * closingSpeed. The latter cannot fly against wind, so ground
       speed can never fall below wind speed: as the error shrinks the steering term
       shrinks with it, the wind keeps pushing, and the load sails past. Measured in
       v0.4.8, the error bottomed at 8.7 m and climbed back to 21.6 m in a 5.5 m/s wind.

    AND WHY MOVING THIS TO ANOTHER MACHINE IS PHYSICS-NEUTRAL

    Because of the shape of finding 3, the wind reading cancels out of the command
    algebraically whenever the glide clamp is not binding:

        cmd = wind + (required - wind) = required

    So even if two machines disagreed about the instantaneous wind, they would command
    the same ground velocity. Wind only enters through the clamp, which is the
    wind-limited regime where guided accuracy is already poor by construction. Better
    still, the machine that reads `wind` here is now the same machine whose simulation
    applies wind to that canopy, so command and physics come from one weather state.

    The corollary is a prohibition: WIND IS NEVER CARRIED IN THE STEER JOB. The steering
    machine must read its own, for exactly the reason above.
*/

params [
    ["_cargo", objNull, [objNull]],
    ["_dz", [], [[]]],
    ["_glideMs", -1, [0]],
    ["_scatterM", -1, [0]],
    ["_releaseAglM", -1, [0]],
    ["_engageVzMs", -1, [0]],
    // The load's slot in the stick, as an aim offset in metres [east, north], supplied by
    // fn_steerBegin. Empty means "no slot" -- one load, or no run-in to spread along --
    // and the random scatter below applies instead.
    ["_stickOffset", [], [[]]]
];

private _idle = {
    params [["_phase", "IDLE"]];
    createHashMapFromArray [
        ["steering", false], ["commanding", false], ["phase", _phase],
        ["errorM", -1], ["closingMs", 0], ["groundMs", 0], ["timeRemainingS", -1]
    ]
};

if (isNull _cargo || {(count _dz) < 3}) exitWith {["IDLE"] call _idle};

// Defaults only. A caller that has the settings (the pilot's client, or the bench)
// passes them; a caller that does not (the server) is handed them in the job.
if (_glideMs < 0) then {_glideMs = missionNamespace getVariable ["USAFDC_setting_jpadsGlideMs", 12]};
if (_scatterM < 0) then {_scatterM = missionNamespace getVariable ["USAFDC_setting_jpadsScatterM", 2]};
if (_releaseAglM < 0) then {_releaseAglM = missionNamespace getVariable ["USAFDC_setting_jpadsReleaseAglM", 3]};
if (_engageVzMs < 0) then {_engageVzMs = missionNamespace getVariable ["USAFDC_setting_jpadsEngageVzMs", 12]};

// One aim offset per package, picked at the first steer tick and stored ON THE LOAD so
// concurrent packages cannot overwrite each other's. Broadcast, because the machine
// that steers and the machines that display the closing error have to agree on where
// the load is actually aiming -- a local-only offset made every other client's readout
// wrong by up to the scatter radius.
private _offset = _cargo getVariable ["USAFDC_jpadsTargetOffset", []];

// Steer the parachute when the load is slung under one; the load follows it. An
// attached object reads zero velocity and setVelocity on it does nothing.
private _attached = attachedTo _cargo;
private _steerTarget = if (!isNull _attached && {_attached isKindOf "ParachuteBase"}) then {_attached} else {_cargo};

// A CANOPY IS A PRECONDITION, NOT A CHOICE OF TARGET.
//
// This is what USAFDC_state_packageTimingState isEqualTo "CHUTE" used to buy, and
// replacing that gate with the line above alone very nearly reintroduced the v0.4.6
// defect it was written for. In level flight the released load inherits the carrier's
// vertical speed, which is about zero, so gravity walks it through the -0.5 to
// -engageVzMs engage window over roughly a second -- at drop altitude, with 140 m/s of
// forward throw, and no parachute. Time-to-ground reads 3000/2 = 1500 s there, so the
// required ground velocity is essentially zero, the command clamps to about zero, and
// the entire forward throw the release point was computed around is deleted in the
// first second of freefall. That is exactly the failure that landed a load 93 m out
// where unguided landed 16 m.
//
// It also ends the job cleanly at the other end: the release code deletes the chute at
// touchdown, so a load settling on a slope with a plausible vertical speed can no longer
// be steered along the ground.
if !(_steerTarget isKindOf "ParachuteBase") exitWith {["NO CANOPY"] call _idle};

// OWNERSHIP DECIDES WHO COMMANDS, NOT WHO CALCULATES.
//
// The locality test is on the object actually commanded -- the canopy, not the load,
// because those can be owned by different machines -- and it is re-tested every frame
// because ownership can move. But it only gates the setVelocity at the bottom. Every
// machine runs the rest, so a pilot whose canopy is being flown by the server still gets
// a true closing error on his HUD instead of a message about whose object it is. Which
// machine holds the canopy is a networking fact and has no business on the readout.
private _commanding = local _steerTarget;

// The aim offset is picked ONCE, by the machine that will actually fly the load, and
// broadcast. A display machine that has not received it yet aims at the DZ centre for
// one or two frames rather than rolling a second offset of its own -- two machines
// rolling independently would put the steering and the readout on different aim points.
//
// A STICK SLOT IS DETERMINISTIC AND THE SCATTER IS NOT, AND THE ORDER MATTERS. The slot
// came from fn_steerBegin, computed once on one machine from the crew's run-in and the
// load's place in the stick, so every machine agrees on it without rolling anything. The
// scatter is then added on top: it exists so one load does not sit exactly on a point,
// and at its 2 m default it cannot undo a 35 m slot.
if ((count _offset) < 2) then {
    if (_commanding) then {
        private _radius = random _scatterM;
        private _bearing = random 360;
        _offset = [_radius * (sin _bearing), _radius * (cos _bearing)];
        if ((count _stickOffset) >= 2) then {
            _offset = [(_offset # 0) + (_stickOffset # 0), (_offset # 1) + (_stickOffset # 1)];
        };
        _cargo setVariable ["USAFDC_jpadsTargetOffset", _offset, true];
    } else {
        _offset = [0, 0];
    };
};

private _aglM = (getPosATL _cargo) # 2;
// Hand the last few metres back to the engine so touchdown is unguided.
if (_aglM <= _releaseAglM) exitWith {["RELEASED"] call _idle};

private _vel = velocity _steerTarget;
private _vz = _vel # 2;
if (_vz > -0.5) exitWith {["IDLE"] call _idle};
if (_vz < -_engageVzMs) exitWith {["INFLATING"] call _idle};

private _timeRemainingS = _aglM / (-_vz);
if (_timeRemainingS < 0.5) exitWith {["IDLE"] call _idle};

private _pos = getPosASL _cargo;
private _errE = ((_dz # 0) + (_offset # 0)) - (_pos # 0);
private _errN = ((_dz # 1) + (_offset # 1)) - (_pos # 1);
private _errM = sqrt ((_errE * _errE) + (_errN * _errN));

private _wind = wind;
private _reqE = _errE / _timeRemainingS;
private _reqN = _errN / _timeRemainingS;
private _airE = _reqE - (_wind # 0);
private _airN = _reqN - (_wind # 1);
private _airM = sqrt ((_airE * _airE) + (_airN * _airN));
if (_airM > _glideMs) then {
    private _scale = _glideMs / _airM;
    _airE = _airE * _scale;
    _airN = _airN * _scale;
    _airM = _glideMs;
};

// ---- flare -----------------------------------------------------------------------
//
// A canopy that is still chasing its aim point at touchdown arrives SIDEWAYS, carrying
// up to jpadsGlideMs of airspeed across the ground. A vehicle does not survive that
// politely -- flown in v0.11.3, one load of a stick destroyed on landing.
//
// Below the flare height the steering term is tapered linearly to zero while the WIND
// term is kept in full. That distinction is the whole design: dropping the wind term too
// would have the load fighting the air mass all the way down, which is the opposite of
// gentle. Keeping it means the load simply rides the air down, which is what an
// uncorrected canopy does and what the ballistic solution already predicts.
//
// The cost is accuracy, and it is bounded and small: at 25 m and a 5 m/s descent the
// load has about five seconds left, and the error it can no longer correct is whatever
// remains at that point -- metres, not tens of metres, on any pass the guidance was
// working on at all.
private _flareAglM = missionNamespace getVariable ["USAFDC_setting_jpadsFlareAglM", 25];
if (_flareAglM > 0 && {_aglM < _flareAglM}) then {
    private _taper = (_aglM / _flareAglM) max 0;
    _airE = _airE * _taper;
    _airN = _airN * _taper;
    _airM = _airM * _taper;
};

private _cmdE = (_wind # 0) + _airE;
private _cmdN = (_wind # 1) + _airN;
if (_commanding) then {
    // What survives is the number that predicts accuracy, and it is not the frame rate.
    // v0.4.6 measured 8.0 m/s commanded against 3.28 m/s achieved at a 0.05 s interval --
    // the canopy's own physics reasserting between calls. An EachFrame handler on a
    // 20 fps server IS a 0.05 s interval, so the 0.76 m and 1.15 m figures, flown on a
    // client, do not transfer until this ratio has been read on the machine now doing
    // the flying. Comparing last frame's command against this frame's achieved speed
    // costs one object variable and answers it directly.
    private _previous = _steerTarget getVariable ["USAFDC_steerCmd", []];
    if ((count _previous) >= 2) then {
        private _achieved = sqrt ((((_vel # 0) - (_wind # 0)) ^ 2) + (((_vel # 1) - (_wind # 1)) ^ 2));
        private _wanted = sqrt ((((_previous # 0) - (_wind # 0)) ^ 2) + (((_previous # 1) - (_wind # 1)) ^ 2));
        if (_wanted > 0.5) then {
            _cargo setVariable ["USAFDC_steerSurvival", _achieved / _wanted, false];
        };
    };
    _steerTarget setVariable ["USAFDC_steerCmd", [_cmdE, _cmdN], false];

    _steerTarget setVelocity [_cmdE, _cmdN, _vz];
    // A heartbeat, at 1 Hz. Without it a display machine cannot tell "another machine is
    // flying this correctly" -- the normal case once the server owns the canopy -- from
    // "no machine owns it, or its owner has no CARP loaded", and those look identical
    // from the cockpit. One public write per second per guided load is a fair price for
    // the difference between a working system and one that only appears to work.
    if ((time - (_cargo getVariable ["USAFDC_steerBeat", -1e9])) >= 1) then {
        _cargo setVariable ["USAFDC_steerBeat", time, true];
    };
};

createHashMapFromArray [
    // STEERING describes the LOAD, on every machine, because from the crew's point of
    // view the load is being steered whoever is holding the stick. "commanding" is the
    // diagnostic fact of which machine issued the command.
    ["steering", true],
    ["commanding", _commanding],
    ["phase", "STEERING"],
    ["errorM", _errM],
    ["closingMs", _airM],
    ["groundMs", sqrt ((_cmdE * _cmdE) + (_cmdN * _cmdN))],
    ["timeRemainingS", _timeRemainingS]
]

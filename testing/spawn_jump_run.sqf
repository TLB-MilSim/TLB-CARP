/* ============================================================================
   TLB CARP -- FFR jump test spawn + canopy recorder
   ----------------------------------------------------------------------------
   Spawns a C-17 with an AI pilot, inbound to the CARP DZ from a set range and
   altitude, drops you in a cargo seat, and records the jump.

   HOW TO RUN
     Do NOT paste this file. Paste spawn_jump_run.console.sqf, which is this file
     with every comment stripped -- the debug console does not run the
     preprocessor, so comments are not safe there. Stripping them also makes the
     script survive a paste that collapses newlines, since SQF is
     whitespace-insensitive but a surviving "//" would swallow the joined line.

     Esc -> Debug Console -> paste the .console.sqf -> LOCAL EXEC.
     Have a parachute in your backpack slot first.

   AFTER EDITING THIS FILE, regenerate the pasteable copy:
     python tools/strip_sqf_comments.py testing/spawn_jump_run.sqf testing/spawn_jump_run.console.sqf

   WHAT TO EXPECT
     You appear in the back of a C-17 15 km out, wings level, 500 km/h. A hint
     in the corner counts down the range. Scroll-wheel on the aircraft:
       Prep Ramp for Free Fall  (needs >200 m -- you are well above it)
       Jumplight Red / Green    (try these, see what the C-17 glow looks like)
       Stand Up                 (then walk aft and off the ramp)

     The CARP HUD will NOT appear. That is correct, not a failure: an empty
     aircraft has no CARP solution at all -- fn_buildWorldSolution.sqf:19 exits
     with NO USAF CARGO -- which is exactly why jump mode needs its own
     solution path. The hint replaces it for this test.

   WHAT IT MEASURES
     Exit point, canopy open point, and touchdown, per frame. Prints a one-line
     result and copies it to your clipboard. That line contains the one constant
     that cannot be read out of any mod's source: canopy descent rate and drift.
   ========================================================================== */

[] spawn {

    // ---- settings ----------------------------------------------------------
    private _aglM       = 3000;              // exit altitude, m above the DZ's terrain
    private _rangeM     = 15000;             // start range. 15 km = ~108 s at 500 km/h,
                                             // enough to prep the ramp, stand up and
                                             // walk aft without rushing.
    private _speedKmh   = 500;               // CARP's calibrated drop speed
    private _trackDeg   = -1;                // -1 = along the wind (see below).
                                             // Set a bearing to force a track, or
                                             // use getDir player to face it manually.
    private _dzPosASL   = [];                // empty -> use the CARP DZ, else where you stand
    private _dzName     = "JUMP DZ";
    private _planeClass = "USAF_C17";
    private _pilotClass = "B_Pilot_F";
    private _armJump = true;                 // arm CARP jump mode automatically
    private _rail     = true;                // hold the aircraft on the run-in line

    // ---- preconditions -----------------------------------------------------
    if (isNil "TLB_CARP_fnc_setDZ") exitWith {
        systemChat "TLB CARP is not loaded.";
    };
    if !(isClass (configFile >> "CfgVehicles" >> _planeClass)) exitWith {
        systemChat format ["%1 is not available -- is the USAF mod loaded?", _planeClass];
    };
    if !(isClass (configFile >> "CfgPatches" >> "ffr_main")) then {
        systemChat "WARNING: Free Fall Off The Ramp not loaded -- no ramp or jumplight actions.";
    };
    if (isNull (unitBackpack player)) then {
        systemChat "WARNING: no backpack. Put a parachute on before you jump.";
    };

    // ---- DZ ----------------------------------------------------------------
    if ((count _dzPosASL) < 3) then {
        private _existing = missionNamespace getVariable ["TLB_CARP_state_dzPosASL", []];
        if ((count _existing) > 2) then {
            _dzPosASL = +_existing;
            _dzName = missionNamespace getVariable ["TLB_CARP_state_dzName", _dzName];
            systemChat format ["DZ: reusing the CARP DZ already set (%1)", _dzName];
        } else {
            _dzPosASL = getPosASL player;
            systemChat "DZ: using where you are standing right now.";
        };
    };
    [_dzPosASL, _dzName] call TLB_CARP_fnc_setDZ;

    // ---- run-in track ------------------------------------------------------
    // Default: fly ALONG the wind, so the exit point lies on the flown line.
    //
    // The exit point is the DZ displaced UPWIND. It only sits on a run-in through
    // the DZ when the wind is along that run-in; in a crosswind it sits off to one
    // side, and the pilot is meant to fly a laterally offset track so the exit point
    // is dead ahead -- which is what the readout's OFF-TRK figure is for.
    //
    // An AI pilot corrects nothing. The first flown test ran with an arbitrary track
    // against a 10 m/s crosswind component, so the exit point was never on the line
    // the aircraft flew: the cue fired as it passed abeam a point far to one side,
    // 1569 m from the DZ against a 420 m rule, and the jump missed by 596 m. That is
    // the geometry, not the solver. Aligning the track with the wind removes the
    // variable the harness cannot control.
    if (_trackDeg < 0) then {
        private _w = wind;
        private _wMs = sqrt (((_w # 0) ^ 2) + ((_w # 1) ^ 2));
        if (_wMs > 1) then {
            _trackDeg = (((_w # 0) atan2 (_w # 1)) + 360) mod 360;
            systemChat format ["Run-in track %1 deg, along the %2 m/s wind.", round _trackDeg, _wMs toFixed 1];
        } else {
            _trackDeg = getDir player;
            systemChat format ["Wind is calm, so run-in track %1 deg from your facing.", round _trackDeg];
        };
    };

    // ---- geometry ----------------------------------------------------------
    // Trig in DEGREES. Arma's sin/cos take degrees, and a radians slip here
    // would put the start point somewhere unrelated.
    private _dirX = sin _trackDeg;
    private _dirY = cos _trackDeg;

    // Flight ASL = the DZ's terrain elevation + the exit AGL, which is the same
    // rule the CARP vertical profile uses. Deriving it from the DZ rather than
    // from the start point means the aircraft is already at the right altitude
    // when it arrives instead of climbing or sinking the whole way in.
    private _dzX = _dzPosASL # 0;
    private _dzY = _dzPosASL # 1;
    private _flightASL = (AGLToASL [_dzX, _dzY, _aglM]) # 2;

    private _start  = [_dzX - (_dirX * _rangeM), _dzY - (_dirY * _rangeM), _flightASL];
    private _beyond = [_dzX + (_dirX * _rangeM), _dzY + (_dirY * _rangeM), _flightASL];

    // ---- you must lead your own group ---------------------------------------
    // FFR's "Prep Ramp for Free Fall" condition is
    //   _this == driver _target || (AI driver && _this == leader _this)
    // so as a passenger you only get the action if you lead your own group.
    if (leader player != player) then {
        [player] joinSilent (createGroup [side player, true]);
        systemChat "Moved you into your own group -- FFR's Prep Ramp needs you to be leader.";
    };

    // ---- aircraft ----------------------------------------------------------
    private _plane = createVehicle [_planeClass, [_start # 0, _start # 1, 0], [], 0, "FLY"];
    _plane allowDamage false;
    _plane setFuel 1;
    _plane engineOn true;

    // Orientation BEFORE velocity. setDir / setVectorDirAndUp wipe velocity in
    // Arma -- that ordering was the v0.3.0 autopilot bug and it is just as wrong
    // here: reversed, the aircraft spawns pointing correctly and stationary.
    _plane setPosASL _start;
    _plane setVectorDirAndUp [[_dirX, _dirY, 0], [0, 0, 1]];
    private _speedMs = _speedKmh / 3.6;
    _plane setVelocity [_dirX * _speedMs, _dirY * _speedMs, 0];
    _plane flyInHeight _aglM;

    // ---- AI pilot, in its own group so yours stays yours --------------------
    private _grp = createGroup [side player, true];
    private _pilot = _grp createUnit [_pilotClass, [_start # 0, _start # 1, 0], [], 0, "NONE"];
    _pilot allowDamage false;
    _pilot moveInDriver _plane;
    _grp setBehaviour "CARELESS";
    _grp setCombatMode "BLUE";
    private _wp = _grp addWaypoint [_beyond, 0];
    _wp setWaypointType "MOVE";
    // NOT "FULL". The first version set FULL, which overrides the spawn velocity:
    // the AI wound a C-17 up to 231 m/s (833 km/h) and the exit forward throw was
    // measured at 208 m/s instead of the 125 m/s that 500 km/h should give. Every
    // throw figure taken before this fix is scaled to the wrong airspeed.
    _wp setWaypointSpeed "NORMAL";
    _wp setWaypointBehaviour "CARELESS";
    _plane forceSpeed _speedMs;

    // ---- hold the aircraft on the line -------------------------------------
    // VELOCITY ONLY. Do not add an orientation write to this loop.
    //
    // The first version of this rail called setVectorDirAndUp every frame, just
    // before setVelocity, and it FROZE THE AIRCRAFT: velocity read exactly the
    // commanded 138.9 m/s on the correct bearing, the aircraft was not attached to
    // anything, and it did not move. Measured in one session on one aircraft:
    //
    //     rail with per-frame orientation :   2.0 m/s of actual travel
    //     no rail at all                  : 138.3 m/s
    //     velocity only                   : 130.8 m/s (still accelerating)
    //
    // Re-seating the transform every frame stops movement accumulating. It cost a
    // whole flown test: the exit happened 14.8 km from the DZ because the aircraft
    // had been sitting still since spawn.
    //
    // fn_updateAutopilot does the same two calls in the same order and flies fine,
    // because it runs on the 20 Hz guidance loop rather than every frame. The
    // ordering rule stands; the frequency is what broke this.
    //
    // fn_parallelDropBench's pin also writes orientation every frame and is fine,
    // because it never relies on integration at all -- it computes position
    // analytically from elapsed time and sets it. That approach gives exact speed,
    // but it is a position rail with a player aboard, so it is not used here.
    //
    // Velocity is CRABBED onto the line rather than holding the nose on track and
    // sliding sideways: commanded velocity and commanded heading must not be flown
    // apart, which is what produced the reverse-flight bug fixed in v0.3.2. Here the
    // nose simply follows the velocity, because nothing forces it.
    //
    // This is a test harness, not the autopilot, and validates nothing about it.
    if (_rail) then {
        if (!isNil "TLB_CARP_JUMPTEST_RAIL") then {
            [TLB_CARP_JUMPTEST_RAIL] call CBA_fnc_removePerFrameHandler;
        };
        TLB_CARP_JUMPTEST_RAIL = [{
            params ["_args", "_pfID"];
            _args params ["_plane", "_dz", "_tE", "_tN", "_speedMs", "_flightASL"];
            if (isNull _plane || {!alive _plane}) exitWith {
                [_pfID] call CBA_fnc_removePerFrameHandler;
            };
            private _pos = getPosASL _plane;
            // Right-hand normal to the track. Cross-track error is positive when the
            // aircraft sits right of the line through the DZ.
            private _nE = _tN;
            private _nN = -_tE;
            private _xtk = (((_pos # 0) - (_dz # 0)) * _nE) + (((_pos # 1) - (_dz # 1)) * _nN);
            private _latMs = ((-_xtk * 0.15) max -20) min 20;
            private _vzMs = ((((_flightASL - (_pos # 2)) * 0.4) max -12) min 12);
            private _vE = (_tE * _speedMs) + (_nE * _latMs);
            private _vN = (_tN * _speedMs) + (_nN * _latMs);
            _plane setVelocity [_vE, _vN, _vzMs];
        }, 0, [_plane, _dzPosASL, _dirX, _dirY, _speedMs, _flightASL]] call CBA_fnc_addPerFrameHandler;
        systemChat "Aircraft held on the run-in line by the harness.";
    };

    player moveInCargo _plane;

    systemChat format [
        "Inbound: %1 km on track %2, %3 m AGL, %4 km/h. Prep Ramp when ready.",
        (_rangeM / 1000) toFixed 1, round _trackDeg, _aglM, _speedKmh
    ];

    // ---- lock the run-in and arm jump mode ---------------------------------
    // Done from here rather than through the CARP panel because the panel's gating
    // on an empty aircraft is not something this script should depend on:
    // fn_buildWorldSolution refuses an empty carrier outright, and whether that
    // reaches the panel's lock control is a question for the panel, not the test.
    // fn_lockRunIn itself only needs a valid aircraft state, which an empty C-17 has.
    //
    // The wait is for the ground track to mean something. lockRunIn captures the
    // aircraft's CURRENT ground track as the required final heading, so capturing it
    // before the AI has settled onto the leg locks a track it is not actually flying.
    if (_armJump && {!isNil "TLB_CARP_fnc_armJumpRun"}) then {
        // Wait until the aircraft is actually TRACKING AT THE DZ before locking, not
        // merely up to speed. fn_lockRunIn captures the current ground track as the
        // required final heading -- by design, and that invariant is not up for
        // negotiation -- so locking while the AI is still settling locks a line that
        // does not pass through the DZ. Every subsequent exit point then sits off
        // that line, the cue refuses, and it looks like a solver fault.
        //
        // The first flown test locked on speed alone and did exactly this.
        private _deadline = time + 30;
        waitUntil {
            uiSleep 0.25;
            isNull _plane || {time > _deadline} || {
                (speed _plane) > 300 && {
                    (velocity _plane) params ["_vx", "_vy"];
                    private _trk = ((_vx atan2 _vy) + 360) mod 360;
                    private _brg = (getPosASL _plane) getDir _dzPosASL;
                    (abs (((_trk - _brg + 540) mod 360) - 180)) < 1.5
                }
            }
        };
        uiSleep 1;
        if (!isNull _plane) then {
            if ([] call TLB_CARP_fnc_lockRunIn) then {
                private _probe = [_plane] call TLB_CARP_fnc_buildJumpSolution;
                if (_probe getOrDefault ["valid", false]) then {
                    [] call TLB_CARP_fnc_armJumpRun;
                    systemChat format [
                        "JUMP ARMED: exit %1 m upwind, open %2 m, freefall %3 s, wind %4 m/s",
                        round (_probe get "exitRangeM"),
                        round (_probe get "openAglM"),
                        (_probe get "freefallTimeS") toFixed 1,
                        (_probe get "windMs") toFixed 1
                    ];
                } else {
                    systemChat format ["jump solution invalid: %1", _probe getOrDefault ["reason", "?"]];
                };
            } else {
                systemChat "run-in lock failed -- lock from the CARP panel, arm by ACE self-action";
            };
        };
    };

    // ---- recorder ----------------------------------------------------------
    TLB_CARP_JUMPTEST = createHashMapFromArray [
        ["phase", "ABOARD"], ["plane", _plane], ["dz", _dzPosASL],
        ["toldRamp", false], ["lastReport", -1],
        ["exitTime", -1], ["exitPosASL", []], ["exitVel", []], ["wind", [0, 0, 0]],
        ["exitAgl", -1], ["exitDzRange", -1],
        ["chuteTime", -1], ["chutePosASL", []], ["chuteAgl", -1],
        // Steady-state marks. The first seconds after each transition are a
        // deceleration transient, and a rate averaged across one is not a rate --
        // run 1 of the first batch opened at 129 m, spent 10.5 s under canopy and
        // returned 11.94 m/s against 7.7-10.0 for the longer runs, purely because
        // the opening deceleration filled most of its window. Marking a point a
        // few seconds in and measuring from there gives the steady figure, and the
        // difference between the two is itself the transient's cost in altitude.
        ["ffMarkTime", -1], ["ffMarkAsl", -1],
        ["canMarkTime", -1], ["canMarkPosASL", []]
    ];

    if !(isNil "TLB_CARP_JUMPTEST_EH") then {
        removeMissionEventHandler ["EachFrame", TLB_CARP_JUMPTEST_EH];
    };

    // PER FRAME, deliberately, not a uiSleep loop. In the cargo campaign a
    // 0.05 s poll reported canopy attach at 230-254 m against a fixed 300 m
    // trigger and that artefact was mistaken for physics for a full release.
    // The same poll here would put the canopy open point tens of metres low and
    // corrupt the descent rate this test exists to measure.
    TLB_CARP_JUMPTEST_EH = addMissionEventHandler ["EachFrame", {

        private _r = TLB_CARP_JUMPTEST;
        private _phase = _r get "phase";
        private _veh = objectParent player;
        private _agl = (getPosATL player) # 2;
        private _vel = velocity player;
        private _horizMs = sqrt (((_vel # 0) ^ 2) + ((_vel # 1) ^ 2));
        private _dz = _r get "dz";
        private _dzRange = (getPosASL player) distance2D _dz;

        // ---- rolling readout ----
        // Jump mode owns the hint slot when it is armed. Arma has ONE hint, so the
        // recorder's readout and fn_updateJumpCue's both writing it at a few Hz
        // makes the two flicker over each other -- which is exactly what the first
        // flown test reported. The recorder's readout is the expendable one.
        if (!(missionNamespace getVariable ["TLB_CARP_state_jumpArmed", false])
            && {(time - (_r get "lastReport")) >= 1}) then {
            _r set ["lastReport", time];
            private _plane = _r get "plane";
            private _text = switch (_phase) do {
                case "ABOARD": {
                    if (isNull _plane) then {"aircraft gone"} else {
                        format [
                            "DZ  %1 km\nALT %2 m\nGS  %3 km/h\n%4",
                            (((getPosASL _plane) distance2D _dz) / 1000) toFixed 2,
                            round ((getPosATL _plane) # 2),
                            round (speed _plane),
                            if (isNull _veh) then {"ON RAMP"} else {"SEATED"}
                        ]
                    }
                };
                case "FREEFALL": {
                    format ["FREEFALL\nAGL %1 m\nVS  %2 m/s\nDZ  %3 m",
                        round _agl, round (_vel # 2), round _dzRange]
                };
                case "CANOPY": {
                    format ["CANOPY\nAGL %1 m\nVS  %2 m/s\nDZ  %3 m",
                        round _agl, (_vel # 2) toFixed 1, round _dzRange]
                };
                default {""};
            };
            if !(_text isEqualTo "") then {hintSilent parseText ("<t size='0.9'>" + _text + "</t>")};
        };

        switch (_phase) do {

            case "ABOARD": {
                // Standing up in FFR calls moveOut, so objectParent goes null and
                // you are on foot at altitude 2 km away inside the hidden dummy.
                // Altitude alone would read that as an exit. The discriminator is
                // horizontal speed: the dummy is attached to a static helper, so
                // on the ramp you are doing ~0, and the instant FFR hands you back
                // to the real aircraft you are doing 0.9 x its velocity.
                if (isNull _veh && {!(_r get "toldRamp")} && {_horizMs < 5} && {_agl > 30}) then {
                    _r set ["toldRamp", true];
                    systemChat "Standing on the ramp (FFR dummy). Walk aft to jump.";
                };
                if (isNull _veh && {_horizMs > 30} && {_agl > 30}) then {
                    _r set ["phase", "FREEFALL"];
                    _r set ["exitTime", time];
                    _r set ["exitPosASL", getPosASL player];
                    _r set ["exitVel", _vel];
                    _r set ["wind", wind];
                    // Exit AGL was missing from the first version's result line,
                    // which is the one number needed to derive freefall terminal
                    // velocity from the freefall duration. Without it, a run whose
                    // freefall lasted 149 s could not be distinguished between a
                    // high exit and a broken measurement.
                    _r set ["exitAgl", _agl];
                    _r set ["exitDzRange", _dzRange];
                    private _line = format [
                        "EXIT  agl=%1 m  dzRange=%2 m  horiz=%3 m/s  vs=%4 m/s  wind=[%5, %6]",
                        round _agl, round _dzRange, _horizMs toFixed 1, (_vel # 2) toFixed 1,
                        (wind # 0) toFixed 2, (wind # 1) toFixed 2
                    ];
                    systemChat _line;
                    diag_log ("TLB_CARP_JUMPTEST " + _line);
                };
            };

            case "FREEFALL": {
                if (((_r get "ffMarkTime") < 0) && {(time - (_r get "exitTime")) >= 3}) then {
                    _r set ["ffMarkTime", time];
                    _r set ["ffMarkAsl", (getPosASL player) # 2];
                };
                if (!isNull _veh && {_veh isKindOf "ParachuteBase"}) then {
                    _r set ["phase", "CANOPY"];
                    _r set ["chuteTime", time];
                    _r set ["chutePosASL", getPosASL player];
                    _r set ["chuteAgl", _agl];
                    private _line = format [
                        "CANOPY  t+%1 s after exit  agl=%2 m  dzRange=%3 m  fell=%4 m",
                        (time - (_r get "exitTime")) toFixed 2, round _agl, round _dzRange,
                        round (((_r get "exitPosASL") # 2) - ((getPosASL player) # 2))
                    ];
                    systemChat _line;
                    diag_log ("TLB_CARP_JUMPTEST " + _line);
                };
                if (_agl < 2) then {
                    _r set ["phase", "DONE"];
                    systemChat "Ground contact with no canopy detected.";
                    removeMissionEventHandler ["EachFrame", _thisEventHandler];
                };
            };

            case "CANOPY": {
                if (((_r get "canMarkTime") < 0) && {(time - (_r get "chuteTime")) >= 4}) then {
                    _r set ["canMarkTime", time];
                    _r set ["canMarkPosASL", getPosASL player];
                };
                if (_agl < 2) then {
                    _r set ["phase", "DONE"];
                    private _dt = (time - (_r get "chuteTime")) max 0.01;
                    private _chutePos = _r get "chutePosASL";
                    private _drop = (_chutePos # 2) - ((getPosASL player) # 2);
                    private _drift = _chutePos distance2D (getPosASL player);
                    private _w = _r get "wind";
                    private _land = getPosASL player;
                    private _ffT = (_r get "chuteTime") - (_r get "exitTime");

                    // Freefall steady-state vertical speed, from the 3 s mark to
                    // canopy open. Combined with exitAgl this is what pins terminal
                    // velocity instead of leaving it inferred from a guessed exit.
                    private _ffVz = -1;
                    if ((_r get "ffMarkTime") > 0) then {
                        private _ffDt = ((_r get "chuteTime") - (_r get "ffMarkTime")) max 0.01;
                        _ffVz = ((_r get "ffMarkAsl") - (_chutePos # 2)) / _ffDt;
                    };

                    // Freefall horizontal displacement, and what is left of it once
                    // the wind's share is subtracted.
                    //
                    // The wind drift law -- drift = windSpeed x freefallTime -- came
                    // out within 4% on the 10 m/s run, but only because that exit
                    // happened to sit almost exactly upwind of the DZ, so the
                    // exit-to-DZ range stood in for the drift. That is luck, not
                    // instrumentation. Measuring the displacement vector directly and
                    // subtracting the wind leaves the residual: the exit forward
                    // throw (0.9 x aircraft velocity, ~125 m/s at 500 km/h, decaying
                    // over the first seconds) plus whatever tracking the jumper did.
                    // If that residual lies along the run-in track it is throw.
                    private _exitPos = _r get "exitPosASL";
                    private _ffTravel = -1;
                    private _ffBearing = -1;
                    private _residM = -1;
                    private _residBearing = -1;
                    if ((count _exitPos) > 2) then {
                        _ffTravel = _exitPos distance2D _chutePos;
                        _ffBearing = _exitPos getDir _chutePos;
                        private _wdE = (_w # 0) * _ffT;
                        private _wdN = (_w # 1) * _ffT;
                        private _rE = ((_chutePos # 0) - (_exitPos # 0)) - _wdE;
                        private _rN = ((_chutePos # 1) - (_exitPos # 1)) - _wdN;
                        _residM = sqrt ((_rE * _rE) + (_rN * _rN));
                        _residBearing = (((_rE atan2 _rN) + 360) mod 360);
                    };
                    private _exitVel = _r get "exitVel";
                    private _exitHoriz = -1;
                    if ((count _exitVel) > 1) then {
                        _exitHoriz = sqrt (((_exitVel # 0) ^ 2) + ((_exitVel # 1) ^ 2));
                    };

                    // Canopy steady state, from the 4 s mark to touchdown.
                    private _stRate = -1;
                    private _stGlide = -1;
                    private _stRatio = -1;
                    private _transientM = -1;
                    // Air-relative, not ground-relative. The ground figure is
                    // wind-contaminated and useless as a canopy constant: the same
                    // canopy read a ground glide of 1.44 crosswind and 2.30 downwind,
                    // while subtracting the wind gave 1.274 and 1.271 -- the same
                    // number to 0.3%. Ground speed is reported alongside for context
                    // but the ratio is the air-relative one.
                    private _stAirSpeed = -1;
                    if ((_r get "canMarkTime") > 0) then {
                        private _m = _r get "canMarkPosASL";
                        private _stDt = (time - (_r get "canMarkTime")) max 0.01;
                        _stRate = ((_m # 2) - (_land # 2)) / _stDt;
                        _stGlide = (_m distance2D _land) / _stDt;
                        private _airE = (((_land # 0) - (_m # 0)) / _stDt) - (_w # 0);
                        private _airN = (((_land # 1) - (_m # 1)) / _stDt) - (_w # 1);
                        _stAirSpeed = sqrt ((_airE * _airE) + (_airN * _airN));
                        if (_stRate > 0.01) then {_stRatio = _stAirSpeed / _stRate};
                        _transientM = (_chutePos # 2) - (_m # 2);
                    };

                    private _line = format [
                        "CANOPY RESULT  exitAgl=%1 m  exitDzRange=%2 m  freefall=%3 s  ffVz=%4 m/s  openAgl=%5 m  canopyTime=%6 s  descent=%7 m  rateAvg=%8 m/s  rateSteady=%9 m/s  openTransient=%10 m in 4 s",
                        round (_r get "exitAgl"),
                        round (_r get "exitDzRange"),
                        _ffT toFixed 2,
                        _ffVz toFixed 2,
                        round (_r get "chuteAgl"),
                        _dt toFixed 2,
                        round _drop,
                        (_drop / _dt) toFixed 2,
                        _stRate toFixed 2,
                        round _transientM
                    ] + format [
                        "  ||  exitHoriz=%1 m/s  ffTravel=%2 m  ffBearing=%3  windDriftPredicted=%4 m  residual=%5 m toward %6",
                        _exitHoriz toFixed 1,
                        round _ffTravel,
                        round _ffBearing,
                        round ((sqrt (((_w # 0) ^ 2) + ((_w # 1) ^ 2))) * _ffT),
                        round _residM,
                        round _residBearing
                    ] + format [
                        "  ||  groundGlideAvg=%1 m/s  groundGlideSteady=%2 m/s  AIRSPEED=%10 m/s  AIRGLIDERATIO=%3  travel=%4 m  bearing=%5  wind=[%6, %7] (%8 m/s)  dzMiss=%9 m",
                        (_drift / _dt) toFixed 2,
                        _stGlide toFixed 2,
                        _stRatio toFixed 3,
                        round _drift,
                        round (_chutePos getDir _land),
                        (_w # 0) toFixed 2, (_w # 1) toFixed 2,
                        (sqrt (((_w # 0) ^ 2) + ((_w # 1) ^ 2))) toFixed 2,
                        round (_land distance2D _dz),
                        _stAirSpeed toFixed 2
                    ];
                    systemChat _line;
                    diag_log ("TLB_CARP_JUMPTEST " + _line);
                    copyToClipboard _line;
                    systemChat "Result copied to clipboard.";
                    removeMissionEventHandler ["EachFrame", _thisEventHandler];
                };
            };

            default {};
        };
    }];
};

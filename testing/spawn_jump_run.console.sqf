[] spawn {

    private _aglM       = 3000;
    private _rangeM     = 15000;

    private _speedKmh   = 500;
    private _trackDeg   = -1;

    private _dzPosASL   = [];
    private _dzName     = "JUMP DZ";
    private _planeClass = "USAF_C17";
    private _pilotClass = "B_Pilot_F";
    private _armJump = true;
    private _rail     = true;

    if (isNil "USAFDC_fnc_setDZ") exitWith {
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

    if ((count _dzPosASL) < 3) then {
        private _existing = missionNamespace getVariable ["USAFDC_state_dzPosASL", []];
        if ((count _existing) > 2) then {
            _dzPosASL = +_existing;
            _dzName = missionNamespace getVariable ["USAFDC_state_dzName", _dzName];
            systemChat format ["DZ: reusing the CARP DZ already set (%1)", _dzName];
        } else {
            _dzPosASL = getPosASL player;
            systemChat "DZ: using where you are standing right now.";
        };
    };
    [_dzPosASL, _dzName] call USAFDC_fnc_setDZ;

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

    private _dirX = sin _trackDeg;
    private _dirY = cos _trackDeg;

    private _dzX = _dzPosASL # 0;
    private _dzY = _dzPosASL # 1;
    private _flightASL = (AGLToASL [_dzX, _dzY, _aglM]) # 2;

    private _start  = [_dzX - (_dirX * _rangeM), _dzY - (_dirY * _rangeM), _flightASL];
    private _beyond = [_dzX + (_dirX * _rangeM), _dzY + (_dirY * _rangeM), _flightASL];

    if (leader player != player) then {
        [player] joinSilent (createGroup [side player, true]);
        systemChat "Moved you into your own group -- FFR's Prep Ramp needs you to be leader.";
    };

    private _plane = createVehicle [_planeClass, [_start # 0, _start # 1, 0], [], 0, "FLY"];
    _plane allowDamage false;
    _plane setFuel 1;
    _plane engineOn true;

    _plane setPosASL _start;
    _plane setVectorDirAndUp [[_dirX, _dirY, 0], [0, 0, 1]];
    private _speedMs = _speedKmh / 3.6;
    _plane setVelocity [_dirX * _speedMs, _dirY * _speedMs, 0];
    _plane flyInHeight _aglM;

    private _grp = createGroup [side player, true];
    private _pilot = _grp createUnit [_pilotClass, [_start # 0, _start # 1, 0], [], 0, "NONE"];
    _pilot allowDamage false;
    _pilot moveInDriver _plane;
    _grp setBehaviour "CARELESS";
    _grp setCombatMode "BLUE";
    private _wp = _grp addWaypoint [_beyond, 0];
    _wp setWaypointType "MOVE";

    _wp setWaypointSpeed "NORMAL";
    _wp setWaypointBehaviour "CARELESS";
    _plane forceSpeed _speedMs;

    if (_rail) then {
        if (!isNil "USAFDC_JUMPTEST_RAIL") then {
            [USAFDC_JUMPTEST_RAIL] call CBA_fnc_removePerFrameHandler;
        };
        USAFDC_JUMPTEST_RAIL = [{
            params ["_args", "_pfID"];
            _args params ["_plane", "_dz", "_tE", "_tN", "_speedMs", "_flightASL"];
            if (isNull _plane || {!alive _plane}) exitWith {
                [_pfID] call CBA_fnc_removePerFrameHandler;
            };
            private _pos = getPosASL _plane;

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

    if (_armJump && {!isNil "USAFDC_fnc_armJumpRun"}) then {

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
            if ([] call USAFDC_fnc_lockRunIn) then {
                private _probe = [_plane] call USAFDC_fnc_buildJumpSolution;
                if (_probe getOrDefault ["valid", false]) then {
                    [] call USAFDC_fnc_armJumpRun;
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

    USAFDC_JUMPTEST = createHashMapFromArray [
        ["phase", "ABOARD"], ["plane", _plane], ["dz", _dzPosASL],
        ["toldRamp", false], ["lastReport", -1],
        ["exitTime", -1], ["exitPosASL", []], ["exitVel", []], ["wind", [0, 0, 0]],
        ["exitAgl", -1], ["exitDzRange", -1],
        ["chuteTime", -1], ["chutePosASL", []], ["chuteAgl", -1],

        ["ffMarkTime", -1], ["ffMarkAsl", -1],
        ["canMarkTime", -1], ["canMarkPosASL", []]
    ];

    if !(isNil "USAFDC_JUMPTEST_EH") then {
        removeMissionEventHandler ["EachFrame", USAFDC_JUMPTEST_EH];
    };

    USAFDC_JUMPTEST_EH = addMissionEventHandler ["EachFrame", {

        private _r = USAFDC_JUMPTEST;
        private _phase = _r get "phase";
        private _veh = objectParent player;
        private _agl = (getPosATL player) # 2;
        private _vel = velocity player;
        private _horizMs = sqrt (((_vel # 0) ^ 2) + ((_vel # 1) ^ 2));
        private _dz = _r get "dz";
        private _dzRange = (getPosASL player) distance2D _dz;

        if (!(missionNamespace getVariable ["USAFDC_state_jumpArmed", false])
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

                    _r set ["exitAgl", _agl];
                    _r set ["exitDzRange", _dzRange];
                    private _line = format [
                        "EXIT  agl=%1 m  dzRange=%2 m  horiz=%3 m/s  vs=%4 m/s  wind=[%5, %6]",
                        round _agl, round _dzRange, _horizMs toFixed 1, (_vel # 2) toFixed 1,
                        (wind # 0) toFixed 2, (wind # 1) toFixed 2
                    ];
                    systemChat _line;
                    diag_log ("USAFDC_JUMPTEST " + _line);
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
                    diag_log ("USAFDC_JUMPTEST " + _line);
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

                    private _ffVz = -1;
                    if ((_r get "ffMarkTime") > 0) then {
                        private _ffDt = ((_r get "chuteTime") - (_r get "ffMarkTime")) max 0.01;
                        _ffVz = ((_r get "ffMarkAsl") - (_chutePos # 2)) / _ffDt;
                    };

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

                    private _stRate = -1;
                    private _stGlide = -1;
                    private _stRatio = -1;
                    private _transientM = -1;

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
                    diag_log ("USAFDC_JUMPTEST " + _line);
                    copyToClipboard _line;
                    systemChat "Result copied to clipboard.";
                    removeMissionEventHandler ["EachFrame", _thisEventHandler];
                };
            };

            default {};
        };
    }];
};

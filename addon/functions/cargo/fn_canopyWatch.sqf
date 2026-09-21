/*
    USAFDC_fnc_canopyWatch

    Opens a released load's canopy on the frame it crosses the trigger altitude, and
    owns everything from there to the load sitting still on the ground.

        [_cargo, _carrier, _smoke] call USAFDC_fnc_canopyWatch

    WHY THIS IS NOT A waitUntil IN THE RELEASE SCRIPT ANY MORE

    USAF's fn_dropCargo does `waitUntil {getPos _obj select 2 < 300}` inside a spawned
    script, and CARP's release copied it. A scheduled script shares roughly three
    milliseconds of frame time with every other scheduled script, so a condition written
    as "check every frame" actually means "check whenever the scheduler reaches me".

    With one load that is prompt, and 300 m is met. With a stick it is not: three release
    threads, the guidance loop, the package tracker and the steering all want the same
    three milliseconds. Cargo freefalls at about 230 m/s, so every slipped frame is
    another four to five metres.

    And 300 m is not generous. The load decelerates from terminal over about five
    seconds, which needs most of it. A canopy that opens late does not open in time and
    the load arrives still travelling. Flown in v0.11.3: a stick of three, one canopy
    late, that load destroyed on impact.

    The project has met this from the other side. v0.4.x read canopy attach altitudes of
    229.8, 236.7 and 253.7 m against a fixed 300 m trigger and reported it as "the chute
    attaches late" -- which was the poll, not the physics, and it drove a release-throttle
    change that had to be reverted. The lesson then was to detect per frame. Here the
    poll is not the instrument but the MECHANISM, so the same answer applies with more
    force: the altitude test runs on the frame loop, and the canopy is created inline on
    the frame that crosses, not handed back to a scheduler that may be several frames
    behind.

    ONE HANDLER FOR ANY NUMBER OF LOADS

    A handler per load would put the scheduling problem back in a different costume -- a
    stick of eight would be eight handlers competing. One handler walks a pending list
    and stops itself when the list empties, so the per-frame cost is zero between drops.

    WHAT STAYS SCHEDULED

    Only the housekeeping after the canopy is attached: the five-second wait before the
    chute is levelled, the descent, the touchdown tidy-up and the smoke relight loop.
    None of it is timing-critical to a metre, and all of it sleeps.
*/

params ["_cargo", "_carrier", ["_smoke", true], ["_triggerAglM", 300]];
if (isNull _cargo) exitWith {false};

_cargo setVariable ["USAFDC_canopyPending", true, false];

if (isNil "USAFDC_state_canopyPending") then {USAFDC_state_canopyPending = []};
USAFDC_state_canopyPending pushBack [_cargo, _carrier, _smoke, _triggerAglM];

// Already running: it will pick the new entry up on its next frame.
if !(isNil "USAFDC_state_canopyPfh") exitWith {true};

USAFDC_state_canopyPfh = [{
    private _survivors = [];
    {
        _x params ["_cargo", "_carrier", ["_smoke", true], ["_triggerAglM", 300]];

        if (isNull _cargo) then {continue};

        // A LOAD THAT IS STILL ATTACHED TO ANYTHING HAS NO ALTITUDE OF ITS OWN.
        //
        // This destroyed an aircraft in v0.16.3. getPos on an attached object returns its
        // offset from its PARENT, not its height above the ground -- so a load sitting in
        // the release sequence's attachTo, three thousand metres up, tests as about one
        // metre and crosses a 300 m trigger instantly. The RPT recorded it exactly:
        //
        //   [CANOPY] open agl=-1 trigger=300 vz=2 sim=430.622   <- release was sim=430.061
        //   [CAL] chute attachSim=1.15  cargoPos=[...,2841.17]  <- 23.5 s expected
        //
        // A canopy inflating at the ramp stops the load dead a few metres behind the
        // aircraft that just released it, and the aircraft flies into it.
        //
        // Two independent guards, because either alone leaves a hole. The attachment test
        // is the meaning -- a load being carried is not falling and cannot need a chute --
        // and it also covers our own canopy already being on. The altitude below is then
        // read from getPosASL, which is a real world position whatever the object is
        // attached to, instead of getPos, whose answer depends on that.
        if !(isNull (attachedTo _cargo)) then {
            _survivors pushBack _x;
            continue;
        };
        if (((ASLToAGL (getPosASL _cargo)) # 2) >= _triggerAglM) then {
            _survivors pushBack _x;
            continue;
        };

        // ---- crossed. Everything here runs INLINE, on this frame. ----------------
        _cargo setVariable ["USAFDC_canopyPending", false, false];
        // What it actually opened at, so a late canopy can never again be argued about
        // from memory. Compare it against the trigger in the RPT.
        // BOTH readings, deliberately. getPos is parent-relative for an attached object and
        // getPosASL is not, and the two disagreeing is the whole defect -- so the next RPT
        // says which was which instead of leaving it to be argued from memory.
        diag_log format ["[TLB CARP][CANOPY] open cargo=%1 agl=%2 rawGetPosZ=%3 attachedTo=%4 trigger=%5 vz=%6 sim=%7",
            typeOf _cargo, round ((ASLToAGL (getPosASL _cargo)) # 2), round ((getPos _cargo) # 2),
            typeOf (attachedTo _cargo), _triggerAglM, round ((velocity _cargo) # 2), time];

        // USAF's side mapping, reproduced rather than called, so this works with USAF
        // absent. The strobe colours look transposed against the sides; that is USAF's
        // table as shipped and copying it faithfully matters more than tidying it.
        private _side = if (isNull (driver _carrier)) then {west} else {side (driver _carrier)};
        private _chuteClass = "B_Parachute_02_F";
        private _strobeClass = "NVG_TargetC";
        switch (_side) do {
            case east: {_chuteClass = "O_Parachute_02_F"; _strobeClass = "NVG_TargetW"};
            case west: {_chuteClass = "B_Parachute_02_F"; _strobeClass = "NVG_TargetE"};
            case resistance: {_chuteClass = "I_Parachute_02_F"; _strobeClass = "NVG_TargetC"};
        };

        // Created at the load's real world position. getPos would place them relative to a
        // parent if it ever had one, which is how a canopy ends up somewhere the load is not.
        private _openAt = ASLToAGL (getPosASL _cargo);
        private _chute = _chuteClass createVehicle _openAt;
        private _strobe = _strobeClass createVehicle _openAt;
        _chute attachTo [_cargo, [0, 0, 0]];
        _strobe attachTo [_cargo, [0, -2, 0.5]];
        detach _chute;

        /*
         * THE CANOPY MUST OPEN FACING BACKWARD. Measured 2026-09-21: three flown drops on
         * one path at one condition, plus sixteen bench runs.
         *
         * Nothing here ever set the chute's heading. attachTo followed by detach leaves it
         * on the CARGO's heading, so the canopy faced whichever way the load happened to be
         * sitting -- which depends on how it was put aboard. USAF's loader turns everything
         * 180 (fn_loadAttach copies that setDir 180), so every load USAF ever released
         * opened its canopy pointing back down the run-in. A load that arrived by
         * vehicle-in-vehicle, by ACE, or by a mission maker's attachTo did not.
         *
         * B_Parachute_02_F is a steerable canopy and it FLIES. Facing into 106 m/s of
         * forward airflow it balloons -- the flown transients show the load braking to
         * -1.8 m/s at t=4 s and levelling off 41 m HIGHER than the same drop on USAF's
         * path, then riding that extra altitude down at the same 4.4 m/s terminal:
         *
         *     chute hdg   canopy   miss      path
         *      58 deg     42.910 s  113.5 m  CARP release, canopy forward
         *      59 deg     44.031 s   76.6 m  CARP release, canopy forward
         *     238 deg     35.126 s   21.1 m  USAF release, canopy backward
         *
         * Nine seconds of extra canopy, and at 4 m/s of wind that is fifty metres of drift
         * the release point never accounted for.
         *
         * THE CALIBRATION WAS NEVER WRONG. The parallel bench drops through USAF's canDrop,
         * so all 140 calibration runs flew a backward canopy: 35.29-35.65 s at this exact
         * condition, which is run 3 to within half a second. Since v0.10.0 CARP had simply
         * stopped producing the canopy the tables describe.
         *
         * Forced HERE rather than at the load, because all four cargo sources converge on
         * this one line. What a drop does must not depend on how the loadmaster packed it.
         *
         * A pure 180 yaw about world Z: (x,y,z) -> (-x,-y,z). setVectorDirAndUp and not
         * setDir, because setDir wipes velocity and this object is about to carry the load.
         */
        private _cd = vectorDir _chute;
        private _cu = vectorUp _chute;
        _chute setVectorDirAndUp [
            [-(_cd # 0), -(_cd # 1), _cd # 2],
            [-(_cu # 0), -(_cu # 1), _cu # 2]
        ];
        if (_cargo isKindOf "ReammoBox_F") then {
            _cargo attachTo [_chute, [0, 0, -0.5 - (((0 boundingBoxReal _cargo) # 1) # 2)]];
        } else {
            _cargo attachTo [_chute, [0, 0, 0]];
        };

        // ---- from here nothing is timing-critical, so it goes back to the scheduler
        [_cargo, _chute, _strobe, _smoke, _side] spawn {
            params ["_cargo", "_chute", "_strobe", "_smoke", "_side"];

            // USAF marks the descending load with a smoke shell re-created as each one
            // burns out. Reproduced rather than called, and switchable from the CARP
            // panel, because a marked load is a liability on some missions.
            //
            // USAF dispatches its loop with `spawn BIS_fnc_MP` and no target, so it runs
            // on EVERY machine and each one calls createVehicle -- global-effect, so a
            // four-player server gets four stacked shells per load. This runs once.
            if (_smoke) then {
                private _smokeClass = switch (_side) do {
                    case east: {"SmokeShellRed"};
                    case west: {"SmokeShellBlue"};
                    case resistance: {"SmokeShellGreen"};
                    default {"SmokeShell"};
                };
                [_cargo, _smokeClass] spawn {
                    params ["_cargo", "_smokeClass"];
                    while {
                        !isNull _cargo
                        && {((ASLToAGL (getPosASL _cargo)) # 2) > 1}
                        && {(count (crew _cargo)) isEqualTo 0}
                    } do {
                        private _at = ASLToAGL (getPosASL _cargo);
                        private _shell = _smokeClass createVehicle [_at # 0, _at # 1, 0.2];
                        _shell attachTo [_cargo, [0, 0, 0]];
                        waitUntil {sleep 0.5; isNull _shell || {isNull _cargo}};
                    };
                };
            };

            sleep 5;
            if (!isNull _chute) then {_chute setVectorUp [0, 0, 1]};

            // THE LOAD IS ATTACHED TO THE CHUTE FOR THIS ENTIRE DESCENT, so getPos here is
            // its offset from the canopy -- zero -- and this wait would end on its first
            // evaluation, detaching the load and deleting its chute at altitude.
            waitUntil {((ASLToAGL (getPosASL _cargo)) # 2) < 1 || {isNull _cargo} || {isNull _chute}};
            if (isNull _cargo) exitWith {if (!isNull _chute) then {deleteVehicle _chute}};
            detach _cargo;
            _cargo setVectorUp (surfaceNormal (ASLToAGL (getPosASL _cargo)));
            _cargo setPos (getPosVisual _cargo);

            detach _strobe;
            deleteVehicle _chute;
            sleep 1;
            private _settled = getPosVisual _cargo;
            waitUntil {(count (crew _cargo)) > 0 || {!(_settled isEqualTo (getPosVisual _cargo))} || {isNull _cargo}};
            deleteVehicle _strobe;
        };
    } forEach USAFDC_state_canopyPending;

    USAFDC_state_canopyPending = _survivors;

    // Nothing left to watch. Stopping costs a frame of bookkeeping on the next drop and
    // saves a handler running for the rest of the mission.
    if ((count USAFDC_state_canopyPending) isEqualTo 0) then {
        [USAFDC_state_canopyPfh] call CBA_fnc_removePerFrameHandler;
        USAFDC_state_canopyPfh = nil;
    };
}, 0] call CBA_fnc_addPerFrameHandler;

true

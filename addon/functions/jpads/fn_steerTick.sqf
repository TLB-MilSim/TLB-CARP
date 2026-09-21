/*
    TLB_CARP_fnc_steerTick

    Runs every frame on EVERY machine, server included, and flies whichever canopies this
    machine happens to own.

    THIS IS THE FIX FOR "JPADS DOES NOTHING ON THE SERVER"

    Three separate things were wrong and all three had to go.

      The command went to the wrong machine. setVelocity is local-effect, and USAF
      releases cargo where the CARGO is local -- fn_canDrop ends with
      remoteExec ["USAF_CARGO_fnc_dropCargo", _cargo] -- which on a dedicated server is
      normally the server itself, for anything placed in Eden, spawned by Zeus or spawned
      by a mission script. The pilot's client was commanding an object it did not own and
      the engine discarded every call without a word. Now each machine steers only what
      it owns, re-tested each frame because ownership can move.

      The loop did not run on the server at all. Its EachFrame handler sat below
      fn_postInit's hasInterface guard, so the one machine that owned the canopy was also
      the one machine not trying to steer it. That registration has moved above the guard.

      And the gate was client state. Steering required
      TLB_CARP_state_packageTimingState isEqualTo "CHUTE" -- a global written only by the
      guidance loop, on a client, with a panel open. A dedicated server has no such
      thing and never will. The conditions are now facts any machine can read off the
      object: is it hanging under a ParachuteBase, is it above the release height, has
      its descent settled. fn_steerCargo tests those.

    RUNNING EVERY FRAME IS NOT OPTIONAL. Measured in v0.4.6: at the 0.05 s guidance
    interval the parachute's own physics reasserted between calls and only 41% of the
    commanded closing speed survived -- 8.0 m/s commanded against 3.28 m/s achieved. The
    early exit below is a single count, so the cost with nothing in the air is nil.

    WHY THE READOUT IS COMPUTED HERE RATHER THAN SENT

    Every input to the HUD's guided-cargo line is visible to any machine: the load's
    position, the DZ the crew already share, and the aim offset broadcast on the load. So
    each display machine computes its own, and nothing about the readout has to cross the
    network or can go stale. On a server this whole block is skipped.
*/

private _jobs = missionNamespace getVariable ["TLB_CARP_state_steerJobs", []];

if ((count _jobs) isEqualTo 0) exitWith {
    if (hasInterface && {missionNamespace getVariable ["TLB_CARP_state_jpadsActive", false]}) then {
        TLB_CARP_state_jpadsActive = false;
        TLB_CARP_state_jpadsPhase = "IDLE";
    };
    false
};

private _live = missionNamespace getVariable ["TLB_CARP_state_packagePrimaryCargo", objNull];
private _survivors = [];
private _commandedThisFrame = 0;

{
    _x params ["_cargo", "_dz", "_glideMs", "_scatterM", "_releaseAglM", "_engageVzMs", "_startedS", "_jipID", ["_aimOffset", []]];

    private _done = isNull _cargo;
    // On the ground: finished. The ten-minute backstop is for a load deleted mid-descent
    // or one that comes to rest somewhere the height test never sees, either of which
    // would otherwise leak a job and its JIP entry for the rest of the mission.
    if (!_done && {((getPosATL _cargo) # 2) <= _releaseAglM}) then {_done = true};
    if (!_done && {(time - _startedS) > 600}) then {_done = true};

    if (_done) then {
        // One machine retires the JIP entry, not all of them. The server is the only one
        // guaranteed to be present, and CBA routes the call there anyway.
        if (isServer && {_jipID isEqualType ""} && {_jipID != ""}) then {
            [_jipID] call CBA_fnc_removeGlobalEventJIP;
            // Clear what was stamped on the load as well. A pallet can be recovered,
            // re-loaded and dropped again on a different DZ, and a surviving aim offset
            // would carry the previous sortie's scatter into the next one.
            if (!isNull _cargo) then {
                _cargo setVariable ["TLB_CARP_jpadsTargetOffset", nil, true];
                _cargo setVariable ["TLB_CARP_steerBeat", nil, true];
            };
        };
        if (hasInterface && {!isNull _cargo} && {_cargo isEqualTo _live}) then {
            TLB_CARP_state_jpadsActive = false;
            TLB_CARP_state_jpadsPhase = "RELEASED";
        };
    } else {
        _survivors pushBack _x;

        // fn_steerCargo re-tests locality on the object it actually commands -- the
        // canopy, not the load, because those can differ -- and returns without
        // commanding anything when this machine does not own it.
        private _result = [_cargo, _dz, _glideMs, _scatterM, _releaseAglM, _engageVzMs, _aimOffset] call TLB_CARP_fnc_steerCargo;
        if (_result get "commanding") then {_commandedThisFrame = _commandedThisFrame + 1};

        if (hasInterface && {_cargo isEqualTo _live}) then {
            // If this machine is not the one commanding, check somebody is. The heartbeat
            // is stamped by whichever machine actually issues setVelocity, so its absence
            // means the canopy has no owner that can steer -- a server without the addon,
            // say. Reporting that is the whole difference between guided cargo working
            // and guided cargo appearing to work.
            private _phase = _result get "phase";
            if ((_result get "steering") && {!(_result get "commanding")}) then {
                private _beat = _cargo getVariable ["TLB_CARP_steerBeat", -1e9];
                if ((time - _beat) > 3) then {_phase = "UNSTEERED - NO OWNER"};
            };
            TLB_CARP_state_jpadsActive = _result get "steering";
            TLB_CARP_state_jpadsPhase = _phase;
            TLB_CARP_state_jpadsErrorM = _result get "errorM";
            TLB_CARP_state_jpadsClosingMs = _result get "closingMs";
            TLB_CARP_state_jpadsGroundMs = _result get "groundMs";
            TLB_CARP_state_jpadsTimeRemainingS = _result get "timeRemainingS";
            TLB_CARP_state_jpadsPackage = _cargo;
            TLB_CARP_state_jpadsTargetOffset = _cargo getVariable ["TLB_CARP_jpadsTargetOffset", [0, 0]];
        };
    };
} forEach _jobs;

TLB_CARP_state_steerJobs = _survivors;

// ---- instrumentation, on the machine actually flying them ---------------------------
// The 0.76 m and 1.15 m accuracy figures were measured with the steering running on a
// CLIENT at client framerate. This now usually runs on a dedicated server, whose
// simulation rate under a populated mission is a different and unmeasured number, and
// the control law divides the position error by time-remaining once per frame -- so a
// longer frame is a coarser integration step. Two lines a second while something is in
// the air is what turns that from an argument into a measurement.
if (_commandedThisFrame > 0 && {(time - (missionNamespace getVariable ["TLB_CARP_state_steerLogTick", -1e9])) >= 2}) then {
    TLB_CARP_state_steerLogTick = time;
    private _survival = -1;
    if ((count _survivors) > 0) then {
        _survival = ((_survivors # 0) # 0) getVariable ["TLB_CARP_steerSurvival", -1];
    };
    diag_log format [
        "[TLB CARP][JPADS] steering=%1 jobs=%2 fps=%3 frameMs=%4 survival=%5 isServer=%6",
        _commandedThisFrame, count _survivors, round diag_fps,
        round ((diag_deltaTime) * 1000), _survival toFixed 2, isServer
    ];
};
true

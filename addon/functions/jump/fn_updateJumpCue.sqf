/*
    TLB_CARP_fnc_updateJumpCue

    Runs the jump run: rebuilds the exit geometry, works the countdown, and drives
    the light. Called from the per-frame handler started by fn_armJumpRun.

    Phases: INBOUND -> COUNTDOWN -> GREEN -> PASSED

    Three things here are deliberate and each would be a defect if done the obvious
    way instead.

    THE AIRCRAFT IS LATCHED, NOT RESOLVED. Every other CARP function reads
    "objectParent player", which is right for a pilot in a seat. It is wrong here:
    FFR's fnc_standUp calls moveOut before teleporting the jumper into its hidden
    stationary dummy, so from the moment a jumper stands up their objectParent is
    null and they are on foot two kilometres away. Resolving the aircraft that way
    would drop the cue exactly when the people who need it are on the ramp.

    THE COUNTDOWN LATCHES. The exit point moves as altitude, speed and wind change,
    so range-to-exit is not monotonic. Without a latch a wobble across the threshold
    restarts the count and the jumpers hear two overlapping countdowns. Once it
    starts it runs, and the only thing that stops it is a disarm.

    THE AUDIO **AND THE READOUT** ARE BROADCAST, NOT playSound AND hintSilent, AND
    NOT TO "crew". CARP's existing three
    sound calls are local, which is correct because only the pilot needs them. This
    is the opposite: the jumpers need to hear it and the pilot is the one running it.
    It goes out by CBA target event to a roster snapshotted at arm time unioned with
    the live crew -- NOT to crew alone, because FFR's fnc_standUp calls moveOut and a
    standing jumper is therefore not in crew. Since the countdown only starts 10 s
    before green, by then every jumper is on the ramp, and targeting crew would have
    made the countdown inaudible to exactly the people it exists for while sounding
    perfectly correct to the pilot.

    The readout was the half of that which got missed until it was flown: hintSilent is
    local, so every phase, range and countdown below was drawn only on the machine
    running this function. The jumpers could hear the run working and see nothing. It
    now goes to the same roster by the same mechanism.
*/

if (!TLB_CARP_state_jumpArmed) exitWith {false};

private _aircraft = TLB_CARP_state_jumpAircraft;
if (isNull _aircraft || {!alive _aircraft}) exitWith {
    ["AIRCRAFT LOST"] call TLB_CARP_fnc_disarmJumpRun;
    false
};

// THE READOUT GOES TO THE JUMPERS, NOT JUST TO WHOEVER ARMED THE RUN.
//
// This whole function runs on ONE machine -- the one that armed the jump run, which
// in practice is the pilot's. hintSilent is local, so every readout below was drawn
// on that machine alone: the pilot watched a countdown the people on the ramp could
// not see. The audio was already broadcast to a roster and was audible to everyone,
// which is exactly why the gap was easy to miss -- the jumpers could HEAR the run
// working while seeing nothing at all.
//
// Same audience as the audio, and for the same reason: FFR's fnc_standUp calls
// moveOut, so a standing jumper is not in `crew` and a roster snapshotted at arm time
// is the only thing that still knows they are aboard.
private _hint = {
    private _roster = (TLB_CARP_state_jumpRoster select {alive _x}) + (crew TLB_CARP_state_jumpAircraft);
    private _targets = _roster arrayIntersect _roster;
    if ((count _targets) isEqualTo 0) exitWith {};
    ["TLB_CARP_jumpHint", [_this], _targets] call CBA_fnc_targetEvent;
};

private _solution = [_aircraft] call TLB_CARP_fnc_buildJumpSolution;
TLB_CARP_state_jumpSolution = _solution;
if !(_solution getOrDefault ["valid", false]) exitWith {
    // Not a disarm: an aircraft that has descended below the opening altitude on a
    // go-around is still on a jump run, and the reason belongs on the HUD rather
    // than in a teardown. Only a lost aircraft or a pilot disarm ends the run.
    TLB_CARP_state_jumpPhase = "HOLD";
    [_aircraft, "red"] call TLB_CARP_fnc_setJumpLight;
    // Say why. This exit is before the readout block, so without it the hint freezes
    // on its last good values and a hold looks identical to a stalled system.
    if ((time - TLB_CARP_state_jumpHintTick) >= 0.25) then {
        TLB_CARP_state_jumpHintTick = time;
        (format [
            "<t align='center'><t size='1.0' color='#e8523f'>JUMP HOLD</t><br/><t size='0.9' color='#f0b429'>%1</t></t>",
            _solution getOrDefault ["reason", "UNAVAILABLE"]
        ]) call _hint;
    };
    false
};

private _along = _solution get "alongM";
private _gs = (_solution get "groundSpeedMs") max 1;
private _countdownS = missionNamespace getVariable ["TLB_CARP_setting_jumpCountdownS", 10];
// The green light has to outlast the stick. With the light called half a stick length
// early, the last jumper leaves a full stick DURATION after the first, so a window
// shorter than that turns the light red with people still queued on the ramp. The
// setting becomes a minimum plus margin rather than the whole answer.
private _greenWindowS = (missionNamespace getVariable ["TLB_CARP_setting_jumpGreenWindowS", 8])
                        max ((_solution get "stickDurationS") + 2);
private _secondsToExit = _along / _gs;
private _dzRangeM = (getPosASL _aircraft) distance2D TLB_CARP_state_dzPosASL;

// The roster, not "crew". FFR's fnc_standUp calls moveOut before teleporting a
// jumper into its hidden dummy, so a standing jumper is NOT in crew _aircraft --
// and since the countdown only begins 10 s before green, by then every jumper is on
// the ramp. Targeting crew alone would have made the countdown inaudible to exactly
// the people it exists for, while sounding perfectly correct to the pilot.
//
// So the roster is snapshotted at arm time and unioned with the live crew, which
// also picks up anyone who boarded after arming. arrayIntersect with itself is the
// SQF idiom for deduplicating, so nobody gets the tick twice.
private _cue = {
    params ["_sound"];
    private _roster = (TLB_CARP_state_jumpRoster select {alive _x}) + (crew TLB_CARP_state_jumpAircraft);
    private _targets = _roster arrayIntersect _roster;
    if ((count _targets) isEqualTo 0) exitWith {};
    ["TLB_CARP_jumpCue", [_sound], _targets] call CBA_fnc_targetEvent;
};

// ---- refuse a green light the jumper cannot use ------------------------------
// The exit point is a POINT and the aircraft flies a LINE. If the aircraft is off
// the locked run-in, or the wind is across it, the two are far apart -- and because
// the cue fires on the ALONG-track projection reaching zero, it would otherwise go
// green as the aircraft passes abeam an exit point a kilometre to one side.
//
// That is what happened on the first flown test: the aircraft never tracked at the
// DZ, the light went green 1569 m out against a 420 m rule, and the jump missed by
// 596 m. A green light that cannot be made good is worse than no green light, and
// CARP already takes this position for cargo -- the release gate refuses a pass
// rather than releasing on a geometry that will miss.
//
// So: hold red, say why, and let it proceed the moment the pilot corrects onto the
// line. The countdown latch is deliberately NOT cleared, so a correction resumes the
// count where it was rather than restarting it at ten.
if (!(_solution get "achievable") && {!(TLB_CARP_state_jumpPhase in ["GREEN", "PASSED"])}) exitWith {
    TLB_CARP_state_jumpPhase = "REFUSED";
    [_aircraft, "red"] call TLB_CARP_fnc_setJumpLight;
    if ((time - TLB_CARP_state_jumpHintTick) >= 0.25) then {
        TLB_CARP_state_jumpHintTick = time;
        (format [
            "<t align='center'><t size='1.4' color='#e8523f'>NO JUMP</t><br/>"
            + "<t size='0.9' color='#f0b429'>OFF TRACK %1 m</t><br/>"
            + "<t size='0.8' color='#7e929f'>max recoverable %2 m<br/>correct onto the run-in</t></t>",
            round (_solution get "requiredCorrectionM"),
            round (_solution get "recoveryM")
        ]) call _hint;
    };
    false
};

// ---- green, and everything after it -----------------------------------------
if (TLB_CARP_state_jumpPhase isEqualTo "GREEN") then {
    if (time >= TLB_CARP_state_jumpGreenUntil) then {
        TLB_CARP_state_jumpPhase = "PASSED";
        [_aircraft, "red"] call TLB_CARP_fnc_setJumpLight;
        ["FD_Finish_F"] call _cue;
    };
} else {
    if (TLB_CARP_state_jumpPhase isEqualTo "PASSED") then {
        [_aircraft, "red"] call TLB_CARP_fnc_setJumpLight;
    } else {
        if (_along <= 0) then {
            // GREEN LIGHT.
            TLB_CARP_state_jumpPhase = "GREEN";
            TLB_CARP_state_jumpGreenUntil = time + _greenWindowS;
            [_aircraft, "green"] call TLB_CARP_fnc_setJumpLight;
            ["FD_Start_F"] call _cue;
            TLB_CARP_state_jumpGreenExitAglM = _solution get "exitAglM";
            TLB_CARP_state_jumpGreenOffTrackM = _solution get "offTrackM";
        } else {
            if (TLB_CARP_state_jumpCountdownLatched || {_secondsToExit <= _countdownS}) then {
                if (!TLB_CARP_state_jumpCountdownLatched) then {
                    TLB_CARP_state_jumpCountdownLatched = true;
                    TLB_CARP_state_jumpPhase = "COUNTDOWN";
                    // ceil, not round: at 9.6 s remaining the next whole second to
                    // announce is 10, and rounding to 10 then announcing 10 again a
                    // frame later would double the first tick.
                    TLB_CARP_state_jumpLastTickAnnounced = (ceil _secondsToExit) + 1;
                };
                private _remaining = ceil _secondsToExit;
                if (_remaining < TLB_CARP_state_jumpLastTickAnnounced) then {
                    TLB_CARP_state_jumpLastTickAnnounced = _remaining;
                    ["FD_Timer_F"] call _cue;
                };
            } else {
                TLB_CARP_state_jumpPhase = "INBOUND";
                [_aircraft, "red"] call TLB_CARP_fnc_setJumpLight;
            };
        };
    };
};

_solution set ["phase", TLB_CARP_state_jumpPhase];
_solution set ["secondsToExit", _secondsToExit];
_solution set ["countdownRemaining", if (TLB_CARP_state_jumpCountdownLatched) then {(ceil _secondsToExit) max 0} else {-1}];
_solution set ["lightDriven", !(isNull (_aircraft getVariable ["ffr_jumplight", objNull]))];

// ---- readout ------------------------------------------------------------------
// A hint, not the HUD. Three reasons, in order of how much they matter:
//
// The HUD's three controls (9401/9402/9403) are the only ones config.bin declares
// and fn_updateHud owns all of them, so jump rows mean restructuring that file --
// which is worth doing, but only once this has actually flown. It is also the file
// that produced three separate layout defects today, and the cargo HUD is the thing
// most likely to be broken by a hurried second consumer.
//
// A hint is screen-space and survives standing up. The HUD is gated on
// TLB_CARP_state_guidanceArmed, which jump mode cannot set because arming guidance
// needs a valid cargo solution.
//
// Throttled to 4 Hz. The cue loop runs at the guidance interval, 20 Hz by default,
// and re-issuing a hint every frame flickers it.
if ((time - TLB_CARP_state_jumpHintTick) >= 0.25) then {
    TLB_CARP_state_jumpHintTick = time;
    private _phaseText = switch (TLB_CARP_state_jumpPhase) do {
        case "GREEN":     {"<t size='1.6' color='#5fd39b'>GO</t>"};
        case "COUNTDOWN": {format ["<t size='1.6' color='#f0b429'>%1</t>", (ceil _secondsToExit) max 0]};
        case "PASSED":    {"<t size='1.2' color='#e8523f'>EXIT PASSED</t>"};
        case "HOLD":      {format ["<t size='1.0' color='#e8523f'>%1</t>", _solution getOrDefault ["reason", "HOLD"]]};
        default           {"<t size='1.0' color='#7e929f'>STAND BY</t>"};
    };
    private _stickText = "";
    if ((_solution get "stickCount") > 1) then {
        _stickText = format [
            "<br/><t size='0.8' color='#7e929f'>STICK %1 over %2 m, green %3 s</t>",
            _solution get "stickCount",
            round (_solution get "stickLengthM"),
            _greenWindowS toFixed 0
        ];
    };
    private _warnText = "";
    private _warnings = _solution getOrDefault ["warnings", []];
    if ((count _warnings) > 0) then {
        _warnText = format ["<br/><t size='0.8' color='#f0b429'>%1</t>", _warnings joinString " / "];
    };
    (format [
        "<t align='center'>%1<br/>"
        + "<t size='0.9' color='#dce6ec'>EXIT %2 m  |  %3 s</t><br/>"
        + "<t size='0.8' color='#7e929f'>DZ %4 m   ALT %5 m   OPEN %6 m</t><br/>"
        + "<t size='0.8' color='#7e929f'>WIND %7 m/s / %8   OFF-TRK %9 m</t>"
        + "%11%10</t>",
        _phaseText,
        round _along,
        (_secondsToExit max 0) toFixed 0,
        round _dzRangeM,
        round (_solution get "exitAglM"),
        round (_solution get "openAglM"),
        (_solution get "windMs") toFixed 1,
        round (_solution get "windDirDeg"),
        round (_solution get "offTrackM"),
        _warnText,
        _stickText
    ]) call _hint;
};
true

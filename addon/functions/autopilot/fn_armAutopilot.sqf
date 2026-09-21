private _vehicle = objectParent player;
if (isNull _vehicle) exitWith {hint "TLB CARP AP: enter a supported aircraft first"; false};
if !((driver _vehicle) isEqualTo player) exitWith {hint "TLB CARP AP: pilot seat required"; false};
// setVelocity and setAirplaneThrottle are local-effect commands: issued against an
// aircraft this machine does not own they silently do nothing, while setDir still
// lands. That degrades the controller from "orientation write followed by velocity
// restore" into "orientation write alone" at the guidance rate, with the documented
// setDir velocity wipe applying unopposed -- an aircraft pinned in place on every
// machine, with no error anywhere. Being the driver normally implies locality, so this
// should never fire; it exists because when it does fire the symptom is
// indistinguishable from a physics bug.
if !(local _vehicle) exitWith {hint "TLB CARP AP: aircraft not local to this machine"; false};
if (!USAFDC_state_guidanceArmed) exitWith {hint "TLB CARP AP: arm guidance first"; false};
if (!USAFDC_state_runInLocked) exitWith {hint "TLB CARP AP: lock the run-in first"; false};

private _solution = USAFDC_state_solution;
if !(_solution getOrDefault ["valid", false]) then {
    _solution = [_vehicle] call USAFDC_fnc_buildWorldSolution;
};
if !(_solution getOrDefault ["valid", false]) exitWith {hint "TLB CARP AP: valid solution required"; false};
if ((_solution getOrDefault ["signedRpM", -1]) <= 0) exitWith {hint "TLB CARP AP: RP already passed"; false};

// The path check must be at FUNCTION scope. exitWith leaves only the innermost scope,
// and a then-block is a scope: nested inside the `then` below, a refused path hinted
// "valid path required" and then fell straight through to the arm, so the pilot saw a
// refusal immediately followed by "AP ENGAGED" -- and USAFDC_state_pathSolution kept
// the previous run's stale path. The AP survived it only because fn_updateAutopilot
// re-checks pathValid on the next tick and disarms with INVALID PATH, which is to say
// the arm-time gate was not a gate at all, and it failed exactly on the re-engage.
private _path = if !(isNil "USAFDC_fnc_buildPathSolution")
    then {[_vehicle, _solution] call USAFDC_fnc_buildPathSolution}
    else {createHashMapFromArray [["pathValid", true]]};
{_solution set [_x, _path get _x]} forEach keys _path;
if !(_path getOrDefault ["pathValid", false]) exitWith {hint "TLB CARP AP: valid path required"; false};
USAFDC_state_pathSolution = _path;

USAFDC_state_apArmed = true;
USAFDC_state_apState = "INTERCEPT";
USAFDC_state_apOverrideSince = -1;
USAFDC_state_apOverrideInhibitUntil = diag_tickTime + 0.5;
USAFDC_state_apLastTick = diag_tickTime;
// A fresh engagement must not inherit the rate-limit stamps from the previous one:
// a stale future tick would mute actuation, and a stale frame number would let the
// first orientation write land on the same frame as the last one of the old run.
// Cleared, not set: the first actuation seeds them from the aircraft's ACTUAL velocity
// so engaging is continuous with whatever the pilot was doing. Seeding here instead
// would go stale if anything changed between the arm and that first tick.
USAFDC_state_apCmdSpeedMs = -1;
// The trim offset belongs to one engagement on one aircraft. Carrying it across arms
// would apply a C-17's standing force deficit to a C-130.
// Rates are differences, so a stale previous sample across an arm would read as a huge
// turn rate on the first tick and command full opposite bank.
USAFDC_state_apPrevDir = -1e9;
USAFDC_state_apPrevBank = -1e9;
USAFDC_state_apTrimCount = 0;
USAFDC_state_apTrimSum = 0;
USAFDC_state_apTrimOffset = 0;
USAFDC_state_apCmdVzMs = -1e9;
USAFDC_state_apLastActuateTick = -1;
USAFDC_state_apLastDirFrame = -1;
USAFDC_state_apThrottleBaseline = inputAction "HeliThrottlePos";
USAFDC_state_apDisconnectReason = "";
// A freelook latch left set from a previous engagement would suppress override
// detection for this one, so every arm starts from a known state.
USAFDC_state_apFreelookToggled = false;
USAFDC_state_apLookAroundTogglePrev = false;
// Arming requires the pilot seat, so the ACE interaction menu cannot legitimately be
// open. If an ace_interactMenuClosed event was ever missed -- which happens when the
// menu is torn down by a display change rather than closed -- this latch sticks true,
// fn_inputFocusActive returns true forever and pilot-override detection is silently
// dead for the rest of the session. Clearing it here bounds that to one engagement.
USAFDC_state_apAceInteractOpen = false;

hint "TLB CARP AP ENGAGED";
true

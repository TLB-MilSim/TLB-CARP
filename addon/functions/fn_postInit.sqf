diag_log format ["[TLB CARP][LOAD] postInit begin hasInterface=%1", hasInterface];

// THIS FILE RUNS ON EVERY MACHINE, AND USED TO RUN ON NONE BUT CLIENTS.
//
// A blanket "if (!hasInterface) exitWith {}" stood here, which meant a dedicated
// server registered no CBA settings at all -- so a mission maker could not pin
// updateInterval, apOverrideThreshold or any jump-run constant server-wide, which is
// how a unit standardises a mod. It also left the server with half the addon: the
// functions declared in config.bin are compiled on every machine regardless, while
// every USAFDC_state_* global they read was nil there, so any remoteExec of a CARP
// function to the server would have thrown rather than failed cleanly.
//
// State, settings, the runtime compile table and the event receivers are now
// registered everywhere. The interface guard has moved down to exactly the things that
// need a screen: the HUD layer, the keybinds, the ACE self-actions and the two mission
// event handlers that draw or steer.

// Source of truth for the shipped version. Bump this with every release:
// build_release.py fails if it disagrees with --version, and packaging/mod.cpp
// stamps the same number into the launcher entry.
USAFDC_VERSION = "1.0.0";

USAFDC_state_guidanceArmed = false;
USAFDC_state_autoArmed = false;
USAFDC_state_apArmed = false;
USAFDC_state_apState = "OFF";
USAFDC_state_apOverrideSince = -1;
USAFDC_state_apOverrideInhibitUntil = -1;
USAFDC_state_apLastTick = diag_tickTime;
// Actuation rate limiting. CBA fires a per-frame handler every frame once the
// framerate drops below its interval, and never recovers the schedule; writing the
// aircraft transform that often stops position integrating. See fn_updateAutopilot.
USAFDC_state_apLastActuateTick = -1;
USAFDC_state_apLastDirFrame = -1;
USAFDC_state_apTrackLogTick = -1e9;
USAFDC_state_apCmdSpeedMs = -1;
USAFDC_state_apCmdVzMs = -1e9;
// Integral trim for the force-mode pitch channel. Every flight model has a standing
// force deficit at trim, and a proportional term alone answers it with a permanent
// small error -- which is an aircraft that slowly sinks.
USAFDC_state_apPrevDir = -1e9;
USAFDC_state_apPrevBank = -1e9;
USAFDC_state_apTrimCount = 0;
USAFDC_state_apTrimSum = 0;
USAFDC_state_apTrimOffset = 0;
USAFDC_state_apThrottleBaseline = 0;
USAFDC_state_apDisconnectReason = "";
USAFDC_state_apAceInteractOpen = false;
USAFDC_state_apFreelookToggled = false;
USAFDC_state_apLookAroundTogglePrev = false;
USAFDC_state_packageEstimatedChuteAttachTimeS = 0;
USAFDC_state_jpadsActive = false;
USAFDC_state_jpadsPackage = objNull;
USAFDC_state_jpadsTargetOffset = [0, 0];
USAFDC_state_jpadsErrorM = -1;
USAFDC_state_jpadsClosingMs = 0;
USAFDC_state_jpadsPhase = "IDLE";
USAFDC_state_jpadsTimeRemainingS = -1;
USAFDC_state_jpadsGroundMs = 0;
USAFDC_state_jpadsEh = -1;
// Guided-cargo steering jobs, held on EVERY machine including the server. Each one
// is acted on only by whichever machine owns that canopy; see fn_steerTick.
USAFDC_state_steerJobs = [];
USAFDC_state_steerSeenCarrier = objNull;
USAFDC_state_steerSeenCargo = [];
USAFDC_state_steerLogTick = -1e9;
USAFDC_state_packageEstimatedCanopyTimeS = 0;
USAFDC_state_pathSolution = createHashMap;
USAFDC_state_panelLastTelemetryTick = -1;
USAFDC_state_dzPosASL = [];
USAFDC_state_dzName = "";
USAFDC_state_mode = "TOUCHDOWN";
USAFDC_state_runInLocked = false;
USAFDC_state_runInDeg = 0;
USAFDC_state_profileOverride = "";
USAFDC_state_manualWind = false;
USAFDC_state_manualWindMs = 0;
USAFDC_state_manualWindFromDeg = 0;
USAFDC_state_targetAglM = 3000;
USAFDC_state_targetGroundSpeedKmh = 500;
USAFDC_state_cargoCount = -1;
// Smoke on a released load. Crew intent, not a mission setting: the loadmaster decides
// per drop whether the package gets marked, and both seats see the same answer.
USAFDC_state_smokeEnabled = true;
// Guided cargo. Crew intent rather than a per-client Addon Option: it decides what
// happens to the load both seats are dropping, and it belongs on the panel where the
// loadmaster can change it on the run.
USAFDC_state_jpadsEnabled = false;
// Loads waiting to cross the canopy trigger, and the one frame handler watching them.
USAFDC_state_canopyPending = [];
// Jump run values the crew sets in the panel rather than in Addon Options, because they
// change per serial. 0 in either means "fall back to the Addon Option".
USAFDC_state_jumpPlannedStick = 0;
USAFDC_state_jumpOpenAglM = 0;
USAFDC_state_lastSignedRpM = 1e9;
USAFDC_state_dropLatched = false;
USAFDC_state_solution = createHashMap;
USAFDC_state_displaySolution = createHashMap;
USAFDC_state_pfh = -1;
USAFDC_state_3dEh = -1;
USAFDC_state_mapClickEh = -1;
USAFDC_state_releaseCrossed = false;
USAFDC_state_dropCueUntil = -1;
USAFDC_state_standbyCueSent = false;
USAFDC_state_smoothedDesiredTrackDeg = nil;
USAFDC_state_guidanceLastTick = diag_tickTime;
USAFDC_state_passMissed = false;
USAFDC_state_displayRpM = nil;
USAFDC_state_displayXtkM = nil;
USAFDC_state_calibrationActive = false;
USAFDC_state_autoDropCommand = [];
USAFDC_state_calChuteWatchEh = -1;
USAFDC_state_calChuteWatchCargo = objNull;
USAFDC_state_calChuteWatchCarrier = objNull;
USAFDC_state_calibrationRun = createHashMap;
USAFDC_state_lastCalibrationRun = createHashMap;
USAFDC_state_lastCalibrationText = "";
USAFDC_state_calibrationSerial = 0;
USAFDC_state_debugHarnessActive = false;
USAFDC_state_debugHarnessObjects = [];
USAFDC_state_debugSeriesSerial = 0;
USAFDC_state_debugSeriesResults = [];
USAFDC_state_lastDebugSeriesText = "";
USAFDC_state_pbenchActive = false;
USAFDC_state_pbenchPending = 0;
USAFDC_state_pbenchObjects = [];
USAFDC_state_pbenchPins = [];
USAFDC_state_pbenchChuteWatch = [];
USAFDC_state_pbenchSteer = [];
USAFDC_state_pbenchJpads = false;
USAFDC_state_stickProbeActive = false;
USAFDC_state_stickProbeEh = -1;
USAFDC_state_stickProbePin = [];
USAFDC_state_stickProbeStamps = [];
USAFDC_state_pbenchPinEh = -1;

USAFDC_state_panelRefreshing = false;

// ---- crew sync ---------------------------------------------------------------
// CARP was written single-client: every USAFDC_state_* here is per-machine, so a
// co-pilot opening the panel saw a factory-default CARP no matter what the pilot had
// set up. Only INTENT is shared -- the values a human chose. Everything derived from
// it (the solution, the path, the HUD, the markers, the 3D cue, the package tracker)
// stays local and is recomputed by each client's own guidance loop, because those all
// read that client's own view of the aircraft and a local answer is the correct one.
//
// The record lives on the AIRCRAFT object with the public flag, not in missionNamespace:
// airframe-scoped so two aircraft running CARP cannot overwrite each other's DZ,
// delivered to joining players by the engine with no handshake, and it outlives any
// one crew member because the airframe holds it.
//
// v0.9.0: the record is [rev, authorUid, authorName, authorVersion, payload] under
// USAFDC_carpRecord. A client adopts it whenever it is not the record that client last
// adopted, and publishes only the fields it changed since USAFDC_state_syncBase. Only
// players the access rule admits take part at all: inside the aircraft, carrying a CARP
// Computer unless the mission has switched that requirement off.
USAFDC_state_syncRev = -1;
USAFDC_state_syncUid = "";
USAFDC_state_syncAuthor = "";
USAFDC_state_syncAdoptedAt = -1;
USAFDC_state_syncBase = [];
USAFDC_state_syncAircraft = objNull;
USAFDC_state_syncVersionWarned = [];
USAFDC_state_syncLegacyWarned = [];
USAFDC_state_syncApplying = false;
USAFDC_state_syncWantGuidance = false;
USAFDC_state_syncWantAuto = false;
USAFDC_state_syncSeenGuidance = false;
USAFDC_state_syncSeenAuto = false;
USAFDC_state_syncAutoAttempted = false;
USAFDC_state_syncPfh = -1;

// ---- jump run (HALO/HAHO cue) -----------------------------------------------
// jumpAircraft is LATCHED at arm time and held for the run. It is not resolved as
// objectParent player like every other CARP entry point, because FFR's fnc_standUp
// calls moveOut before teleporting a jumper into its hidden dummy: a standing
// jumper has no objectParent, and that is exactly when the cue matters.
USAFDC_state_jumpArmed = false;
USAFDC_state_jumpAircraft = objNull;
USAFDC_state_jumpSolution = createHashMap;
USAFDC_state_jumpPfh = -1;
USAFDC_state_jumpPhase = "IDLE";
USAFDC_state_jumpCountdownLatched = false;
USAFDC_state_jumpLastTickAnnounced = 1e9;
USAFDC_state_jumpGreenUntil = -1;
USAFDC_state_jumpGreenExitAglM = -1;
USAFDC_state_jumpGreenOffTrackM = 0;
USAFDC_state_jumpLightState = "off";
USAFDC_state_jumpDisarmReason = "";
USAFDC_state_jumpHintTick = -1;
USAFDC_state_jumpRoster = [];
USAFDC_state_jumpHintLayer = nil;
USAFDC_state_jumpStickCount = 0;
// Resolved here rather than lazily, because a lazy "if (isNil ...)" that had
// already been initialised to false would latch false forever and silently kill
// the jumplight. Config is loaded by postInit, so the check is safe here.
USAFDC_state_jumpFfrLoaded = isClass (configFile >> "CfgPatches" >> "ffr_main");

["USAFDC_setting_hudEnabled", "CHECKBOX", ["HUD Enabled", "Show compact live drop guidance HUD"], ["TLB CARP", "Display"], true, 0] call CBA_fnc_addSetting;
["USAFDC_setting_hudScale", "SLIDER", ["HUD Scale", "HUD size multiplier"], ["TLB CARP", "Display"], [0.7, 1.5, 1.0, 2], 0] call CBA_fnc_addSetting;
["USAFDC_setting_3dEnabled", "CHECKBOX", ["3D RP Cue", "Show the world-space release point cue"], ["TLB CARP", "Display"], true, 0] call CBA_fnc_addSetting;
["USAFDC_setting_mapTrajectory", "CHECKBOX", ["Map Trajectory", "Show local RP/chute/touchdown/run-in markers"], ["TLB CARP", "Display"], true, 0] call CBA_fnc_addSetting;
["USAFDC_setting_sounds", "CHECKBOX", ["Guidance Sounds", "Use standby and drop UI sounds"], ["TLB CARP", "Audio"], true, 0] call CBA_fnc_addSetting;
["USAFDC_setting_updateInterval", "SLIDER", ["Update Interval", "Seconds between guidance updates"], ["TLB CARP", "Advanced"], [0.02, 0.20, 0.05, 2], 0] call CBA_fnc_addSetting;
["USAFDC_setting_debug", "CHECKBOX", ["Diagnostics Enabled", "Enable debug/calibration controls, detailed panel diagnostics, and recorder controls"], ["TLB CARP", "Advanced"], false, 0] call CBA_fnc_addSetting;
["USAFDC_setting_calibrationRecorder", "CHECKBOX", ["Calibration Recording", "Track the next released cargo to touchdown and retain a pasteable calibration record"], ["TLB CARP", "Advanced"], false, 0] call CBA_fnc_addSetting;
["USAFDC_setting_useUsafRelease", "CHECKBOX", ["Use USAF Release Sequence", "Hand drops on a USAF aircraft back to the USAF mod's own drop action instead of releasing them with CARP. Off by default: CARP runs the whole release itself and does not need the USAF mod loaded. Turn it on only to compare the two, or if a USAF update changes something CARP should follow."], ["TLB CARP", "Auto Drop"], false, 1] call CBA_fnc_addSetting;
// How fast the autopilot is allowed to CHANGE the aircraft's state, rather than how fast
// it may fly. Both are accelerations, both are scope 1 so a mission can force them, and
// both exist as settings because the right numbers are a flying judgement rather than a
// measurement -- 1.5 m/s2 is roughly a loaded transport shedding speed on idle thrust,
// and 2.5 m/s2 of vertical-rate change is a gentle pull rather than a snap.
// FLY THE AIRCRAFT, OR MOVE IT.
//
// On: the autopilot applies forces and torques and lets Arma's flight model do the
// flying, which is how @Realistic Auto Pilots does it -- not one file in that mod calls
// setVelocity or setDir. Off: the legacy path, which writes the transform directly and
// is what the crew described as juddering "forward and back every half second".
//
// A setting rather than a straight replacement because the old path is measured and the
// new one is not: force response depends on each airframe's flight model, and CARP flies
// a C-17, a C-130, a V-44 and anything else that is kindOf Air.
// SCOPE 0 -- CLIENT. Every setting in this block changes how the autopilot flies, and the
// autopilot only ever runs on the machine flying the aircraft. Scope 1 put them behind
// the server tab where a pilot could not reach them, which was reported as "I don't see
// the sliders": correct, they were not there to see.
["USAFDC_setting_apForceMode", "CHECKBOX", ["AP Flies With Forces", "Apply forces and torques and let the flight model fly, instead of writing velocity and heading directly. Smoother, and turns at the rate a real aircraft would. Off restores the pre-v0.16.8 behaviour."], ["TLB CARP", "Autopilot"], true, 0] call CBA_fnc_addSetting;
// HOW THE TURN IS FLOWN. Commanded bank was proportional to heading error alone, which
// oscillates: at zero error the commanded bank is zero while the aircraft is still
// turning, so it sails through and reverses. Lead predicts the error forward by the
// measured turn rate; roll damping stops the bank loop overshooting its own command.
["USAFDC_setting_apTurnLeadS", "SLIDER", ["AP Turn Lead", "How many seconds ahead the autopilot predicts its own turn before rolling out. Higher rolls out earlier and settles sooner; too high and it will not complete a turn."], ["TLB CARP", "Autopilot"], [0, 10, 4, 1], 0] call CBA_fnc_addSetting;
["USAFDC_setting_apRollDamping", "SLIDER", ["AP Roll Damping", "Opposes roll RATE, so the aircraft stops at its commanded bank instead of swinging past it."], ["TLB CARP", "Autopilot"], [0, 600, 150, 0], 0] call CBA_fnc_addSetting;
// Rudder with the turn, not only with the slip -- a turn coordinator. Never a steering
// input: rudder used to TURN makes the aircraft skid, and lateral velocity at release is
// what the gate punishes hardest.
["USAFDC_setting_apYawCoordination", "SLIDER", ["AP Turn Coordination", "Rudder applied with bank to hold the ball centred through roll in and roll out. Zero leaves the rudder answering sideslip only."], ["TLB CARP", "Autopilot"], [0, 150, 40, 0], 0] call CBA_fnc_addSetting;
["USAFDC_setting_apAccelMs2", "SLIDER", ["AP Acceleration Limit", "How fast the autopilot may change ground speed, m/s squared. Lower is smoother and slower to settle."], ["TLB CARP", "Autopilot"], [0.3, 6.0, 1.5, 2], 0] call CBA_fnc_addSetting;
["USAFDC_setting_apVzRateMs2", "SLIDER", ["AP Vertical Rate Limit", "How fast the autopilot may change vertical speed, m/s squared. Lower is a gentler pull out of a dive or climb."], ["TLB CARP", "Autopilot"], [0.5, 8.0, 2.5, 2], 0] call CBA_fnc_addSetting;
// The release gate's lateral-drift tolerance. 25 m matches the cross-track limit; see
// fn_buildWorldSolution for why 15 m was never actually exercised before v0.16.8.
["USAFDC_setting_releaseDriftLimitM", "SLIDER", ["Release Drift Limit", "How much predicted lateral displacement the release gate will accept, in metres. Raising it lets a pass through with more sideways motion at release."], ["TLB CARP", "Autopilot"], [5, 60, 25, 0], 0] call CBA_fnc_addSetting;
["USAFDC_setting_apOverrideThreshold", "SLIDER", ["AP Manual Override Threshold", "Control deflection required to disconnect CARP autopilot"], ["TLB CARP", "Autopilot"], [0.10, 0.60, 0.25, 2], 0] call CBA_fnc_addSetting;
["USAFDC_setting_jpadsGlideMs", "SLIDER", ["Canopy Glide Speed", "Horizontal airspeed the steerable cargo canopy can fly, in m/s."], ["TLB CARP", "Guided Cargo"], [2, 25, 12, 1], 0] call CBA_fnc_addSetting;
["USAFDC_setting_jpadsScatterM", "SLIDER", ["Aim Scatter", "Radius of a random aim offset, in metres, so a load does not sit exactly on the aim point. Added on top of the stick spacing when several loads are dropped together."], ["TLB CARP", "Guided Cargo"], [0, 15, 2, 1], 0] call CBA_fnc_addSetting;
["USAFDC_setting_jpadsFlareAglM", "SLIDER", ["Stop Steering At", "Height above the ground, in metres, at which a guided load stops correcting and simply rides the wind down. A canopy still chasing its aim point at touchdown arrives sideways; stopping earlier trades a little accuracy for a soft landing."], ["TLB CARP", "Guided Cargo"], [0, 100, 25, 0], 1] call CBA_fnc_addSetting;
["USAFDC_setting_jpadsStickSpacingM", "SLIDER", ["Stick Spacing", "Metres between guided loads of the same stick, spread along the run-in so they do not all steer onto one point and land on top of each other. Set 0 to aim every load at the drop zone."], ["TLB CARP", "Guided Cargo"], [0, 150, 35, 0], 1] call CBA_fnc_addSetting;
["USAFDC_setting_jpadsReleaseAglM", "SLIDER", ["Steering Release AGL", "Height above ground at which canopy steering stops, leaving the last metres of descent unguided."], ["TLB CARP", "Guided Cargo"], [0, 60, 3, 0], 0] call CBA_fnc_addSetting;
["USAFDC_setting_jumpOpenAglM", "SLIDER", ["Jump Opening Altitude", "Height above the drop zone at which jumpers plan to open their canopy, in metres. The exit point is computed from this. A higher opening leaves more room to glide onto the DZ; a lower one needs a more accurate exit."], ["TLB CARP", "Jump Run"], [150, 1200, 600, 0], 1] call CBA_fnc_addSetting;
["USAFDC_setting_jumpStickCount", "SLIDER", ["Jumpers In Stick", "How many jumpers will exit. The green light is spread over the whole stick instead of a single point. Set 0 to count everyone aboard except the pilot when the run is armed."], ["TLB CARP", "Jump Run"], [0, 30, 0, 0], 1] call CBA_fnc_addSetting;
["USAFDC_setting_jumpStickIntervalS", "SLIDER", ["Jumper Interval", "Time between one jumper leaving the ramp and the next, in seconds."], ["TLB CARP", "Jump Run"], [0.5, 5, 1, 1], 1] call CBA_fnc_addSetting;
["USAFDC_setting_jumpCountdownS", "SLIDER", ["Jump Countdown", "Length of the audible countdown before the green light, in seconds."], ["TLB CARP", "Jump Run"], [5, 20, 10, 0], 1] call CBA_fnc_addSetting;
["USAFDC_setting_jumpGreenWindowS", "SLIDER", ["Green Light Duration", "How long the green light stays on once the aircraft reaches the exit point, in seconds."], ["TLB CARP", "Jump Run"], [2, 30, 8, 0], 1] call CBA_fnc_addSetting;
["USAFDC_setting_jumpEarlyBiasM", "SLIDER", ["Early Exit Bias", "Metres the exit point is moved earlier along the run-in, so exit-timing errors fall on the side the canopy can recover. Flying downwind to the drop zone is many times faster than flying upwind to it, so an early exit is recoverable and a late one usually is not."], ["TLB CARP", "Jump Run"], [0, 800, 250, 0], 1] call CBA_fnc_addSetting;
["USAFDC_setting_jumpTrackOffsetM", "SLIDER", ["Jump Exit Bias", "Shifts the exit point along the run-in, in metres. Positive calls the jump earlier, negative later. Leave at 0 unless jumpers consistently land long or short in the direction of flight."], ["TLB CARP", "Jump Run"], [-600, 600, 0, 0], 1] call CBA_fnc_addSetting;
["USAFDC_setting_jpadsEngageVzMs", "SLIDER", ["Steering Engage Descent Rate", "Descent rate at which canopy steering begins, in m/s. Steering waits until the canopy has slowed to near-terminal descent."], ["TLB CARP", "Guided Cargo"], [5, 30, 12, 0], 0] call CBA_fnc_addSetting;
["USAFDC_setting_requireComputer", "CHECKBOX", ["Require CARP Computer", "Only players carrying a CARP Computer get TLB CARP in the aircraft's interaction menu and share the crew's CARP. Turn off for missions that do not hand the item out."], ["TLB CARP", "Access"], true, 1] call CBA_fnc_addSetting;

{
    _x params ["_name", "_path"];
    missionNamespace setVariable [_name, compile preprocessFileLineNumbers _path];
} forEach [
    ["USAFDC_fnc_armAutopilot", "\x\usafdc\addons\drop_computer\functions\autopilot\fn_armAutopilot.sqf"],
    ["USAFDC_fnc_disarmAutopilot", "\x\usafdc\addons\drop_computer\functions\autopilot\fn_disarmAutopilot.sqf"],
    ["USAFDC_fnc_updateAutopilot", "\x\usafdc\addons\drop_computer\functions\autopilot\fn_updateAutopilot.sqf"],
    ["USAFDC_fnc_inputFocusActive", "\x\usafdc\addons\drop_computer\functions\autopilot\fn_inputFocusActive.sqf"],
    ["USAFDC_fnc_buildPathSolution", "\x\usafdc\addons\drop_computer\functions\path\fn_buildPathSolution.sqf"],
    ["USAFDC_fnc_estimatePackageTiming", "\x\usafdc\addons\drop_computer\functions\guidance\fn_estimatePackageTiming.sqf"],
    ["USAFDC_fnc_resetPackageTiming", "\x\usafdc\addons\drop_computer\functions\timing\fn_resetPackageTiming.sqf"],
    ["USAFDC_fnc_updatePackageTiming", "\x\usafdc\addons\drop_computer\functions\timing\fn_updatePackageTiming.sqf"],
    ["USAFDC_fnc_ensurePanelEnhancements", "\x\usafdc\addons\drop_computer\functions\ui\fn_ensurePanelEnhancements.sqf"],
    ["USAFDC_fnc_updatePanelTelemetry", "\x\usafdc\addons\drop_computer\functions\ui\fn_updatePanelTelemetry.sqf"],
    ["USAFDC_fnc_steerCargo", "\x\usafdc\addons\drop_computer\functions\jpads\fn_steerCargo.sqf"],
    ["USAFDC_fnc_steerBegin", "\x\usafdc\addons\drop_computer\functions\jpads\fn_steerBegin.sqf"],
    ["USAFDC_fnc_steerTick", "\x\usafdc\addons\drop_computer\functions\jpads\fn_steerTick.sqf"],
    ["USAFDC_fnc_steerPublisher", "\x\usafdc\addons\drop_computer\functions\jpads\fn_steerPublisher.sqf"],
    // Arma truncates a diag_log string at about a kilobyte, silently. Every long record
    // this addon writes goes through here so it survives the cut.
    ["USAFDC_fnc_logLong", "\x\usafdc\addons\drop_computer\functions\debug\fn_logLong.sqf"],
    ["USAFDC_fnc_parallelDropBench", "\x\usafdc\addons\drop_computer\functions\debug\fn_parallelDropBench.sqf"],
    ["USAFDC_fnc_stickTimingProbe", "\x\usafdc\addons\drop_computer\functions\debug\fn_stickTimingProbe.sqf"],
    ["USAFDC_fnc_buildJumpSolution", "\x\usafdc\addons\drop_computer\functions\jump\fn_buildJumpSolution.sqf"],
    ["USAFDC_fnc_setJumpLight", "\x\usafdc\addons\drop_computer\functions\jump\fn_setJumpLight.sqf"],
    ["USAFDC_fnc_armJumpRun", "\x\usafdc\addons\drop_computer\functions\jump\fn_armJumpRun.sqf"],
    ["USAFDC_fnc_disarmJumpRun", "\x\usafdc\addons\drop_computer\functions\jump\fn_disarmJumpRun.sqf"],
    ["USAFDC_fnc_updateJumpCue", "\x\usafdc\addons\drop_computer\functions\jump\fn_updateJumpCue.sqf"],
    ["USAFDC_fnc_syncSnapshot", "\x\usafdc\addons\drop_computer\functions\sync\fn_syncSnapshot.sqf"],
    ["USAFDC_fnc_syncPublish", "\x\usafdc\addons\drop_computer\functions\sync\fn_syncPublish.sqf"],
    ["USAFDC_fnc_syncApply", "\x\usafdc\addons\drop_computer\functions\sync\fn_syncApply.sqf"],
    ["USAFDC_fnc_syncReconcile", "\x\usafdc\addons\drop_computer\functions\sync\fn_syncReconcile.sqf"],
    ["USAFDC_fnc_syncTick", "\x\usafdc\addons\drop_computer\functions\sync\fn_syncTick.sqf"],
    ["USAFDC_fnc_cargoManifest", "\x\usafdc\addons\drop_computer\functions\cargo\fn_cargoManifest.sqf"],
    ["USAFDC_fnc_releaseModelOffset", "\x\usafdc\addons\drop_computer\functions\cargo\fn_releaseModelOffset.sqf"],
    ["USAFDC_fnc_releaseCargo", "\x\usafdc\addons\drop_computer\functions\cargo\fn_releaseCargo.sqf"],
    ["USAFDC_fnc_canopyWatch", "\x\usafdc\addons\drop_computer\functions\cargo\fn_canopyWatch.sqf"],
    ["USAFDC_fnc_loadModelOffset", "\x\usafdc\addons\drop_computer\functions\cargo\fn_loadModelOffset.sqf"],
    ["USAFDC_fnc_canLoadCargo", "\x\usafdc\addons\drop_computer\functions\cargo\fn_canLoadCargo.sqf"],
    ["USAFDC_fnc_nearestLoader", "\x\usafdc\addons\drop_computer\functions\cargo\fn_nearestLoader.sqf"],
    ["USAFDC_fnc_loadCargo", "\x\usafdc\addons\drop_computer\functions\cargo\fn_loadCargo.sqf"],
    ["USAFDC_fnc_loadViv", "\x\usafdc\addons\drop_computer\functions\cargo\fn_loadViv.sqf"],
    ["USAFDC_fnc_loadAttach", "\x\usafdc\addons\drop_computer\functions\cargo\fn_loadAttach.sqf"],
    ["USAFDC_fnc_unloadCargo", "\x\usafdc\addons\drop_computer\functions\cargo\fn_unloadCargo.sqf"],
    ["USAFDC_fnc_unloadViv", "\x\usafdc\addons\drop_computer\functions\cargo\fn_unloadViv.sqf"],
    ["USAFDC_fnc_unloadAttach", "\x\usafdc\addons\drop_computer\functions\cargo\fn_unloadAttach.sqf"],
    ["USAFDC_fnc_releaseSelected", "\x\usafdc\addons\drop_computer\functions\cargo\fn_releaseSelected.sqf"],
    ["USAFDC_fnc_syncMerge", "\x\usafdc\addons\drop_computer\functions\sync\fn_syncMerge.sqf"],
    ["USAFDC_fnc_hasComputer", "\x\usafdc\addons\drop_computer\functions\access\fn_hasComputer.sqf"],
    ["USAFDC_fnc_canUseCarp", "\x\usafdc\addons\drop_computer\functions\access\fn_canUseCarp.sqf"]
];

["USAFDC_jumpCue", {
    params ["_sound"];
    if (missionNamespace getVariable ["USAFDC_setting_sounds", true]) then {playSound _sound};
}] call CBA_fnc_addEventHandler;

// The jump readout, drawn on every machine in the roster rather than only on the one
// running fn_updateJumpCue. Not gated on the sounds setting: a jumper who has turned
// cue audio off still needs to see the countdown, and it is not gated on hasInterface
// either because CBA only delivers this where a rostered unit is local.
//
// IT IS A TITLE LAYER, NOT hintSilent. The hint box is ONE slot shared by every mod in
// the session and the last writer wins. Flown in MP on 2026-09-21: the readout was
// visible from a seat, vanished the moment the jumper stood up on the ramp under the
// free-fall mod, and CAME BACK once their canopy opened. That last part is what settled
// it -- if the roster had stopped addressing the client it would have stayed gone, since
// the roster is a snapshot taken at arm time and a jumper under canopy is in neither it
// nor `crew`. Coming back means the event was arriving throughout and something else
// owned the hint slot for exactly as long as the ramp UI was up.
//
// A title layer CARP allocates for itself cannot be taken. isStructured, so the markup
// the cue already builds renders unchanged. An empty string clears the layer, which is
// how fn_disarmJumpRun wipes every screen at once -- without that the last frame of the
// readout would stay on screen after the run ended.
["USAFDC_jumpHint", {
    params ["_text"];
    if (isNil "USAFDC_state_jumpHintLayer") exitWith {};
    if (_text isEqualTo "") exitWith {USAFDC_state_jumpHintLayer cutText ["", "PLAIN"]};
    USAFDC_state_jumpHintLayer cutText [_text, "PLAIN", 0, true, true];
}] call CBA_fnc_addEventHandler;

// The doorbell for crew sync. The aircraft object variable is the record; this only
// makes a change visible immediately rather than on the receiver's next tick, so a
// missed event costs latency and never correctness. It only ever moves a client forward
// on the airframe it is already following: a late doorbell must not roll it back, and
// anything else -- a different aircraft, a record from before boarding -- is fn_syncTick's
// to settle.
["USAFDC_carpRecordChanged", {
    params ["_aircraft", "_record"];
    if (!hasInterface || {isNull _aircraft} || {(count _record) < 5}) exitWith {};
    if !([player, _aircraft] call USAFDC_fnc_canUseCarp) exitWith {};
    if !((_aircraft isEqualTo (missionNamespace getVariable ["USAFDC_state_syncAircraft", objNull])) && {(_record # 0) > (missionNamespace getVariable ["USAFDC_state_syncRev", -1])}) exitWith {};
    [_aircraft, _record] call USAFDC_fnc_syncApply;
}] call CBA_fnc_addEventHandler;

// The server half of crew sync. Every crew edit is merged here, one patch at a time, so
// the server is the only machine that writes an aircraft's record. See fn_syncMerge.
["USAFDC_carpPatch", {
    if (!isServer) exitWith {};
    _this call USAFDC_fnc_syncMerge;
}] call CBA_fnc_addEventHandler;
// How a client knows there is a server to merge for it. A server without CARP never
// sets this, and fn_syncPublish then merges on the client instead.
if (isServer) then {missionNamespace setVariable ["USAFDC_serverVersion", USAFDC_VERSION, true]};

// ---- guided cargo: every machine, because the canopy is usually the server's ----
// Delivered with CBA_fnc_globalEventJIP so a player joining during a descent gets the
// job too. Registered here, above the interface guard, because the machine that has to
// ACT on it is normally the dedicated server -- USAF releases cargo where the cargo is
// local, and Eden-placed, Zeus-spawned and script-spawned loads all belong to it.
["USAFDC_steerBegin", {
    params ["_job"];
    private _cargo = _job # 0;
    if (isNull _cargo) exitWith {};
    // Replace rather than append: a re-published job for the same load must not leave
    // two entries steering it with two different aim points.
    USAFDC_state_steerJobs = (USAFDC_state_steerJobs select {!((_x # 0) isEqualTo _cargo)}) + [_job];
}] call CBA_fnc_addEventHandler;

// EVERY FRAME, and on every machine. Measured in v0.4.6: at the 0.05 s guidance interval
// the parachute's own physics reasserted between calls and only 41% of the commanded
// closing speed survived. fn_steerTick exits on a single count when nothing is in the
// air, so the cost on an idle server is nil.
if (USAFDC_state_jpadsEh < 0) then {
    USAFDC_state_jpadsEh = addMissionEventHandler ["EachFrame", {
        if !(isNil "USAFDC_fnc_steerTick") then {[] call USAFDC_fnc_steerTick};
    }];
};

[] call USAFDC_fnc_resetPackageTiming;

diag_log format ["[TLB CARP][LOAD] state, settings and functions registered hasInterface=%1", hasInterface];

// ---- everything below here needs a screen ------------------------------------
if (!hasInterface) exitWith {
    diag_log "[TLB CARP][LOAD] headless: no HUD, keybinds, actions or draw handlers";
};

// The HUD's display layer. BIS_fnc_rscLayer is a UI allocation and has nothing to do
// on a machine with no display.
USAFDC_state_hudLayer = "USAFDC_HUD_LAYER" call BIS_fnc_rscLayer;

// The jump readout's OWN layer, and it is a title layer rather than the hint box for a
// reason that cost a flown MP session to find. See the USAFDC_jumpHint receiver above.
USAFDC_state_jumpHintLayer = "USAFDC_JUMP_LAYER" call BIS_fnc_rscLayer;

// 5 Hz, and deliberately not folded into the guidance loop: adoption has to work
// BEFORE guidance is armed, which is exactly when a co-pilot needs to pick up the
// pilot's DZ, and it has to keep working when the guidance loop is not running. It
// resolves the aircraft through `player`, so it belongs on this side of the guard.
if (USAFDC_state_syncPfh >= 0) then {
    [USAFDC_state_syncPfh] call CBA_fnc_removePerFrameHandler;
};
USAFDC_state_syncPfh = [{[] call USAFDC_fnc_syncTick}, 0.2, []] call CBA_fnc_addPerFrameHandler;

[
    "TLB CARP",
    "OpenComputer",
    ["Open TLB CARP", "Open the TLB Computed Air Release Point system"],
    {[] call USAFDC_fnc_openPanel},
    {},
    [0, [false, false, false]]
] call CBA_fnc_addKeybind;

// ---- the CARP panel: an action on the AIRCRAFT, for whoever carries the computer ----
// Pressing the interaction key inside a vehicle shows that vehicle's ACE_SelfActions
// (ace_interact_menu fnc_renderActionPoints: "Render vehicle self actions when in
// vehicle"), so that is where an action that only makes sense from inside the airframe
// belongs. It used to be a self-interaction on every CAManBase. Registered with
// inheritance on "Air"; fn_canUseCarp narrows it to aircraft CARP can solve for and to
// players carrying a CARP Computer.
private _openAction = [
    "USAFDC_Open",
    "TLB CARP",
    "\x\tlbcarp\addons\items\data\tlb_carp_computer_ca.paa",
    {[] call USAFDC_fnc_openPanel},
    {
        params ["_target", "_player"];
        [_player, _target] call USAFDC_fnc_canUseCarp
    }
] call ace_interact_menu_fnc_createAction;
["Air", 1, ["ACE_SelfActions"], _openAction, true] call ace_interact_menu_fnc_addActionToClass;

// ---- jump run: keybind AND an ACE self-action --------------------------------
// Both, because neither alone is enough. The keybind is unbound by default (like
// OpenComputer above), so a fresh install has no way to reach the feature without
// the self-action; and the self-action needs an objectParent, which a jumper
// standing in FFR's dummy does not have, so the pilot needs the key.
//
// The condition is only "is it an aircraft", NOT resolveAircraftProfile. Jump mode
// has no calibration profile to resolve -- the cargo profiles carry a canopy model
// and a release delay that mean nothing for a human -- so gating on one would
// refuse to arm on any airframe that is not a calibrated C-17 or C-130.
[
    "TLB CARP",
    "ToggleJumpRun",
    ["Toggle Jump Run", "Arm or disarm the HALO/HAHO exit cue: computed exit point, audible countdown, and the jumplight."],
    {
        if (USAFDC_state_jumpArmed) then {
            ["PILOT DISARM"] call USAFDC_fnc_disarmJumpRun
        } else {
            [] call USAFDC_fnc_armJumpRun
        };
        true
    },
    {},
    [0, [false, false, false]]
] call CBA_fnc_addKeybind;

// The jump run moved onto the CARP panel in v0.15.0 (button idc 9337) and the two ACE
// interaction entries that used to live here are gone with it.
//
// It was the last CARP action outside the panel, and a panel button is strictly better:
// the label reads USAFDC_jumpArmedBy, which is public and set on the AIRCRAFT, so every
// seat sees that the run is armed and by whom -- an ACE action could only ever show its
// own client's flag. Locality is unchanged: clicking it arms on that machine exactly as
// the action did, so one machine still runs fn_updateJumpCue and the readout still
// broadcasts to the roster, and fn_armJumpRun's own check on USAFDC_jumpArmedBy is what
// stops a second crew member starting a competing run.


// ---- loading, on the LOAD rather than on the aircraft ------------------------------
//
// ACE puts its own Load action on the object being loaded, and that is the right place:
// a loadmaster walks up to the truck, not to the wing. It also answers "which aircraft"
// without asking -- the nearest one that can take it.
//
// ACE_MainActions, not ACE_SelfActions, because this is done from OUTSIDE the aircraft.
// The jump run above is the opposite case and that is why the two sit in different menus.
private _loadAction = [
    "USAFDC_LoadCargo",
    "Load Into Aircraft",
    "",
    {
        params ["_target"];
        private _carrier = [_target] call USAFDC_fnc_nearestLoader;
        if (isNull _carrier) exitWith {};
        private _method = [_carrier, _target] call USAFDC_fnc_loadCargo;
        if (_method isEqualTo "") then {
            hint format ["TLB CARP: cannot load -- %1",
                ([_carrier, _target] call USAFDC_fnc_canLoadCargo) param [1, "no aircraft"]];
        } else {
            hint format ["TLB CARP: loaded into %1 (%2)",
                getText (configFile >> "CfgVehicles" >> typeOf _carrier >> "displayName"), toUpper _method];
        };
    },
    {
        params ["_target", "_player"];
        // Cheap tests first: the expensive one walks nearby aircraft and derives a hold.
        (alive _target) && {isNull (attachedTo _target)} && {(count (crew _target)) isEqualTo 0}
            && {!isNull ([_target] call USAFDC_fnc_nearestLoader)}
    }
] call ace_interact_menu_fnc_createAction;
{
    [_x, 0, ["ACE_MainActions"], _loadAction, true] call ace_interact_menu_fnc_addActionToClass;
} forEach ["LandVehicle", "Ship", "ThingX", "ReammoBox_F"];

// ---- unloading, on the aircraft ----------------------------------------------------
//
// The counterpart to loading, NOT to the drop. It refuses above walking height: ACE's own
// Unload on an airborne aircraft can open the canopy at altitude, and the drop is the only
// way cargo should leave a flying aircraft.
private _unloadAction = [
    "USAFDC_UnloadCargo",
    "Unload Last Load",
    "",
    {
        params ["_target"];
        private _manifest = [_target] call USAFDC_fnc_getLoadedCargo;
        if ((count _manifest) isEqualTo 0) exitWith {};
        [_target, _manifest select ((count _manifest) - 1)] call USAFDC_fnc_unloadCargo;
    },
    {
        params ["_target"];
        ((getPos _target) # 2) <= 3 && {(count ([_target] call USAFDC_fnc_getLoadedCargo)) > 0}
    }
] call ace_interact_menu_fnc_createAction;
["Air", 0, ["ACE_MainActions"], _unloadAction, true] call ace_interact_menu_fnc_addActionToClass;


["ace_interactMenuOpened", {
    USAFDC_state_apAceInteractOpen = true;
    USAFDC_state_apOverrideSince = -1;
    USAFDC_state_apOverrideInhibitUntil = diag_tickTime + 0.5;
}] call CBA_fnc_addEventHandler;
["ace_interactMenuClosed", {
    USAFDC_state_apAceInteractOpen = false;
    USAFDC_state_apOverrideSince = -1;
    USAFDC_state_apOverrideInhibitUntil = diag_tickTime + 0.5;
}] call CBA_fnc_addEventHandler;

diag_log "[TLB CARP][LOAD] registrations complete";


if (USAFDC_state_3dEh < 0) then {
    USAFDC_state_3dEh = addMissionEventHandler ["Draw3D", {
        if (!USAFDC_setting_3dEnabled || {!USAFDC_state_guidanceArmed}) exitWith {};
        private _solution = USAFDC_state_solution;
        if !(_solution getOrDefault ["valid", false]) exitWith {};
        private _desiredTrackDeg = _solution getOrDefault ["desiredTrackDeg", _solution get "runInDeg"];
        private _liveRp = _solution getOrDefault ["liveRpPosASL", _solution get "rpPosASL"];
        private _plannedRp = _solution getOrDefault ["plannedRpPosASL", _liveRp];
        drawIcon3D [
            "\a3\ui_f\data\map\markers\military\dot_CA.paa",
            [0.4, 0.9, 0.65, 0.9],
            ASLToAGL _liveRp,
            0.8, 0.8, 0,
            format ["LIVE RP %1 m | DES TRK %2", round (abs (_solution get "signedRpM")), round _desiredTrackDeg],
            1, 0.03, "RobotoCondensed"
        ];
        if ((_liveRp distance2D _plannedRp) > 50) then {
            drawIcon3D [
                "\a3\ui_f\data\map\markers\military\circle_CA.paa",
                [0.8, 0.8, 0.8, 0.35],
                ASLToAGL _plannedRp,
                0.65, 0.65, 0,
                "PLANNED RP",
                1, 0.025, "RobotoCondensed"
            ];
        };
    }];
};

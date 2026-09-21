/*
    USAFDC_fnc_setJumpLight

    Drive the physical jumplight if Free Fall Off The Ramp is providing one, and
    report honestly when it is not.

    [_aircraft, "red" | "green" | "off"] call USAFDC_fnc_setJumpLight
    Returns true only if a real light was commanded.

    FFR's own integration point, read from its source rather than guessed:
        ["ffr_main_setJumplight", [_aircraft, "green"]] call CBA_fnc_globalEvent
    It registers that handler in XEH_postInit and dispatches to fnc_setJumplight,
    which colours the light objects and, for RHS_C130J only, also drives a modelled
    "jumplight" animation source.

    Two things about that light are worth knowing before relying on it:

      The light OBJECT DOES NOT EXIST until someone has used FFR's "Prep Ramp for
      Free Fall" action, which sets ffr_jumplight on the aircraft and is itself
      gated above 200 m. Commanding the event before that is a silent no-op, so
      this checks for the object and returns false instead, letting the caller fall
      back to the HUD cue and the audio.

      On the USAF C-17 there is no modelled lamp. FFR creates a #lightreflector and
      attaches it in the bay at [0, -6, 3], so what jumpers see is a red or green
      glow in the hold rather than a lit panel. That is a reason the HUD cue and the
      audio countdown carry the cue rather than decorate it.
*/

params ["_aircraft", "_state"];

if (isNull _aircraft) exitWith {false};
if !(_state in ["red", "green", "off"]) exitWith {false};

// Cached once. isClass on CfgPatches is the load check; the per-aircraft object
// check below is the readiness check, and they are not the same question.
if (isNil "USAFDC_state_jumpFfrLoaded") then {
    USAFDC_state_jumpFfrLoaded = isClass (configFile >> "CfgPatches" >> "ffr_main");
};
if (!USAFDC_state_jumpFfrLoaded) exitWith {false};

private _light = _aircraft getVariable ["ffr_jumplight", objNull];
if (isNull _light) exitWith {false};

// Only on a CHANGE. fn_updateJumpCue calls this unconditionally from every branch of
// its per-frame handler, and INBOUND lasts the whole run-in while PASSED lasts until
// the pilot disarms -- so without this, a [object, string] payload went out as a
// GLOBAL event, to every machine in the mission and not just the crew, twenty times a
// second for minutes at a stretch. Each receiver then re-coloured the light objects
// and, on an RHS C-130J, re-drove an animation source. Cached after the broadcast so
// a failed send is not remembered as delivered.
if (_state isEqualTo (missionNamespace getVariable ["USAFDC_state_jumpLightState", ""])) exitWith {true};

["ffr_main_setJumplight", [_aircraft, _state]] call CBA_fnc_globalEvent;
USAFDC_state_jumpLightState = _state;
true

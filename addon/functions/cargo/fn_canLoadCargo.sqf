/*
    USAFDC_fnc_canLoadCargo

    Whether this vehicle can be loaded into this aircraft, and by which mechanism.

        [_carrier, _cargo] call USAFDC_fnc_canLoadCargo
            -> ["viv" | "usaf" | "carp" | "", reason]

    THREE MECHANISMS, IN PREFERENCE ORDER, AND THE ORDER IS THE POINT

    "any cargo aircraft from any mod" cannot be one mechanism, because Arma has no shared
    idea of a cargo hold. What it has is three partial ones, and the right answer is to
    use the most supported one each airframe offers rather than to impose ours on all of
    them.

      viv   Vanilla vehicle-in-vehicle. The aircraft declares VehicleTransport and the
            engine does the rest -- ramp animation, capacity, the lot. Any mod that
            configured it gets the behaviour its author intended, and CARP adds nothing.

      usaf  The airframe publishes USAF's own hold geometry -- USAF_Cargo_endOffset and
            the Max* limits. We use the NUMBERS, not USAF's function: those coordinates
            were placed by hand against that model and are better than anything derivable,
            but the loading itself stays ours so USAF need not be installed.

            Through v0.16.2 this looked for USAF_Cargo_LoadPos, which does not exist on
            any airframe in either USAF mod, so the branch never once fired.

      carp  Neither. The hold is derived from the bounding box -- see
            USAFDC_fnc_loadModelOffset, which explains why a derivation is acceptable for
            a load position and would not be for a release point.

    WHY "" IS A RESULT AND NOT AN ERROR

    Plenty of aircraft have no hold at all, and a jet that refuses a truck is correct
    behaviour rather than a missing feature. The reason string is what the interaction
    menu shows, so it has to say which of those it is.
*/

params ["_carrier", "_cargo"];
if (isNull _carrier || {isNull _cargo}) exitWith {["", "NOTHING SELECTED"]};
if !(_carrier isKindOf "Air") exitWith {["", "NOT AN AIRCRAFT"]};
if (_carrier isEqualTo _cargo) exitWith {["", "NOT ITSELF"]};
if !(alive _carrier && {alive _cargo}) exitWith {["", "DESTROYED"]};

// Already aboard by any mechanism. Asked before anything else, because the answer to
// "can I load this" when it is already loaded is not "no room".
if (_cargo in ([_carrier] call USAFDC_fnc_getLoadedCargo)) exitWith {["", "ALREADY ABOARD"]};
if !(isNull (attachedTo _cargo)) exitWith {["", "ATTACHED TO SOMETHING ELSE"]};
if !(isNull (isVehicleCargo _cargo)) exitWith {["", "LOADED IN SOMETHING ELSE"]};
if ((count (crew _cargo)) > 0) exitWith {["", "CREW ABOARD THE LOAD"]};

// The same type set the manifest accepts, so nothing can be loaded that the manifest
// would then refuse to see. A load CARP cannot find is a load CARP cannot drop.
private _droppable =
    _cargo isKindOf "LandVehicle" || {_cargo isKindOf "Ship"}
    || {_cargo isKindOf "ThingX"} || {_cargo isKindOf "ReammoBox_F"};
if (!_droppable) exitWith {["", "NOT A LOADABLE TYPE"]};

// ---- 1. the engine's own mechanism, wherever the airframe supports it ---------------
private _viv = _carrier canVehicleCargo _cargo;
if ((_viv param [0, false]) && {_viv param [1, false]}) exitWith {["viv", "VEHICLE-IN-VEHICLE"]};

// ---- 2 and 3. ONE QUESTION, ASKED ONCE ----------------------------------------------
//
// This used to test for USAF_Cargo_LoadPos here and then read it again in fn_loadCargo.
// THAT PROPERTY DOES NOT EXIST -- not on any airframe, in either USAF mod, ever. So this
// branch never fired and every load on every aircraft fell through to the derivation,
// which is what put a vehicle behind the tail of a C-130 whose hold is placed by hand in
// its own config. Two readers of one config key is also how they come to disagree.
//
// USAFDC_fnc_loadModelOffset is now the single answer: it prefers a mission override,
// then the airframe author's published hold, then its own derivation, and reports which
// it used. The mechanism name here is that answer relabelled, so "can I load this" and
// "where does it go" can no longer give different results.
private _offset = [_carrier, _cargo] call USAFDC_fnc_loadModelOffset;
if ((count _offset) < 4) exitWith {["", "WILL NOT FIT"]};

switch (_offset # 3) do {
    case "override": {["carp", "MISSION-DEFINED HOLD"]};
    case "usafConfig": {["usaf", "USAF HOLD"]};
    default {["carp", "DERIVED HOLD"]};
}

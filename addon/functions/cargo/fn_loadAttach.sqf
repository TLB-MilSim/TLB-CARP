/*
    TLB_CARP_fnc_loadAttach

    CARP's own load: attach the vehicle in the hold, run where the CARGO is local.

        [_carrier, _cargo, _offset] call TLB_CARP_fnc_loadAttach

    MUST RUN WHERE THE CARGO IS LOCAL. attachTo, setDir and disableCollisionWith are all
    local-effect, and on a dedicated server a Zeus-spawned or Eden-placed vehicle belongs
    to the server rather than to the player who asked for it to be loaded. fn_loadCargo
    remoteExecs here for that reason, exactly as the release does.

    THE LOAD IS SQUARED TO THE AIRCRAFT BEFORE IT IS ATTACHED

    attachTo keeps the object's current world orientation unless it is set afterwards, so
    a truck driven up at an angle stays at that angle inside the hold and looks wrong from
    the ramp. setVectorDirAndUp against the carrier's own vectors puts it nose-forward and
    level with the floor.

    COLLISION IS DISABLED FOR THE SAME REASON THE RELEASE DISABLES IT

    An attached vehicle inside a fuselage is interpenetrating it by definition. USAF calls
    disableCollisionWith at release; doing it at load instead means the load is not
    fighting the airframe for the whole flight. fn_releaseCargo calls it again on the way
    out, which is harmless and keeps that sequence unchanged.
*/

params ["_carrier", "_cargo", "_offset"];
if (isNull _carrier || {isNull _cargo}) exitWith {false};
if ((count _offset) < 3) exitWith {false};
if !(local _cargo) exitWith {
    diag_log format ["[TLB CARP][LOAD] attach refused: cargo %1 is not local here", _cargo];
    false
};

_cargo disableCollisionWith _carrier;
_carrier disableCollisionWith _cargo;
_cargo attachTo [_carrier, [_offset # 0, _offset # 1, _offset # 2]];
// PARENT-RELATIVE, NOT WORLD. Orientation commands on an ATTACHED object are expressed in
// its parent's frame, so handing this the carrier's WORLD vectors applied the aircraft's
// heading a second time on top of the one it already had -- a load came out square to the
// compass and sideways in the hold, which is what a flown C-130 showed.
//
// [0,-1,0] is 180 degrees in the carrier's frame: nose toward the tail, which is USAF's
// own `setDir 180` and therefore how every load USAF put in this hold is already facing.
// Matching it matters because the two can be mixed in one aircraft.
_cargo setVectorDirAndUp [[0, -1, 0], [0, 0, 1]];

// Stamped so the manifest's next rebuild does not have to guess, and so an unload knows
// this was ours rather than something a mission maker attached by hand.
_cargo setVariable ["TLB_CARP_cargoSource", "attached", true];
_cargo setVariable ["TLB_CARP_loadedByCarp", true, true];
true

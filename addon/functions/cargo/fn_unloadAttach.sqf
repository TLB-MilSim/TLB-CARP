/*
    TLB_CARP_fnc_unloadAttach -- detach a load and set it down, where the CARGO is local.

    detach, setPos and setVectorDirAndUp are local-effect, so this runs on the cargo's
    machine for the same reason fn_loadAttach does.

    Placed BESIDE the aircraft rather than under it. Detaching in place leaves the vehicle
    inside the fuselage with collisions still disabled, and re-enabling them there throws
    it out at speed. Six metres off the port side and on the surface is somewhere it can
    simply stand.
*/
params ["_carrier", "_cargo"];
if (isNull _carrier || {isNull _cargo}) exitWith {false};
if !(local _cargo) exitWith {false};

detach _cargo;

private _side = _carrier modelToWorld [-8, 0, 0];
_cargo setPos [_side # 0, _side # 1, 0];
_cargo setVectorDirAndUp [vectorDir _carrier, surfaceNormal (getPos _cargo)];
_cargo setVelocity [0, 0, 0];

_cargo enableCollisionWith _carrier;
_carrier enableCollisionWith _cargo;
_cargo setVariable ["TLB_CARP_loadedByCarp", nil, true];
_cargo setVariable ["TLB_CARP_loadSlotY", nil, false];
_cargo setVariable ["TLB_CARP_loadSlotEndY", nil, false];
true

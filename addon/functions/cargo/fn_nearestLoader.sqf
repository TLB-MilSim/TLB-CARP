/*
    TLB_CARP_fnc_nearestLoader

    The nearest aircraft that could actually take this load.

        [_cargo] call TLB_CARP_fnc_nearestLoader  ->  aircraft or objNull

    Exists so the interaction menu does not have to ask "which aircraft" -- a loadmaster
    walks up to the truck and there is only ever one plausible answer, which is the
    transport parked beside it.

    "Could actually take it" is fn_canLoadCargo, not proximity. An aircraft with no hold
    and a full one are both wrong answers, and offering Load and then refusing it is worse
    than not offering it, so the predicate that decides the menu entry and the predicate
    that performs the load are the same one.

    Distance is checked from the CARGO, and the radius is generous rather than tight: a
    C-17 is fifty metres long and its origin is nowhere near its ramp, so a truck sitting
    correctly behind one is already twenty-five metres from the aircraft's position.
*/

params ["_cargo", ["_radiusM", 60]];
if (isNull _cargo) exitWith {objNull};

private _best = objNull;
private _bestDist = 1e9;
{
    if (alive _x && {!(_x isEqualTo _cargo)}) then {
        private _d = _cargo distance _x;
        if (_d < _bestDist) then {
            if ((([_x, _cargo] call TLB_CARP_fnc_canLoadCargo) param [0, ""]) != "") then {
                _best = _x;
                _bestDist = _d;
            };
        };
    };
} forEach (_cargo nearEntities [["Air"], _radiusM]);

_best

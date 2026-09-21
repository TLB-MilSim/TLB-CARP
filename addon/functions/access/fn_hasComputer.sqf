/*
    USAFDC_fnc_hasComputer

    Whether a unit carries a CARP Computer.

        [unit] call USAFDC_fnc_hasComputer

    The item is a CBA misc item, so it sits in the uniform, vest or backpack and `items`
    finds it wherever it was put. `==` on strings ignores case, which matters because
    hand-written loadouts do not always match the config's spelling.
*/

params [["_unit", objNull, [objNull]]];
if (isNull _unit) exitWith {false};
((items _unit) findIf {_x == "TLB_CARP_Computer"}) >= 0

/*
    USAFDC_fnc_getLoadedCargo

    What is aboard and droppable. Thin wrapper over USAFDC_fnc_cargoManifest, kept
    because it is declared in the pre-binarized config.bin and several call sites reach
    it by that name.

    This used to be the line that tied CARP to one mod's loading action:

        +(_vehicle getVariable ["usaf_cargo", []])

    which meant a load put aboard by ACE, by vanilla vehicle-in-vehicle or by a mission
    maker's attachTo simply did not exist as far as the solver, the panel, the package
    tracker and Auto Drop were concerned.
*/

params ["_vehicle"];
if (isNull _vehicle) exitWith {[]};
if (isNil "USAFDC_fnc_cargoManifest") exitWith {+(_vehicle getVariable ["usaf_cargo", []])};
[_vehicle] call USAFDC_fnc_cargoManifest

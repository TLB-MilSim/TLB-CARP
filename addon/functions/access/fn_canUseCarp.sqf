/*
    TLB_CARP_fnc_canUseCarp

    The one access rule for the CARP panel and for crew sync.

        [unit, aircraft] call TLB_CARP_fnc_canUseCarp

    A unit may use CARP when it is inside that aircraft, the aircraft resolves to a
    profile, and -- unless the mission has switched the requirement off -- the unit
    carries a CARP Computer.

    The ACE action on the airframe, fn_openPanel (which the keybind reaches without any
    ACE condition), fn_syncPublish, fn_syncTick and the crew-sync doorbell all ask this
    function and nothing else. That is what keeps "can open the panel" and "shares the
    crew's CARP" from ever disagreeing.
*/

params [["_unit", objNull, [objNull]], ["_aircraft", objNull, [objNull]]];
if (isNull _unit || {isNull _aircraft}) exitWith {false};
if !((objectParent _unit) isEqualTo _aircraft) exitWith {false};
if (([_aircraft] call TLB_CARP_fnc_resolveAircraftProfile) isEqualTo "") exitWith {false};
!(missionNamespace getVariable ["TLB_CARP_setting_requireComputer", true]) || {[_unit] call TLB_CARP_fnc_hasComputer}

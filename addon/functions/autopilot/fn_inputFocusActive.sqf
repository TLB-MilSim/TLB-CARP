// THE MAP. Reported from a flown session: arm the AP, open the map, move the mouse, and
// the AP disconnects with PILOT OVERRIDE.
//
// Reading only the pilot's own bound keys would not fix it, which is worth stating because
// it is the obvious idea. inputAction ALREADY reports bound keys -- that is what it is for.
// The problem is not a key at all: aircraft pitch and roll are on the MOUSE AXES, and Arma
// keeps feeding mouse motion to those channels while the map is up. There is no binding to
// exclude, because the thing generating the input is the mouse the pilot is using to pan.
//
// So it belongs here with the other four cases, all of which are the same shape: something
// else owns the mouse right now.
private _mapOpen = visibleMap;
private _carpOpen = !(isNull (findDisplay 9300));
private _zeusOpen = !(isNull (findDisplay 312));
private _aceOpen = missionNamespace getVariable ["TLB_CARP_state_apAceInteractOpen", false];
private _lookAroundHeld = (inputAction "lookAround") > 0.1;

// "lookAroundToggle" reports a momentary key pulse, not the freelook state.
// Once double-tap freelook latches on, both freelook channels read 0 while the
// mouse still drives the view, so mouse motion looked like pilot input and
// disconnected the AP. Latch the toggle here on the key's rising edge.
private _togglePulse = (inputAction "lookAroundToggle") > 0.1;
private _prevPulse = missionNamespace getVariable ["TLB_CARP_state_apLookAroundTogglePrev", false];
if (_togglePulse && {!_prevPulse}) then {
    TLB_CARP_state_apFreelookToggled = !(missionNamespace getVariable ["TLB_CARP_state_apFreelookToggled", false]);
};
TLB_CARP_state_apLookAroundTogglePrev = _togglePulse;
private _freelookToggled = missionNamespace getVariable ["TLB_CARP_state_apFreelookToggled", false];

_mapOpen
|| {_carpOpen}
|| {_zeusOpen}
|| {_aceOpen}
|| {_lookAroundHeld}
|| {_togglePulse}
|| {_freelookToggled}

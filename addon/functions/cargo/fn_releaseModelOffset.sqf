/*
    TLB_CARP_fnc_releaseModelOffset

    Where on the carrier the load leaves from, in model space.

    [_carrier, _cargo] call TLB_CARP_fnc_releaseModelOffset  ->  [x, y, z, source]

    The z already includes the load's own bounding-box top, exactly as USAF's
    fn_dropCargo does, so the returned vector is ready to hand to attachTo.

    THREE SOURCES, IN PRIORITY ORDER, AND THE MIDDLE ONE IS WHY THE CALIBRATION IS SAFE

      override  TLB_CARP_dropPos set on the carrier by a mission maker. Highest priority
                so a unit can correct an airframe without a rebuild.

      config    USAF_Cargo_DropPos from the carrier's config. For a C-17 or a C-130
                this returns exactly what CARP has always used, so nothing about the
                calibrated airframes changes.

      bbox      Derived, for an airframe nobody has configured. Centreline, six metres
                aft of the model's rear extent, a metre and a half below the hull.

    THE DERIVATION IS CHECKED AGAINST THE ONE AIRFRAME WE KNOW

    On the USAF C-17 the rule gives [0, -30.02, -4.86] against the hand-placed config
    value of [0, -30, -5]: 2 cm along and 14 cm vertically. That agreement is the
    reason to trust the rule, not a coincidence to note in passing.

    It does NOT reproduce the C-130's [0, -30, -0.2] -- the rule gives [0, -21.0, -1.55]
    there -- but USAF's C-130 number puts the release fifteen metres behind the tail,
    and it is the outlier rather than the rule. Both calibrated airframes read their
    config value anyway, so the disagreement costs nothing.

    ERROR BUDGET, using the solver's own sensitivities. The along and right offsets
    enter the release point one for one, so ten metres of error aft is ten metres of
    along-track miss. The vertical enters through release AGL into freefall time: at
    3000 m AGL, t = sqrt(2*2700/9.81) = 23.46 s and dt/dh = 1/(g*t) = 0.00434 s/m, so
    at 140 m/s one metre of vertical error is 0.61 m along-track and five metres is
    three. Against a 50 m operational box and the ~20 m of unguided canopy scatter this
    project already measures in wind, a derived offset on an unknown airframe is a
    minor error source.
*/

params ["_carrier", ["_cargo", objNull]];
if (isNull _carrier) exitWith {[0, 0, 0, "none"]};

// USAF adds the load's bounding-box top so the attach point sits under the load rather
// than through it. Same here, for the same reason.
private _bboxTop = if (isNull _cargo) then {0} else {((0 boundingBoxReal _cargo) # 1) # 2};

private _override = _carrier getVariable ["TLB_CARP_dropPos", []];
if ((count _override) >= 3) exitWith {
    [_override # 0, _override # 1, (_override # 2) + _bboxTop, "override"]
};

private _cfg = configFile >> "CfgVehicles" >> typeOf _carrier;
private _configured = getArray (_cfg >> "USAF_Cargo_DropPos");
if ((count _configured) >= 3) exitWith {
    [_configured # 0, _configured # 1, (_configured # 2) + _bboxTop, "config"]
};

(0 boundingBoxReal _carrier) params ["_bbMin", "_bbMax"];
private _aft = (_bbMin # 1) - 6;
private _below = (_bbMin # 2) - 1.5;
[0, _aft, _below + _bboxTop, "bbox"]

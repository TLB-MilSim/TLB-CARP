/*
    TLB_CARP_fnc_loadModelOffset

    Where inside a carrier the next load should sit.

        [_carrier, _cargo] call TLB_CARP_fnc_loadModelOffset
            -> [x, y, z, source] in the carrier's model space, or [] if it will not fit

    THREE SOURCES, BEST FIRST: an explicit override, the airframe author's own hold
    coordinates, and only failing both, a derivation from the bounding box.

    v0.16.3 -- THE MIDDLE ONE HAD NEVER ONCE FIRED

    CARP looked for USAF_Cargo_LoadPos. That property does not exist. It has never existed:
    a scan of every PBO in both USAF mods finds zero occurrences of the string. What USAF
    actually publishes is USAF_Cargo_InitPos (a preview position for its fit check),
    USAF_Cargo_initOffset / midOffset / endOffset (the load animation, ending at the hold),
    and USAF_Cargo_Max{Width,Length,Height,Weight} (per-load limits, not hold extents).

    So every load on every airframe fell through to the derivation below, including the
    C-17 and C-130 whose holds are placed by hand in their own configs. It took a flown
    report to surface it because the fallback usually looks plausible.

    HOW USAF PLACES A LOAD, WHICH IS WHAT THIS NOW MIRRORS

    From USAF_CARGO_fnc_loadCargo: the stack starts at USAF_Cargo_endOffset and walks AFT
    by the new load's own forward half-length plus the full length of everything already
    aboard. So the first load sits flush with the forward end of the hold and each one
    after it goes directly behind the last, no gaps. For USAF_C130J_Cargo that endOffset is
    [0, 9, 1.25].

    Two deliberate departures from USAF's arithmetic:

      - The vertical. USAF computes its z from `(_obj worldToModel getPosATLVisual _obj)`,
        which mixes an ATL height into a world-to-model conversion and does not mean what
        it looks like. endOffset.z is treated here as the FLOOR and the load is lifted by
        its own -bbMin.z, which is the same thing this file already does for the derived
        hold and is geometrically what "sitting on the floor" means. If it is fractionally
        high the load rests on the floor instead of sinking through it, which is the safe
        direction for something CLAUDE.md classes as cosmetic.

      - What counts as already aboard. USAF sums `usaf_cargo` only. This sums the whole
        manifest, so a load put there by ACE, by vehicle-in-vehicle or by CARP occupies
        space too. That is the other half of the flown bug -- see below.

    WHY THE DERIVATION IS STILL ACCEPTABLE WHERE IT IS USED

    Nothing ballistic depends on this. The load rides attached until release, and the
    RELEASE offset -- TLB_CARP_fnc_releaseModelOffset, which reproduces the C-17's
    hand-placed value to within two centimetres -- is what the solver is calibrated
    against. This only has to put the vehicle somewhere that looks like the inside of the
    aircraft and rides with it.

    ARMA HAS NO CONCEPT OF A CARGO HOLD

    boundingBoxReal returns the whole model including wings and tail. There is no interior
    volume, no floor, no ramp aperture. So where nothing is published the hold is DERIVED,
    and the derivation is deliberately conservative -- it is better to refuse a load that
    would have fitted than to put a truck through a wing.

    A mission that knows better sets TLB_CARP_loadPos on the carrier -- the same override
    TLB_CARP_dropPos gives the release -- and everything below is skipped.

    LOADS STACK FROM THE FORWARD END, AND THE LAST ONE IN IS NEAREST THE RAMP

    Both sources agree on this and it matters for more than tidiness: the manifest is
    last-in-first-out at release, so the load that leaves first is the one that was packed
    last, which is the one at the back. A loadmaster expects that, and it makes the stick
    spacing along the run-in correspond to how the aircraft was packed.
*/

params ["_carrier", "_cargo"];
if (isNull _carrier || {isNull _cargo}) exitWith {[]};

// Fractions of the model's length, from the rear extent forward. A transport's usable
// hold is most of the fuselage but never the tail cone or the flight deck.
//
// THESE WERE MEASURED IN v0.16.3 AND THE OLD ONES WERE WRONG ON BOTH AIRFRAMES CHECKED.
//
// Deriving the real hold limits from the published configs -- endOffset.y as the forward
// end and MaxLength as the usable length -- gives, as a fraction of model length from the
// rear extent:
//
//                       HOLD_AFT   HOLD_FORE   floor above bbMin.z
//     C-130J              0.3993      0.8046      1.302 m  (0.1107 of height)
//     C-17                0.3079      0.7059      2.098 m  (0.1188 of height)
//     shipped to v0.16.2  0.1200      0.7800      0.200 m flat
//
// HOLD_AFT 0.12 put the aft limit 8.3 m (C-130J) and 10.4 m (C-17) behind the real floor,
// which is past the tip of an open ramp -- the flown symptom. HOLD_FORE 0.78 reaches 4.1 m
// into the C-17's flight deck.
//
// The values below are the CONSERVATIVE end of each pair rather than a best fit, because
// this branch now only runs for airframes that publish nothing, where nothing can check
// the answer. A load placed too far forward is still inside the fuselage; one placed too
// far aft is hanging in the air. So the derived hold is narrower than either aircraft
// measured: it refuses loads that would have fitted, which is the trade this file has
// always said it wants.
//
// Two airframes is a fit, not a law. Any airframe that cares should publish a hold or set
// TLB_CARP_loadPos, and both are read in preference to this.
#define HOLD_AFT 0.40
#define HOLD_FORE 0.70
// The floor scales with the airframe rather than sitting 0.2 m above the bottom of the
// landing gear. The two measurements agree to 0.008, which is the only reason this is a
// fraction at all; the flat constant was out by 1.10 m on the C-130J and 1.90 m on the
// C-17 -- i.e. the load sat on the ground the wheels stand on, not on the cargo deck.
#define FLOOR_FRACTION 0.115
#define GAP_M 1.0

private _override = _carrier getVariable ["TLB_CARP_loadPos", []];
if ((count _override) >= 3) exitWith {[_override # 0, _override # 1, _override # 2, "override"]};

(0 boundingBoxReal _carrier) params ["_cMin", "_cMax"];
(0 boundingBoxReal _cargo) params ["_gMin", "_gMax"];

private _cargoLen = (_gMax # 1) - (_gMin # 1);
private _cargoWide = (_gMax # 0) - (_gMin # 0);
private _cargoTall = (_gMax # 2) - (_gMin # 2);

private _loaded = [_carrier] call TLB_CARP_fnc_getLoadedCargo;
private _cfg = configFile >> "CfgVehicles" >> typeOf _carrier;

// ---- 1. the airframe author's own hold ----------------------------------------------
// NOTE ON SCOPE: this is one top-level `exitWith`, not an `if/then` containing several.
// In SQF `exitWith` leaves the nearest enclosing scope, and an `if ... then {}` block IS
// one -- an exitWith in there returns from the BLOCK and execution carries on down the
// file. The whole branch therefore has to be a single expression.
private _endOffset = getArray (_cfg >> "USAF_Cargo_endOffset");
if ((count _endOffset) >= 3) exitWith {
    // The author's limits, applied the way USAF's own fit check applies them. Width and
    // height are per load; LENGTH AND WEIGHT ARE CUMULATIVE over everything aboard --
    // USAF_CARGO_fnc_canLoad sums both across usaf_cargo before comparing. So MaxLength is
    // the usable hold length, which is the aft bound this branch would otherwise lack:
    // 12.1 m for USAF_C130J_Cargo, against an endOffset of [0, 9, 1.25].
    //
    // Each limit is honoured only when published and positive. A zero or missing entry
    // means "not specified", never "nothing fits" -- USAF_C130J's own base class carries
    // MaxLength 0.6, and reading that as a hold would refuse every vehicle in the game.
    private _maxW = getNumber (_cfg >> "USAF_Cargo_MaxWidth");
    private _maxL = getNumber (_cfg >> "USAF_Cargo_MaxLength");
    private _maxH = getNumber (_cfg >> "USAF_Cargo_MaxHeight");
    private _maxKg = getNumber (_cfg >> "USAF_Cargo_MaxWeight");

    // USAF's accumulator, over the whole manifest rather than usaf_cargo alone, so a hold
    // filled by ACE or vehicle-in-vehicle is not read as empty.
    private _usedLen = 0;
    private _usedKg = 0;
    {
        if (!isNull _x && {!(_x isEqualTo _cargo)}) then {
            (0 boundingBoxReal _x) params ["_oMin", "_oMax"];
            _usedLen = _usedLen + ((_oMax # 1) - (_oMin # 1));
            _usedKg = _usedKg + (getMass _x);
        };
    } forEach _loaded;

    // USAF defaults a massless object to 250 kg rather than letting it ride free.
    private _mass = getMass _cargo;
    if (_mass <= 0) then {_mass = 250};

    private _refused = (_maxW > 0 && {_cargoWide > _maxW})
        || {_maxH > 0 && {_cargoTall > _maxH}}
        || {_maxL > 0 && {(_usedLen + _cargoLen) > _maxL}}
        || {_maxKg > 0 && {(_usedKg + _mass) > _maxKg}};

    if (_refused) then {
        // The author said it does not fit. Honour that rather than routing around it into
        // a derivation that knows less about this airframe than its own config does.
        []
    } else {
        // Flush with the forward end, then each load directly behind the last.
        private _y = (_endOffset # 1) - ((_gMax # 1) + _usedLen);
        // Recorded so the derived branch's cursor can see this load if the two ever mix.
        _cargo setVariable ["TLB_CARP_loadSlotY", _y, false];
        _cargo setVariable ["TLB_CARP_loadSlotEndY", _y + (_cargoLen / 2) + GAP_M, false];
        [_endOffset # 0, _y, (_endOffset # 2) - (_gMin # 2), "usafConfig"]
    }
};

// ---- 2. derived, and only if the derivation finds room ------------------------------
private _len = (_cMax # 1) - (_cMin # 1);
private _rearY = (_cMin # 1) + (_len * HOLD_AFT);
private _foreY = (_cMin # 1) + (_len * HOLD_FORE);
private _floorZ = (_cMin # 2) + (((_cMax # 2) - (_cMin # 2)) * FLOOR_FRACTION);

// Refuse rather than clip. The carrier's full width and height are generous compared
// with any real hold, so these bounds are already lenient; a load that fails them would
// not have fitted under any derivation.
private _holdWide = ((_cMax # 0) - (_cMin # 0)) * 0.55;
private _holdTall = ((_cMax # 2) - (_cMin # 2)) * 0.55;
if (_cargoWide > _holdWide || {_cargoTall > _holdTall}) exitWith {[]};

// Where the aft-most free space starts: ahead of everything already aboard.
//
// THE CURSOR USED TO SEE ONLY CARP'S OWN LOADS, AND THAT WAS HALF THE FLOWN BUG.
//
// It read TLB_CARP_loadSlotY, which nothing but this file ever sets. A hold filled by
// USAF's action, by ACE or by a mission maker therefore looked EMPTY, so the next CARP
// load was placed at the aft-most slot regardless of what was already sitting there.
// Reported from the field as a vehicle ending up outside the tail of a C-130 -- two loads
// in by USAF's action, the third by ours.
//
// Anything without a CARP slot has its occupied span worked out from where it actually
// is. Rotation is ignored deliberately: USAF turns its loads 180 degrees, so the wider of
// the two half-lengths is the honest half-extent either way.
private _cursor = _rearY;
{
    if (!isNull _x && {!(_x isEqualTo _cargo)}) then {
        private _slot = _x getVariable ["TLB_CARP_loadSlotY", -1e9];
        private _end = _x getVariable ["TLB_CARP_loadSlotEndY", -1e9];
        if (_slot <= -1e8) then {
            // Not ours. Measure it.
            private _m = _carrier worldToModel (getPosWorld _x);
            (0 boundingBoxReal _x) params ["_oMin", "_oMax"];
            private _half = ((abs (_oMax # 1)) max (abs (_oMin # 1)));
            // A load ACE has hidden is parked about 100 m below the carrier and occupies
            // nothing. Only positions that are plausibly inside the airframe count.
            private _inside = ((_m # 1) >= ((_cMin # 1) - 2)) && {(_m # 1) <= ((_cMax # 1) + 2)}
                && {(abs (_m # 2)) <= (((_cMax # 2) - (_cMin # 2)) + 5)};
            if (_inside) then {
                _slot = _m # 1;
                _end = _slot + _half + GAP_M;
            };
        };
        if (_end > _cursor) then {_cursor = _end};
        if (_slot > -1e8 && {(_slot + GAP_M) > _cursor}) then {_cursor = _slot + GAP_M};
    };
} forEach _loaded;

private _y = _cursor + (_cargoLen / 2);
if ((_y + (_cargoLen / 2)) > _foreY) exitWith {[]};

_cargo setVariable ["TLB_CARP_loadSlotY", _y, false];
_cargo setVariable ["TLB_CARP_loadSlotEndY", _y + (_cargoLen / 2) + GAP_M, false];

// The model origin is not the bottom of the model, so the load is lifted by however far
// its own origin sits above its lowest point. Without this a tall vehicle is buried to
// its axles in the floor.
[0, _y, _floorZ - (_gMin # 2), "bbox"]

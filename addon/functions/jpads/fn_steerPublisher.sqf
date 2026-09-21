/*
    TLB_CARP_fnc_steerPublisher

    Is THIS machine the one that should publish steer jobs for this aircraft?

    [_vehicle] call TLB_CARP_fnc_steerPublisher  ->  BOOL

    Every crew member's package tracker sees the same load leave the aircraft within a
    frame or two of the others. If each published, one load would get several jobs
    carrying several different aim points and several different sets of guided-cargo
    settings, and the last broadcast to arrive would win at random.

    So exactly one machine publishes, and every machine works out which one without
    talking to any other -- the answer is computed from `crew _vehicle`, which everyone
    can see identically.

    WHY NOT SIMPLY `local _vehicle`

    Because there are ordinary missions where no machine satisfies both "owns the
    aircraft" and "has a screen". An AI-flown C-17 with human loadmasters aboard is the
    obvious one: the aircraft belongs to the server, the server runs no guidance loop and
    has no DZ, and every human aboard fails the locality test. Guided cargo would be
    switched on, the drop would happen, the canopy would open, and nothing would ever be
    published. A player riding in a server-owned aircraft's hold is the same case.

    The publisher has to be a HUMAN, because what it is publishing is a human's drop zone
    and a human's settings. So: the pilot if a player is flying, and otherwise the crew
    member with the lowest player UID, which is an arbitrary but stable and universally
    agreed choice.
*/

params ["_vehicle"];
if (!hasInterface) exitWith {false};
if (isNull _vehicle) exitWith {false};

// A player at the controls owns the drop, which is the same authority rule
// fn_triggerAutoDrop and fn_armAutopilot already use.
private _driver = driver _vehicle;
if (isPlayer _driver) exitWith {_driver isEqualTo player};

// Nobody human is flying. Fall back to a deterministic pick over the human crew. UIDs
// are stable strings visible on every machine, so every client sorts the same list and
// reaches the same answer with no coordination and no election.
private _humans = (crew _vehicle) select {isPlayer _x};
if ((count _humans) isEqualTo 0) exitWith {false};
private _uids = _humans apply {getPlayerUID _x};
_uids sort true;
(getPlayerUID player) isEqualTo (_uids # 0)

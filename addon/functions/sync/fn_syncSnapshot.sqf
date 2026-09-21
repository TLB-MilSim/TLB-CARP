/*
    TLB_CARP_fnc_syncSnapshot

    The crew-shared CARP intent, as one ordered array.

    WHAT IS IN HERE AND WHAT IS NOT

    Only INTENT is shared -- the values a human chose. Everything derived from intent
    is recomputed by each client's own guidance loop and must never be sent: the
    solution, the path, the HUD, the markers, the 3D cue and the package tracker all
    read that client's own view of the aircraft, and a co-pilot solving locally gets
    the right answer for free. Sharing derived state would replace a correct local
    computation with a stale remote one and put a solver on the network at 20 Hz.

    An ARRAY, not a HashMap, and ordered rather than keyed, because this crosses the
    network as an object variable and a plain array has no serialisation questions.

    The two armed flags are the WANT flags, not the live ones. A client can fail to arm
    guidance -- its own solver may be momentarily invalid -- and if this reported the
    live flag, that client's next publish would send "guidance off" and disarm the
    whole crew. Want is what the crew asked for; TLB_CARP_state_guidanceArmed is what
    this machine managed to do about it, and fn_syncTick keeps trying to close the gap.
*/

[
    +TLB_CARP_state_dzPosASL,
    TLB_CARP_state_dzName,
    TLB_CARP_state_mode,
    TLB_CARP_state_profileOverride,
    TLB_CARP_state_manualWind,
    TLB_CARP_state_manualWindMs,
    TLB_CARP_state_manualWindFromDeg,
    TLB_CARP_state_targetAglM,
    TLB_CARP_state_targetGroundSpeedKmh,
    TLB_CARP_state_cargoCount,
    TLB_CARP_state_runInLocked,
    TLB_CARP_state_runInDeg,
    missionNamespace getVariable ["TLB_CARP_state_syncWantGuidance", false],
    missionNamespace getVariable ["TLB_CARP_state_syncWantAuto", false],
    missionNamespace getVariable ["TLB_CARP_state_smokeEnabled", true],
    missionNamespace getVariable ["TLB_CARP_state_jumpPlannedStick", 0],
    missionNamespace getVariable ["TLB_CARP_state_jumpOpenAglM", 0],
    missionNamespace getVariable ["TLB_CARP_state_jpadsEnabled", false]
]

TLB_CARP_diagLog = [];
TLB_CARP_diagLastPos = [];
TLB_CARP_diagLastApTick = -1;
TLB_CARP_diagLastGuidTick = -1;
TLB_CARP_diagFrames = 0;
TLB_CARP_diagApTicks = 0;
TLB_CARP_diagGuidTicks = 0;
TLB_CARP_diagMoved = 0;
TLB_CARP_diagWindowStart = diag_tickTime;

TLB_CARP_diagAircraft = {
    private _v = objectParent player;
    if (!isNull _v) exitWith {_v};

    private _near = (player nearEntities [["Air"], 5000]) select {alive _x};
    if ((count _near) > 0) then {_near # 0} else {objNull}
};

if (!isNil "TLB_CARP_diagEh") then {removeMissionEventHandler ["EachFrame", TLB_CARP_diagEh]};
TLB_CARP_diagEh = addMissionEventHandler ["EachFrame", {
    private _veh = [] call TLB_CARP_diagAircraft;
    if (isNull _veh) exitWith {};

    private _pos = getPosASL _veh;
    if ((count TLB_CARP_diagLastPos) >= 3) then {
        TLB_CARP_diagMoved = TLB_CARP_diagMoved + (_pos distance2D TLB_CARP_diagLastPos);
    };
    TLB_CARP_diagLastPos = _pos;
    TLB_CARP_diagFrames = TLB_CARP_diagFrames + 1;

    private _apTick = missionNamespace getVariable ["TLB_CARP_state_apLastTick", -1];
    if !(_apTick isEqualTo TLB_CARP_diagLastApTick) then {
        TLB_CARP_diagLastApTick = _apTick;
        TLB_CARP_diagApTicks = TLB_CARP_diagApTicks + 1;
    };
    private _gTick = missionNamespace getVariable ["TLB_CARP_state_guidanceLastTick", -1];
    if !(_gTick isEqualTo TLB_CARP_diagLastGuidTick) then {
        TLB_CARP_diagLastGuidTick = _gTick;
        TLB_CARP_diagGuidTicks = TLB_CARP_diagGuidTicks + 1;
    };

    private _elapsed = diag_tickTime - TLB_CARP_diagWindowStart;
    if (_elapsed >= 1) then {
        private _vel = velocity _veh;
        private _vm = sqrt (((_vel # 0) ^ 2) + ((_vel # 1) ^ 2));
        private _path = missionNamespace getVariable ["TLB_CARP_state_pathSolution", createHashMap];
        private _line = format [
            "CARP AP DIAG t=%1 MOVED=%2 VEL=%3 vz=%4 | frames/s=%5 apTicks/s=%6 guid/s=%7 fps=%8 | local=%9 isDriver=%10 armed=%11 ap=%12 path=%13 | agl=%14 dir=%15",
            round time,
            (TLB_CARP_diagMoved / _elapsed) toFixed 1,
            _vm toFixed 1,
            (_vel # 2) toFixed 1,
            (TLB_CARP_diagFrames / _elapsed) toFixed 1,
            (TLB_CARP_diagApTicks / _elapsed) toFixed 1,
            (TLB_CARP_diagGuidTicks / _elapsed) toFixed 1,
            round diag_fps,
            local _veh,
            (driver _veh) isEqualTo player,
            missionNamespace getVariable ["TLB_CARP_state_apArmed", false],
            missionNamespace getVariable ["TLB_CARP_state_apState", "?"],
            _path getOrDefault ["pathState", "?"],
            round ((getPosATL _veh) # 2),
            round (getDir _veh)
        ];
        systemChat _line;
        diag_log _line;
        TLB_CARP_diagLog pushBack _line;

        TLB_CARP_diagFrames = 0;
        TLB_CARP_diagApTicks = 0;
        TLB_CARP_diagGuidTicks = 0;
        TLB_CARP_diagMoved = 0;
        TLB_CARP_diagWindowStart = diag_tickTime;
    };
}];

TLB_CARP_diagStop = {
    if (!isNil "TLB_CARP_diagEh") then {
        removeMissionEventHandler ["EachFrame", TLB_CARP_diagEh];
        TLB_CARP_diagEh = nil;
    };
    copyToClipboard (TLB_CARP_diagLog joinString endl);
    systemChat format ["CARP AP DIAG stopped -- %1 lines copied to clipboard", count TLB_CARP_diagLog];
    count TLB_CARP_diagLog
};

systemChat "CARP AP DIAG running. Engage the AP. Stop with:  [] call TLB_CARP_diagStop;";
true

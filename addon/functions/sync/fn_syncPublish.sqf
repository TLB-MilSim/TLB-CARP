/*
    USAFDC_fnc_syncPublish

    Send this client's CARP edits to the aircraft's crew record.

    WHERE THIS IS CALLED FROM, AND WHY THOSE TWO PLACES ONLY

    config.bin is pre-binarized, so the panel's control handlers cannot be edited.
    Several of them assign the intent globals directly --

        USAFDC_state_mode=_v
        USAFDC_state_cargoCount=parseNumber ((_this#0) lbData (_this#1))
        USAFDC_state_targetAglM=(parseNumber ctrlText ...) max 300

    -- so there is no function to hook for those. What every one of them DOES do is end
    with a call to USAFDC_fnc_refreshPanel, which calls this before it paints anything.
    The other entry point is fn_setDZ, because the map-click path (fn_beginMapDZ) sets a
    DZ without ever touching the panel.

    Deliberately NOT called from a polling timer. A poll cannot tell "this crew member
    changed something" from "this crew member failed to apply what someone else
    changed", and publishing the second one clobbers the author's intent.

    THE SERVER MERGES, FIELD BY FIELD (v0.9.0)

    v0.7.0 had every client write the whole fourteen-field record straight onto the
    aircraft, under a sequence number it chose for itself. A client that had missed one
    update therefore overwrote every field with its stale copy -- change the AGL, and the
    DZ the pilot had set a moment before vanished for the whole crew -- and when two crew
    edited in the same instant, whichever write reached the server last erased the other.

    Now a client sends only the fields a human changed here since it last synced
    (USAFDC_state_syncBase), as [index, value] pairs, and the server folds them into the
    record one patch at a time in fn_syncMerge. The server is the only writer, so
    revisions only ever go up and two edits to different fields both survive. This
    client keeps its edit on screen until the merged record comes back.

    A server that is not running CARP has nobody to merge, so the client then merges
    against its own view of the record. That still works, but it brings back the
    lost-update race, and the player is told so once.

    THE ARMED FLAGS ARE DETECTED BY TRANSITION, NOT READ DIRECTLY.

    The guidance and auto-drop buttons run through functions that are also called
    internally -- fn_updateGuidance disarms guidance when the player leaves the aircraft,
    fn_setDZ disarms auto drop. A live read of the armed flag cannot be trusted as
    intent; a change in it observed at the moment a human used the panel can.
*/

if (!hasInterface) exitWith {false};
// An apply is in progress: everything about to change is somebody else's intent
// arriving, and echoing it back would fight the author.
if (missionNamespace getVariable ["USAFDC_state_syncApplying", false]) exitWith {false};

private _aircraft = objectParent player;
// Nothing to publish to, and no airframe to scope it to. This also stops a player who
// has just left the aircraft from publishing the disarm that leaving caused.
if (isNull _aircraft) exitWith {false};
if !([player, _aircraft] call USAFDC_fnc_canUseCarp) exitWith {false};

if !(USAFDC_state_guidanceArmed isEqualTo (missionNamespace getVariable ["USAFDC_state_syncSeenGuidance", false])) then {
    USAFDC_state_syncWantGuidance = USAFDC_state_guidanceArmed;
    USAFDC_state_syncSeenGuidance = USAFDC_state_guidanceArmed;
};
if !(USAFDC_state_autoArmed isEqualTo (missionNamespace getVariable ["USAFDC_state_syncSeenAuto", false])) then {
    USAFDC_state_syncWantAuto = USAFDC_state_autoArmed;
    USAFDC_state_syncSeenAuto = USAFDC_state_autoArmed;
};

private _local = [] call USAFDC_fnc_syncSnapshot;
private _base = missionNamespace getVariable ["USAFDC_state_syncBase", []];
private _haveBase = (count _base) isEqualTo (count _local);

// Changed on this client since it last synced -- or everything, when nothing has been
// adopted or seeded on this airframe yet.
private _changes = [];
{
    if (!_haveBase || {!(_x isEqualTo (_base # _forEachIndex))}) then {
        _changes pushBack [_forEachIndex, _x];
    };
} forEach _local;
if ((count _changes) isEqualTo 0) exitWith {false};

// Sent, so no longer this client's to send again. The merged record replaces it when it
// comes back through fn_syncApply.
USAFDC_state_syncBase = +_local;

private _uid = getPlayerUID player;
if (_uid isEqualTo "") then {_uid = str clientOwner};
// The whole payload rides along only so the server can start a record on an airframe
// that has none; an existing record is never rebuilt from it.
private _patch = [_aircraft, _changes, _local, _uid, name player, USAFDC_VERSION];

private _serverVersion = missionNamespace getVariable ["USAFDC_serverVersion", ""];
if (_serverVersion isEqualTo "") then {
    if !(missionNamespace getVariable ["USAFDC_state_syncNoServerWarned", false]) then {
        USAFDC_state_syncNoServerWarned = true;
        systemChat "TLB CARP: the server is not running TLB CARP, so crew edits made at the same moment can overwrite each other. Load the mod on the server as well.";
    };
    _patch call USAFDC_fnc_syncMerge;
} else {
    if (!(_serverVersion isEqualTo USAFDC_VERSION) && {!(missionNamespace getVariable ["USAFDC_state_syncServerVersionWarned", false])}) then {
        USAFDC_state_syncServerVersionWarned = true;
        systemChat format ["TLB CARP: the server runs v%1 and you run v%2. Crew sync needs the same version everywhere.", _serverVersion, USAFDC_VERSION];
    };
    ["USAFDC_carpPatch", _patch] call CBA_fnc_serverEvent;
};
true

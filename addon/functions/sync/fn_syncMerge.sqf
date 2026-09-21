/*
    TLB_CARP_fnc_syncMerge

    Fold one crew member's CARP edits into the aircraft's record, and ring the crew.

        [aircraft, changes, senderPayload, authorUid, authorName, authorVersion] call TLB_CARP_fnc_syncMerge

    changes is [[index, value], ...] into the fourteen-field payload of fn_syncSnapshot.
    senderPayload is the sender's whole payload, used only to start a record on an
    airframe that has none.

    RUNS ON THE SERVER. The server takes patches one at a time, which makes it the only
    writer of TLB_CARP_carpRecord: the revision only ever goes up, and each edit lands on
    the record as it stands at that moment rather than on whatever copy the sender
    happened to hold. That is what lets two crew members change two different fields in
    the same second without one erasing the other. A client runs this itself only when
    the server is not running CARP; see fn_syncPublish.
*/

params [
    ["_aircraft", objNull, [objNull]],
    ["_changes", [], [[]]],
    ["_senderPayload", [], [[]]],
    ["_uid", "", [""]],
    ["_author", "", [""]],
    ["_version", "", [""]]
];
if (isNull _aircraft || {(count _changes) isEqualTo 0}) exitWith {false};

private _record = _aircraft getVariable ["TLB_CARP_carpRecord", []];
private _hasRecord = (count _record) >= 5 && {((_record # 4) isEqualType []) && {(count (_record # 4)) isEqualTo (count _senderPayload)}};
private _payload = if (_hasRecord) then {+(_record # 4)} else {+_senderPayload};
{
    _x params [["_index", -1, [0]], "_value"];
    if (_index >= 0 && {_index < (count _payload)}) then {_payload set [_index, _value]};
} forEach _changes;

private _rev = (if (_hasRecord) then {_record # 0} else {0}) + 1;
private _newRecord = [_rev, _uid, _author, _version, _payload];

// The aircraft object is the record: airframe-scoped so two aircraft running CARP
// cannot overwrite each other, delivered to joining players by the engine with no
// handshake, and it survives crew changes because the airframe holds it rather than
// any one player.
_aircraft setVariable ["TLB_CARP_carpRecord", _newRecord, true];
// The record is the truth; this is only the doorbell, so the crew sees the change now
// instead of on their next sync tick.
["TLB_CARP_carpRecordChanged", [_aircraft, _newRecord], crew _aircraft] call CBA_fnc_targetEvent;
true

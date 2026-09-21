private _markers = allMapMarkers select {((toUpper _x) find "DZ_") isEqualTo 0};
_markers apply {
    private _pos = getMarkerPos _x;
    private _asl = [_pos # 0, _pos # 1, getTerrainHeightASL _pos];
    private _text = markerText _x;
    if (_text isEqualTo "") then {_text = _x};
    [_x, _text, _asl]
}

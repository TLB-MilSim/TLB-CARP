params ["_verticalPathM", "_attachVz", "_canopy"];
private _loss = _canopy get "transientVerticalLossM";
private _transientS = _canopy get "transientDurationS";
private _terminalMs = _canopy get "terminalDescentMs";
private _thresholdVz = _canopy get "highEnergyAttachVzThresholdMs";
private _highEnergy = _attachVz <= _thresholdVz;
private _path = 0 max _verticalPathM;
private _timeS = if (_path <= _loss) then {
    _transientS * _path / _loss
} else {
    _transientS + ((_path - _loss) / _terminalMs)
};
createHashMapFromArray [
    ["timeS", 0 max _timeS],
    ["highEnergy", _highEnergy]
]

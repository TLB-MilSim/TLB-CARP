from __future__ import annotations

import math


def _normalize_heading(value: float) -> float:
    return value % 360.0


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _interp_scalar(heading: float, anchors, values):
    h = _normalize_heading(heading)
    for anchor, value in zip(anchors, values):
        if abs(h - anchor) < 1e-9:
            return float(value), [int(anchor), int(anchor)]
    lo_i = 0
    for i, anchor in enumerate(anchors):
        if h >= anchor:
            lo_i = i
    hi_i = (lo_i + 1) % len(anchors)
    lo = float(anchors[lo_i])
    hi = 360.0 if hi_i == 0 else float(anchors[hi_i])
    t = (h - lo) / (hi - lo)
    return _lerp(float(values[lo_i]), float(values[hi_i]), t), [int(lo), int(hi)]


def _interp_vec(heading: float, anchors, values):
    h = _normalize_heading(heading)
    for anchor, value in zip(anchors, values):
        if abs(h - anchor) < 1e-9:
            return [float(value[0]), float(value[1])], [int(anchor), int(anchor)]
    lo_i = 0
    for i, anchor in enumerate(anchors):
        if h >= anchor:
            lo_i = i
    hi_i = (lo_i + 1) % len(anchors)
    lo = float(anchors[lo_i])
    hi = 360.0 if hi_i == 0 else float(anchors[hi_i])
    t = (h - lo) / (hi - lo)
    a, b = values[lo_i], values[hi_i]
    return [_lerp(float(a[0]), float(b[0]), t), _lerp(float(a[1]), float(b[1]), t)], [int(lo), int(hi)]


def _eval_axis(heading, speed, emp, prefix):
    h5 = emp["headingAnchorsDeg"]
    h10 = emp["cardinalHeadingAnchorsDeg"]
    v5, _ = _interp_vec(heading, h5, emp[f"{prefix}5CorrectionWorldM"])
    t5, _ = _interp_scalar(heading, h5, emp[f"{prefix}5TimeDeltaS"])
    v10, _ = _interp_vec(heading, h10, emp[f"{prefix}10CorrectionWorldM"])
    t10, _ = _interp_scalar(heading, h10, emp[f"{prefix}10TimeDeltaS"])
    if speed <= 1e-9:
        return [0.0, 0.0], 0.0, [0, 0], False
    if abs(speed - 5.0) < 1e-9:
        return v5, t5, [5, 5], False
    if speed < 5.0:
        f = speed / 5.0
        return [v5[0] * f, v5[1] * f], t5 * f, [0, 5], False
    if abs(speed - 10.0) < 1e-9:
        return v10, t10, [10, 10], False
    f = (speed - 5.0) / 5.0
    return [_lerp(v5[0], v10[0], f), _lerp(v5[1], v10[1], f)], _lerp(t5, t10, f), [5, 10], speed > 10.0


def _merge_speed_brackets(brackets):
    if not brackets:
        return [0, 0]
    if all(b == brackets[0] for b in brackets):
        return list(brackets[0])
    return [min(b[0] for b in brackets), max(b[1] for b in brackets)]


def solve_empirical_canopy(heading_deg, wind_world, emp, entry_speed_ms=-1.0, freefall_s=-1.0):
    """Mirrors fn_empiricalCanopyC17.sqf, including the v0.16.7 forward-throw speed scale.

    The baseline is a displacement measured at one airspeed (~500 km/h); the throw scales
    as ln(v/vt) because the load decelerates under quadratic drag. Baseline only -- the
    wind correction is drift and scales with canopy duration, not entry speed.
    """
    heading = _normalize_heading(float(heading_deg))
    baseline, heading_bracket = _interp_vec(heading, emp["headingAnchorsDeg"], emp["zeroWorldM"])
    throw_ref = float(emp.get("throwRefSpeedMs", -1))
    throw_term = float(emp.get("throwTerminalMs", -1))
    throw_scale = 1.0
    if throw_ref > 0 and throw_term > 0 and entry_speed_ms > throw_term and throw_ref > throw_term:
        throw_scale = math.log(entry_speed_ms / throw_term) / math.log(throw_ref / throw_term)
        baseline = [baseline[0] * throw_scale, baseline[1] * throw_scale]
    base_time, _ = _interp_scalar(heading, emp["headingAnchorsDeg"], emp["zeroTimeS"])
    # v0.16.9: canopy duration depends on drop altitude via the entry vertical speed, and
    # zeroTimeS was measured at one. TOT and the calibration record only -- not the RP.
    time_ref = float(emp.get("canopyTimeRefFreefallS", -1))
    time_slopes = emp.get("canopyTimeSlopeS", [])
    if time_ref > 0 and len(time_slopes) == len(emp["headingAnchorsDeg"]) and freefall_s > 0:
        slope, _ = _interp_scalar(heading, emp["headingAnchorsDeg"], time_slopes)
        base_time = max(1.0, base_time + slope * (freefall_s - time_ref))
    wx, wy = float(wind_world[0]), float(wind_world[1])
    wind_speed = math.hypot(wx, wy)

    correction = [0.0, 0.0]
    dt = 0.0
    active_directions = []
    speed_brackets = []
    warnings = []

    if abs(wx) > 1e-9:
        prefix = "east" if wx > 0 else "west"
        direction = 90 if wx > 0 else 270
        corr, axis_dt, bracket, above = _eval_axis(heading, abs(wx), emp, prefix)
        correction[0] += corr[0]
        correction[1] += corr[1]
        dt += axis_dt
        active_directions.append(direction)
        speed_brackets.append(bracket)
        if above:
            warnings.append("WIND ABOVE EMPIRICAL RANGE")

    if abs(wy) > 1e-9:
        prefix = "north" if wy > 0 else "south"
        direction = 0 if wy > 0 else 180
        corr, axis_dt, bracket, above = _eval_axis(heading, abs(wy), emp, prefix)
        correction[0] += corr[0]
        correction[1] += corr[1]
        dt += axis_dt
        active_directions.append(direction)
        speed_brackets.append(bracket)
        if above and "WIND ABOVE EMPIRICAL RANGE" not in warnings:
            warnings.append("WIND ABOVE EMPIRICAL RANGE")

    if wind_speed > 10.0 and "WIND ABOVE EMPIRICAL RANGE" not in warnings:
        warnings.append("WIND ABOVE EMPIRICAL RANGE")

    if len(active_directions) > 1:
        warnings.append("DIAGONAL WIND COMPONENT COMBINATION PROVISIONAL")
        dirs = sorted(active_directions)
        direction_bracket = [270, 360] if dirs == [0, 270] else dirs
    elif active_directions:
        direction_bracket = [active_directions[0], active_directions[0]]
    else:
        direction_bracket = [0, 0]

    speed_bracket = _merge_speed_brackets(speed_brackets)
    canopy = [baseline[0] + correction[0], baseline[1] + correction[1]]
    return {
        "valid": True,
        "modelId": emp["modelId"],
        "baselineWorld": baseline,
        "throwScale": throw_scale,
        "windCorrectionWorld": correction,
        "canopyWorld": canopy,
        "predictedCanopyTimeS": max(0.0, base_time + dt),
        "headingBracket": heading_bracket,
        "windDirectionBracket": direction_bracket,
        "windSpeedBracket": speed_bracket,
        "usedOppositeDirectionSymmetry": False,
        "warnings": warnings,
    }

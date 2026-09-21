/* generated from calibration/model.json; do not hand edit */
createHashMapFromArray [
    ["schemaVersion", 3],
    ["physics", createHashMapFromArray [
        ["gravityMs2", 9.81]
    ]],
    ["usaf", createHashMapFromArray [
        ["triggerAglM", 300],
        ["attachLagS", 0.04],
        ["windFreefall", false]
    ]],
    ["aircraft", createHashMapFromArray [
        ["c17", createHashMapFromArray [
            ["displayName", "USAF C-17"],
            ["classNames", ["USAF_C17"]],
            ["releaseDelayS", 0.5607],
            ["dropPos", [0, -27, -5]],
            ["calibrationState", "ready"],
            ["releaseDelaySource", "0.5607 s, set 2026-09-01 from 15 clean bench runs across TWO speeds (8 headings at 500 km/h and 8 at 350 km/h, verified zero wind, timeRatio 1.000 on every run, one LATE_CHUTE_ATTACH run excluded).
The lag is a fixed TIME, not a fixed distance: lagS measured 0.602 s at 500 km/h and 0.601 s at 350 km/h, while lagM scaled 81.48 -> 56.78 m, a ratio of 0.70 against the expected 350/500 = 0.70. That resolves an ambiguity three flown drops at one speed could not, and confirms releaseDelayS is the correct home for it rather than dropPos.
Directly measured lag is 0.601 s (sd 0.023), consistent with USAF fn_dropCargo.sqf's hardcoded `sleep 0.5` plus door wait, remoteExec and 0.05 s poll granularity. The shipped 0.5607 is the least-squares value that minimises openAlong across both speeds: it takes openAlong from +5.02 to +0.55 m at 500 km/h and +2.44 to -0.69 m at 350 km/h. Using the raw 0.601 instead would give -5.18 and -4.70 m. The 0.040 s difference therefore absorbs a small freefall-model bias; both numbers are recorded here so they can be separated if a freefall correction term is ever added.
HISTORY: 0.585 before v0.4.6; 0.5285 from a two-speed debug-series fit; briefly and wrongly 0.211 in v0.4.29, derived from a flown cue-to-release interval that could not be reconciled with the `sleep 0.5` in the mod source, and reverted in v0.4.32."],
            ["canopyRef", "empiricalC17"]
        ]],
        ["c130", createHashMapFromArray [
            ["displayName", "USAF C-130J"],
            ["classNames", ["USAF_C130J_Cargo", "USAF_C130J_cargo", "USAF_C130J_Cargo_VIV", "USAF_C130J"]],
            ["releaseDelayS", 0.5607],
            ["dropPos", [0, -30, -0.2]],
            ["calibrationState", "zero-wind-measured"],
            ["doors", ["ramp_top", "ramp_bottom"]],
            ["canopyRef", "empiricalC130"],
            ["profileSource", "dropPos and doors read from the live USAF config 2026-08-31 (USAF_Cargo_DropPos [0,-30,-0.2], USAF_Cargo_Doors [ramp_top, ramp_bottom]).
releaseDelayS borrowed from the C-17 at 0.5607 s, and that borrowing is JUSTIFIED rather than assumed: the delay is script timing in USAF's fn_dropCargo.sqf -- a hardcoded `sleep 0.5` plus door check and remoteExec -- and that is the same code for every airframe. USAFDC_fnc_stickTimingProbe can confirm it per aircraft.
canopyRef points at empiricalC17, which is a HYPOTHESIS TO TEST, not a claim. The canopy table is empirical per airframe and the C-130 has never been measured. The DEGRADED tier and its warnings were removed on 2026-09-20 -- see the generic profile's note -- so this no longer announces itself on every solve. The canopyRef remains a hypothesis rather than a measurement, and that is recorded HERE, where someone changing the number will read it, rather than on the HUD where a pilot read it on every drop and learned to ignore it.
Note the C-130's dropPos z is -0.2 against the C-17's -5, so release geometry differs materially even if the canopy behaviour turns out to match.
Also note the USAF mod ships USAF_C130J with USAF_Cargo_MaxLength = 0.6 m, which makes its own load action reject everything; forceLoadCargo bypasses the check, so CARP and the bench are unaffected. See docs/C130_CONFIG_PROBE.md.
classNames[0] is USAF_C130J_Cargo, the variant actually flown (confirmed from a flown CAL_V3 record: aircraftClass=USAF_C130J_Cargo). The harnesses spawn classNames[0], and a v0.4.42 bench batch spawned the USAF_C130J base class whose USAF_Cargo_Doors list differs -- 5 entries against the 2 on the flown variant."]
        ]],
        ["generic", createHashMapFromArray [
            ["displayName", "Air transport"],
            ["classNames", []],
            ["releaseDelayS", 0.5607],
            ["calibrationState", "ready"],
            ["canopyRef", "empiricalC17"],
            ["profileSource", "The C-17 model, applied to every airframe that is not the C-17 or the C-130. releaseDelayS 0.5607 and canopyRef empiricalC17 were already the C-17's -- this profile has ALWAYS used the C-17 numbers and only differed in what it called them. It said 'provisional-borrowed', which raised a warning on every solve, forced DEGRADED and gated Auto Drop.
Set to 'ready' on 2026-09-20 by the project owner, on flown evidence: the C-17 model was flown against the C-17, the C-130 and the V-44 Blackfish and held on all three, and guided cargo (JPADS) absorbs whatever residual the tables leave. Nothing about the numbers changed; the warning did.
This is a DELIBERATE, OWNER-APPROVED loosening of what CARP claims to know. If a future airframe misses consistently in one direction, that is a real signal and the answer is to measure it into its own profile -- not to restore a warning that fired on every drop of every aircraft and so told a pilot nothing."]
        ]]
    ]],
    ["cargo", createHashMapFromArray [
        ["default", createHashMapFromArray [
            ["displayName", "Generic vehicle"],
            ["releaseVerticalOffsetM", 0]
        ]]
    ]],
    ["canopy", createHashMapFromArray [
        ["highEnergy", createHashMapFromArray [
            ["parachuteClass", "B_Parachute_02_F"],
            ["forwardThrowM", 234.37],
            ["intrinsicRightM", -51.3],
            ["windTauS", 4.19],
            ["transientDurationS", 6],
            ["transientVerticalLossM", 211],
            ["terminalDescentMs", 4.3],
            ["highEnergyAttachVzThresholdMs", -180]
        ]],
        ["empiricalC17", createHashMapFromArray [
            ["modelId", "EMPIRICAL_C17_V2"],
            ["headingAnchorsDeg", [0, 45, 90, 135, 180, 225, 270, 315]],
            ["zeroWorldM", [[9.477, 223.8235], [128.1455, 168.01], [229.89, 35.3113], [186.6334, -128.5538], [-0.6216, -214.131], [-185.6151, -126.5329], [-229.34, 34.2744], [-126.0995, 166.2315]]],
            ["zeroTimeS", [28.6735, 28.394, 27.669, 38.936, 47.32, 45.265, 34.486, 28.438]],
            ["east5CorrectionWorldM", [[17.7554, -9.8955], [83.7585, -1.033], [126.641, -13.1394], [212.1066, -19.6122], [234.2906, -0.0005], [212.3729, -5.7581], [158.0861, 27.2022], [131.6073, 19.7255]]],
            ["east5TimeDeltaS", [-3.8195, -1.833, 5.477, 5.964, 3.525, -0.338, -0.827, 0.349]],
            ["north5CorrectionWorldM", [[-5.7465, 163.9495], [-1.6595, 139.635], [-2.027, 157.8547], [-3.0104, 203.962], [0.023, 234.547], [2.3221, 200.9216], [2.506, 161.2376], [-6.1155, 94.7215]]],
            ["north5TimeDeltaS", [1.2925, 0.324, 5.906, 6.946, 0.252, -0.318, -0.349, -7.693]],
            ["cardinalHeadingAnchorsDeg", [0, 90, 180, 270]],
            ["east10CorrectionWorldM", [[37.6343, -22.7145], [292.575, -17.5867], [469.0806, 3.674], [283.3048, 47.5342]]],
            ["east10TimeDeltaS", [-8.6775, 5.857, 3.312, -3.555]],
            ["north10CorrectionWorldM", [[-6.0805, 315.7355], [9.919, 254.2257], [0.1431, 496.449], [-10.707, 262.4116]]],
            ["north10TimeDeltaS", [1.7865, -0.343, 2.922, -6.427]],
            ["south5CorrectionWorldM", [[-3.3231, -51.8763], [-23.9741, -42.6628], [-6.316, -137.2786], [-0.1954, -219.4972], [-0.464, -245.859], [-0.9139, -221.2701], [19.05, -143.0834], [34.0608, -53.0398]]],
            ["south5TimeDeltaS", [-4.1585, -4.315999999999999, -0.16199999999999903, 5.689999999999998, 2.4570000000000007, -0.6700000000000017, -0.931999999999995, -4.0219999999999985]],
            ["south10CorrectionWorldM", [[-1.3442, -198.3977], [-6.544, -240.7743], [0.2915, -487.348], [7.776, -247.4544]]],
            ["south10TimeDeltaS", [-6.868500000000001, -0.6069999999999993, 2.064, -6.628999999999998]],
            ["west5CorrectionWorldM", [[-36.0883, -9.5735], [-129.6396, 17.789], [-156.8744, 26.1301], [-182.7643, 2.0398], [-198.9154, 2.598], [-183.1939, -8.3461], [-128.461, -13.7939], [-85.8435, -1.0885]]],
            ["west5TimeDeltaS", [-4.063500000000001, -0.2809999999999988, 5.709, -0.1670000000000016, -3.2820000000000036, -6.4979999999999976, -0.8499999999999943, -1.2609999999999992]],
            ["west10CorrectionWorldM", [[-56.5493, -24.1205], [-253.5834, 7.5832], [-465.3004, 3.746], [-297.254, -17.9306]]],
            ["west10TimeDeltaS", [-8.7975, -1.1769999999999996, 2.872, -0.5039999999999978]],
            ["zeroWorldMSource", "re-fitted 2026-08-31 from 40 bench runs (8 headings x n=5) at verified zero wind (setWind converged to 0.000 m/s, gusts 0), 8-concurrent batches with chuteAgl 296.5-299.9 m; heading-to-cell assignment rotated across batches. Reduced mean radial miss 5.94 -> 2.24 m, median 6.16 -> 1.62 m. Wind-correction deltas NOT re-fitted and still require validation against this baseline."],
            ["windCorrectionSource", "wind deltas counter-shifted by -(zeroWorldM correction) on 2026-08-31. They were originally fitted as (observed drift with wind) - (OLD zero-wind baseline), verified to 3dp against c17_controlled_observations_v1.json on all 8 headings, so they had absorbed the baseline error. Re-fitting zeroWorldM without this counter-shift double-corrected every wind case: a 5 m/s south batch measured mean radial 12.93 m against 9.52 m for the pre-change table, worst at headings 45 and 315 whose baseline corrections were largest (~10.6 and ~10.8 m). After the counter-shift the exact 5/10 m/s anchor predictions are identical to v0.4.25 and intermediate wind speeds are now correct too, because baseline and delta are finally the true physical decomposition."],
            ["south5Source", "5 m/s south deltas re-fitted 2026-08-31 from 40 bench runs (8 headings x n=5), verified wind (engine reported [0,-5,0], error 0.000 m/s), 8-concurrent batches, 0/40 late chute attach, heading-to-cell rotated. Only components resolved above noise (|mean|/sem >= 3) were corrected; unresolved components were left alone rather than fitted to scatter. Largest: hdg 45 along +20.23+-3.61, hdg 90 right +15.44+-4.40. Expected mean radial 9.23 -> 5.61 m, median 5.57 -> 3.79 m, 39/40 inside a 25 m box. Other wind directions and all 10 m/s entries are UNCHANGED and still rest on the original n=1 controlled set."],
            ["throwRefSpeedMs", 138.89],
            ["throwTerminalMs", 21.9],
            ["throwScaleSource", "throwRefSpeedMs / throwTerminalMs added 2026-09-21. zeroWorldM is a displacement measured at ONE airspeed -- every one of the original 140 runs flew at ~500 km/h -- and was applied at every airspeed. Measured: 8 headings x 4 speeds at 3000 m AGL, verified zero wind (engine reported 0.000 m/s on all four batches), 32 runs, 0 degraded. Along-track bias vs the model: 350 km/h -40.03 (sem 4.90), 425 km/h -18.04 (sem 3.70), 500 km/h +4.08 (sem 1.91), 600 km/h +24.08 (sem 1.32). Cross-track bias stayed within 2.2 m at every speed, so this is a forward-throw term and not a heading or wind effect. A fifth batch at 1500 m / 500 km/h gave +2.61 against +4.08 at 3000 m, so DROP ALTITUDE IS NOT AN AXIS -- the freefall solver already handles it. FORM IS DERIVED, NOT FITTED: quadratic drag gives distance proportional to ln(v0/vt), which beat a power law and a straight line on the same points (RMS 0.96 m vs 2.13 and 2.33, chi 0.45). Only the two constants are fitted. Applied multiplicatively to the baseline ONLY -- the wind correction is drift and scales with canopy duration, not entry speed. Validated per-run over all 40 bench runs: median radial 19.20 -> 7.02 m, mean 20.58 -> 9.32 m, and the calibrated 500 km/h point is unchanged (5.58 -> 5.59 at 3000 m, 6.78 -> 6.78 at 1500 m). UNMEASURED OUTSIDE 350-600 km/h; the log form extrapolates gently but nothing has been flown there."],
            ["canopyTimeRefFreefallS", 23.24],
            ["canopyTimeSlopeS", [-0.96, -0.982, -0.741, -0.725, -0.726, -0.714, -0.786, -0.978]],
            ["canopyTimeSlopeSource", "canopyTimeSlopeS / canopyTimeRefFreefallS added 2026-09-21. zeroTimeS is a canopy duration measured at ONE drop altitude -- every original run had a freefall of 23.26 +/- 0.41 s, about 3000 m -- and was applied at every altitude. MECHANISM: from 3000 m the load reaches the chute at about -230 m/s and plunges deep during inflation, spending most of the 300 m fast; from 1500 m it arrives at -153 m/s, does not plunge as far, and has far more altitude left to spend at the canopy's ~4.3 m/s terminal. Flown transients show it directly: 300 m to 182 m in three seconds, then 182 m at 4.3 m/s. MEASURED: 8 headings x 4 drop altitudes (freefall 11.91 / 15.59 / 19.54 / 23.24 s), verified zero wind on all four batches, 32 runs, 0 degraded. Slope is s of canopy per s of freefall, anchored at the 23.24 s freefall the existing zeroTimeS was measured at. Per-heading because every other axis in this table is per-heading, and because a single global slope (-0.851, RMS 0.56 s over headings 0/45/90/135) made 180/225/270 WORSE. Validated over all 32: mean |duration error| 4.43 -> 2.08 s. The 315 slope EXCLUDES the 1900 m run, whose 23.34 s reading sits more than 3 sd from every neighbour; fitting it gave -1.203 against -0.96 and -0.74 either side, which is fitting scatter. Refitted on the other three: -0.978. SCOPE: predictedCanopyTimeS feeds the TOT countdown and the calibration record ONLY -- it does not reach the release point, and this changes no drop geometry. WHAT THIS DELIBERATELY DOES NOT DO: scale the wind correction by the corrected duration. That is physically the right idea and it made two of three flown drops WORSE (canopy-phase error 27.2 -> 39.8 m and 19.0 -> 39.0 m), because the model over-corrects wind on some drops and under-corrects on others and duration does not resolve that. STILL UNEXPLAINED: a flown C-130 canopy lasts about 9 s longer than the bench C-17 at the same drop altitude and the same entry vertical speed, and headings 180/225/270 do not track the altitude trend the other five do."]
        ]],
        ["empiricalC130", createHashMapFromArray [
            ["modelId", "EMPIRICAL_C130_V1"],
            ["headingAnchorsDeg", [0, 45, 90, 135, 180, 225, 270, 315]],
            ["zeroWorldM", [[9.477, 223.8235], [125.3748, 175.7894], [225.6867, 35.3113], [185.7318, -128.5538], [-0.6216, -214.131], [-185.6151, -126.5329], [-224.9433, 36.4794], [-126.0995, 175.5146]]],
            ["zeroTimeS", [28.6735, 28.394, 27.669, 38.936, 47.32, 45.265, 34.486, 28.438]],
            ["east5CorrectionWorldM", [[17.7554, -9.8955], [86.5292, -8.8124], [130.8443, -13.1394], [213.0082, -19.6122], [234.2906, -0.0005], [212.3729, -5.7581], [153.6894, 24.9972], [131.6073, 10.4424]]],
            ["east5TimeDeltaS", [-3.8195, -1.833, 5.477, 5.964, 3.525, -0.338, -0.827, 0.349]],
            ["north5CorrectionWorldM", [[-5.7465, 163.9495], [1.1112, 131.8556], [2.1763, 157.8547], [-2.1088, 203.962], [0.023, 234.547], [2.3221, 200.9216], [-1.8907, 159.0326], [-6.1155, 85.4384]]],
            ["north5TimeDeltaS", [1.2925, 0.324, 5.906, 6.946, 0.252, -0.318, -0.349, -7.693]],
            ["cardinalHeadingAnchorsDeg", [0, 90, 180, 270]],
            ["east10CorrectionWorldM", [[37.6343, -22.7145], [296.7783, -17.5867], [469.0806, 3.674], [278.9081, 45.3292]]],
            ["east10TimeDeltaS", [-8.6775, 5.857, 3.312, -3.555]],
            ["north10CorrectionWorldM", [[-6.0805, 315.7355], [14.1223, 254.2257], [0.1431, 496.449], [-15.1037, 260.2066]]],
            ["north10TimeDeltaS", [1.7865, -0.343, 2.922, -6.427]],
            ["south5CorrectionWorldM", [[-3.3231, -51.8763], [-21.2034, -50.4422], [-2.1127, -137.2786], [0.7062, -219.4972], [-0.464, -245.859], [-0.9139, -221.2701], [14.6533, -145.2884], [34.0608, -62.3229]]],
            ["south5TimeDeltaS", [-4.1585, -4.315999999999999, -0.16199999999999903, 5.689999999999998, 2.4570000000000007, -0.6700000000000017, -0.931999999999995, -4.0219999999999985]],
            ["south10CorrectionWorldM", [[-1.3442, -198.3977], [-2.3407, -240.7743], [0.2915, -487.348], [3.3793, -249.6594]]],
            ["south10TimeDeltaS", [-6.868500000000001, -0.6069999999999993, 2.064, -6.628999999999998]],
            ["west5CorrectionWorldM", [[-36.0883, -9.5735], [-126.8689, 10.0096], [-152.6711, 26.1301], [-181.8627, 2.0398], [-198.9154, 2.598], [-183.1939, -8.3461], [-132.8577, -15.9989], [-85.8435, -10.3716]]],
            ["west5TimeDeltaS", [-4.063500000000001, -0.2809999999999988, 5.709, -0.1670000000000016, -3.2820000000000036, -6.4979999999999976, -0.8499999999999943, -1.2609999999999992]],
            ["west10CorrectionWorldM", [[-56.5493, -24.1205], [-249.3801, 7.5832], [-465.3004, 3.746], [-301.6507, -20.1356]]],
            ["west10TimeDeltaS", [-8.7975, -1.1769999999999996, 2.872, -0.5039999999999978]],
            ["zeroWorldMSource", "re-fitted 2026-08-31 from 40 bench runs (8 headings x n=5) at verified zero wind (setWind converged to 0.000 m/s, gusts 0), 8-concurrent batches with chuteAgl 296.5-299.9 m; heading-to-cell assignment rotated across batches. Reduced mean radial miss 5.94 -> 2.24 m, median 6.16 -> 1.62 m. Wind-correction deltas NOT re-fitted and still require validation against this baseline."],
            ["windCorrectionSource", "wind deltas counter-shifted by -(zeroWorldM correction) on 2026-08-31. They were originally fitted as (observed drift with wind) - (OLD zero-wind baseline), verified to 3dp against c17_controlled_observations_v1.json on all 8 headings, so they had absorbed the baseline error. Re-fitting zeroWorldM without this counter-shift double-corrected every wind case: a 5 m/s south batch measured mean radial 12.93 m against 9.52 m for the pre-change table, worst at headings 45 and 315 whose baseline corrections were largest (~10.6 and ~10.8 m). After the counter-shift the exact 5/10 m/s anchor predictions are identical to v0.4.25 and intermediate wind speeds are now correct too, because baseline and delta are finally the true physical decomposition."],
            ["south5Source", "5 m/s south deltas re-fitted 2026-08-31 from 40 bench runs (8 headings x n=5), verified wind (engine reported [0,-5,0], error 0.000 m/s), 8-concurrent batches, 0/40 late chute attach, heading-to-cell rotated. Only components resolved above noise (|mean|/sem >= 3) were corrected; unresolved components were left alone rather than fitted to scatter. Largest: hdg 45 along +20.23+-3.61, hdg 90 right +15.44+-4.40. Expected mean radial 9.23 -> 5.61 m, median 5.57 -> 3.79 m, 39/40 inside a 25 m box. Other wind directions and all 10 m/s entries are UNCHANGED and still rest on the original n=1 controlled set."],
            ["source", "empiricalC130 forked from empiricalC17 on 2026-09-01.
zeroWorldM: shifted by the measured C-130 zero-wind residual from 48 bench runs (8 headings x n=6, verified zero wind, chuteAgl 293.7-299.9 m on every run, 0 degraded, 48/48 inside a 25 m box). Only components resolved above noise (|mean|/sem >= 3) were applied -- 6 of 16 -- taking the zero-wind canopy residual from 5.47 m to 3.21 m. Correcting all 16 would have reached 3.03 m by fitting scatter, which is not worth 0.18 m.
Wind delta tables: counter-shifted by the same amount, so C-130 wind predictions are numerically IDENTICAL to what the borrowed C-17 tables gave. That preserves measured behaviour -- C-130 at 5 m/s diagonal was 26.30 m against the C-17's 26.30 -- while fixing zero wind. Omitting the counter-shift would double-correct every wind case, which is exactly the error made and corrected in v0.4.26/v0.4.27.
STILL BORROWED AND UNMEASURED for the C-130: all wind deltas and all canopy times. Wind performance is scatter-dominated (~20 m RMS at 5 m/s) so the two airframes are statistically indistinguishable there, but that is an absence of evidence for a difference, not evidence of absence.
Known residual: at NON-cardinal headings with 10 m/s wind, C-130 predictions differ from the borrowed C-17 ones by up to 8.47 m (mean 2.49 m). Cause: the 5 m/s deltas and the baseline share the 8-entry headingAnchorsDeg grid so the counter-shift cancels exactly, but the 10 m/s deltas use the 4-entry cardinalHeadingAnchorsDeg grid, so cancellation is exact only at 0/90/180/270. All 5 m/s cases are identical to 0.000 m. Accepted: 8.47 m sits well inside the ~20 m of canopy scatter measured at 5 m/s, and the same caveat already applies to the C-17's own v0.4.27 counter-shift."],
            ["throwRefSpeedMs", 138.89],
            ["throwTerminalMs", 21.9],
            ["throwScaleSource", "throwRefSpeedMs / throwTerminalMs added 2026-09-21. zeroWorldM is a displacement measured at ONE airspeed -- every one of the original 140 runs flew at ~500 km/h -- and was applied at every airspeed. Measured: 8 headings x 4 speeds at 3000 m AGL, verified zero wind (engine reported 0.000 m/s on all four batches), 32 runs, 0 degraded. Along-track bias vs the model: 350 km/h -40.03 (sem 4.90), 425 km/h -18.04 (sem 3.70), 500 km/h +4.08 (sem 1.91), 600 km/h +24.08 (sem 1.32). Cross-track bias stayed within 2.2 m at every speed, so this is a forward-throw term and not a heading or wind effect. A fifth batch at 1500 m / 500 km/h gave +2.61 against +4.08 at 3000 m, so DROP ALTITUDE IS NOT AN AXIS -- the freefall solver already handles it. FORM IS DERIVED, NOT FITTED: quadratic drag gives distance proportional to ln(v0/vt), which beat a power law and a straight line on the same points (RMS 0.96 m vs 2.13 and 2.33, chi 0.45). Only the two constants are fitted. Applied multiplicatively to the baseline ONLY -- the wind correction is drift and scales with canopy duration, not entry speed. Validated per-run over all 40 bench runs: median radial 19.20 -> 7.02 m, mean 20.58 -> 9.32 m, and the calibrated 500 km/h point is unchanged (5.58 -> 5.59 at 3000 m, 6.78 -> 6.78 at 1500 m). UNMEASURED OUTSIDE 350-600 km/h; the log form extrapolates gently but nothing has been flown there.  C-130 shares the C-17 constants: the term is a property of the LOAD and its canopy, not of the aircraft, and the C-130's baseline is already a shifted C-17 baseline. Not separately measured."],
            ["canopyTimeRefFreefallS", 23.24],
            ["canopyTimeSlopeS", [-0.96, -0.982, -0.741, -0.725, -0.726, -0.714, -0.786, -0.978]],
            ["canopyTimeSlopeSource", "canopyTimeSlopeS / canopyTimeRefFreefallS added 2026-09-21. zeroTimeS is a canopy duration measured at ONE drop altitude -- every original run had a freefall of 23.26 +/- 0.41 s, about 3000 m -- and was applied at every altitude. MECHANISM: from 3000 m the load reaches the chute at about -230 m/s and plunges deep during inflation, spending most of the 300 m fast; from 1500 m it arrives at -153 m/s, does not plunge as far, and has far more altitude left to spend at the canopy's ~4.3 m/s terminal. Flown transients show it directly: 300 m to 182 m in three seconds, then 182 m at 4.3 m/s. MEASURED: 8 headings x 4 drop altitudes (freefall 11.91 / 15.59 / 19.54 / 23.24 s), verified zero wind on all four batches, 32 runs, 0 degraded. Slope is s of canopy per s of freefall, anchored at the 23.24 s freefall the existing zeroTimeS was measured at. Per-heading because every other axis in this table is per-heading, and because a single global slope (-0.851, RMS 0.56 s over headings 0/45/90/135) made 180/225/270 WORSE. Validated over all 32: mean |duration error| 4.43 -> 2.08 s. The 315 slope EXCLUDES the 1900 m run, whose 23.34 s reading sits more than 3 sd from every neighbour; fitting it gave -1.203 against -0.96 and -0.74 either side, which is fitting scatter. Refitted on the other three: -0.978. SCOPE: predictedCanopyTimeS feeds the TOT countdown and the calibration record ONLY -- it does not reach the release point, and this changes no drop geometry. WHAT THIS DELIBERATELY DOES NOT DO: scale the wind correction by the corrected duration. That is physically the right idea and it made two of three flown drops WORSE (canopy-phase error 27.2 -> 39.8 m and 19.0 -> 39.0 m), because the model over-corrects wind on some drops and under-corrects on others and duration does not resolve that. STILL UNEXPLAINED: a flown C-130 canopy lasts about 9 s longer than the bench C-17 at the same drop altitude and the same entry vertical speed, and headings 180/225/270 do not track the altitude trend the other five do.  C-130 shares the C-17 slopes: canopy descent is a property of the load and its canopy, not of the aircraft. Not separately measured."]
        ]]
    ]],
    ["confidence", createHashMapFromArray [
        ["normalSpeedKmhMin", 480],
        ["normalSpeedKmhMax", 525],
        ["testedWindMsMax", 10],
        ["operationalBoxM", 50]
    ]],
    ["multiCargo", createHashMapFromArray [
        ["sequenceIntervalS", 0.588],
        ["calibrationState", "interval-measured"],
        ["stickWarningLengthM", 50],
        ["sequenceIntervalSource", "0.5880 s (sd 0.0159, n=39 gaps over 10 reps), measured 2026-09-01 by USAFDC_fnc_stickTimingProbe at 3000 m / 500 km/h. Release instants are stamped in a per-frame handler, not a 0.05 s poll.
HISTORY: 0.53 s originally (provisional, never measured). Briefly 0.7603 s in v0.4.40 from a 12-gap sample -- that sample was the probe's FIRST invocation and was warm-up contaminated: its three reps trended 0.788 -> 0.765 -> 0.728 and its sd was 0.0646 against 0.0159 for the settled 39-gap sample. Corrected in v0.4.41.
Mechanism: fn_sequenceCargo is serial, so each gap is one full canDrop cycle -- USAF's hardcoded `sleep 0.5` plus the door check, remoteExec and the detection of the previous load leaving usaf_cargo. 0.588 s sits just above the 0.5607 s single-drop releaseDelayS, which is the expected relationship.
First-release lag on the sequenceCargo path measured 0.6115 s (sd 0.0121, n=10), only +7.1 m of whole-stick displacement against releaseDelayS at 500 km/h. Too small to justify a separate firstReleaseDelayS field.
STILL UNVERIFIED: stick CENTRING has not been checked against actual landing positions. Also 1 load of 50 failed to release within the probe's deadline (rep 3 reported 4 releases of 5), which is a sequencer reliability question, not a timing one."]
    ]]
]

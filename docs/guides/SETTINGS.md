# Settings

Everything lives under **Options → Addon Options → TLB CARP**, in the categories below.

**Who a setting belongs to.** *Client* settings are yours alone — change them freely, they
affect nothing but your screen or your own aircraft. *Server* settings are forced by the
mission or the server and are the same for everyone.

Two things that look like settings are **not** here: **JPADS** and **SMOKE** are buttons on
the CARP panel, because they change from drop to drop and the whole crew shares them.

## Access

| Setting | Default | Who | What it does |
| --- | --- | --- | --- |
| Require CARP Computer | On | Server | Only players carrying a `TLB_CARP_Computer` get **TLB CARP** in an aircraft's interaction menu and share the crew's CARP. Turn it off for missions that do not hand the item out. |

## Display

| Setting | Default | Range | Who | What it does |
| --- | --- | --- | --- | --- |
| HUD Enabled | On | — | Client | The drop guidance HUD, shown once guidance is armed. |
| HUD Scale | 1.0 | 0.7 – 1.5 | Client | Size multiplier for the HUD. |
| 3D RP Cue | On | — | Client | The release point drawn out in the world. |
| Map Trajectory | On | — | Client | Release point, canopy, touchdown and run-in markers on your map. Local to you; CARP never creates a global marker. |

## Audio

| Setting | Default | Who | What it does |
| --- | --- | --- | --- |
| Guidance Sounds | On | Client | Standby and drop cues. |

## Autopilot

| Setting | Default | Range | Who | What it does |
| --- | --- | --- | --- | --- |
| AP Flies With Forces | On | — | Client | Flies with control forces, so the aircraft banks and pitches like an aeroplane. Off restores the pre-v0.16.8 behaviour of writing velocity and heading directly. |
| AP Turn Lead | 4 s | 0 – 10 | Client | How far ahead it predicts its own turn before rolling out. Higher rolls out earlier; too high and it never completes a turn. |
| AP Roll Damping | 150 | 0 – 600 | Client | Opposes roll rate, so it stops at the commanded bank instead of swinging past it. |
| AP Turn Coordination | 40 | 0 – 150 | Client | Rudder applied with bank to hold the ball centred through roll in and roll out. |
| AP Acceleration Limit | 1.5 m/s² | 0.3 – 6.0 | Client | How fast it may change ground speed. Lower is smoother and slower to settle. |
| AP Vertical Rate Limit | 2.5 m/s² | 0.5 – 8.0 | Client | How fast it may change vertical speed. Lower is a gentler pull out of a climb or dive. |
| Release Drift Limit | 25 m | 5 – 60 | Client | How much predicted sideways displacement the release gate accepts. Raise it and a pass gets through with more lateral motion — which the load then inherits. |
| AP Manual Override Threshold | 0.25 | 0.10 – 0.60 | Client | How far you have to move a control before the autopilot hands back. |

## Guided Cargo

Guided cargo is switched on with the **JPADS** button on the panel. These shape how it flies.

| Setting | Default | Range | Who | What it does |
| --- | --- | --- | --- | --- |
| Canopy Glide Speed | 12 m/s | 2 – 25 | Client | Horizontal airspeed a steerable canopy can fly. It cannot beat a headwind stronger than this. |
| Aim Scatter | 2 m | 0 – 15 | Client | Random aim offset, so a load does not sit exactly on the aim point. |
| Stop Steering At | 25 m | 0 – 100 | Server | Height at which a guided load stops correcting and rides the wind down. A canopy still chasing its aim point at touchdown arrives sideways. |
| Stick Spacing | 35 m | 0 – 150 | Server | Metres between guided loads of one stick, spread along the run-in so they do not land on top of each other. 0 aims every load at the drop zone. |
| Steering Release AGL | 3 m | 0 – 60 | Client | Height at which steering stops entirely. |
| Steering Engage Descent Rate | 12 m/s | 5 – 30 | Client | Steering waits until the canopy has slowed to this descent rate, so it never steers during inflation. |

## Jump Run

Stick size and opening height are also on the panel, because they change every serial.

| Setting | Default | Range | Who | What it does |
| --- | --- | --- | --- | --- |
| Jump Opening Altitude | 600 m | 150 – 1200 | Server | Height above the DZ at which jumpers plan to open. The exit point is computed from it. |
| Jumpers In Stick | 0 | 0 – 30 | Server | How many will exit. 0 counts everyone aboard except the pilot when the run is armed. |
| Jumper Interval | 1 s | 0.5 – 5 | Server | Time between one jumper leaving the ramp and the next. |
| Jump Countdown | 10 s | 5 – 20 | Server | Length of the audible countdown before the green light. |
| Green Light Duration | 8 s | 2 – 30 | Server | How long the green light stays on once the aircraft reaches the exit point. |
| Early Exit Bias | 250 m | 0 – 800 | Server | Moves the exit point earlier, so timing errors fall on the recoverable side: flying downwind to the DZ is far faster than flying upwind to it. |
| Jump Exit Bias | 0 m | −600 – 600 | Server | Shifts the exit along the run-in. Positive calls the jump earlier. Leave at 0 unless jumpers consistently land long or short. |

## Auto Drop

| Setting | Default | Who | What it does |
| --- | --- | --- | --- |
| Use USAF Release Sequence | Off | Server | Hands drops on a USAF aircraft back to the USAF mod's own drop action. Off by default: CARP runs the whole release itself and does not need the USAF mod. Turn it on only to compare the two. |

## Advanced

| Setting | Default | Range | Who | What it does |
| --- | --- | --- | --- | --- |
| Update Interval | 0.05 s | 0.02 – 0.20 | Client | Seconds between guidance updates. |
| Diagnostics Enabled | Off | — | Client | Debug and calibration controls on the panel, plus the detailed telemetry block. |
| Calibration Recording | Off | — | Client | Tracks the next released load to touchdown and keeps a pasteable record of where it landed. |

## Forcing settings on a server

Put the server-forced ones in the server's `cba_settings.sqf`:

```sqf
force USAFDC_setting_requireComputer = true;
force USAFDC_setting_jumpOpenAglM = 800;
force USAFDC_setting_jpadsStickSpacingM = 50;
```

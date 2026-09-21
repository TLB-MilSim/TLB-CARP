<p align="center">
  <img src="docs/images/logo.png" alt="TLB CARP" width="240">
</p>

<h1 align="center">TLB CARP</h1>

<p align="center">
  Computed Air Release Point for Arma 3.<br>
  <strong>Work out where to let go, so the load lands on the X.</strong>
</p>

<p align="center">
  <a href="https://github.com/TLB-MilSim/TLB-CARP/wiki">Wiki</a> ·
  <a href="https://github.com/TLB-MilSim/TLB-CARP/wiki/Quick-Start">Quick start</a> ·
  <a href="https://github.com/TLB-MilSim/TLB-CARP/wiki/Pilot-Guide">Pilot guide</a> ·
  <a href="https://github.com/TLB-MilSim/TLB-CARP/wiki/Jump-Run">Jump run</a> ·
  <a href="https://github.com/TLB-MilSim/TLB-CARP/wiki/Mission-Making">Mission making</a> ·
  <a href="https://github.com/TLB-MilSim/TLB-CARP/wiki/Settings">Settings</a> ·
  <a href="https://github.com/TLB-MilSim/TLB-CARP/releases">Releases</a>
</p>

<p align="center">
  <img src="docs/images/screenshots/hud-run-in.png" alt="The CARP HUD on a run-in: range to the release point, cross-track, track error, altitude and speed against target, drift, and time on target" width="820">
</p>

---

## What it is

CARP tells you where to release so the load lands on the drop zone.

It doesn't use a lookup table and it doesn't assume you hit your planned numbers. It reads
the aircraft you're actually flying (height, speed, rate of climb, wind) and re-solves
several times a second. Fly it fast and the release point slides back. Fly it low and it
slides forward. You can be well off plan and still put the load on the X.

What you get:

- A release point that updates live, so being high or fast moves the mark instead of
  blocking the drop.
- An autopilot that intercepts the run-in and flies it, using control forces, so the
  aircraft banks and pitches properly.
- Auto drop, which releases at the right instant and refuses a bad pass rather than
  wasting the load.
- Cargo handling: load it, stack it, drop it. Works with its own loading, USAF, ACE and
  vehicle-in-vehicle.
- Guided cargo, where the canopy steers itself onto the DZ after it opens.
- A HALO jump run with a computed exit point, countdown and jumplight.
- Time on target, tracked from release through canopy to impact.
- One shared drop computer per aircraft, for the whole crew.

## Showcase

[![TLB CARP showcase](https://img.youtube.com/vi/3v0Nm9U3178/hqdefault.jpg)](https://youtu.be/3v0Nm9U3178)

A walkthrough of the system in flight: [youtu.be/3v0Nm9U3178](https://youtu.be/3v0Nm9U3178)

## Screenshots

| The panel | The jump readout |
| --- | --- |
| <img src="docs/images/screenshots/panel.png" alt="The CARP panel: drop zone, mission, environment, jump run and cargo sections" width="420"> | <img src="docs/images/screenshots/jump-standby.png" alt="Jump readout on standby" width="420"><br><img src="docs/images/screenshots/jump-go.png" alt="Green light" width="420"> |

| Capturing the final line | Release stable |
| --- | --- |
| <img src="docs/images/screenshots/hud-capture-final.png" alt="HUD capturing the final line" width="420"> | <img src="docs/images/screenshots/hud-release-stable.png" alt="HUD showing release stable" width="420"> |

## Requirements

| | |
| --- | --- |
| Arma 3 | v2.14 or newer |
| [CBA_A3](https://steamcommunity.com/workshop/filedetails/?id=450814997) | required |
| [ACE3](https://steamcommunity.com/workshop/filedetails/?id=463939057) | required. CARP opens from the ACE interaction menu |
| [USAF Mod](https://steamcommunity.com/workshop/filedetails/?id=2397360831) | optional. Its C-17 and C-130J are the calibrated airframes, but CARP does its own loading and releasing |
| [Free Fall Off The Ramp](https://steamcommunity.com/workshop/filedetails/?id=2654268308) | optional. Drives the jumplight on a jump run |

## Installation

1. Load `@TLB_CARP_System` alongside CBA_A3 and ACE3.
2. On a server, load it on the server too, not just the clients. Cargo usually belongs to
   the server, and that's the machine that performs the release.
3. Give aircrew a **CARP Computer**. It's in the Arsenal, or place it from Zeus under
   Equipment. Mission makers who'd rather not bother can switch the requirement off in
   Addon Options.

Server admins: every release is signed, and ships its public key in the mod's `keys/`
folder. Copy that `.bikey` into the server's own `Keys/` folder and `verifySignatures = 2`
works normally.

## Quick start

1. Get in the aircraft with a CARP Computer and press **Interact** → **TLB CARP**. There's
   also an *Open TLB CARP* keybind under Options → Controls → Configure Addons.
2. Press **SET ON MAP** and click your drop zone, or pick a `DZ_*` marker from the list.
3. Type your **TARGET AGL** and **TARGET GS**, then **APPLY**.
4. Roll out on the heading you want to drop on, let the aircraft settle, then hit
   **RUN-IN**. It locks the track you're actually flying at that moment, so don't lock in
   a turn.
5. **ARM GUIDANCE** lights up the HUD. Fly it like an ILS.
6. **AUTO DROP** releases for you, or leave it off and drop on the cue. **AP** will fly
   the whole run-in if you want it to.

The [pilot guide](https://github.com/TLB-MilSim/TLB-CARP/wiki/Pilot-Guide) covers all of
it, and [The HUD](https://github.com/TLB-MilSim/TLB-CARP/wiki/The-HUD) explains every row
on the instrument.

## Crew

Everyone in the aircraft carrying a CARP Computer shares one CARP. Any of them can set the
DZ, lock the run-in, change the mode or arm guidance, and the rest see it within a second.
Edits are merged per field on the server, so two people changing different things at the
same moment both keep their change. The **CREW** line on the panel shows which record you
hold and who touched it last.

The autopilot and the release command stay with whoever is flying.

## Accuracy

Radial error at touchdown, measured on flown drops.

| | |
| --- | --- |
| Unguided C-130J, live wind, 1485 m at ~383 km/h | **19.3 m** |
| Unguided C-17, same conditions | **21.1 m** |
| Guided cargo (JPADS), zero wind | **0.76 m** |
| Guided cargo, 10 m/s wind | **1.15 m** |
| Jump run exit cue | **7 m** and **12 m** on two flown runs |

The C-17 is fully calibrated. The C-130J has its own measured zero-wind baseline and
borrows the C-17's wind corrections. Other aircraft fly on the C-17's numbers and solve
normally, with no warning and no gate on auto drop, but the figures above were measured on
the calibrated airframes and don't automatically carry across.

More detail, including what each figure is worth, is on the
[Accuracy](https://github.com/TLB-MilSim/TLB-CARP/wiki/Accuracy) page.

## Limits

Worth knowing before you build a mission around it:

- Only the C-17 and C-130J are calibrated. Anything else flies and drops, but treat the
  accuracy above as a best case rather than a promise.
- The autopilot holds a fixed height above the DZ. It won't terrain-follow, so pick a run
  altitude that clears the ground along your whole run-in.
- In strong wind, unguided accuracy is limited by how far the canopy drifts, not by the
  maths. Turn on JPADS if the wind is up.
- A guided canopy can't fly upwind faster than its glide speed, 12 m/s by default. Past
  roughly that, it's being carried and accuracy falls off.
- Cargo cannot be unloaded above 3 m. Unloading at altitude opens the canopy next to the
  tail, so the drop is the only way cargo leaves a flying aircraft.

## Documentation

The [wiki](https://github.com/TLB-MilSim/TLB-CARP/wiki) is the documentation. It's the one
copy, and it's kept current with the mod.

| Page | For |
| --- | --- |
| [Quick Start](https://github.com/TLB-MilSim/TLB-CARP/wiki/Quick-Start) | A drop in six steps. |
| [Pilot Guide](https://github.com/TLB-MilSim/TLB-CARP/wiki/Pilot-Guide) | Aircrew: the panel, the HUD, the run-in, cargo, autopilot, auto drop. |
| [The HUD](https://github.com/TLB-MilSim/TLB-CARP/wiki/The-HUD) | Every row, phase, state and message on the instrument. |
| [Cargo](https://github.com/TLB-MilSim/TLB-CARP/wiki/Cargo) · [Guided Cargo](https://github.com/TLB-MilSim/TLB-CARP/wiki/Guided-Cargo) | Loading, sticks, and canopies that steer themselves. |
| [Jump Run](https://github.com/TLB-MilSim/TLB-CARP/wiki/Jump-Run) | Jumpmasters: the exit point, the countdown, the jumplight. |
| [Crew and Multiplayer](https://github.com/TLB-MilSim/TLB-CARP/wiki/Crew-and-Multiplayer) | What's shared, who owns what, and what the server has to run. |
| [Settings](https://github.com/TLB-MilSim/TLB-CARP/wiki/Settings) | Admins: all 31 addon options with default, range and owner. |
| [Mission Making](https://github.com/TLB-MilSim/TLB-CARP/wiki/Mission-Making) | DZ markers, the item, servers, aircraft support, script hooks. |
| [How It Works](https://github.com/TLB-MilSim/TLB-CARP/wiki/How-It-Works) · [Accuracy](https://github.com/TLB-MilSim/TLB-CARP/wiki/Accuracy) | The solver, the path manager, and what each measured figure is worth. |
| [Troubleshooting](https://github.com/TLB-MilSim/TLB-CARP/wiki/Troubleshooting) | Everyone: symptom first, then what to check. |
| [Changelog](https://github.com/TLB-MilSim/TLB-CARP/wiki/Changelog) | What changed, release by release. |

Building it yourself, the test suite and the packaging traps are on
[Building From Source](https://github.com/TLB-MilSim/TLB-CARP/wiki/Building-From-Source).
How a change lands in this repository is in [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

TLB CARP is licensed under the
**[Arma Public License No Derivatives (APL-ND)](https://www.bohemia.net/community/licenses/arma-public-license-nd)**.
Share it unmodified, for non-commercial use, with attribution. You may not modify it or
publish derivative works, and it may only be used with Bohemia Interactive's Arma games.
See [`LICENSE`](LICENSE).

The **TLB** and **TLB MilSim** names and the logo aren't covered by the licence and remain
ours.

## Credits

Made by **TLB MilSim**. The logo is TLB artwork. The CARP Computer icon and the Workshop
banners are generated by the scripts in `tools/`. CBA_A3, ACE3 and the USAF Mod are used
through their public functions.

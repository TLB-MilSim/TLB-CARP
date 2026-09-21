# Troubleshooting

Symptoms first. Each one lists what to check, in the order worth checking it.

## There is no TLB CARP in my interaction menu

1. **Are you carrying a CARP Computer?** It is an item, it is in the Arsenal, and without
   it there is no entry. A mission can switch that requirement off in Addon Options →
   TLB CARP → Access.
2. **Are you using the right menu?** It is on the **Interact** menu aimed at the aircraft
   you are sitting in, not self-interact.
3. **Are you inside the aircraft?** The action lives on the airframe and only appears from
   a seat inside it.
4. **Is the mod loaded?** Check the launcher, and check that **TLB CARP** appears in Addon
   Options.

You can also bind **Open TLB CARP** under *Options → Controls → Configure Addons →
TLB CARP*, which skips the menu entirely.

## The DZ list is empty

The list is built from mission markers whose name starts with `DZ_`. If the mission has
none, press **SET ON MAP** and click your point instead — that works in any mission.

## Cargo never leaves the aircraft

1. **Is the mod on the server?** Not just on the clients. On a dedicated server the load
   is usually owned by the server, and that is the machine that performs the release. If
   the server does not have CARP, drops quietly do nothing.
2. **Is anything actually loaded?** The panel's CARGO line says what it can see. A vehicle
   Zeus merely *placed* in the hold is carried by nothing — load it properly.
3. **Was the pass refused?** See the next entry.
4. **Check the RPT** for lines tagged `[TLB CARP][RELEASE]`.

## AUTO DROP is armed but nothing dropped

The gate refused the pass. Inside the final stretch CARP requires all three of:

- within **25 m** of the run-in line,
- within **2°** of the locked run-in heading,
- predicted sideways drift under the **Release Drift Limit** (25 m by default).

The HUD says which one failed. This is deliberate: a load released off the line misses by
about as much as you were off, so it would rather send you round again.

## The co-pilot does not see my changes

1. **Both need a CARP Computer** (or the requirement switched off).
2. **Compare the CREW line** on both panels. The same REV number means you are in sync.
3. **Look at system chat.** CARP names a crew member running a different version, and
   warns when the server is not running the mod.
4. **The server must run the mod** for edits to be merged properly.

If it still disagrees, run `testing/mp_carp_diagnostic.sqf` in the debug console on both
machines and compare the `access:` and `SHARED record` lines.

## I cannot unload cargo in the air

By design. Above 3 m the unload action refuses, because unloading at altitude opens the
canopy next to the tail. The drop is the only way cargo leaves a flying aircraft.

## The load action is not on the vehicle

Walk up to **the vehicle**, not the aircraft — the load action sits on the thing being
loaded, and works out which aircraft you mean. The aircraft has to be close, and it has to
be able to take that load: a jet refusing a truck is the correct answer.

## The server kicks me when I connect

The server does not have the key. Releases are signed — copy
`keys/tlb_carp.bikey` from the mod folder into the server's `Keys/` folder.

If you are on a release older than 1.0.0, it is genuinely unsigned; update.

If the key is installed and it still kicks you, check the `.bisign` files are actually
in `addons/` beside the PBOs. Copying just the PBOs out of a release leaves them behind,
and a PBO without its signature is refused exactly as an unsigned one is.

## The jumplight stays red

The aircraft is not tracking the run-in. A green light when the exit point is a kilometre
off to one side is worse than no light, so CARP holds red and asks the pilot to correct.
Get cross-track and track error small and it goes green.

## The HUD is missing

The HUD appears once **guidance is armed**, and only if *HUD Enabled* is on under Addon
Options → TLB CARP → Display.

## The panel says NO SUPPORTED AIRCRAFT

You are not in an aircraft CARP can solve for. Any aircraft works, but only the C-17 and
C-130J are calibrated; anything else borrows a profile, reports **DEGRADED** and says so
on the HUD.

## Something else

Turn on *Diagnostics Enabled* (Addon Options → TLB CARP → Advanced) for the full telemetry
block on the panel, then send the `[TLB CARP]` lines from your RPT together with the output
of `testing/mp_carp_diagnostic.sqf`.

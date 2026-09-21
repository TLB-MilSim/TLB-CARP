# Mission making

What to put in a mission so a crew can use CARP, and the handful of things worth knowing
before you build around it.

## Drop zones

The panel's DZ list is built from **map markers whose name starts with `DZ_`**. The
marker's text is used as the label, so `DZ_alpha` with the text "DZ ALPHA" reads properly
in the list. Anything else in the mission is ignored.

Crews can always skip the list: **SET ON MAP** lets them click any point.

## The CARP Computer

Players need the item `TLB_CARP_Computer` to open CARP and to share the crew's drop:

- **In a loadout:** add `TLB_CARP_Computer` to the unit's items, or leave it in an Arsenal.
- **On the ground:** place `TLB_CARP_Item_Computer` from Eden or Zeus under
  *Equipment → Inventory Items*.
- **Or drop the requirement:** turn off *Require CARP Computer* in Addon Options →
  TLB CARP → Access, and anyone aboard can use CARP.

## On a server

- **Load the mod on the server as well as the clients.** On a dedicated server the cargo
  is usually owned by the server, and that is the machine that performs the release and
  flies guided canopies. Without it, drops quietly do nothing.
- **Install the key.** Every release is signed. Copy `keys/tlb_carp.bikey`
  out of the mod folder into the server's own `Keys/` folder and `verifySignatures = 2`
  works as normal. It is one persistent key, so you install it once and not per release.
- **Force the settings you care about** in `cba_settings.sqf` — see
  [Settings](SETTINGS.md#forcing-settings-on-a-server).

## Aircraft

Any aircraft can fly a drop. Only the USAF C-17 and C-130J are calibrated; everything else
borrows a profile, always reports **DEGRADED**, and says `UNCAL AIRFRAME` on the HUD. The
maths still runs — the accuracy claim does not.

Two escape hatches for unusual airframes:

```sqf
// Where a load leaves the aircraft from, in model coordinates.
aircraft setVariable ["USAFDC_dropPos", [0, -30, -5], true];

// Where a loaded vehicle rides inside the hold.
aircraft setVariable ["USAFDC_loadPos", [0, -8, -2], true];
```

Without them CARP derives the hold and the release point from the aircraft's bounding box,
which is good enough for carriage but is not a calibration.

## Cargo

CARP recognises loads from four sources: its own load action, the USAF cargo system, ACE
cargo (real objects, not ACE's virtual entries), and vehicle-in-vehicle. A vehicle that
Zeus has merely *placed* inside a fuselage is carried by nothing and cannot be dropped —
load it with one of the four.

Loads stack forward from the ramp and leave back to front, which is also the order guided
loads are spaced along the run-in.

Unloading is refused above 3 m, deliberately.

## Zeus

- Zeus can place the CARP Computer as an item, and can place or spawn loads — but a spawned
  vehicle still has to be *loaded* to be droppable.
- Zeus teleporting a crew member between aircraft is handled: they adopt whatever CARP
  state that airframe holds within a second.

## What CARP never does to your mission

- **No global markers.** The DZ, release point, canopy and touchdown markers are local to
  each client, so two aircraft running CARP never write over each other's map.
- **No shared state between aircraft.** The crew's drop is stored on the airframe itself.
- **No changes to anybody's cargo system.** USAF and ACE loads are read where they are;
  CARP's own release reproduces the same sequence.

## Talking to CARP from a script

Most missions need none of this, but it exists:

| Variable | On | Meaning |
| --- | --- | --- |
| `USAFDC_dropPos` | aircraft | Release offset override, model coordinates |
| `USAFDC_loadPos` | aircraft | Cargo hold position override |
| `USAFDC_carpRecord` | aircraft | The crew's shared drop record. Read it; do not write it — the server owns it |

## Checking a mission before you ship it

1. Get in the aircraft with a CARP Computer and confirm **TLB CARP** is on the interaction
   menu.
2. Confirm your `DZ_*` markers appear in the list.
3. Load a vehicle, fly a pass with AUTO DROP armed, and watch it leave.
4. On a dedicated server, do it again with a second player aboard: both panels should show
   the same **CREW** revision.

Do the same four checks again on a dedicated server, with a second player aboard, before
a mission depends on CARP in a live operation. A listen server hides the one thing most
likely to break: on a dedicated server the cargo usually belongs to the server, and that
is the machine that performs the release.

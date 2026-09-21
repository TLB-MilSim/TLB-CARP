# Contributing

How a change gets into this repository. It applies to everyone working here — people and
AI assistants alike.

## Work reaches main through a pull request

`main` is the only long-lived branch and **nobody pushes to it directly**. A GitHub
ruleset enforces that, for admins too, so an accidental `git push` to `main` is refused
rather than discussed.

```bash
git checkout -b what-the-change-is
# work, commit as often as you like
git push -u origin what-the-change-is
gh pr create --base main
```

Branch names say what the change is — `carp-computer-icon`, `jump-run-refusal` — not
`fix`, `patch-2`, or a date.

## Squash is the only merge button

Merge commits and rebase merges are switched off. A PR lands on `main` as exactly one
commit, however many it took to get there.

That is deliberate. Work here iterates: a fix, the test that pins it, another look at the
wording, a correction after someone reads it. The branch keeps those steps. `main` keeps
the change.

**One change, one PR, however many pushes it takes.** If something is wrong with an open
PR, push another commit to the same branch — it all collapses on merge, so iterating costs
nothing. Do not open a second PR to correct one that is still open.

**Merge only when the feature is finished.** Not at a checkpoint, and not when the first
half works. Merging something half-done means the rest has to arrive as a second PR with a
subject of its own, which puts one piece of work on `main` twice and undoes the point of
squashing. An open PR costs nothing while you finish it.

**After a PR merges, a follow-up is a new PR** with a subject of its own.

Merged branches delete themselves.

## The PR title and description become the commit message

GitHub is configured to take the squashed commit's subject from the PR title and its body
from the PR description. A PR description is therefore not scratch paper: it is what
`git log` shows for as long as this project exists.

Write both as a commit message:

- **Subject:** what changed, in plain words, under about 70 characters. `Refuse a green
  light the jumper cannot use`, not `Update fn_updateJumpCue.sqf` or `fixes`.
- **Body:** what changed and, more importantly, **why** — the reasoning that would
  otherwise be lost, what was tried and rejected, what a reader would otherwise have to
  rediscover. If a decision rests on a measurement, give the number.
- Plain English. No marketing, no emoji, no "as requested", no restating the diff line by
  line.
- Review scaffolding — checklists, "ready for review", screenshots of your own terminal —
  does not belong in the body, because it ends up in the history.

## Releases

1. Bump `USAFDC_VERSION` in `addon/functions/fn_postInit.sqf`.
2. Build and verify: `python tools/build_release.py --version <x.y.z.0> --label <slug>`.
   It runs the suite, builds and signs both PBOs, writes the release and source ZIPs, and
   re-runs the suite from a fresh extraction of the source ZIP. It fails rather than
   shipping something unverified.
3. Open the release PR. **Title it `v1.2.3 - short title`, and make the description the
   release notes themselves** — no checklists, no test plan. `tools/publish_release.py`
   takes the GitHub Release notes from the commit body of the tag, which after squashing
   is that description.
4. Merge, then tag `main` and publish: `python tools/publish_release.py --tag v1.2.3`.

## Tests

`python -m unittest discover -s tests -v`

The suite is static contracts over the source: it reads the SQF and asserts that specific
decisions are still there. So:

- A failing test after a deliberate change is the test doing its job. Update it **as part
  of the change**, saying why in the PR body. Never weaken one to turn red green.
- A green suite proves the source says what it should. It proves **nothing** about how the
  mod behaves in Arma. Never describe a flight-behaviour fix as working on the strength of
  the suite alone — say it is source-verified and needs flying.

## Saying what is true

Accuracy figures in this repository are measured, not estimated, and every one of them
traces to a flown or benched drop. If you quote a number, quote the measured one. If a
change has not been tested in game, say so, in the PR and in the documentation.

## Assets and generated files

- `python tools/gen_assets.py` — the CARP Computer icon and the launcher logos.
- `python tools/gen_banners.py` — the Steam Workshop banners and preview image.
- `addon/config.bin` is built from `addon/config.cpp` with Arma 3 Tools' CfgConvert. The
  binary is what ships.

Never commit `build/`, `release/`, or a `.biprivatekey`. The signing key lives outside the
repository.

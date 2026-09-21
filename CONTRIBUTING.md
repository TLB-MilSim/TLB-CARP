# Contributing

How a change gets into this repository. It applies to everyone and everything working
here, with no exceptions for tooling.

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
- **Body:** what changed and **why**, in a handful of lines. The reasoning that would
  otherwise be lost, and nothing else. If a decision rests on a measurement, give the
  number.
- **Keep it short.** Past about fifteen lines you are writing a report, not a commit
  message. Leave out anything a reader can see in the diff, anything you did on the way to
  the answer, and any explanation of a problem you then solved. One paragraph per idea, and
  most changes are one idea.
- Plain English. No marketing, no emoji, no "as requested", no restating the diff line by
  line.
- Review scaffolding — checklists, "ready for review", screenshots of your own terminal —
  does not belong in the body, because it ends up in the history.

## Nothing merges until it has been checked

Opening a pull request and merging it a minute later is not review, it is a slow direct
push. A PR sits open until somebody has actually gone through this:

1. **The full suite passes.** `python -m unittest discover -s tests`
2. **The diff has been read**, by a person, in the GitHub diff view. Not skimmed from a
   terminal, and not just the files you meant to change. Line-ending churn, a stray
   generated file and a blanket find-and-replace that hit something it should not have are
   all invisible until you look.
3. **Anything that runs in Arma has been loaded in Arma.** Not "the tests are green". The
   suite reads the source; it has never once started the game. Load the mod, open the
   panel, and exercise the thing you changed.
4. **`config.bin` has been rebuilt** if `config.cpp` was touched
   (`python tools/build_config.py`), because the binary is what ships.
5. **Somebody says so.** The person merging confirms 1 to 4 were done, in a PR comment or
   out loud. If nobody has said it, it is not done.

**Opening a pull request and merging it are two separate acts, by two separate
parties.** Whatever opened it does not also wave it through: a PR opened and merged a
minute later has had no review at all, and "the tests passed" is precisely the assurance
this step exists to distrust. Leave it open and say what still needs checking.

An open PR costs nothing. A bad commit on `main` costs a revert, a second commit, and the
history that was the whole point of squashing.

## Releases

1. Bump `TLB_CARP_VERSION` in `addon/functions/fn_postInit.sqf`.
2. **Make the signing key for this version.** Every release is signed with its own key,
   named for the version, the way the other TLB mods are: `tlb_carp_v1_1_0`. Create it
   with Arma 3 Tools' `DSCreateKey`, keep the `.biprivatekey` outside the repository, and
   pass the pair to the build with `--key-dir` and `--key-name`.

   The cost of this is real and admins carry it: a new key means every server operator
   installs a new `.bikey` on every release, and a server that misses one kicks everybody
   running the new build. Say clearly in the release notes that the key changed.
3. Build and verify: `python tools/build_release.py --version <x.y.z.0> --label <slug>`.
   It runs the suite, builds and signs both PBOs, writes the release and source ZIPs, and
   re-runs the suite from a fresh extraction of the source ZIP. It fails rather than
   shipping something unverified.
4. Open the release PR. **Title it `v1.2.3 - short title`, and make the description the
   release notes themselves** — no checklists, no test plan. `tools/publish_release.py`
   takes the GitHub Release notes from the commit body of the tag, which after squashing
   is that description.
5. **Fly it.** A release is the one change that cannot be "source-verified only".
6. Merge, then tag `main` and publish: `python tools/publish_release.py --tag v1.2.3`.

**A release page carries two things:** the mod ZIP and GitHub's own source archive. Do not
attach loose PBOs, signatures or keys. They are all inside the ZIP already, and a release
with six assets buries the one people came for.

## Do not rename what records history

Some strings in this repository are facts about what already shipped: the names a PBO was
released under, an old variable kept only so an out-of-date client can be detected. They
look like leftovers and they are not.

A blanket find-and-replace has already broken one. The rename pass swept up
`LEGACY_PBO_NAMES`, made it equal to the current PBO name, and would have had deploy
delete the PBO it had just installed. `tests/test_tlb_carp_rename.py` lists every
deliberate exception with its reason; add to that list rather than to the replacement.

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

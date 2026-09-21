# AGENTS.md

Instructions for AI coding agents working in this repository. Claude Code, Codex, Cursor
and anything else that follows the AGENTS.md convention all read this file.

**Read [CONTRIBUTING.md](CONTRIBUTING.md) and follow it.** It is the whole rulebook and it
applies to you exactly as it applies to a person. The rest of this file is the short
version of the parts agents get wrong.

## The workflow, in one paragraph

Branch off `main`, commit as often as you like, push, open a pull request. Never push to
`main` directly; a ruleset refuses it anyway. Merging is squash-only, so the PR becomes
exactly one commit. The PR title is the commit subject and the PR description is the
commit body, which means the description is what `git log` shows forever. Write it as a
commit message, not as a status report.

**Keep it short.** A handful of lines. Agents write PR descriptions far too long: every
consideration weighed, every problem met and fixed along the way, every guard explained.
None of that belongs in `git log`. Say what changed and why, and stop.

## One session is one pull request

A session's worth of adjustments is **one** PR. When a change is asked for and then
refined five times, that is five pushes to the same branch, not five pull requests. The
whole point of squash merging is that `main` reads as a list of changes rather than a list
of attempts.

## Do not merge your own pull request

Open it, then stop. A PR is merged by a human, after the checklist in CONTRIBUTING.md has
actually been done, and after the change has been loaded in Arma where that applies. An
agent that opens and immediately merges its own work has removed the only review step this
project has.

## Say what you tested

Run `python -m unittest discover -s tests` before opening a PR.

Then be precise about what that proves. The suite is static assertions over the source: it
checks the code still says what it should. It proves **nothing** about how the mod behaves
in Arma. Never describe a flight-behaviour change as working because the suite is green.
Say it is source-verified, and say it still needs flying.

The same goes for numbers. Every accuracy figure here came off a flown or benched drop.
Quote the measured one or do not quote one.

## Three traps that cost a day each

- `addon/config.cpp` is the source; `addon/config.bin` is built from it with
  `python tools/build_config.py`. The binary is what ships, so a `.cpp` edit that is not
  rebuilt does nothing in game.
- A new function reaches the engine only through the compile table in
  `addon/functions/fn_postInit.sqf`, and a new file has to be `--include`d in its first
  release build.
- A compiled `.sqfc` sibling shadows the `.sqf` beside it at load. There are none in the
  tree now and it should stay that way. If a change appears to do nothing in game, look
  for one before theorising.

## Do not rename what records history

Some strings are facts about what already shipped: legacy PBO names, old variable names
kept for detecting an out-of-date client. A blanket find-and-replace has already broken
one of these. `tests/test_tlb_carp_rename.py` lists the deliberate exceptions.

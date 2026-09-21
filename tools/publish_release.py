#!/usr/bin/env python3
"""Publish a GitHub Release for one tag, or for every tag that does not have one.

    python tools/publish_release.py --all
    python tools/publish_release.py --tag v0.8.1

A release turns a tag into something a unit member can actually use: a download link for
the mod ZIP, ready to unpack and put on the Steam Workshop, without cloning the repo or
knowing what a PBO is.

DELIBERATELY NOT PART OF build_release.py
-----------------------------------------
build_release.py has no network dependency at all, which is why it can be trusted to say
a build is good. It also runs for throwaway verification builds (`--out-dir build/check`),
and a GitHub outage must never turn a perfectly good build red. Publishing is a separate,
explicit step that can be re-run at any time and is idempotent.

THE @ IN THE FILENAME
---------------------
Every release ZIP is named `@TLB_CARP_System_v*.zip` (`@USAF_CARP_System_v*.zip` through
v0.8.4). Passed through a shell, that
leading `@` is a splat operator in PowerShell and an @file indirection to several CLIs,
and `gh` itself will try to read some arguments beginning with `@` as files. This script
never uses a shell: subprocess is given an argument LIST, so the filename reaches gh as
one opaque string and nothing gets a chance to interpret it.

THE NOTES
---------
The commit body is already written as release notes -- that is the house style -- and it
contains multi-line text, backticks and non-ASCII. Passing that as a command-line argument
is a quoting problem in three layers, so it goes to a temporary file and gh reads it with
--notes-file. The curated per-release notes under docs/releases/ were retired with the
v0.2-v0.5 papers, so the commit body is now the only source.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "TLB-MilSim/TLB-CARP-System"


def run(args: list[str], check: bool = True) -> str:
    """Always an argument list, never a shell string. See the module docstring."""
    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and proc.returncode != 0:
        raise RuntimeError(f"{' '.join(args)}\n{proc.stdout}\n{proc.stderr}")
    return proc.stdout.strip()


def tags() -> list[str]:
    out = run(["git", "-C", str(ROOT), "tag", "--sort=v:refname"])
    return [t for t in out.splitlines() if t.strip()]


def published() -> set[str]:
    """Ask for the tag explicitly.

    `gh release list`'s table puts the TITLE first and the tag third, so splitting on the
    first tab silently returns a set of titles -- which matches no tag, so every release
    looks unpublished and a refresh pass quietly finds nothing to do.
    """
    out = run(
        ["gh", "release", "list", "--repo", REPO, "--limit", "200",
         "--json", "tagName", "--jq", ".[].tagName"],
        check=False,
    )
    return {line.strip() for line in out.splitlines() if line.strip()}


def asset_for(tag: str) -> Path | None:
    """The mod ZIP for this version, wherever it currently lives.

    build_release.py keeps exactly one release ZIP at the repo root -- the one the user is
    running -- and rotates every superseded one into releases/. So a given version is in
    one place or the other, never both.
    """
    version = tag.lstrip("v")
    # The mod folder was @USAF_CARP_System through v0.8.4, so older ZIPs carry that name.
    for prefix in ("@TLB_CARP_System", "@USAF_CARP_System"):
        for folder in (ROOT, ROOT / "releases"):
            hits = sorted(folder.glob(f"{prefix}_v{version}-*.zip"))
            if hits:
                return hits[0]
        # The earliest releases have no -label suffix.
        for folder in (ROOT, ROOT / "releases"):
            hits = sorted(folder.glob(f"{prefix}_v{version}.zip"))
            if hits:
                return hits[0]
    return None


def pbos_for(tag: str) -> list[Path]:
    """The loose PBOs for this version, if the build exported them.

    build_release.py writes them to releases/pbo/v<version>/ under their exact runtime
    names from v0.16.12 on, and their .bisign signatures plus the public .bikey from
    v0.16.14. Releases built before those have none, so this returns an empty list or a
    short one and publishing still works.
    """
    folder = ROOT / "releases" / "pbo" / f"v{tag.lstrip('v')}"
    if not folder.is_dir():
        return []
    # The signatures and the public key ride with them. From v0.16.14 a PBO without its
    # .bisign is exactly as unloadable on a signature-checking server as an unsigned one,
    # and the .bikey is what the admin installs. Attaching the PBOs alone would look
    # complete and not be.
    out = []
    for pattern in ("*.pbo", "*.bisign", "*.bikey"):
        out += sorted(folder.glob(pattern))
    return out


def assets_for(tag: str) -> list[Path]:
    """Everything attached to this version's GitHub Release.

    The mod ZIP is what a player installs. The loose PBOs ride along so a Workshop
    upload can refresh a staging folder by copying two files instead of re-extracting
    the archive -- `gh release download <tag> -p '*.pbo'` lands them under the names
    Arma expects. Asked for 2026-09-21.
    """
    zip_asset = asset_for(tag)
    return ([zip_asset] if zip_asset is not None else []) + pbos_for(tag)


def notes_for(tag: str) -> str:
    """The commit body, which is where this project writes its release notes."""
    # %b, the body WITHOUT the subject. %B's first line is the subject, which is already
    # the release title, so notes built from %B render the title twice on the page.
    body = run(["git", "-C", str(ROOT), "log", "-1", "--format=%b", tag])
    # The co-author trailer is git bookkeeping, not release notes.
    return re.sub(r"\n*Co-Authored-By:.*$", "", body, flags=re.S).strip() + "\n"


def title_for(tag: str) -> str:
    subject = run(["git", "-C", str(ROOT), "log", "-1", "--format=%s", tag])
    return subject if subject else tag


def publish(tag: str, dry_run: bool = False, refresh: bool = False) -> bool:
    assets = assets_for(tag)
    title = title_for(tag)
    notes = notes_for(tag)

    print(f"  {tag}: {title[:72]}")
    print(f"      assets: {', '.join(a.name for a in assets) or '(none found)'}")
    if dry_run:
        return True

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
        handle.write(notes)
        notes_path = handle.name

    if refresh:
        args = ["gh", "release", "edit", tag, "--repo", REPO, "--notes-file", notes_path]
    else:
        args = [
            "gh", "release", "create", tag,
            "--repo", REPO,
            "--title", title,
            "--notes-file", notes_path,
            # Without this, a mistyped tag does not fail -- gh creates that tag at HEAD
            # and publishes a release pointing at a commit the ZIP did not come from.
            "--verify-tag",
        ]
        # Each is its own list element. No shell, so a leading @ is never interpreted.
        args.extend(str(a) for a in assets)

    try:
        out = run(args, check=False)
        print(f"      {out.strip() or 'created'}")
        return True
    finally:
        Path(notes_path).unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--tag", help="publish this tag only")
    group.add_argument("--all", action="store_true", help="publish every tag that has no release yet")
    ap.add_argument("--dry-run", action="store_true", help="show what would be published")
    ap.add_argument("--refresh-notes", action="store_true",
                    help="rewrite the notes of releases that already exist")
    args = ap.parse_args()

    existing = published()
    if args.refresh_notes:
        targets = [args.tag] if args.tag else [t for t in tags() if t in existing]
    else:
        targets = [args.tag] if args.tag else [t for t in tags() if t not in existing]

    if not targets:
        print("Every tag already has a release.")
        return 0

    verb = "Refreshing notes on" if args.refresh_notes else "Publishing"
    print(f"{verb} {len(targets)} release(s) to {REPO}:")
    ok = all(publish(tag, args.dry_run, args.refresh_notes) for tag in targets)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

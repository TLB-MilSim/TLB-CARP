#!/usr/bin/env python3
"""Rebuild addon/config.bin from addon/config.cpp with Arma 3 Tools' CfgConvert.

    python tools/build_config.py            # config.cpp -> config.bin
    python tools/build_config.py --decompile # config.bin -> config.cpp (first time only)
    python tools/build_config.py --verify     # prove the round trip is still lossless

THE CONSTRAINT THIS REMOVES
---------------------------
Every design note in this project up to v0.12.0 says config.bin is pre-binarized and
cannot be regenerated, and the architecture is shaped around it: the dialog cannot gain
controls, so they are built at runtime with ctrlCreate; new functions cannot be declared
in CfgFunctions, so they go in a compile table in fn_postInit; ui/*.hpp is compiled in and
editing it does nothing, so HUD geometry is written with ctrlSetPosition.

None of that was ever true once Arma 3 Tools was installed. CfgConvert de-rapifies a
config.bin to text and rapifies it back, and on this project's config the round trip is
BYTE-IDENTICAL -- 11856 bytes and sha256 d87f8780... in both directions, verified
2026-09-19 before the first edit was made.

So config.cpp is now the source of truth and config.bin is a build artifact, which is how
every other Arma addon works and how items/config.cpp in this repo already worked.

WHY THE ROUND TRIP IS CHECKED AND NOT ASSUMED
---------------------------------------------
A rebuilt config that silently drops a control or a handler would not fail any test here
-- the suite reads .sqf text -- and would not fail the PBO build either, because the
rebuilt file is legitimately its own source. It would fail in the aircraft, once, in
front of a crew.

--verify therefore decompiles whatever config.bin currently is, recompiles that text, and
compares. It proves the tool is lossless on this exact file. It cannot prove an EDIT is
correct; that still takes one flight.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_CPP = ROOT / "addon" / "config.cpp"
CONFIG_BIN = ROOT / "addon" / "config.bin"

# Installed with Arma 3 Tools. Searched rather than hard-coded to one drive, because a
# Steam library can live anywhere and a wrong path here reads as "the tool is missing".
CANDIDATES = [
    Path(d) / "SteamLibrary/steamapps/common/Arma 3 Tools/CfgConvert/CfgConvert.exe"
    for d in ("E:/", "C:/", "D:/", "F:/")
] + [
    Path("C:/Program Files (x86)/Steam/steamapps/common/Arma 3 Tools/CfgConvert/CfgConvert.exe"),
]


def cfgconvert() -> Path:
    for path in CANDIDATES:
        if path.is_file():
            return path
    raise SystemExit(
        "CfgConvert.exe not found. It ships with Arma 3 Tools (free on Steam).\n"
        "Looked in:\n  " + "\n  ".join(str(p) for p in CANDIDATES)
    )


def run(tool: Path, mode: str, src: Path, dst: Path) -> None:
    proc = subprocess.run(
        [str(tool), mode, "-dst", str(dst), str(src)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0 or not dst.exists():
        raise SystemExit(f"CfgConvert {mode} failed:\n{proc.stdout}\n{proc.stderr}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--decompile", action="store_true", help="config.bin -> config.cpp")
    group.add_argument("--verify", action="store_true", help="prove the round trip is lossless")
    args = ap.parse_args()

    tool = cfgconvert()
    print(f"CfgConvert: {tool}")

    if args.decompile:
        if CONFIG_CPP.exists():
            raise SystemExit(f"{CONFIG_CPP} already exists -- refusing to overwrite the source of truth")
        run(tool, "-txt", CONFIG_BIN, CONFIG_CPP)
        print(f"  wrote {CONFIG_CPP.relative_to(ROOT)} ({CONFIG_CPP.stat().st_size} bytes)")
        return 0

    if args.verify:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            run(tool, "-txt", CONFIG_BIN, tmp / "check.cpp")
            run(tool, "-bin", tmp / "check.cpp", tmp / "check.bin")
            before, after = sha256(CONFIG_BIN), sha256(tmp / "check.bin")
            print(f"  config.bin        {CONFIG_BIN.stat().st_size:6} bytes  {before[:16]}")
            print(f"  bin->txt->bin     {(tmp / 'check.bin').stat().st_size:6} bytes  {after[:16]}")
            if before != after:
                raise SystemExit("ROUND TRIP IS NOT LOSSLESS -- do not edit config.cpp until this is understood")
            print("  byte-identical")
        return 0

    if not CONFIG_CPP.exists():
        raise SystemExit(f"{CONFIG_CPP} missing -- run --decompile once to create it from config.bin")

    previous = sha256(CONFIG_BIN) if CONFIG_BIN.exists() else ""
    backup = None
    if CONFIG_BIN.exists():
        backup = Path(tempfile.gettempdir()) / "tlb_carp_config_prev.bin"
        shutil.copy2(CONFIG_BIN, backup)

    run(tool, "-bin", CONFIG_CPP, CONFIG_BIN)
    built = sha256(CONFIG_BIN)
    print(f"  {CONFIG_BIN.relative_to(ROOT)} {CONFIG_BIN.stat().st_size} bytes  {built}")
    if previous:
        print("  unchanged" if built == previous else f"  changed from {previous[:16]} (previous kept at {backup})")

    # A rebuilt config that lost a control would pass every test in this repo, because the
    # suite reads .sqf text, and would pass the PBO build too, because the rebuilt file is
    # legitimately its own source. Reading it back and comparing against the source is the
    # cheapest guard against it.
    #
    # Compared against config.cpp itself, NOT against a fixed number. A magic threshold is
    # a guess about a file that is meant to change -- the first version of this guard used
    # one and failed a build whose only difference was twelve bytes of removed dependency.
    source = CONFIG_CPP.read_text(encoding="utf-8", errors="replace")
    with tempfile.TemporaryDirectory() as tmp:
        check = Path(tmp) / "back.cpp"
        run(tool, "-txt", CONFIG_BIN, check)
        text = check.read_text(encoding="utf-8", errors="replace")
        for what in ("idc=", "class "):
            want, got = source.count(what), text.count(what)
            if want != got:
                raise SystemExit(
                    f"{what!r}: config.cpp has {want}, the rebuilt binary reads back {got} "
                    "-- something did not survive rapify"
                )
        print(f"  reads back with {text.count('idc=')} idc entries and {text.count('class ')} classes, matching source")
    return 0


if __name__ == "__main__":
    sys.exit(main())

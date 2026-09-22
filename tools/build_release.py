#!/usr/bin/env python3
"""Build and verify a TLB CARP release.

Automates the release packaging checklist:
run tests, build the PBO, emit release + source ZIPs, re-run the suite from a
fresh extraction of the source ZIP, then verify the artifacts against source.

The build fails loudly rather than shipping an unverified artifact. Every check
that can be automated is; the ones that cannot (in-engine validation) are not
claimed to have run.

Root-folder convention: exactly one @TLB_CARP_System_v*.zip lives at the project
root -- the release currently loaded in game. On a successful build the previous
release is rotated into releases/ and the new one takes its place. Source ZIPs go
straight to releases/.

Example:

    python tools/build_release.py --version 0.4.2.0 --label ap-vertical-tuning

Build and push straight into the Arma mod folder:

    python tools/build_release.py --version 0.4.2.0 --label ap-vertical-tuning \
        --deploy "E:/@TLB_CARP_System"

Reproduce an existing release to prove source/PBO fidelity:

    python tools/build_release.py --version 0.4.1.0 --label usability-fixes \
        --base-release @USAF_CARP_System_v0.4.0-ap-v2-path-management.zip \
        --out-dir build/check --expect-pbo-sha256 <sha>
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import time
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PBO_NAME = "TLB_CARP_System.pbo"
# Names this PBO shipped under before. Each carries the same CfgPatches class, so one
# left beside the current PBO loads the addon twice; deploy removes them.
# These are FACTS ABOUT WHAT SHIPPED and must never be swept up in a rename. The
# USAFDC_ -> TLB_CARP_ pass did exactly that and left this equal to PBO_NAME, which
# would have made deploy delete the PBO it had just installed.
LEGACY_PBO_NAMES = ["usafdc_drop_computer.pbo"]
MOD_DIR = "@TLB_CARP_System"
# Mod folder names releases shipped under before. Release ZIPs still named for one of
# these are found and rotated like any other; deploy warns if the old folder sits
# beside the new one, since Arma would load the addon from both.
LEGACY_MOD_DIRS = ["@USAF_CARP_System"]
# The CARP Computer item. addon/config.bin is pre-binarized and cannot take a new class,
# so the item is a second addon with a plain-text config.cpp, packed from its directory
# by pack_pbo.pack_directory rather than from a base PBO.
ITEMS_PBO_NAME = "TLB_CARP_Items.pbo"
ITEMS_SOURCE = "items"

# Signing. The private key lives outside the repository on purpose -- see step 3.
DEFAULT_KEY_DIR = os.environ.get("TLB_CARP_SIGNING_DIR", "E:/CARP-SIGNING")
# No DEFAULT_KEY_NAME: the basename is DERIVED from the version being built, by
# key_name_for() below. Through v1.0.0 this was one persistent "tlb_carp" for every
# release, on the reasoning that a key admins reinstall every time is a key they stop
# installing. The owner reversed that on 2026-09-22 to match the other TLB mods, which
# version their keys. The cost is real and belongs in the release notes every time: a
# server that misses the new key kicks every client running the new build.
DEFAULT_TOOLS_DIR = os.environ.get(
    "ARMA3TOOLS_DIR", "E:/SteamLibrary/steamapps/common/Arma 3 Tools")
ITEMS_PREFIX = "x\\tlbcarp\\addons\\items"
# The drop computer's own prefix. It was x\usafdc\addons\drop_computer until the
# TLB_CARP rename. pack_pbo inherits header properties from the base PBO, and a base
# built before the rename still carries the old prefix, so this has to be forced until
# a post-rename release becomes the base. It must match the paths in config.cpp's
# CfgFunctions and in fn_postInit's compile table, or nothing resolves in game.
PREFIX = "x\\tlbcarp\\addons\\drop_computer"

# The 24 compiled .sqfc siblings were deleted with the rename: each had the old USAFDC_
# symbol names COMPILED IN and shadowed the .sqf beside it, so keeping one would have
# silently run pre-rename code. A base PBO built before the rename still lists them and
# pack_pbo requires every base entry to exist in source, so they are excluded here
# rather than by hand. An exclude that matches nothing is a no-op, so this stays
# correct once a post-rename release becomes the base.
DELETED_SQFC_ENTRIES = [
    "functions\\aircraft\\fn_projectAircraftKinematics.sqfc",
    "functions\\auto\\fn_armAutoDrop.sqfc",
    "functions\\auto\\fn_disarmAutoDrop.sqfc",
    "functions\\debug\\fn_computeCalibrationError.sqfc",
    "functions\\debug\\fn_copyLastDebugSeries.sqfc",
    "functions\\debug\\fn_debugSnapshot.sqfc",
    "functions\\debug\\fn_formatCalibrationRun.sqfc",
    "functions\\debug\\fn_runSolverSelfTest.sqfc",
    "functions\\debug\\fn_sampleParachuteTelemetry.sqfc",
    "functions\\debug\\fn_sampleWindTelemetry.sqfc",
    "functions\\dz\\fn_beginMapDZ.sqfc",
    "functions\\dz\\fn_getMissionDZs.sqfc",
    "functions\\fn_preInit.sqfc",
    "functions\\generated\\fn_getTestVectors.sqfc",
    "functions\\guidance\\fn_armGuidance.sqfc",
    "functions\\guidance\\fn_buildPlannedReference.sqfc",
    "functions\\guidance\\fn_computeRunInGuidance.sqfc",
    "functions\\guidance\\fn_interceptLimitDeg.sqfc",
    "functions\\guidance\\fn_solveWorldReference.sqfc",
    "functions\\solver\\fn_acquiredWindDisplacement.sqfc",
    "functions\\solver\\fn_ballisticToTrigger.sqfc",
    "functions\\solver\\fn_basisFromHeading.sqfc",
    "functions\\solver\\fn_canopyTime.sqfc",
    "functions\\ui\\fn_updateMarkers.sqfc",
]

def key_name_for(version: str) -> str:
    """Signing key basename for a version, e.g. 1.1.0.0 -> tlb_carp_v1_1_0.

    The build number (the fourth part) is deliberately dropped: it moves for reasons that
    do not concern an admin, and a key per build would be absurd. Dots become underscores
    because the basename ends up inside a .bisign filename.
    """
    parts = [p for p in version.split(".") if p != ""]
    if len(parts) < 3:
        raise BuildError(f"cannot derive a key name from version {version!r}")
    return "tlb_carp_v" + "_".join(parts[:3])


ARCHIVE_DIR = "releases"
# "testing" carries the debug-console diagnostic, which the suite asserts against -- it is
# what the panel's removed status block points at for the manifest, the crew record and the
# cargo sources. Leaving it out made the working tree pass and a fresh extraction fail,
# which is exactly the gap step 5 exists to find.
SOURCE_TREES = ["addon", "items", "calibration", "tests", "testing", "tools", "docs", "packaging"]
MOD_CPP_TEMPLATE = "packaging/mod.cpp"
VERSION_SOURCE = "addon/functions/fn_postInit.sqf"
CALIBRATION_ENTRIES = [
    "functions\\generated\\fn_getModel.sqf",
    "functions\\solver\\fn_empiricalCanopyC17.sqf",
]
# Fixed DOS timestamp (1980-01-01) so identical inputs produce identical ZIPs.
ZIP_DATE = (1980, 1, 1, 0, 0, 0)


def _load_pack_pbo():
    spec = importlib.util.spec_from_file_location("pack_pbo", ROOT / "tools/pack_pbo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pack_pbo = _load_pack_pbo()


class BuildError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def step(index: int, text: str) -> None:
    print(f"\n[{index:>2}] {text}")


def run_suite(cwd: Path, label: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    tail = (result.stderr or result.stdout).strip().splitlines()
    summary = tail[-1] if tail else "(no output)"
    ran = next((line for line in tail if line.startswith("Ran ")), "")
    if result.returncode != 0:
        print("\n".join(tail[-25:]))
        raise BuildError(f"test suite failed ({label})")
    print(f"     {label}: {ran} -> {summary}")


def source_version() -> str:
    """The version declared in SQF, which is what actually runs in-engine."""
    text = (ROOT / VERSION_SOURCE).read_text(encoding="utf-8")
    match = re.search(r'TLB_CARP_VERSION\s*=\s*"([^"]+)"', text)
    if match is None:
        raise BuildError(f"no TLB_CARP_VERSION declared in {VERSION_SOURCE}")
    return match.group(1)


def read_mod_cpp(explicit: Path | None, base_release: Path, short_version: str) -> bytes:
    """Stamp the version into the launcher name so the loaded build is
    identifiable at a glance."""
    if explicit is not None:
        return explicit.read_bytes()
    template = ROOT / MOD_CPP_TEMPLATE
    if template.is_file():
        text = template.read_text(encoding="utf-8")
        if "{VERSION}" not in text:
            raise BuildError(f"{MOD_CPP_TEMPLATE} has no {{VERSION}} placeholder")
        return text.replace("{VERSION}", short_version).encode("utf-8")
    with zipfile.ZipFile(base_release) as zf:
        for name in zf.namelist():
            if name.endswith("mod.cpp"):
                return zf.read(name)
    raise BuildError(f"no {MOD_CPP_TEMPLATE} and no mod.cpp in {base_release}; pass --mod-cpp")


def extract_base_pbo(base_release: Path, dest: Path) -> Path:
    """The drop computer's PBO from a previous release.

    From v0.9.0 a release also carries TLB_CARP_Items.pbo, and release ZIP entries are
    sorted, so "the first .pbo in the ZIP" would now be the items PBO. Take it by name.
    """
    wanted = {name.lower() for name in [PBO_NAME, *LEGACY_PBO_NAMES]}
    with zipfile.ZipFile(base_release) as zf:
        for name in zf.namelist():
            if name.rsplit("/", 1)[-1].lower() in wanted:
                dest.write_bytes(zf.read(name))
                return dest
    raise BuildError(f"no drop computer PBO in {base_release}")


def iter_source_files() -> list[Path]:
    files: list[Path] = []
    for tree in SOURCE_TREES:
        base = ROOT / tree
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            files.append(path)
    files.extend(sorted(ROOT.glob("*.md")))
    # LICENSE has no extension, so the globs above miss it -- and the suite that runs from
    # a fresh extraction of this ZIP checks the licence is there.
    licence = ROOT / "LICENSE"
    if licence.is_file():
        files.append(licence)
    return files


def write_zip(target: Path, members: list[tuple[str, bytes]]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for arcname, blob in sorted(members):
            info = zipfile.ZipInfo(arcname, date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, blob)


def verify_pbo_against_source(pbo: Path, version: str, source_dir: Path | None = None) -> list[str]:
    source_dir = ROOT / "addon" if source_dir is None else source_dir
    props, entries = pack_pbo.parse_pbo_header(pbo)
    prop_map = dict(props)
    if prop_map.get("version") != version:
        raise BuildError(f"PBO version is {prop_map.get('version')!r}, expected {version!r}")

    data = pbo.read_bytes()
    # Entry bodies follow the header block, in entry order.
    offset = len(data)
    body = 0
    for entry in entries:
        body += entry["size"]
    offset = len(data) - 21 - body  # 21 = 0x00 + 20-byte SHA-1 trailer

    mismatches = []
    cursor = offset
    for entry in entries:
        blob = data[cursor : cursor + entry["size"]]
        cursor += entry["size"]
        source = source_dir / Path(entry["name"].replace("\\", "/"))
        if not source.is_file():
            mismatches.append(f"missing source for {entry['name']}")
            continue
        if source.read_bytes() != blob:
            mismatches.append(f"PBO/source byte mismatch: {entry['name']}")

    trailer = data[-20:]
    if hashlib.sha1(data[:-21]).digest() != trailer:
        raise BuildError("PBO SHA-1 trailer does not match body")
    return mismatches


def verify_no_stale_sqfc() -> list[str]:
    """Every raw runtime .sqf registered in fn_postInit or pinned by the
    precedence test must not have a compiled sibling that would shadow it."""
    post_init = (ROOT / "addon/functions/fn_postInit.sqf").read_text(encoding="utf-8")
    problems = []
    for sqf in sorted((ROOT / "addon/functions").rglob("*.sqf")):
        rel = sqf.relative_to(ROOT / "addon").as_posix()
        registered_raw = rel.replace("/", "\\") in post_init.replace("/", "\\")
        if registered_raw and sqf.with_suffix(".sqfc").exists():
            problems.append(f"stale .sqfc shadows runtime-compiled {rel}")
    return problems


def release_zips(folder: Path) -> list[Path]:
    """Release ZIPs in folder under the current mod folder name, then legacy names."""
    zips: list[Path] = []
    for prefix in [MOD_DIR, *LEGACY_MOD_DIRS]:
        zips.extend(sorted(folder.glob(f"{prefix}_v*.zip")))
    return zips


def rotate_old_releases(root: Path, keep: Path, archive: Path) -> list[str]:
    """Keep exactly one release ZIP at the root: the one just built."""
    archive.mkdir(parents=True, exist_ok=True)
    moved = []
    for path in release_zips(root):
        if path.resolve() == keep.resolve():
            continue
        dest = archive / path.name
        if dest.exists():
            if dest.read_bytes() == path.read_bytes():
                path.unlink()
                moved.append(f"{path.name} (duplicate of archived copy, removed)")
                continue
            raise BuildError(
                f"{path.name} differs from the copy already in {archive.name}/; resolve by hand"
            )
        digest = sha256(path.read_bytes())
        shutil.move(str(path), str(dest))
        if sha256(dest.read_bytes()) != digest:
            raise BuildError(f"archive move corrupted {path.name}")
        moved.append(path.name)
    return moved


ARMA_PROCESSES = ["arma3_x64.exe", "arma3launcher.exe", "arma3.exe"]


def kill_arma(timeout_s: float = 20.0) -> list[str]:
    """Close Arma so the PBO can be replaced.

    Arma holds addons/*.pbo open while running, so a deploy into a live mod folder
    is refused. The user asked for this to happen automatically on every release
    rather than being told to close the game each time.

    Anything unsaved in the Eden editor is lost -- that is the user's standing
    choice, not an assumption.
    """
    killed = []
    for name in ARMA_PROCESSES:
        result = subprocess.run(["taskkill", "/F", "/IM", name],
                                capture_output=True, text=True)
        if result.returncode == 0:
            killed.append(name)
    if not killed:
        return killed
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        listing = subprocess.run(["tasklist"], capture_output=True, text=True).stdout.lower()
        if not any(name.lower() in listing for name in ARMA_PROCESSES):
            return killed
        time.sleep(0.5)
    raise BuildError(f"Arma still running after {timeout_s:.0f}s; cannot replace the PBO")


def deploy(release_zip: Path, target: Path) -> None:
    """Extract the release into an Arma mod folder, then verify what landed."""
    # Every PBO the release carries -- the drop computer and, from v0.9.0, the items
    # addon -- not one hard-coded name.
    prefix = f"{MOD_DIR}/addons/"
    keys_prefix = f"{MOD_DIR}/keys/"
    with zipfile.ZipFile(release_zip) as zf:
        # EVERYTHING under addons/, not just the PBOs. A .bisign left behind in the ZIP
        # makes the deployed folder unsigned, and this filter read ".pbo" only until the
        # first signed build: the archive was correct and the live mod folder was not,
        # which is precisely the failure the re-hash rule exists to catch.
        expected = {
            name[len(prefix):]: zf.read(name)
            for name in zf.namelist()
            if name.startswith(prefix) and not name.endswith("/")
        }
        keys = {
            name[len(keys_prefix):]: zf.read(name)
            for name in zf.namelist()
            if name.startswith(keys_prefix) and not name.endswith("/")
        }
        mod_cpp = zf.read(f"{MOD_DIR}/mod.cpp")
    if PBO_NAME not in expected:
        raise BuildError(f"{release_zip.name} has no addons/{PBO_NAME}")
    addons = target / "addons"
    addons.mkdir(parents=True, exist_ok=True)
    try:
        for name, blob in expected.items():
            (addons / name).write_bytes(blob)
        (target / "mod.cpp").write_bytes(mod_cpp)
        for legacy in LEGACY_PBO_NAMES:
            (addons / legacy).unlink(missing_ok=True)
        # A signature from a superseded key would sit beside a PBO it no longer matches
        # and fail the server's check while looking installed.
        for stale in addons.glob("*.bisign"):
            if stale.name not in expected:
                stale.unlink()
        if keys:
            keys_dir = target / "keys"
            keys_dir.mkdir(parents=True, exist_ok=True)
            for name, blob in keys.items():
                (keys_dir / name).write_bytes(blob)
    except PermissionError:
        # Arma holds the PBO open while running, so this is the expected failure
        # when a build lands mid-session. The artifacts are already built and
        # verified; only the copy into the mod folder is outstanding.
        raise BuildError(
            f"{addons / PBO_NAME} is locked -- Arma 3 is most likely running.\n"
            f"     The release is built and verified; only the deploy is pending.\n"
            f"     Close Arma 3 (and the launcher), then re-run with --deploy, or\n"
            f"     extract {release_zip.name} over {target} by hand and delete\n"
            f"     any of {', '.join(LEGACY_PBO_NAMES)} left in addons/."
        ) from None
    print(f"     {target}")
    for name, blob in sorted(expected.items()):
        landed = (addons / name).read_bytes()
        if landed != blob:
            raise BuildError(f"deployed {name} does not match the release ZIP at {target}")
        if name.lower().endswith(".pbo"):
            print(f"     addons/{name} sha256 {sha256(landed)}")
        else:
            print(f"     addons/{name} ({len(landed)} bytes)")
    for name, blob in sorted(keys.items()):
        if (target / "keys" / name).read_bytes() != blob:
            raise BuildError(f"deployed keys/{name} does not match the release ZIP")
        print(f"     keys/{name} -- copy this into the SERVER's Keys folder")
    for legacy in LEGACY_MOD_DIRS:
        old = target.parent / legacy
        if old.is_dir() and old.resolve() != target.resolve():
            print(f"     WARNING {old} still exists -- delete it or drop it from the\n"
                  f"     launcher, or Arma loads the addon from both folders")


def verify_calibration_unchanged(base_pbo: Path, new_pbo: Path) -> list[str]:
    def entry_blobs(path: Path) -> dict[str, bytes]:
        props, entries = path and pack_pbo.parse_pbo_header(path)
        data = path.read_bytes()
        body = sum(e["size"] for e in entries)
        cursor = len(data) - 21 - body
        out = {}
        for entry in entries:
            out[entry["name"]] = data[cursor : cursor + entry["size"]]
            cursor += entry["size"]
        return out

    old = entry_blobs(base_pbo)
    new = entry_blobs(new_pbo)
    changed = []
    for name in CALIBRATION_ENTRIES:
        if name in old and name in new and old[name] != new[name]:
            changed.append(name)
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", required=True, help="PBO version, e.g. 0.4.2.0")
    ap.add_argument("--label", required=True, help="release slug, e.g. ap-vertical-tuning")
    ap.add_argument("--base-release", type=Path, help="previous release ZIP (default: newest at root)")
    ap.add_argument("--mod-cpp", type=Path, help="override mod.cpp (default: taken from base release)")
    ap.add_argument("--out-dir", type=Path, default=ROOT, help="where the active release ZIP lands")
    ap.add_argument("--archive-dir", type=Path, default=ROOT / ARCHIVE_DIR,
                    help="where superseded releases and source ZIPs are kept")
    ap.add_argument("--deploy", type=Path,
                    help="Arma mod folder to extract the built release into, e.g. E:/@TLB_CARP_System")
    ap.add_argument("--no-kill-arma", action="store_true",
                    help="do not close Arma before deploying (deploy will fail if it holds the PBO)")
    ap.add_argument("--no-rotate", action="store_true",
                    help="leave superseded release ZIPs in place instead of archiving them")
    ap.add_argument("--key-dir", default=DEFAULT_KEY_DIR,
                    help="directory holding <key-name>.biprivatekey and .bikey. Kept OUTSIDE "
                         "the repository so a private key can never reach a commit or the "
                         "source ZIP")
    ap.add_argument("--key-name", default=None,
                    help="signing key basename. Defaults to the version's own key, "
                         "tlb_carp_v<major>_<minor>_<patch>. An explicit name must still "
                         "contain that, so a release cannot be signed with another "
                         "version's key by accident")
    ap.add_argument("--tools-dir", default=DEFAULT_TOOLS_DIR,
                    help="Arma 3 Tools directory containing DSSignFile/")
    ap.add_argument("--no-sign", action="store_true",
                    help="ship an UNSIGNED release. A server running verifySignatures = 2 "
                         "kicks every client that loads an unsigned mod")
    ap.add_argument("--exclude", action="append", default=[], help="PBO entry to drop (repeatable)")
    ap.add_argument("--include", action="append", default=[], help="new PBO entry to add (repeatable)")
    ap.add_argument("--allow-calibration-change", action="store_true",
                    help="permit changes to protected calibration assets")
    ap.add_argument("--expect-pbo-sha256", help="fail unless the built PBO matches this digest")
    ap.add_argument("--skip-tests", action="store_true", help="diagnostics only; never for a real release")
    args = ap.parse_args()

    short = args.version.rsplit(".", 1)[0]

    base_release = args.base_release
    if base_release is None:
        candidates = sorted(ROOT.glob(f"{MOD_DIR}_v*.zip")) or release_zips(ROOT)
        if not candidates:
            raise BuildError("no base release ZIP found; pass --base-release")
        base_release = candidates[-1]
    if not base_release.is_absolute():
        base_release = ROOT / base_release
    print(f"base release : {base_release.name}")
    print(f"target       : v{short} ({args.version}) [{args.label}]")

    out_dir = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    archive_dir = args.archive_dir if args.archive_dir.is_absolute() else ROOT / args.archive_dir
    archive_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        step(1, "Verify declared version and run full test suite on working source")
        declared = source_version()
        if declared != short:
            raise BuildError(
                f"TLB_CARP_VERSION is {declared!r} in {VERSION_SOURCE} but --version "
                f"gives {short!r}; bump the source constant so the running build "
                f"reports its own version correctly"
            )
        print(f"     TLB_CARP_VERSION={declared} matches --version")
        if args.skip_tests:
            print("     SKIPPED (--skip-tests)")
        else:
            run_suite(ROOT, "working source")

        step(2, "Build PBO from source")
        base_pbo = extract_base_pbo(base_release, tmp_path / "base.pbo")
        pbo_path = tmp_path / PBO_NAME
        cmd = [
            sys.executable, str(ROOT / "tools/pack_pbo.py"),
            "--base-pbo", str(base_pbo),
            "--source-dir", str(ROOT / "addon"),
            "--output", str(pbo_path),
            "--version", args.version,
            "--prefix", PREFIX,
        ]
        for value in DELETED_SQFC_ENTRIES:
            cmd += ["--exclude", value]
        for value in args.exclude:
            cmd += ["--exclude", value]
        for value in args.include:
            cmd += ["--include", value]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stdout + result.stderr)
            raise BuildError("pack_pbo failed")
        print("     " + result.stdout.strip().replace("\n", "\n     "))

        pbo_bytes = pbo_path.read_bytes()
        pbo_digest = sha256(pbo_bytes)

        # The CARP Computer item. Its config is plain text and it has no base PBO, so its
        # entry set is simply the items/ directory.
        items_path = tmp_path / ITEMS_PBO_NAME
        items_bytes = pack_pbo.pack_directory(ROOT / ITEMS_SOURCE, ITEMS_PREFIX, args.version)
        items_path.write_bytes(items_bytes)
        print(f"     {ITEMS_PBO_NAME}: {len(pack_pbo.parse_pbo_header(items_path)[1])} entries, {len(items_bytes)} bytes")

        step(3, "Sign the PBOs")
        # A server running verifySignatures = 2 kicks every client that loads an unsigned
        # mod, so an unsigned release is undeployable rather than merely untidy. Signing
        # here, between the build and the ZIP, is what puts the .bisign files INSIDE the
        # release archive -- signing afterwards would leave the ZIP and the mod folder
        # disagreeing about what shipped.
        #
        # ONE PERSISTENT KEY, not one per version. A versioned key would make every server
        # admin install a new .bikey on every release, which is how a unit ends up running
        # signature checks turned off. The private key lives OUTSIDE the repository: there
        # is then no path by which it reaches a commit or the source ZIP, and anyone
        # holding it could sign a hostile PBO that passes as TLB CARP.
        signatures = []
        bikey = None
        if args.no_sign:
            print("     SKIPPED (--no-sign): this release is UNSIGNED and a server running "
                  "verifySignatures = 2 will kick every client that loads it")
        else:
            key_dir = Path(args.key_dir)
            expected = key_name_for(args.version)
            key_name = args.key_name or expected
            if expected not in key_name:
                raise BuildError(
                    f"--key-name {key_name!r} does not carry version {args.version}. "
                    f"Every release is signed with its own key: expected a name "
                    f"containing {expected!r}. Signing v{args.version} with another "
                    f"version's key is the one mistake this check exists to stop."
                )
            private_key = key_dir / f"{key_name}.biprivatekey"
            public_key = key_dir / f"{key_name}.bikey"
            for needed in (private_key, public_key):
                if not needed.is_file():
                    raise BuildError(
                        f"signing key {needed} not found. Create one once with: "
                        f"cd {key_dir} && DSCreateKey.exe {key_name} -- "
                        f"or pass --no-sign to ship an unsigned release deliberately"
                    )
            dssign = Path(args.tools_dir) / "DSSignFile" / "DSSignFile.exe"
            dscheck = Path(args.tools_dir) / "DSSignFile" / "DSCheckSignatures.exe"
            if not dssign.is_file():
                raise BuildError(f"DSSignFile.exe not found at {dssign}; pass --tools-dir or --no-sign")
            for built in (pbo_path, items_path):
                # DSSignFile drops <pbo>.<keyname>.bisign beside the file it signs.
                result = subprocess.run([str(dssign), str(private_key), str(built)],
                                        capture_output=True, text=True)
                sig = built.with_name(f"{built.name}.{key_name}.bisign")
                if result.returncode != 0 or not sig.is_file():
                    print(result.stdout + result.stderr)
                    raise BuildError(f"signing {built.name} failed")
                signatures.append((sig.name, sig.read_bytes()))
                print(f"     {sig.name} ({sig.stat().st_size} bytes)")
            bikey = (f"{key_name}.bikey", public_key.read_bytes())
            # Verified, not assumed. A signature the engine will reject is worse than none,
            # because the build would claim the deployment blocker was closed.
            if dscheck.is_file():
                # A DEDICATED FOLDER, not tmp_path. DSCheckSignatures walks every PBO it
                # finds, and tmp_path also holds base.pbo -- the previous release extracted
                # to supply the entry set. That one is not ours to sign, and checking it
                # failed the build on the first signed run.
                check_dir = tmp_path / "signcheck"
                check_dir.mkdir(exist_ok=True)
                for built in (pbo_path, items_path):
                    shutil.copy2(built, check_dir / built.name)
                    sig = built.with_name(f"{built.name}.{key_name}.bisign")
                    shutil.copy2(sig, check_dir / sig.name)
                check = subprocess.run([str(dscheck), str(check_dir), str(key_dir)],
                                       capture_output=True, text=True)
                # ITS CONTRACT IS SILENCE. Measured against this exact tool rather than
                # assumed: a good folder prints NOTHING and exits 0; an unsigned PBO gives
                # "No signature found for ..." and exit 1; a missing public key gives "Key
                # not found for signature ..." and exit 2. So the exit code is the verdict
                # and the output is only the reason. Keying on a "Verified" string -- the
                # first thing written here -- fails every good build.
                out = (check.stdout + check.stderr).strip()
                if check.returncode != 0:
                    print("     " + (out or "(no output)"))
                    raise BuildError(
                        f"DSCheckSignatures rejected the signed PBOs (exit {check.returncode})")
                print(f"     DSCheckSignatures: verified against {public_key.name} (exit 0, silent)")

        step(4, "Write release ZIP")
        mod_cpp = read_mod_cpp(args.mod_cpp, base_release, short)
        release_zip = out_dir / f"{MOD_DIR}_v{short}-{args.label}.zip"
        zip_members = [
            (f"{MOD_DIR}/mod.cpp", mod_cpp),
            (f"{MOD_DIR}/addons/{PBO_NAME}", pbo_bytes),
            (f"{MOD_DIR}/addons/{ITEMS_PBO_NAME}", items_bytes),
        ]
        # APL-ND asks for attribution wherever the work is redistributed, and a mod folder
        # is how this one travels: most people who load it will never see the repository.
        # The other TLB mods ship it in the same place.
        licence = ROOT / "LICENSE"
        if licence.is_file():
            zip_members.append((f"{MOD_DIR}/LICENSE", licence.read_bytes()))
        # .bisign beside the PBO it signs; the public .bikey in keys/, which is where a
        # server admin expects to find it and copy it into the server's own Keys folder.
        for name, body in signatures:
            zip_members.append((f"{MOD_DIR}/addons/{name}", body))
        if bikey is not None:
            zip_members.append((f"{MOD_DIR}/keys/{bikey[0]}", bikey[1]))
        write_zip(release_zip, zip_members)
        print(f"     {release_zip.name}")

        step(5, "Write source ZIP")
        source_root = f"TLB_CARP_v{short}-source-and-tests"
        members = []
        for path in iter_source_files():
            members.append((f"{source_root}/{path.relative_to(ROOT).as_posix()}", path.read_bytes()))
        source_zip = archive_dir / f"TLB_CARP_v{short}-source-and-tests.zip"
        write_zip(source_zip, members)
        print(f"     {archive_dir.name}/{source_zip.name} ({len(members)} files)")

        step(6, "Re-run suite from a fresh extraction of the source ZIP")
        if args.skip_tests:
            print("     SKIPPED (--skip-tests)")
        else:
            fresh = tmp_path / "fresh"
            with zipfile.ZipFile(source_zip) as zf:
                zf.extractall(fresh)
            run_suite(fresh / source_root, "fresh extraction")

        step(7, "Verify ZIP integrity")
        for archive in (release_zip, source_zip):
            with zipfile.ZipFile(archive) as zf:
                bad = zf.testzip()
                if bad is not None:
                    raise BuildError(f"corrupt entry {bad} in {archive.name}")
            print(f"     {archive.name}: OK")

        step(8, "Verify PBO version, entry bodies, and SHA-1 trailer against source")
        for built, source in ((pbo_path, ROOT / "addon"), (items_path, ROOT / ITEMS_SOURCE)):
            mismatches = verify_pbo_against_source(built, args.version, source)
            if mismatches:
                for line in mismatches:
                    print(f"     FAIL {line}")
                raise BuildError(f"{len(mismatches)} PBO/source mismatches in {built.name}")
            props, entries = pack_pbo.parse_pbo_header(built)
            print(f"     {built.name}: {len(entries)} entries, version={dict(props)['version']}, trailer OK")

        step(9, "Verify no stale .sqfc shadows a runtime-compiled function")
        problems = verify_no_stale_sqfc()
        if problems:
            for line in problems:
                print(f"     FAIL {line}")
            raise BuildError("source precedence violated")
        print("     clean")

        step(10, "Verify protected calibration assets")
        changed = verify_calibration_unchanged(base_pbo, pbo_path)
        if changed and not args.allow_calibration_change:
            for name in changed:
                print(f"     FAIL calibration asset changed: {name}")
            raise BuildError("calibration changed without --allow-calibration-change")
        if changed:
            for name in changed:
                print(f"     CHANGED (approved): {name}")
        else:
            print("     unchanged vs base release")

        step(11, "Checksums")
        results = []
        for path in (pbo_path, items_path, release_zip, source_zip):
            digest = sha256(path.read_bytes())
            results.append((path.name, digest, path.stat().st_size))
            print(f"     {digest}  {path.name}  ({path.stat().st_size} bytes)")

        if args.expect_pbo_sha256:
            if pbo_digest != args.expect_pbo_sha256:
                raise BuildError(
                    f"PBO digest {pbo_digest} != expected {args.expect_pbo_sha256}"
                )
            print(f"\n     PBO reproduces expected digest exactly.")

        step(12, "Export loose PBOs for Workshop packaging")
        # Asked for 2026-09-21: a Steam Workshop upload keeps a staging folder, and
        # refreshing it by dropping in two files beats re-extracting the mod ZIP every
        # release. Exact runtime names, so they can be copied straight across, and a
        # version folder so two releases cannot collide. NOT at the repo root -- the
        # one-release-ZIP-and-no-loose-PBO rule there is enforced by the next step.
        # Verified against the ZIP rather than trusted: these are the bytes that shipped.
        pbo_out = archive_dir / "pbo" / f"v{short}"
        pbo_out.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(release_zip) as zf:
            shipped = {Path(n).name: zf.read(n) for n in zf.namelist() if n.endswith(".pbo")}
        for built in (pbo_path, items_path):
            body = built.read_bytes()
            if shipped.get(built.name) != body:
                raise BuildError(f"{built.name} differs from the copy inside {release_zip.name}")
            (pbo_out / built.name).write_bytes(body)
            print(f"     {archive_dir.name}/pbo/v{short}/{built.name}  ({len(body)} bytes, matches ZIP)")
        # The signatures go with them: a PBO copied into a server's addons folder without
        # its .bisign is exactly as unloadable as an unsigned one.
        for name, body in signatures:
            (pbo_out / name).write_bytes(body)
            print(f"     {archive_dir.name}/pbo/v{short}/{name}")
        if bikey is not None:
            (pbo_out / bikey[0]).write_bytes(bikey[1])
            print(f"     {archive_dir.name}/pbo/v{short}/{bikey[0]}")

        step(13, "Rotate superseded releases out of the root folder")
        if args.no_rotate:
            print("     SKIPPED (--no-rotate)")
        else:
            moved = rotate_old_releases(out_dir, release_zip, archive_dir)
            for name in moved:
                print(f"     {name} -> {archive_dir.name}/")
            active = release_zips(out_dir)
            if len(active) != 1:
                raise BuildError(
                    f"expected exactly 1 release ZIP at {out_dir}, found {len(active)}"
                )
            print(f"     active release in root: {active[0].name}")

        step(14, "Deploy to Arma mod folder")
        if args.deploy is None:
            print("     skipped (no --deploy); extract the root ZIP to load in game")
        else:
            if not args.no_kill_arma:
                killed = kill_arma()
                if killed:
                    print(f"     closed {', '.join(killed)} so the PBO can be replaced")
            deploy(release_zip, args.deploy)

    print("\nBuild verified. NOT verified by this script: in-engine Arma behavior "
          "(see V0*_RUNTIME_VALIDATION.md).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BuildError as exc:
        # Flush stdout FIRST. Without it the error goes out on stderr while the step
        # log is still buffered on stdout, so the failure prints ABOVE everything it
        # followed -- and `tail` on the output shows a clean-looking build that
        # actually failed. This project has already shipped one "deployed" claim on
        # a build that never landed; the second way to make that mistake ends here.
        sys.stdout.flush()
        print(f"\nBUILD FAILED: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)

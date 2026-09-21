#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

VERSION_METHOD = 0x56657273


def read_cstr(data: bytes, pos: int) -> tuple[bytes, int]:
    end = data.index(b"\0", pos)
    return data[pos:end], end + 1


def parse_pbo_header(path: Path):
    data = path.read_bytes()
    pos = 0
    name, pos = read_cstr(data, pos)
    method, original, reserved, timestamp, size = struct.unpack_from("<IIIII", data, pos)
    pos += 20
    if name or method != VERSION_METHOD:
        raise ValueError("Unsupported PBO header")

    props: list[tuple[str, str]] = []
    while True:
        key, pos = read_cstr(data, pos)
        if not key:
            break
        value, pos = read_cstr(data, pos)
        props.append((key.decode("utf-8"), value.decode("utf-8")))

    entries = []
    while True:
        raw_name, pos = read_cstr(data, pos)
        method, original, reserved, timestamp, size = struct.unpack_from("<IIIII", data, pos)
        pos += 20
        if not raw_name:
            break
        entries.append(
            {
                "name": raw_name.decode("utf-8"),
                "method": method,
                "original": original,
                "reserved": reserved,
                "timestamp": timestamp,
                "size": size,
            }
        )
    return props, entries


def asciiz(value: str) -> bytes:
    return value.encode("utf-8") + b"\0"


def pack_directory(source_dir: Path, prefix: str, version: str) -> bytes:
    """A PBO holding every file under source_dir, for an addon with no base PBO.

    main() fills a previous release's entry set, because the drop computer's config.bin
    cannot be regenerated and the base PBO is the only record of what belongs in it. The
    items addon has a plain-text config.cpp and nothing to inherit, so its entry set is
    simply its directory. Entries are sorted and carry zero timestamps, so the same
    files always pack to the same bytes.
    """
    files = sorted(p for p in source_dir.rglob("*") if p.is_file())
    if not files:
        raise FileNotFoundError(f"nothing to pack under {source_dir}")
    entries = [(p.relative_to(source_dir).as_posix().replace("/", "\\"), p.read_bytes()) for p in files]

    out = bytearray()
    out += b"\0" + struct.pack("<IIIII", VERSION_METHOD, 0, 0, 0, 0)
    for key, value in (("prefix", prefix), ("version", version)):
        out += asciiz(key) + asciiz(value)
    out += b"\0"
    for name, blob in entries:
        out += asciiz(name) + struct.pack("<IIIII", 0, len(blob), 0, 0, len(blob))
    out += b"\0" + struct.pack("<IIIII", 0, 0, 0, 0, 0)
    for _, blob in entries:
        out += blob
    out += b"\0" + hashlib.sha1(out).digest()
    return bytes(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-pbo", type=Path, required=True)
    ap.add_argument("--source-dir", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--version", default="0.1.9.1")
    ap.add_argument("--prefix", default=None,
                    help="Override the PBO header prefix inherited from the base PBO. "
                         "Needed when the addon path itself changes, as it did when "
                         "x/usafdc/addons/drop_computer became x/tlbcarp/addons/"
                         "drop_computer. Must match the paths in CfgFunctions and in "
                         "the fn_postInit compile table.")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--include", action="append", default=[])
    args = ap.parse_args()

    props, entries = parse_pbo_header(args.base_pbo)
    props = [(k, args.version if k == "version" else v) for k, v in props]
    if args.prefix is not None:
        if not any(k == "prefix" for k, _ in props):
            raise ValueError("base PBO has no prefix property to override")
        props = [(k, args.prefix if k == "prefix" else v) for k, v in props]
    excludes = {x.replace("/", "\\").lower() for x in args.exclude}

    selected = []
    selected_names: set[str] = set()
    for entry in entries:
        name = entry["name"]
        lowered = name.lower()
        if lowered in excludes:
            continue
        path = args.source_dir / Path(name.replace("\\", "/"))
        if not path.is_file():
            raise FileNotFoundError(f"Missing source entry: {name} -> {path}")
        blob = path.read_bytes()
        selected.append((entry, blob))
        selected_names.add(lowered)

    for raw_name in args.include:
        name = raw_name.replace("/", "\\")
        lowered = name.lower()
        if lowered in selected_names:
            raise ValueError(f"Included entry already exists in PBO selection: {name}")
        if lowered in excludes:
            raise ValueError(f"Included entry is also excluded: {name}")
        path = args.source_dir / Path(name.replace("\\", "/"))
        if not path.is_file():
            raise FileNotFoundError(f"Missing included source entry: {name} -> {path}")
        blob = path.read_bytes()
        selected.append((
            {
                "name": name,
                "method": 0,
                "original": len(blob),
                "reserved": 0,
                "timestamp": 0,
                "size": len(blob),
            },
            blob,
        ))
        selected_names.add(lowered)

    out = bytearray()
    out += b"\0" + struct.pack("<IIIII", VERSION_METHOD, 0, 0, 0, 0)
    for key, value in props:
        out += asciiz(key) + asciiz(value)
    out += b"\0"

    for entry, blob in selected:
        if entry["method"] != 0:
            raise ValueError(f"Compressed entry unsupported: {entry['name']}")
        out += asciiz(entry["name"])
        out += struct.pack(
            "<IIIII",
            0,
            len(blob),
            entry["reserved"],
            entry["timestamp"],
            len(blob),
        )

    out += b"\0" + struct.pack("<IIIII", 0, 0, 0, 0, 0)
    for _, blob in selected:
        out += blob

    digest = hashlib.sha1(out).digest()
    out += b"\0" + digest
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(out)

    print(f"entries={len(selected)}")
    print(f"version={args.version}")
    print(f"sha1={digest.hex()}")
    print(f"bytes={len(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

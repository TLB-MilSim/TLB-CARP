#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "calibration/model.json"
OUTPUT = ROOT / "addon/functions/generated/fn_getModel.sqf"


def sqf_string(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def sqf_number(value: int | float) -> str:
    if isinstance(value, int):
        return str(value)
    text = repr(float(value))
    if "e" in text.lower():
        text = f"{value:.12f}".rstrip("0").rstrip(".")
    return text


def render(value, indent: int = 0) -> str:
    pad = " " * indent
    child = " " * (indent + 4)
    if isinstance(value, dict):
        if not value:
            return "createHashMap"
        lines = ["createHashMapFromArray ["]
        items = list(value.items())
        for index, (key, item) in enumerate(items):
            rendered = render(item, indent + 4)
            comma = "," if index < len(items) - 1 else ""
            lines.append(f"{child}[{sqf_string(key)}, {rendered}]{comma}")
        lines.append(f"{pad}]")
        return "\n".join(lines)
    if isinstance(value, list):
        return "[" + ", ".join(render(item, 0) for item in value) + "]"
    if isinstance(value, str):
        return sqf_string(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "nil"
    if isinstance(value, (int, float)):
        return sqf_number(value)
    raise TypeError(f"Unsupported JSON value: {type(value)!r}")


def main() -> int:
    model = json.loads(SOURCE.read_text(encoding="utf-8"))
    OUTPUT.write_text(
        "/* generated from calibration/model.json; do not hand edit */\n" + render(model) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

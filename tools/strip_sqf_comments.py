"""Strip comments from an SQF file to make it safe to paste into Arma's debug console.

The console does not run the preprocessor the way `preprocessFileLineNumbers` does, so
comments are not reliably handled there. Stripping them has a second benefit: SQF is
whitespace-insensitive, so a comment-free script still runs correctly even if a paste
collapses the newlines -- whereas a single surviving `//` would swallow everything
after it on the joined line.

String-aware: `//` inside a string literal is content, not a comment. SQF escapes a
double quote by doubling it, and single-quoted strings are also valid, so both quote
styles are tracked and neither is treated as opening a string while inside the other.

Usage:
    python tools/strip_sqf_comments.py <in.sqf> <out.sqf>
"""

from __future__ import annotations

import sys
from pathlib import Path


def strip_comments(text: str) -> str:
    out: list[str] = []
    i, n = 0, len(text)
    quote = ""  # "" outside a string, otherwise the opening quote character
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if quote:
            out.append(ch)
            if ch == quote:
                if nxt == quote:  # doubled quote = escaped quote, still inside
                    out.append(nxt)
                    i += 2
                    continue
                quote = ""
            i += 1
            continue
        if ch in ('"', "'"):
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "/" and nxt == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and nxt == "*":
            i += 2
            while i < n and not (text[i] == "*" and i + 1 < n and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def tidy(text: str) -> str:
    """Drop trailing whitespace and runs of blank lines left behind by stripping."""
    lines = [line.rstrip() for line in text.splitlines()]
    kept: list[str] = []
    for line in lines:
        if not line and (not kept or not kept[-1]):
            continue
        kept.append(line)
    while kept and not kept[-1]:
        kept.pop()
    return "\n".join(kept) + "\n"


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    raw = src.read_text(encoding="utf-8")
    stripped = tidy(strip_comments(raw))
    if "//" in stripped:
        # Only legitimate if it is inside a string; report so it can be eyeballed.
        print("note: '//' survives in output (inside a string literal?)", file=sys.stderr)
    dst.write_text(stripped, encoding="utf-8", newline="\r\n")
    print(f"{src} -> {dst}: {len(raw.splitlines())} lines -> {len(stripped.splitlines())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

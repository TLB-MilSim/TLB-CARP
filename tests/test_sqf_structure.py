from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SQF_ROOT = ROOT / "addon/functions"


def strip_comments_and_strings(text: str) -> str:
    out = []
    i = 0
    n = len(text)
    in_string = False
    in_line_comment = False
    in_block_comment = False
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
                out.append(ch)
            else:
                out.append(" ")
            i += 1
            continue
        if in_block_comment:
            if ch == "*" and nxt == "/":
                out.extend("  ")
                i += 2
                in_block_comment = False
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if in_string:
            # SQF escapes an embedded quote by doubling it.
            if ch == '"' and nxt == '"':
                out.extend("  ")
                i += 2
                continue
            if ch == '"':
                in_string = False
            out.append(" ")
            i += 1
            continue
        if ch == "/" and nxt == "/":
            out.extend("  ")
            i += 2
            in_line_comment = True
            continue
        if ch == "/" and nxt == "*":
            out.extend("  ")
            i += 2
            in_block_comment = True
            continue
        if ch == '"':
            in_string = True
            out.append(" ")
            i += 1
            continue
        out.append(ch)
        i += 1
    if in_string:
        raise AssertionError("unterminated string")
    if in_block_comment:
        raise AssertionError("unterminated block comment")
    return "".join(out)


def assert_balanced(path: Path) -> None:
    text = strip_comments_and_strings(path.read_text(encoding="utf-8"))
    pairs = {")": "(", "]": "[", "}": "{"}
    opens = set(pairs.values())
    stack = []
    for line_no, line in enumerate(text.splitlines(), 1):
        for col, ch in enumerate(line, 1):
            if ch in opens:
                stack.append((ch, line_no, col))
            elif ch in pairs:
                if not stack or stack[-1][0] != pairs[ch]:
                    raise AssertionError(f"{path}: unmatched {ch} at {line_no}:{col}")
                stack.pop()
    if stack:
        ch, line_no, col = stack[-1]
        raise AssertionError(f"{path}: unclosed {ch} from {line_no}:{col}")


class SqfStructureTests(unittest.TestCase):
    def test_all_sqf_files_have_balanced_structure(self):
        files = sorted(SQF_ROOT.rglob("*.sqf"))
        self.assertGreater(len(files), 0)
        for path in files:
            with self.subTest(path=path.relative_to(ROOT)):
                assert_balanced(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)

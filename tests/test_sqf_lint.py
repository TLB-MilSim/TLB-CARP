"""Cheap lint for non-SQF tokens used as commands.

`test_sqf_structure.py` only checks bracket balance, so an invalid command name
compiles fine at pack time and fails at runtime with "Error Missing ;". That is
how `radians` -- a Python-ism, and unnecessary since SQF trig already takes
degrees -- shipped in v0.4.11's parallel bench.

This cannot validate SQF command names in general (that needs a command
database). It is a blocklist of constructs from other languages that have
actually leaked in or plausibly would.
"""
from pathlib import Path
import unittest

from tests.test_sqf_structure import strip_comments_and_strings

ROOT = Path(__file__).resolve().parents[1]
SQF_ROOT = ROOT / "addon/functions"

# token -> why it is wrong / what to use instead
BANNED = {
    "radians": "SQF trig takes degrees; there is no 'radians' command",
    "degrees": "SQF trig takes degrees; there is no 'degrees' command",
    "math.": "Python module reference",
    "elif": "not SQF; use else { if ... }",
    "None": "Python literal; SQF uses nil / objNull",
    "True": "Python literal; SQF uses true",
    "False": "Python literal; SQF uses false",
}


class SqfLintTests(unittest.TestCase):
    def test_no_foreign_language_tokens_in_sqf(self):
        offences = []
        for path in sorted(SQF_ROOT.rglob("*.sqf")):
            code = strip_comments_and_strings(path.read_text(encoding="utf-8"))
            for token, why in BANNED.items():
                if token in code:
                    line = code[: code.index(token)].count("\n") + 1
                    offences.append(f"{path.relative_to(ROOT).as_posix()}:{line} '{token}' -- {why}")
        self.assertEqual(offences, [], "non-SQF tokens found:\n  " + "\n  ".join(offences))

    def test_lint_actually_detects_a_planted_offence(self):
        """A lint that never fires is decoration."""
        sample = "private _r = radians _heading;\n"
        self.assertIn("radians", strip_comments_and_strings(sample))

    def test_lint_ignores_comments_and_strings(self):
        sample = '// radians is not SQF\nprivate _s = "radians";\n'
        self.assertNotIn("radians", strip_comments_and_strings(sample))


if __name__ == "__main__":
    unittest.main(verbosity=2)

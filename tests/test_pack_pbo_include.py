from pathlib import Path
import hashlib
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKER = ROOT / "tools/pack_pbo.py"
VERSION_METHOD = 0x56657273


def cstr(text: str) -> bytes:
    return text.encode("utf-8") + b"\0"


def write_minimal_pbo(path: Path, source_name: str, blob: bytes):
    out = bytearray()
    out += b"\0" + struct.pack("<IIIII", VERSION_METHOD, 0, 0, 0, 0)
    out += cstr("prefix") + cstr("x\\test")
    out += cstr("version") + cstr("base")
    out += b"\0"
    out += cstr(source_name) + struct.pack("<IIIII", 0, len(blob), 0, 0, len(blob))
    out += b"\0" + struct.pack("<IIIII", 0, 0, 0, 0, 0)
    out += blob
    out += b"\0" + hashlib.sha1(out).digest()
    path.write_bytes(out)


def parse_names(path: Path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("pack_pbo", PACKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _, entries = module.parse_pbo_header(path)
    return [entry["name"] for entry in entries]


class PackPboIncludeTests(unittest.TestCase):
    def test_include_adds_source_file_not_present_in_base_pbo(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source"
            source.mkdir()
            (source / "existing.sqf").write_text("existing", encoding="utf-8")
            extra = source / "functions/solver/fn_empiricalCanopyC17.sqf"
            extra.parent.mkdir(parents=True)
            extra.write_text("empirical", encoding="utf-8")
            base = root / "base.pbo"
            out = root / "out.pbo"
            write_minimal_pbo(base, "existing.sqf", b"existing")
            proc = subprocess.run([
                "python3", str(PACKER),
                "--base-pbo", str(base),
                "--source-dir", str(source),
                "--output", str(out),
                "--version", "0.2.0.0",
                "--include", "functions/solver/fn_empiricalCanopyC17.sqf",
            ], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("functions\\solver\\fn_empiricalCanopyC17.sqf", parse_names(out))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class DeployKillsArmaTests(unittest.TestCase):
    """Arma holds addons/*.pbo open while running, so deploying into a live mod
    folder is refused. The user asked for the release process to close Arma itself
    rather than telling them to do it every time."""

    @classmethod
    def setUpClass(cls):
        cls.src = (Path(__file__).resolve().parents[1] / "tools/build_release.py").read_text(encoding="utf-8")

    def test_kills_arma_before_copying(self):
        self.assertIn("def kill_arma(", self.src)
        self.assertIn("taskkill", self.src)
        self.assertIn("arma3_x64.exe", self.src)
        self.assertIn("arma3launcher.exe", self.src)

    def test_waits_for_the_handle_to_release(self):
        self.assertIn("still running after", self.src)

    def test_enabled_by_default_with_an_opt_out(self):
        self.assertIn('"--no-kill-arma"', self.src)
        self.assertIn("if not args.no_kill_arma:", self.src)

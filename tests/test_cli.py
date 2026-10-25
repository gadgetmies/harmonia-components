"""manifest.py / sign.py / verify.py end to end on a fake release (no network)."""
import contextlib
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests._util import ROOT, fake_components, write_payload, write_source_stage
from harmonia_components import archive, manifest, signing


def _load(script):
    spec = importlib.util.spec_from_file_location(script, ROOT / f"{script}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.dist = root / "release"
        self.dist.mkdir()
        comp = fake_components()["ffmpeg"]
        stage = root / "stage"
        write_payload(stage, "ffmpeg", "linux-x86_64")
        archive.make_tar_gz(stage, self.dist / comp.archive_name("linux-x86_64"))
        src = root / "src"
        write_source_stage(src)
        archive.make_tar_gz(src, self.dist / comp.source_archive_name)
        data = manifest.dumps(manifest.assemble("2026.10.25.1", self.dist, {"ffmpeg": comp}))
        (self.dist / manifest.MANIFEST).write_bytes(data)
        self.seed, self.pub = signing.generate()
        self.keys = root / "keys"
        self.keys.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, script, argv, env=None):
        out = io.StringIO()
        with mock.patch.dict(os.environ, env or {}), contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(io.StringIO()):
            code = _load(script).main(argv)
        return code, out.getvalue()

    def test_sign_then_verify_with_keys_dir(self):
        code, out = self._run("sign", [str(self.dist), "--key-id", "harmonia-components-1"],
                              {"HARMONIA_COMPONENTS_SIGNING_KEY": self.seed})
        self.assertEqual(code, 0)
        self.assertIn(self.pub, out)
        self.assertEqual((self.dist / "KEY_ID").read_text().strip(), "harmonia-components-1")
        (self.keys / "harmonia-components-1.pub").write_text(self.pub + "\n")
        code, out = self._run("verify", [str(self.dist), "--keys-dir", str(self.keys)])
        self.assertEqual(code, 0)
        self.assertIn("OK release 2026.10.25.1", out)

    def test_verify_rejects_key_id_without_pub_file(self):
        self._run("sign", [str(self.dist), "--key-id", "harmonia-components-2"],
                  {"HARMONIA_COMPONENTS_SIGNING_KEY": self.seed})
        (self.keys / "harmonia-components-1.pub").write_text(self.pub + "\n")
        code, _ = self._run("verify", [str(self.dist), "--keys-dir", str(self.keys)])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from tests._util import fake_components, write_payload, write_source_stage
from harmonia_components import archive, manifest, signing
from harmonia_components.fetch import sha256_file


class ManifestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.dist = self.root / "dist"
        self.dist.mkdir()
        self.comps = fake_components()
        for name, platforms in (("ffmpeg", ["macos-arm64", "linux-x86_64"]), ("taglib", ["windows-x86_64"])):
            comp = self.comps[name]
            for p in platforms:
                stage = self.root / "stage" / name / p
                write_payload(stage, name, p)
                archive.make_tar_gz(stage, self.dist / comp.archive_name(p))
            src = self.root / "stage" / name / "source"
            write_source_stage(src)
            archive.make_tar_gz(src, self.dist / comp.source_archive_name)

    def tearDown(self):
        self.tmp.cleanup()

    def assemble(self):
        return manifest.assemble("dev.2026.10.20.1", self.dist, self.comps, created_at="2026-10-20T12:00:00Z")

    def test_assembles_schema_1(self):
        m = self.assemble()
        self.assertEqual(m["schema"], 1)
        self.assertEqual(m["release"], "dev.2026.10.20.1")
        self.assertEqual(m["created_at"], "2026-10-20T12:00:00Z")
        names = [c["name"] for c in m["components"]]
        self.assertEqual(names, ["ffmpeg", "taglib"])
        ff = m["components"][0]
        self.assertEqual(sorted(ff["builds"]), ["linux-x86_64", "macos-arm64"])
        self.assertEqual(ff["provides"], {"executables": ["ffmpeg", "ffprobe"], "libraries": []})
        entry = ff["builds"]["macos-arm64"]
        path = self.dist / entry["file"]
        self.assertEqual(entry["file"], "ffmpeg-7.1.5-macos-arm64.tar.gz")
        self.assertEqual(entry["sha256"], sha256_file(path))
        self.assertEqual(entry["size"], path.stat().st_size)
        self.assertEqual(ff["source"]["file"], "ffmpeg-7.1.5-source.tar.gz")
        self.assertEqual(m["components"][1]["provides"]["libraries"], ["tag_c"])

    def test_dumps_is_utf8_json_with_newline(self):
        data = manifest.dumps(self.assemble())
        self.assertTrue(data.endswith(b"\n"))
        self.assertEqual(json.loads(data.decode("utf-8"))["schema"], 1)

    def test_builds_without_source_archive_rejected(self):
        (self.dist / self.comps["taglib"].source_archive_name).unlink()
        with self.assertRaisesRegex(manifest.ManifestError, "source archive"):
            self.assemble()

    def test_bad_release_id(self):
        for bad in ("", "../x", "a/b", "x" * 65, ".hidden"):
            with self.subTest(bad=bad), self.assertRaises(manifest.ManifestError):
                manifest.validate_release_id(bad)

    def _release(self):
        seed, pub = signing.generate()
        data = manifest.dumps(self.assemble())
        (self.dist / manifest.MANIFEST).write_bytes(data)
        (self.dist / manifest.SIGNATURE).write_text(signing.sign(data, seed) + "\n")
        (self.dist / manifest.KEY_ID_FILE).write_text("harmonia-components-test\n")
        return {"harmonia-components-test": pub}

    def test_sign_verify_round_trip(self):
        keys = self._release()
        m = manifest.verify_release(self.dist, keys)
        self.assertEqual(m["release"], "dev.2026.10.20.1")

    def test_tampered_manifest_fails_signature(self):
        keys = self._release()
        data = (self.dist / manifest.MANIFEST).read_bytes().replace(b"7.1.5", b"7.1.6", 1)
        (self.dist / manifest.MANIFEST).write_bytes(data)
        with self.assertRaises(signing.SignatureError):
            manifest.verify_release(self.dist, keys)

    def test_tampered_file_fails_hash(self):
        keys = self._release()
        target = self.dist / "taglib-2.3.2-windows-x86_64.tar.gz"
        data = bytearray(target.read_bytes())
        data[len(data) // 2] ^= 0xFF  # same size, different content
        target.write_bytes(bytes(data))
        with self.assertRaisesRegex(manifest.ManifestError, "sha256"):
            manifest.verify_release(self.dist, keys)

    def test_missing_file_fails(self):
        keys = self._release()
        (self.dist / "ffmpeg-7.1.5-linux-x86_64.tar.gz").unlink()
        with self.assertRaisesRegex(manifest.ManifestError, "missing"):
            manifest.verify_release(self.dist, keys)

    def test_untrusted_key_id(self):
        self._release()
        _, other = signing.generate()
        with self.assertRaisesRegex(manifest.ManifestError, "not trusted"):
            manifest.verify_release(self.dist, {"someone-else": other})

    def test_wrong_key_for_id(self):
        self._release()
        _, other = signing.generate()
        with self.assertRaises(signing.SignatureError):
            manifest.verify_release(self.dist, {"harmonia-components-test": other})


class SigningTest(unittest.TestCase):
    def test_round_trip_and_formats(self):
        import base64

        seed, pub = signing.generate()
        self.assertEqual(len(base64.b64decode(seed)), 32)
        self.assertEqual(len(base64.b64decode(pub)), 32)
        self.assertEqual(signing.public_key_of(seed), pub)
        sig = signing.sign(b"hello", seed)
        self.assertEqual(len(base64.b64decode(sig)), 64)
        self.assertTrue(sig.endswith("=="))  # standard, padded base64
        signing.verify(b"hello", sig, pub)
        with self.assertRaises(signing.SignatureError):
            signing.verify(b"hellO", sig, pub)

    def test_rfc8032_vector(self):
        # RFC 8032 section 7.1, TEST 1 (empty message).
        import base64

        seed = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
        pub = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
        expected = bytes.fromhex(
            "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
        )
        seed_b64 = base64.b64encode(seed).decode()
        self.assertEqual(signing.public_key_of(seed_b64), base64.b64encode(pub).decode())
        self.assertEqual(base64.b64decode(signing.sign(b"", seed_b64)), expected)

    def test_bad_key_material(self):
        with self.assertRaises(signing.SignatureError):
            signing.sign(b"x", "not base64!!")
        with self.assertRaises(signing.SignatureError):
            signing.sign(b"x", "AAAA")


if __name__ == "__main__":
    unittest.main()

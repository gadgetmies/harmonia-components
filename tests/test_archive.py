import io
import os
import tarfile
import tempfile
import unittest
from pathlib import Path

from tests._util import write_payload, write_source_stage
from harmonia_components import archive
from harmonia_components.platforms import PLATFORMS


def _tar_with(members):
    """Build TarInfo objects from (name, type, linkname, mode) tuples."""
    infos = []
    for name, kind, link, mode in members:
        ti = tarfile.TarInfo(name)
        ti.type = kind
        ti.linkname = link
        ti.mode = mode
        infos.append(ti)
    return infos


class BinaryLayoutTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_every_component_platform_round_trips(self):
        for component in ("ffmpeg", "rubberband", "taglib"):
            for platform in PLATFORMS:
                with self.subTest(component=component, platform=platform):
                    stage = self.dir / component / platform
                    write_payload(stage, component, platform)
                    out = archive.make_tar_gz(stage, self.dir / f"{component}-{platform}.tar.gz")
                    archive.check_binary_layout(component, platform, archive.members(out))

    def test_no_top_level_directory(self):
        stage = self.dir / "s"
        write_payload(stage / "ffmpeg-7.1.5", "ffmpeg", "linux-x86_64")
        out = archive.make_tar_gz(stage, self.dir / "x.tar.gz")
        with self.assertRaises(archive.LayoutError):
            archive.check_binary_layout("ffmpeg", "linux-x86_64", archive.members(out))

    def test_missing_build_info_and_licenses(self):
        stage = self.dir / "s"
        write_payload(stage, "rubberband", "macos-arm64")
        (stage / "BUILD-INFO.txt").unlink()
        out = archive.make_tar_gz(stage, self.dir / "x.tar.gz")
        with self.assertRaisesRegex(archive.LayoutError, "BUILD-INFO"):
            archive.check_binary_layout("rubberband", "macos-arm64", archive.members(out))

    def test_windows_taglib_needs_dlls_in_bin(self):
        stage = self.dir / "s"
        write_payload(stage, "taglib", "linux-x86_64")
        out = archive.make_tar_gz(stage, self.dir / "x.tar.gz")
        with self.assertRaises(archive.LayoutError):
            archive.check_binary_layout("taglib", "windows-x86_64", archive.members(out))

    def test_executable_bit_preserved_and_required(self):
        stage = self.dir / "s"
        write_payload(stage, "ffmpeg", "linux-arm64")
        out = archive.make_tar_gz(stage, self.dir / "x.tar.gz")
        modes = {m.name: m.mode for m in archive.members(out)}
        self.assertEqual(modes["bin/ffmpeg"] & 0o111, 0o111)
        (stage / "bin" / "ffprobe").chmod(0o644)
        out = archive.make_tar_gz(stage, self.dir / "y.tar.gz")
        with self.assertRaisesRegex(archive.LayoutError, "not executable"):
            archive.check_binary_layout("ffmpeg", "linux-arm64", archive.members(out))

    def test_relative_symlinks_kept(self):
        stage = self.dir / "s"
        write_payload(stage, "taglib", "macos-arm64")
        os.symlink("libtag_c.dylib", stage / "lib" / "libtag_c.2.dylib")
        out = archive.make_tar_gz(stage, self.dir / "x.tar.gz")
        links = {m.name: m.linkname for m in archive.members(out) if m.issym()}
        self.assertEqual(links, {"lib/libtag_c.2.dylib": "libtag_c.dylib"})
        archive.check_binary_layout("taglib", "macos-arm64", archive.members(out))

    def test_deterministic(self):
        stage = self.dir / "s"
        write_payload(stage, "ffmpeg", "macos-arm64")
        a = archive.make_tar_gz(stage, self.dir / "a.tar.gz").read_bytes()
        os.utime(stage / "BUILD-INFO.txt", (1, 1))
        b = archive.make_tar_gz(stage, self.dir / "b.tar.gz").read_bytes()
        self.assertEqual(a, b)


class SafetyTest(unittest.TestCase):
    def test_rejects_unsafe_members(self):
        bad_sets = {
            "absolute": [("/etc/passwd", tarfile.REGTYPE, "", 0o644)],
            "dotdot": [("bin/../../x", tarfile.REGTYPE, "", 0o644)],
            "abs link": [("bin/x", tarfile.SYMTYPE, "/usr/bin/ffmpeg", 0o777)],
            "escaping link": [("lib/x", tarfile.SYMTYPE, "../../y", 0o777)],
            "dangling link": [("lib/x", tarfile.SYMTYPE, "nope", 0o777)],
            "hard link": [("lib/a", tarfile.REGTYPE, "", 0o644), ("lib/b", tarfile.LNKTYPE, "lib/a", 0o644)],
            "device": [("dev", tarfile.CHRTYPE, "", 0o644)],
            "windows path": [("C:/x", tarfile.REGTYPE, "", 0o644)],
        }
        for label, members in bad_sets.items():
            with self.subTest(label), self.assertRaises(archive.LayoutError):
                archive.check_safe(_tar_with(members))

    def test_accepts_in_archive_link(self):
        archive.check_safe(_tar_with([("lib/a.so.2", tarfile.REGTYPE, "", 0o755), ("lib/a.so", tarfile.SYMTYPE, "a.so.2", 0o777)]))


class SourceLayoutTest(unittest.TestCase):
    def test_source_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp) / "s"
            write_source_stage(stage)
            out = archive.make_tar_gz(stage, Path(tmp) / "src.tar.gz")
            archive.check_source_layout(archive.members(out), ["fake-1.0.tar.gz"])
            with self.assertRaisesRegex(archive.LayoutError, "missing upstream/other"):
                archive.check_source_layout(archive.members(out), ["other-2.tar.xz"])
            (stage / "changes.diff").unlink()
            out = archive.make_tar_gz(stage, Path(tmp) / "src2.tar.gz")
            with self.assertRaisesRegex(archive.LayoutError, "changes.diff"):
                archive.check_source_layout(archive.members(out))


if __name__ == "__main__":
    unittest.main()

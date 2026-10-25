import unittest

from tests import _util  # noqa: F401
from harmonia_components import platforms


class PlatformIdTest(unittest.TestCase):
    def test_normalises_os_and_arch(self):
        cases = {
            ("Darwin", "arm64"): "macos-arm64",
            ("Darwin", "x86_64"): "macos-x86_64",
            ("Linux", "aarch64"): "linux-arm64",
            ("Linux", "x86_64"): "linux-x86_64",
            ("Windows", "AMD64"): "windows-x86_64",
            ("MINGW64_NT-10.0-26100", "x86_64"): "windows-x86_64",
            ("win32", "amd64"): "windows-x86_64",
        }
        for (system, machine), expected in cases.items():
            with self.subTest(system=system, machine=machine):
                self.assertEqual(platforms.platform_id(system, machine), expected)

    def test_rejects_unknown(self):
        for system, machine in [("FreeBSD", "amd64"), ("Linux", "riscv64"), ("Windows", "ARM64")]:
            with self.subTest(system=system, machine=machine), self.assertRaises(platforms.UnknownPlatform):
                platforms.platform_id(system, machine)

    def test_current_platform_is_known(self):
        self.assertIn(platforms.current_platform(), platforms.PLATFORMS)

    def test_exe_name(self):
        self.assertEqual(platforms.exe_name("windows-x86_64", "ffmpeg"), "ffmpeg.exe")
        self.assertEqual(platforms.exe_name("linux-arm64", "ffmpeg"), "ffmpeg")

    def test_validate(self):
        with self.assertRaises(platforms.UnknownPlatform):
            platforms.validate("macos-universal")


if __name__ == "__main__":
    unittest.main()

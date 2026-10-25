"""Platform ids: ``<os>-<arch>``, os in {macos, windows, linux}, arch in
{arm64, x86_64}. Same normalisation the Harmonia desktop app uses."""
from __future__ import annotations

import platform as _platform

PLATFORMS = (
    "macos-arm64",
    "macos-x86_64",
    "windows-x86_64",
    "linux-x86_64",
    "linux-arm64",
)

_OS = {
    "darwin": "macos",
    "macos": "macos",
    "macosx": "macos",
    "osx": "macos",
    "windows": "windows",
    "win32": "windows",
    "cygwin": "windows",
    "msys": "windows",
    "linux": "linux",
}

_ARCH = {
    "arm64": "arm64",
    "aarch64": "arm64",
    "armv8": "arm64",
    "x86_64": "x86_64",
    "amd64": "x86_64",
    "x64": "x86_64",
}


class UnknownPlatform(ValueError):
    pass


def normalise_os(name: str) -> str:
    key = name.strip().lower()
    for prefix in ("mingw", "msys", "cygwin"):
        if key.startswith(prefix):
            return "windows"
    try:
        return _OS[key]
    except KeyError:
        raise UnknownPlatform(f"unsupported operating system: {name!r}") from None


def normalise_arch(name: str) -> str:
    try:
        return _ARCH[name.strip().lower()]
    except KeyError:
        raise UnknownPlatform(f"unsupported architecture: {name!r}") from None


def platform_id(system: str, machine: str) -> str:
    pid = f"{normalise_os(system)}-{normalise_arch(machine)}"
    if pid not in PLATFORMS:
        raise UnknownPlatform(f"unsupported platform: {pid}")
    return pid


def current_platform() -> str:
    return platform_id(_platform.system(), _platform.machine())


def validate(pid: str) -> str:
    if pid not in PLATFORMS:
        raise UnknownPlatform(f"unknown platform id {pid!r}; expected one of {', '.join(PLATFORMS)}")
    return pid


def os_of(pid: str) -> str:
    return validate(pid).split("-", 1)[0]


def arch_of(pid: str) -> str:
    return validate(pid).split("-", 1)[1]


def exe_name(pid: str, name: str) -> str:
    return name + ".exe" if os_of(pid) == "windows" else name

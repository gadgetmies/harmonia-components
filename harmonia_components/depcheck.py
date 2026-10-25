"""Check that a built binary links only system libraries (contract: static
dependencies; Linux statically linked except glibc)."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Iterable, List

from .platforms import os_of

_LINUX_ALLOWED = re.compile(
    r"^(linux-vdso\.so\.1|linux-gate\.so\.1|ld-linux[-\w.]*\.so\.\d+|libc\.so\.6|libm\.so\.6|"
    r"libpthread\.so\.0|libdl\.so\.2|librt\.so\.1|libmvec\.so\.1)$"
)
_WINDOWS_ALLOWED = {
    "kernel32.dll", "user32.dll", "advapi32.dll", "shell32.dll", "ole32.dll", "oleaut32.dll",
    "ws2_32.dll", "bcrypt.dll", "secur32.dll", "psapi.dll", "shlwapi.dll", "gdi32.dll",
    "msvcrt.dll", "ucrtbase.dll", "ntdll.dll", "winmm.dll", "crypt32.dll",
}


class DependencyError(RuntimeError):
    pass


def parse_otool(text: str) -> List[str]:
    """Dependent library paths from ``otool -L`` (first line is the file)."""
    deps = []
    for line in text.splitlines()[1:]:
        line = line.strip()
        if line:
            deps.append(line.split(" (", 1)[0])
    return deps


def parse_readelf_needed(text: str) -> List[str]:
    return re.findall(r"\(NEEDED\)\s+Shared library: \[([^\]]+)\]", text)


def parse_objdump_dlls(text: str) -> List[str]:
    return [m.strip() for m in re.findall(r"DLL Name:\s*(\S+)", text)]


def disallowed(platform: str, deps: Iterable[str], own: Iterable[str] = ()) -> List[str]:
    """Return the deps that are neither system libraries nor in ``own`` (the
    archive's own libraries, e.g. libtag for libtag_c)."""
    own = set(own)
    bad = []
    osname = os_of(platform)
    for d in deps:
        base = d.replace("\\", "/").rsplit("/", 1)[-1]
        if osname == "macos":
            if d.startswith(("/usr/lib/", "/System/Library/")):
                continue
            # the archive's own dylibs must load relative to the loader
            if d.startswith(("@rpath/", "@loader_path/")) and base in own:
                continue
            bad.append(d)
            continue
        if base in own:
            continue
        if osname == "linux":
            if _LINUX_ALLOWED.match(base):
                continue
        elif base.lower() in _WINDOWS_ALLOWED or base.lower().startswith("api-ms-win-"):
            continue
        bad.append(d)
    return bad


def linked_libraries(platform: str, path: Path) -> List[str]:
    osname = os_of(platform)
    if osname == "macos":
        out = subprocess.run(["otool", "-L", str(path)], check=True, capture_output=True, text=True).stdout
        deps = parse_otool(out)
        ident = subprocess.run(["otool", "-D", str(path)], check=True, capture_output=True, text=True).stdout
        ids = [line.strip() for line in ident.splitlines()[1:] if line.strip()]
        # a dylib lists its own install name first
        return [d for d in deps if d not in ids]
    if osname == "linux":
        out = subprocess.run(["readelf", "-d", str(path)], check=True, capture_output=True, text=True).stdout
        return parse_readelf_needed(out)
    out = subprocess.run(["objdump", "-p", str(path)], check=True, capture_output=True, text=True).stdout
    return parse_objdump_dlls(out)


def check(platform: str, path: Path, own: Iterable[str] = ()) -> List[str]:
    deps = linked_libraries(platform, path)
    bad = disallowed(platform, deps, own)
    if bad:
        raise DependencyError(f"{path.name} links non-system libraries: {', '.join(bad)}")
    return deps

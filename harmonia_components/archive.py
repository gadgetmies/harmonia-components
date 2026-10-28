"""Deterministic tar.gz creation and the archive layout rules of the contract.

Binary archive (no top-level directory)::

    bin/ffmpeg[.exe] bin/ffprobe[.exe]     ffmpeg
    bin/rubberband[.exe]                    rubberband
    lib/libtag_c.<so|dylib>, lib/libtag.*   taglib (Windows: bin/libtag_c.dll, bin/libtag.dll)
    licenses/<FILES>
    BUILD-INFO.txt

Source archive: ``upstream/*.tar.*``, ``build/``, ``CONFIGURE.txt``, ``changes.diff``.
"""
from __future__ import annotations

import gzip
import io
import os
import posixpath
import tarfile
from pathlib import Path
from typing import Iterable, List, Optional

from .platforms import exe_name, os_of

# Fixed metadata so the same inputs give byte-identical archives.
_EPOCH = int(os.environ.get("SOURCE_DATE_EPOCH", "1767225600"))  # 2026-01-01


class LayoutError(ValueError):
    pass


def _walk(root: Path) -> List[Path]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        d = Path(dirpath)
        for name in sorted(dirnames):
            if (d / name).is_symlink():
                out.append(d / name)
        for name in sorted(filenames):
            out.append(d / name)
    return sorted(out, key=lambda p: p.relative_to(root).as_posix())


def make_tar_gz(src_dir: Path, out_path: Path) -> Path:
    """Pack the CONTENTS of ``src_dir`` (no top-level dir), preserving POSIX
    modes and relative symlinks; owner/mtime normalised."""
    src_dir = Path(src_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for path in _walk(src_dir):
            arc = path.relative_to(src_dir).as_posix()
            info = tarfile.TarInfo(arc)
            info.mtime = _EPOCH
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            if path.is_symlink():
                info.type = tarfile.SYMTYPE
                info.linkname = os.readlink(path).replace("\\", "/")
                info.mode = 0o777
                tar.addfile(info)
                continue
            st = path.stat()
            mode = st.st_mode & 0o777
            if os.name == "nt":  # no exec bits on Windows file systems
                mode = 0o755 if arc.startswith("bin/") or arc.endswith((".sh", ".py")) else 0o644
            info.mode = mode
            info.size = st.st_size
            with open(path, "rb") as fh:
                tar.addfile(info, fh)
    with open(out_path, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as gz:
            gz.write(buf.getvalue())
    return out_path


def members(archive: Path) -> List[tarfile.TarInfo]:
    with tarfile.open(archive, "r:gz") as tar:
        return tar.getmembers()


def check_safe(infos: Iterable[tarfile.TarInfo]) -> None:
    """No absolute paths, no ``..``, links only to targets inside the archive."""
    names = set()
    infos = list(infos)
    for m in infos:
        names.add(posixpath.normpath(m.name))
    for m in infos:
        name = m.name
        if name.startswith("/") or "\\" in name or (len(name) > 1 and name[1] == ":"):
            raise LayoutError(f"absolute or non-POSIX path: {name}")
        norm = posixpath.normpath(name)
        if norm == ".." or norm.startswith("../"):
            raise LayoutError(f"path escapes the archive: {name}")
        if m.islnk():
            raise LayoutError(f"hard links are not allowed: {name}")
        if m.issym():
            if m.linkname.startswith("/"):
                raise LayoutError(f"absolute symlink: {name} -> {m.linkname}")
            target = posixpath.normpath(posixpath.join(posixpath.dirname(norm), m.linkname))
            if target == ".." or target.startswith("../"):
                raise LayoutError(f"symlink escapes the archive: {name} -> {m.linkname}")
            if target not in names:
                raise LayoutError(f"dangling symlink: {name} -> {m.linkname}")
        elif not (m.isfile() or m.isdir()):
            raise LayoutError(f"unsupported member type: {name}")


def required_payload(component: str, platform: str) -> List[str]:
    """Files (by archive path) a binary archive MUST contain."""
    osname = os_of(platform)
    if component == "ffmpeg":
        return [f"bin/{exe_name(platform, 'ffmpeg')}", f"bin/{exe_name(platform, 'ffprobe')}"]
    if component == "rubberband":
        return [f"bin/{exe_name(platform, 'rubberband')}"]
    if component == "taglib":
        if osname == "windows":
            # MinGW's names; libtag_c.dll imports "libtag.dll" by that name.
            return ["bin/libtag_c.dll", "bin/libtag.dll"]
        ext = "dylib" if osname == "macos" else "so"
        return [f"lib/libtag_c.{ext}"]
    raise LayoutError(f"unknown component {component!r}")


def check_binary_layout(component: str, platform: str, infos: Iterable[tarfile.TarInfo]) -> None:
    infos = list(infos)
    check_safe(infos)
    names = {posixpath.normpath(m.name): m for m in infos}
    for req in required_payload(component, platform) + ["BUILD-INFO.txt"]:
        if req not in names:
            raise LayoutError(f"{component} {platform}: missing {req}")
    if not any(n.startswith("licenses/") and names[n].isfile() for n in names):
        raise LayoutError(f"{component} {platform}: no licence texts under licenses/")
    allowed_top = {"bin", "lib", "licenses", "BUILD-INFO.txt"}
    for n in names:
        top = n.split("/", 1)[0]
        if top not in allowed_top:
            raise LayoutError(f"{component} {platform}: unexpected top-level entry {top!r}")
    if component == "taglib" and os_of(platform) != "windows":
        ext = "dylib" if os_of(platform) == "macos" else "so"
        if not any(posixpath.basename(n).startswith("libtag.") and ext in n for n in names):
            raise LayoutError(f"taglib {platform}: missing lib/libtag.{ext}*")
    if os_of(platform) != "windows":
        for req in required_payload(component, platform):
            m = names[req]
            if m.isfile() and req.startswith("bin/") and not (m.mode & 0o111):
                raise LayoutError(f"{component} {platform}: {req} is not executable")


def check_source_layout(infos: Iterable[tarfile.TarInfo], upstream_files: Optional[List[str]] = None) -> None:
    infos = list(infos)
    check_safe(infos)
    names = {posixpath.normpath(m.name) for m in infos}
    for req in ("CONFIGURE.txt", "changes.diff"):
        if req not in names:
            raise LayoutError(f"source archive: missing {req}")
    if not any(n.startswith("build/") for n in names):
        raise LayoutError("source archive: missing build/ (our build scripts)")
    ups = sorted(n for n in names if n.startswith("upstream/"))
    if not any(".tar." in n for n in ups):
        raise LayoutError("source archive: no upstream/*.tar.* tarballs")
    for f in upstream_files or []:
        if f"upstream/{f}" not in names:
            raise LayoutError(f"source archive: missing upstream/{f}")
    allowed_top = {"upstream", "build", "CONFIGURE.txt", "changes.diff"}
    for n in names:
        if n.split("/", 1)[0] not in allowed_top:
            raise LayoutError(f"source archive: unexpected top-level entry {n!r}")


def read_member(archive: Path, name: str) -> bytes:
    with tarfile.open(archive, "r:gz") as tar:
        fh = tar.extractfile(name)
        if fh is None:
            raise LayoutError(f"{name} is not a regular file")
        return fh.read()


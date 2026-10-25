"""Assemble and verify a component release directory (manifest schema 1).

A release directory holds ``manifest.json``, ``manifest.sig``, ``KEY_ID`` and
every file the manifest names, as bare file names. Published as the assets of
the GitHub Release tagged ``<release>`` (``.../releases/download/<release>/<file>``)
and, optionally, by the Harmonia web service under ``components/<release>/<file>``.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from . import archive, config, signing
from .fetch import sha256_file
from .platforms import PLATFORMS

SCHEMA = 1
MANIFEST = "manifest.json"
SIGNATURE = "manifest.sig"
KEY_ID_FILE = "KEY_ID"
_RELEASE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_FILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*\.tar\.gz$")


class ManifestError(ValueError):
    pass


def validate_release_id(release: str) -> str:
    if not _RELEASE_RE.match(release) or ".." in release:
        raise ManifestError(f"invalid release id {release!r} (letters, digits, '.', '_', '-'; max 64)")
    return release


def _entry(path: Path) -> Dict[str, object]:
    return {"file": path.name, "sha256": sha256_file(path), "size": path.stat().st_size}


def assemble(
    release: str,
    dist_dir: Path,
    components: Optional[Dict[str, config.Component]] = None,
    created_at: Optional[str] = None,
) -> Dict[str, object]:
    """Build the manifest dict from the archives found in ``dist_dir``.

    Every archive's layout is checked. A component with at least one build
    must have its source archive (the licences require the source next to
    the binaries); a component with no build at all is left out.
    """
    validate_release_id(release)
    components = components if components is not None else config.load()
    dist_dir = Path(dist_dir)
    if created_at is None:
        created_at = _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    out: List[Dict[str, object]] = []
    for name in config.COMPONENT_NAMES:
        comp = components.get(name)
        if comp is None:
            continue
        builds: Dict[str, object] = {}
        for platform in PLATFORMS:
            path = dist_dir / comp.archive_name(platform)
            if path.exists():
                archive.check_binary_layout(name, platform, archive.members(path))
                builds[platform] = _entry(path)
        if not builds:
            continue
        src = dist_dir / comp.source_archive_name
        if not src.exists():
            raise ManifestError(f"{name}: builds present but source archive {src.name} is missing")
        archive.check_source_layout(archive.members(src), [s.filename for s in comp.sources])
        out.append(
            {
                "name": name,
                "version": comp.version,
                "license": comp.license,
                "attribution": comp.attribution,
                "provides": {"executables": list(comp.executables), "libraries": list(comp.libraries)},
                "source": _entry(src),
                "builds": builds,
            }
        )
    if not out:
        raise ManifestError(f"no component archives found in {dist_dir}")
    return {"schema": SCHEMA, "release": release, "created_at": created_at, "components": out}


def dumps(manifest: Dict[str, object]) -> bytes:
    """The canonical bytes we sign (and every distributor serves verbatim)."""
    return (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def referenced_files(manifest: Dict[str, object]) -> List[Dict[str, object]]:
    files = []
    for comp in manifest.get("components", []):
        files.append(comp["source"])
        files.extend(comp["builds"].values())
    return files


def verify_release(release_dir: Path, trusted_keys: Dict[str, str], check_layout: bool = True) -> Dict[str, object]:
    """Check signature (against ``trusted_keys``), schema, and every file's
    size + sha256 (+ archive layout). Returns the parsed manifest."""
    release_dir = Path(release_dir)
    data = (release_dir / MANIFEST).read_bytes()
    sig = (release_dir / SIGNATURE).read_text(encoding="ascii").strip()
    key_id = (release_dir / KEY_ID_FILE).read_text(encoding="utf-8").strip()
    if key_id not in trusted_keys:
        raise ManifestError(f"signature key id {key_id!r} is not trusted")
    signing.verify(data, sig, trusted_keys[key_id])
    manifest = json.loads(data.decode("utf-8"))
    if manifest.get("schema") != SCHEMA:
        raise ManifestError(f"unsupported manifest schema {manifest.get('schema')!r}")
    validate_release_id(str(manifest.get("release", "")))
    for comp in manifest["components"]:
        name = comp["name"]
        for platform, entry in comp["builds"].items():
            if platform not in PLATFORMS:
                raise ManifestError(f"{name}: unknown platform {platform!r}")
            _check_file(release_dir, entry)
            if check_layout:
                archive.check_binary_layout(name, platform, archive.members(release_dir / entry["file"]))
        _check_file(release_dir, comp["source"])
        if check_layout:
            archive.check_source_layout(archive.members(release_dir / comp["source"]["file"]))
    return manifest


def _check_file(release_dir: Path, entry: Dict[str, object]) -> None:
    fname = str(entry["file"])
    if not _FILE_RE.match(fname) or "/" in fname or "\\" in fname:
        raise ManifestError(f"invalid file name in manifest: {fname!r}")
    path = release_dir / fname
    if not path.is_file():
        raise ManifestError(f"missing file {fname}")
    if path.stat().st_size != entry["size"]:
        raise ManifestError(f"{fname}: size {path.stat().st_size} != manifest {entry['size']}")
    got = sha256_file(path)
    if got != entry["sha256"]:
        raise ManifestError(f"{fname}: sha256 {got} != manifest {entry['sha256']}")

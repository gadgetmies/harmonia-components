"""Load ``versions.toml`` — the pinned upstream sources."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

try:  # Python 3.11+
    import tomllib as _toml
except ModuleNotFoundError:  # pragma: no cover - bullseye's 3.9
    import tomli as _toml  # type: ignore

HERE = Path(__file__).resolve().parent
COMPONENTS_DIR = HERE.parent
VERSIONS_FILE = COMPONENTS_DIR / "versions.toml"
COMPONENT_NAMES = ("ffmpeg", "rubberband", "taglib")


@dataclass(frozen=True)
class Source:
    id: str
    version: str
    url: str
    sha256: str
    license_files: List[str] = field(default_factory=list)

    @property
    def filename(self) -> str:
        return self.url.rstrip("/").rsplit("/", 1)[-1]


@dataclass(frozen=True)
class Component:
    name: str
    version: str
    license: str
    attribution: str
    executables: List[str]
    libraries: List[str]
    sources: List[Source]

    def archive_name(self, platform: str) -> str:
        return f"{self.name}-{self.version}-{platform}.tar.gz"

    @property
    def source_archive_name(self) -> str:
        return f"{self.name}-{self.version}-source.tar.gz"


def load(path: Path = VERSIONS_FILE) -> Dict[str, Component]:
    data = _toml.loads(Path(path).read_text(encoding="utf-8"))
    sources = {}
    for sid, s in data["sources"].items():
        sha = s["sha256"].lower()
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ValueError(f"source {sid}: sha256 must be 64 hex chars")
        sources[sid] = Source(sid, s["version"], s["url"], sha, list(s.get("license_files", [])))
    out = {}
    for name, c in data["components"].items():
        missing = [sid for sid in c["sources"] if sid not in sources]
        if missing:
            raise ValueError(f"component {name}: unknown sources {missing}")
        out[name] = Component(
            name=name,
            version=c["version"],
            license=c["license"],
            attribution=c["attribution"],
            executables=list(c.get("executables", [])),
            libraries=list(c.get("libraries", [])),
            sources=[sources[sid] for sid in c["sources"]],
        )
    return out

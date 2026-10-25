"""Run the recipes, stage the payload, and write the binary + source archives."""
from __future__ import annotations

import datetime as _dt
import os
import platform as _platform
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Dict, List, Optional

from . import archive, config, depcheck, guard, recipes
from .fetch import fetch
from .platforms import PLATFORMS, exe_name, os_of

COMPONENTS_DIR = config.COMPONENTS_DIR
# Not copied into the source archive's build/ directory (the repository root:
# build scripts, recipes, versions.toml, CI workflows, public keys).
_SOURCE_EXCLUDE = {
    ".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".idea", ".DS_Store",
    "dist", "release", "work", "cache",
}
# Private key material never goes into a source archive, even if one is lying
# around in the checkout by mistake.
_SOURCE_EXCLUDE_SUFFIXES = (".pyc", ".log", ".key", ".seed", ".pem", ".priv", ".private")


def _log(msg: str) -> None:
    print(f"[build] {msg}", flush=True)


def _posix(p: Path) -> str:
    # MSYS2's sh/make/configure want forward slashes, also on Windows.
    return Path(p).as_posix()


def _extract(tarball: Path, dest: Path) -> Path:
    """Unpack an upstream tarball; return its single top-level directory."""
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tarball) as tar:
        tops = {m.name.split("/", 1)[0] for m in tar.getmembers() if m.name not in (".", "./")}
        if len(tops) != 1:
            raise RuntimeError(f"{tarball.name}: expected one top-level directory, got {sorted(tops)}")
        top = tops.pop()
        if not (dest / top).exists():
            if hasattr(tarfile, "data_filter"):
                tar.extractall(dest, filter="data")
            else:  # pragma: no cover - Python < 3.9.17
                tar.extractall(dest)
    return dest / top


class Build:
    def __init__(self, component: str, platform: str, out: Path, work: Path, cache: Path, jobs: int):
        self.components = config.load()
        self.comp = self.components[component]
        self.platform = platform
        self.out = out
        self.work = work / platform / component
        self.cache = cache
        self.jobs = jobs
        self.log_path = self.work / "build.log"

    # ---------------------------------------------------------------- running
    def values(self) -> Dict[str, str]:
        v = {
            "prefix": _posix(self.work / "prefix"),
            "inst": _posix(self.work / "inst"),
            "jobs": str(self.jobs),
        }
        for s in self.comp.sources:
            v[f"src_{s.id}"] = _posix(self.srcdirs[s.id])
            v[f"build_{s.id}"] = _posix(self.work / "build" / s.id)
        return v

    def run(self) -> Path:
        self.work.mkdir(parents=True, exist_ok=True)
        for d in ("inst", "stage"):
            shutil.rmtree(self.work / d, ignore_errors=True)
        self.srcdirs = {}
        for s in self.comp.sources:
            tarball = fetch(s, self.cache)
            self.srcdirs[s.id] = _extract(tarball, self.work / "src")
        values = self.values()
        if self.comp.name == "ffmpeg":
            self._check_ffmpeg_names()
        with open(self.log_path, "a", encoding="utf-8") as log:
            for step in recipes.steps_for(self.comp.name, self.platform):
                st = step.render(values)
                Path(st.cwd).mkdir(parents=True, exist_ok=True)
                env = dict(os.environ)
                env.update(st.env)
                _log(st.title)
                log.write(f"\n### {st.title}\n$ (cd {st.cwd}) {' '.join(st.argv)}\n")
                log.flush()
                proc = subprocess.run(st.argv, cwd=st.cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
                if proc.returncode != 0:
                    raise RuntimeError(f"{st.title} failed (exit {proc.returncode}); see {self.log_path}")
        stage = self.stage()
        self.post_checks(stage)
        self.write_build_info(stage)
        dest = self.out / self.comp.archive_name(self.platform)
        archive.make_tar_gz(stage, dest)
        archive.check_binary_layout(self.comp.name, self.platform, archive.members(dest))
        _log(f"wrote {dest} ({dest.stat().st_size} bytes)")
        return dest

    def _check_ffmpeg_names(self) -> None:
        from . import ffmpeg_features

        configure = _posix(self.srcdirs["ffmpeg"] / "configure")
        available = {}
        for kind, listing in ffmpeg_features.KINDS.items():
            out = subprocess.run(["sh", configure, f"--list-{listing}"], check=True, capture_output=True, text=True,
                                 cwd=str(self.work))
            available[kind] = out.stdout.split()
        extra = ["aac_at"] if os_of(self.platform) == "macos" else []
        bad = ffmpeg_features.unknown_names(available, extra)
        if bad:
            raise RuntimeError(f"ffmpeg_features names unknown to this ffmpeg's configure: {bad}")

    # ---------------------------------------------------------------- staging
    def stage(self) -> Path:
        stage = self.work / "stage"
        inst = self.work / "inst"
        osname = os_of(self.platform)
        payload: List[Path] = []
        if self.comp.name in ("ffmpeg", "rubberband"):
            (stage / "bin").mkdir(parents=True)
            for name in self.comp.executables:
                src = inst / "bin" / exe_name(self.platform, name)
                dst = stage / "bin" / src.name
                shutil.copy2(src, dst)
                payload.append(dst)
        else:  # taglib
            if osname == "windows":
                (stage / "bin").mkdir(parents=True)
                for name in ("tag.dll", "tag_c.dll"):
                    dst = stage / "bin" / name
                    shutil.copy2(inst / "bin" / name, dst)
                    payload.append(dst)
            else:
                (stage / "lib").mkdir(parents=True)
                pattern = "*.dylib" if osname == "macos" else "*.so*"
                for src in sorted((inst / "lib").glob(pattern)):
                    if not (src.name.startswith("libtag.") or src.name.startswith("libtag_c.")):
                        continue
                    dst = stage / "lib" / src.name
                    if src.is_symlink():
                        os.symlink(os.readlink(src), dst)
                    else:
                        shutil.copy2(src, dst)
                        payload.append(dst)
        for p in payload:
            self._strip(p)
        if osname == "macos":
            self._macos_relocate([p for p in payload if p.suffix == ".dylib"])
        if osname == "macos":
            for p in payload:
                subprocess.run(["codesign", "--force", "--sign", "-", str(p)], check=True)
        self._licenses(stage)
        return stage

    def _macos_relocate(self, dylibs: List[Path]) -> None:
        """Make the dylibs load from their own directory: id ``@rpath/<name>``,
        references to sibling dylibs ``@rpath/<name>``, rpath ``@loader_path``.
        (TagLib's CMake bakes the absolute install dir into the ids.)"""
        if not dylibs:
            return
        names = {p.name for p in dylibs[0].parent.iterdir()}
        for lib in dylibs:
            out = subprocess.run(["otool", "-D", str(lib)], check=True, capture_output=True, text=True).stdout
            ident = out.splitlines()[-1].strip()
            subprocess.run(["install_name_tool", "-id", "@rpath/" + ident.rsplit("/", 1)[-1], str(lib)], check=True)
            for dep in depcheck.linked_libraries(self.platform, lib):
                base = dep.rsplit("/", 1)[-1]
                if base in names and not dep.startswith("@rpath/"):
                    subprocess.run(["install_name_tool", "-change", dep, "@rpath/" + base, str(lib)], check=True)
            rpaths = subprocess.run(["otool", "-l", str(lib)], check=True, capture_output=True, text=True).stdout
            if "path @loader_path " not in rpaths:
                subprocess.run(["install_name_tool", "-add_rpath", "@loader_path", str(lib)], check=True)

    def _strip(self, path: Path) -> None:
        osname = os_of(self.platform)
        is_lib = path.suffix in (".dylib", ".dll") or ".so" in path.name
        if osname == "macos":
            cmd = ["strip", "-x", str(path)] if is_lib else ["strip", str(path)]
        else:
            cmd = ["strip", "--strip-unneeded", str(path)]
        subprocess.run(cmd, check=True)

    def _licenses(self, stage: Path) -> None:
        lic = stage / "licenses"
        lic.mkdir(parents=True, exist_ok=True)
        for s in self.comp.sources:
            for rel in s.license_files:
                src = self.srcdirs[s.id] / rel
                name = f"{s.id}-{rel.replace('/', '-')}"
                if not name.endswith((".txt", ".md")):
                    name += ".txt"
                shutil.copy2(src, lic / name)
        (lic / "SOURCE.txt").write_text(
            f"{self.comp.name} {self.comp.version} for Harmonia — {self.comp.license}\n\n"
            f"The complete corresponding source code of this archive (the upstream\n"
            f"release tarballs of {self.comp.name} and of every library linked into it,\n"
            f"the build scripts, the exact configure lines and our changes) is\n"
            f"published next to it on the same server, in the same component release:\n\n"
            f"    {self.comp.source_archive_name}\n\n"
            f"Included upstream sources:\n"
            + "".join(f"    {s.filename}  sha256 {s.sha256}  {s.url}\n" for s in self.comp.sources),
            encoding="utf-8",
        )

    # ---------------------------------------------------------------- checks
    def _exe(self, stage: Path, name: str) -> Path:
        return stage / "bin" / exe_name(self.platform, name)

    def post_checks(self, stage: Path) -> None:
        osname = os_of(self.platform)
        files = [p for p in sorted(stage.rglob("*")) if p.is_file() and not p.is_symlink() and "licenses" not in p.parts]
        own = {p.name for p in stage.rglob("*") if "licenses" not in p.parts}
        if osname == "linux":
            own |= {"libtag.so.2"}
        for f in files:
            deps = depcheck.check(self.platform, f, own=own)
            _log(f"{f.name}: links {', '.join(deps) or '(nothing)'}")
        if self.comp.name == "ffmpeg":
            ffmpeg = self._exe(stage, "ffmpeg")
            buildconf = subprocess.run([str(ffmpeg), "-hide_banner", "-buildconf"], check=True, capture_output=True, text=True).stdout
            license_text = subprocess.run([str(ffmpeg), "-hide_banner", "-L"], check=True, capture_output=True, text=True).stdout
            guard.check_build(buildconf, license_text)
            ffprobe = self._exe(stage, "ffprobe")
            subprocess.run([str(ffprobe), "-hide_banner", "-L"], check=True, capture_output=True)
            _log("ffmpeg licence guard: LGPL-2.1, no gpl/nonfree/version3")
        elif self.comp.name == "rubberband":
            out = subprocess.run([str(self._exe(stage, "rubberband")), "--version"], capture_output=True, text=True)
            text = (out.stdout + out.stderr).strip()
            if self.comp.version not in text:
                raise RuntimeError(f"rubberband --version did not report {self.comp.version}: {text!r}")
            _log(f"rubberband --version: {text}")

    def write_build_info(self, stage: Path) -> None:
        cc = os.environ.get("CC", "cc")
        try:
            compiler = subprocess.run([cc, "--version"], capture_output=True, text=True).stdout.splitlines()[0]
        except (OSError, IndexError):
            compiler = "unknown"
        lines = [
            f"component: {self.comp.name}",
            f"version: {self.comp.version}",
            f"license: {self.comp.license}",
            f"platform: {self.platform}",
            f"build_date: {_dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
            f"build_host: {_platform.system()} {_platform.release()} {_platform.machine()}",
            f"compiler: {compiler}",
            f"source_archive: {self.comp.source_archive_name}",
            "",
            "upstream sources:",
        ]
        lines += [f"  {s.id} {s.version}  {s.filename}  sha256 {s.sha256}" for s in self.comp.sources]
        lines += ["", "build commands:", ""]
        lines.append(recipes.render_configure_txt(self.comp.name, self.comp.version, [self.platform]))
        (stage / "BUILD-INFO.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_component(component: str, platform: str, out: Path, work: Path, cache: Path, jobs: int) -> Path:
    return Build(component, platform, out, work, cache, jobs).run()


def _source_ignore(directory: str, names: List[str]) -> List[str]:
    return [n for n in names if n in _SOURCE_EXCLUDE or n.endswith(_SOURCE_EXCLUDE_SUFFIXES)]


def build_source_archive(component: str, out: Path, work: Path, cache: Path) -> Path:
    comp = config.load()[component]
    stage = work / "source" / component
    shutil.rmtree(stage, ignore_errors=True)
    (stage / "upstream").mkdir(parents=True)
    for s in comp.sources:
        shutil.copy2(fetch(s, cache), stage / "upstream" / s.filename)
    shutil.copytree(
        COMPONENTS_DIR,
        stage / "build",
        ignore=_source_ignore,
    )
    (stage / "CONFIGURE.txt").write_text(
        recipes.render_configure_txt(comp.name, comp.version, list(PLATFORMS)), encoding="utf-8"
    )
    patches = sorted((COMPONENTS_DIR / "patches" / component).glob("*.diff"))
    (stage / "changes.diff").write_text("".join(p.read_text(encoding="utf-8") for p in patches), encoding="utf-8")
    dest = out / comp.source_archive_name
    archive.make_tar_gz(stage, dest)
    archive.check_source_layout(archive.members(dest), [s.filename for s in comp.sources])
    _log(f"wrote {dest} ({dest.stat().st_size} bytes)")
    return dest


def default_jobs() -> int:
    return max(1, os.cpu_count() or 1)


def sources_needed(components: Optional[List[str]]) -> List[str]:
    return list(components or config.COMPONENT_NAMES)

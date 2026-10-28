"""Download upstream tarballs into a cache and refuse any sha256 mismatch."""
from __future__ import annotations

import hashlib
import os
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path

from .config import Source


class ChecksumMismatch(RuntimeError):
    pass


# Upstream mirrors (ffmpeg.org, SourceForge, xiph.org) drop connections now and
# then; one reset should not fail a 40-minute CI build. The checksum still
# decides what is accepted, so a retry can never let a different file through.
ATTEMPTS = 4
BACKOFF_SECONDS = 10


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(source: Source, cache_dir: Path) -> Path:
    """Return the verified tarball path, downloading it when not cached."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / source.filename
    if target.exists() and sha256_file(target) == source.sha256:
        return target
    tmp = target.with_name(target.name + ".part")
    print(f"[fetch] {source.url}", flush=True)
    req = urllib.request.Request(source.url, headers={"User-Agent": "harmonia-components-build"})
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as out:
                shutil.copyfileobj(resp, out)
            break
        except (urllib.error.URLError, OSError) as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code < 500 or attempt == ATTEMPTS:
                raise
            wait = BACKOFF_SECONDS * attempt
            print(f"[fetch] attempt {attempt} failed ({exc}); retrying in {wait} s", flush=True)
            time.sleep(wait)
    got = sha256_file(tmp)
    if got != source.sha256:
        tmp.unlink()
        raise ChecksumMismatch(f"{source.filename}: expected sha256 {source.sha256}, got {got}")
    os.replace(tmp, target)
    return target

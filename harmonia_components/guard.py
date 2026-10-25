"""Licence guard for the ffmpeg build: refuse anything that is not LGPL-2.1.

Two independent checks, both must pass:

* the configure line (``ffmpeg -buildconf`` / the argv we pass) carries no
  ``--enable-gpl``, ``--enable-nonfree`` or ``--enable-version3``;
* ``ffmpeg -L`` prints the LGPL-2.1 notice (fftools/opt_common.c prints the GPL,
  LGPLv3 or "nonfree ... not legally redistributable" text otherwise).
"""
from __future__ import annotations

import shlex
from typing import Iterable, List

FORBIDDEN_FLAGS = ("--enable-gpl", "--enable-nonfree", "--enable-version3")


class LicenseGuardError(RuntimeError):
    pass


def parse_buildconf(text: str) -> List[str]:
    """Return the configure flags listed by ``ffmpeg -buildconf``.

    Output shape::

        ffmpeg version ... Copyright ...
          built with ...
          configuration: --prefix=... --disable-everything ...
          ...
          configuration:
            --prefix=...
            --disable-everything
    """
    flags: List[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("configuration:"):
            rest = stripped[len("configuration:"):].strip()
            if rest:
                flags.extend(shlex.split(rest))
            else:  # the one-flag-per-line block that follows
                i += 1
                while i < len(lines) and lines[i].strip().startswith("--"):
                    flags.append(lines[i].strip())
                    i += 1
                continue
        i += 1
    seen = set()
    out = []
    for f in flags:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def check_flags(flags: Iterable[str]) -> None:
    bad = sorted({f.split("=", 1)[0] for f in flags if f.split("=", 1)[0] in FORBIDDEN_FLAGS})
    if bad:
        raise LicenseGuardError(f"ffmpeg configured with forbidden licence flags: {', '.join(bad)}")


def check_license_text(text: str) -> None:
    norm = " ".join(text.split())
    if "nonfree" in norm or "not legally redistributable" in norm:
        raise LicenseGuardError("ffmpeg -L reports nonfree parts")
    if "GNU General Public License as published" in norm:
        raise LicenseGuardError("ffmpeg -L reports a GPL build")
    if "Lesser General Public License" not in norm or "version 2.1" not in norm:
        raise LicenseGuardError("ffmpeg -L does not report LGPL version 2.1")


def check_build(buildconf_text: str, license_text: str) -> List[str]:
    flags = parse_buildconf(buildconf_text)
    if not flags:
        raise LicenseGuardError("could not find a configuration line in ffmpeg -buildconf output")
    check_flags(flags)
    check_license_text(license_text)
    return flags

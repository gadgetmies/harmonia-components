"""Build, package, sign and verify the Harmonia components (ffmpeg, Rubber Band,
TagLib) from pinned upstream sources. See README.md.

Python >= 3.9 (the Linux builds run in a Debian bullseye container); TOML is read
with ``tomllib`` (3.11+) or the ``tomli`` backport.
"""

# Harmonia components

This repository builds the third-party programs and libraries that the
Harmonia desktop app installs during its first-run setup:

| component | what Harmonia uses it for | licence |
|---|---|---|
| **ffmpeg / ffprobe** 7.1.5 | decoding, encoding and analysing audio | LGPL-2.1-or-later (LGPL configuration, see below) |
| **Rubber Band** 4.0.0 command-line program | time-stretching and pitch-shifting | GPL-2.0-or-later, shipped as a separate executable |
| **TagLib** 2.3.2 C library (`tag_c`) | reading and writing audio file tags | LGPL-2.1 or MPL-1.1 |

Everything is built from pinned upstream release tarballs by GitHub Actions,
published as GitHub Releases, and covered by:

- a **build provenance attestation** (Sigstore, issued to this repository's
  release workflow) for every archive and for the manifest files;
- an **Ed25519-signed `manifest.json`** listing every file with its size and
  sha256. The desktop app accepts a release only when the signature verifies
  against a public key built into the app.

## Platforms

`macos-arm64`, `macos-x86_64`, `windows-x86_64`, `linux-x86_64`,
`linux-arm64`. macOS binaries target macOS 12.0+ and are ad-hoc signed (not
notarised). Linux binaries are built in Debian bullseye, so they run on any
system with glibc 2.31 or newer. Windows binaries are built with MinGW-w64 and
linked statically. Every executable links only operating-system libraries (the
build checks this).

## Licences

### ffmpeg: LGPL-2.1 configuration

ffmpeg is configured with `--disable-everything --disable-autodetect` and then
only the audio pieces Harmonia needs are switched on
([`harmonia_components/ffmpeg_features.py`](harmonia_components/ffmpeg_features.py)
lists each one and why). In particular:

- **never** `--enable-gpl`, `--enable-nonfree` or `--enable-version3`. The
  build runs a licence guard on the finished binary: `ffmpeg -buildconf` must
  not show those flags and `ffmpeg -L` must print the LGPL 2.1 notice;
- no GPL or nonfree libraries (for example x264, fdk-aac or librubberband);
- disabled: networking (`--disable-network`), `ffplay`, `libpostproc`,
  documentation, every video encoder, and every filter that needs an external
  library;
- external libraries linked in statically: LAME (`libmp3lame`, LGPL-2.0+),
  Opus (BSD-3-Clause), libogg and libvorbis (BSD-3-Clause). On macOS the
  system AudioToolbox framework is used for the `aac_at` encoder.

### Rubber Band: GPL-2.0-or-later, separate program

Only the `rubberband` command-line program is shipped. Harmonia runs it as a
separate process and never links the library. It is built with the built-in
FFT and resampler (Apple's vDSP FFT on macOS) and with libsndfile
(LGPL-2.1+, statically, no external codecs) for WAV input and output.

### TagLib: LGPL-2.1 or MPL-1.1

Shared libraries `libtag` and `libtag_c` (on Windows `tag.dll` and
`tag_c.dll`), with zlib (zlib licence) linked in statically. The TagLib
tarball bundles utfcpp (Boost Software Licence 1.0).

### What every release contains

- Each binary archive carries, under `licenses/`, the licence texts of the
  component **and of every library linked into it**, plus `licenses/SOURCE.txt`
  (which source archive is its complete source) and `BUILD-INFO.txt` (versions,
  sha256 of every upstream tarball, compiler, exact build commands).
- Each component with a binary in the release has a
  `<component>-<version>-source.tar.gz` **in the same release**. It holds the
  verbatim upstream tarballs of the component and of every linked library
  (`upstream/`), this repository's build scripts (`build/`), the exact
  configure / cmake / meson lines for every platform (`CONFIGURE.txt`) and our
  changes (`changes.diff`, empty when nothing is patched).
- Releases are never deleted, so a release's source stays available as long as
  its binaries do.

The build scripts in this repository are not yet under an open-source licence
(see [Licence of this repository](#licence-of-this-repository)).

## Where things are

| path | what it is |
|---|---|
| [`versions.toml`](versions.toml) | pinned upstream tarballs: URL, version, sha256, licence files |
| [`harmonia_components/recipes.py`](harmonia_components/recipes.py) | the exact configure / cmake / meson command lines per platform |
| [`harmonia_components/ffmpeg_features.py`](harmonia_components/ffmpeg_features.py) | the ffmpeg codecs, formats and filters that are enabled |
| [`build.py`](build.py) | builds one platform's archives and/or the source archives |
| [`manifest.py`](manifest.py), [`sign.py`](sign.py), [`verify.py`](verify.py), [`keygen.py`](keygen.py) | write, sign and check `manifest.json`; make a signing key |
| [`ci/linux-container-build.sh`](ci/linux-container-build.sh) | the Linux build inside Debian bullseye |
| [`.github/workflows/release.yml`](.github/workflows/release.yml) | builds and publishes a release |
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | unit tests on every push and pull request |
| [`keys/`](keys/) | the public keys that manifests are signed with |
| [`tests/`](tests/) | unit tests (no network) |
| [`MAINTAINERS.md`](MAINTAINERS.md) | signing key, repository secrets and how to cut a release |

## How a release is built

A release id has the form `YYYY.MM.DD.N` (for example `2026.10.25.1`) and is
also the git tag. Pushing such a tag (or starting the workflow by hand with a
release id) runs [`release.yml`](.github/workflows/release.yml):

1. **prepare**: checks the release id, the signing secret and the public key
   file, then runs the unit tests;
2. **sources**: builds the three source archives;
3. **build**, one job per platform:

   | platform | runner |
   |---|---|
   | macos-arm64 | `macos-14` |
   | macos-x86_64 | `macos-15-intel` |
   | windows-x86_64 | `windows-latest` with MSYS2 MINGW64 |
   | linux-x86_64 | `ubuntu-24.04`, building inside `debian:bullseye` |
   | linux-arm64 | `ubuntu-24.04-arm`, building inside `debian:bullseye` |

   Each build downloads the sources and checks their sha256, builds the
   static dependencies and the component, strips the binaries, checks the
   linked libraries, runs the ffmpeg licence guard, and writes the archive;
4. **publish**: writes `manifest.json`, signs it, verifies the complete
   release against [`keys/`](keys/), attests build provenance for every file,
   and publishes the GitHub Release (marked latest).

### Release files and URLs

Every file of a release is a flat asset of the GitHub Release tagged with the
release id:

| file | what it is |
|---|---|
| `manifest.json` | the signed list of components, files, sizes and sha256 |
| `manifest.sig` | base64 Ed25519 signature over the exact bytes of `manifest.json` |
| `KEY_ID` | the id of the key that signed it (its public key is `keys/<KEY_ID>.pub`) |
| `<component>-<version>-<platform>.tar.gz` | a platform build, for example `ffmpeg-7.1.5-macos-arm64.tar.gz` |
| `<component>-<version>-source.tar.gz` | the complete corresponding source, for example `ffmpeg-7.1.5-source.tar.gz` |

- The latest manifest:
  `https://github.com/gadgetmies/harmonia-components/releases/latest/download/manifest.json`
- Any file of a release:
  `https://github.com/gadgetmies/harmonia-components/releases/download/<release>/<file>`,
  for example
  `https://github.com/gadgetmies/harmonia-components/releases/download/2026.10.25.1/ffmpeg-7.1.5-linux-x86_64.tar.gz`

The manifest names files by bare file name only; the download URL is built
from the manifest's `release` field (which is the tag) and the file name.
A client fetches `latest/download/manifest.json`, reads `release` from it,
then fetches `manifest.sig` and `KEY_ID` from `releases/download/<release>/`,
so the three files always come from the same release, and checks the
signature before trusting anything else in the manifest.

## Verifying a download

### 1. Build provenance

With the [GitHub CLI](https://cli.github.com/):

```sh
gh attestation verify ffmpeg-7.1.5-macos-arm64.tar.gz --repo gadgetmies/harmonia-components
```

This proves the file was produced by this repository's release workflow and
shows the commit and workflow run that built it. It works the same for every
archive and for `manifest.json`, `manifest.sig` and `KEY_ID`.

### 2. sha256 against the manifest

```sh
shasum -a 256 ffmpeg-7.1.5-macos-arm64.tar.gz      # Linux: sha256sum
grep -A2 '"ffmpeg-7.1.5-macos-arm64.tar.gz"' manifest.json
```

The two hashes must be equal (and so must the size).

### 3. The manifest signature, and every file at once

Download a whole release and check it with `verify.py` and the public keys in
this repository:

```sh
git clone https://github.com/gadgetmies/harmonia-components
cd harmonia-components
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
gh release download 2026.10.25.1 --repo gadgetmies/harmonia-components --dir release-2026.10.25.1
.venv/bin/python verify.py release-2026.10.25.1 --keys-dir keys
```

`verify.py` checks the signature with `keys/<KEY_ID>.pub`, then the size,
sha256 and layout of every file the manifest lists, and prints
`OK release ...` or the first problem it finds.

## Public signing key

> **Not published yet.** The production signing key has not been generated.
> Once it is, its public key will be committed here as
> `keys/harmonia-components-1.pub` (base64 of the raw 32-byte Ed25519 public
> key), and the same key will be built into the Harmonia desktop app. A key is
> trusted only if it is both in this repository and in the app.
>
> | key id | public key (base64) | used for releases |
> |---|---|---|
> | `harmonia-components-1` | *to be added* | *none yet* |

## Building locally

You need Python 3.9+ (3.11+ outside the Linux container), a C/C++ toolchain,
`cmake`, `ninja`, `pkg-config`, `make` and, for x86_64 ffmpeg, `nasm`. Meson
and `cryptography` come from `requirements.txt`. You can only build for the
machine you are on (no cross builds). An ffmpeg build tree needs about 1 GB.

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
PATH="$PWD/.venv/bin:$PATH" python build.py --out dist                          # this platform, all components + sources
PATH="$PWD/.venv/bin:$PATH" python build.py --out dist --component taglib --no-sources
.venv/bin/python build.py --sources-only --out dist                             # just the source archives
```

Linux (needs Docker), from the repository root:

```sh
docker run --rm -v "$PWD":/src -w /src debian:bullseye sh ci/linux-container-build.sh /src/dist
```

Windows: in an MSYS2 **MINGW64** shell, install the packages listed in the
workflow's "MSYS2 MINGW64 toolchain" step, then run
`python build.py --platform windows-x86_64 --out dist`.

Smoke test after a build:

```sh
bin/ffmpeg -hide_banner -buildconf | grep -E -- '--enable-(gpl|nonfree|version3)'   # must print nothing
bin/ffmpeg -hide_banner -L | head -4                                                 # LGPL 2.1 notice
otool -L bin/ffmpeg                                                                  # macOS: only /usr/lib + /System/Library
bin/rubberband --version
```

## Tests

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -t .
```

## Licence of this repository

The licence of the build scripts in this repository has not been chosen yet.
The components built here keep their own licences (above); their licence
texts ship inside every archive.

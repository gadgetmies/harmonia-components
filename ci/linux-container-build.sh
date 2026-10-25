#!/bin/sh
# Build the Linux component archives inside Debian bullseye (glibc 2.31), so
# the binaries run on any glibc >= 2.31 system. Run from the repo root:
#
#   docker run --rm -v "$PWD":/src -w /src debian:bullseye \
#       sh ci/linux-container-build.sh /src/dist
#
# (CI runs exactly this on ubuntu-24.04 for linux-x86_64 and on
# ubuntu-24.04-arm for linux-arm64.) Extra arguments go to build.py.
set -eu
OUT="${1:?usage: linux-container-build.sh <out dir> [build.py args...]}"
shift
HERE="$(cd "$(dirname "$0")/.." && pwd)"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
    build-essential pkg-config ninja-build nasm make autoconf automake libtool \
    python3 python3-venv python3-pip ca-certificates curl xz-utils bzip2 file binutils >/dev/null

# Newer CMake/Meson than bullseye ships (CMake from the PyPI wheel).
VENV="${COMPONENTS_VENV:-/tmp/components-venv}"
python3 -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r "$HERE/requirements.txt" "cmake>=3.28,<4"
export PATH="$VENV/bin:$PATH"

# Keep the build tree off the bind mount (faster, and no root-owned files
# left in the checkout besides the archives).
WORK="${COMPONENTS_WORK:-/tmp/components-work}"
python "$HERE/build.py" --out "$OUT" --work "$WORK" --cache "${COMPONENTS_CACHE:-/tmp/components-cache}" --no-sources "$@"
if [ -n "${HOST_UID:-}" ]; then
    chown -R "$HOST_UID:${HOST_GID:-$HOST_UID}" "$OUT"
fi

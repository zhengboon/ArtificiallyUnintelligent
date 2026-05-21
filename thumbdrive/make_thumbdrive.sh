#!/bin/bash
#
# make_thumbdrive.sh — Build the thumbdrive contents.
#
# Run this on Z's dev VM (must be Linux, must have pip with access to
# the same Python version as the org VM = Ubuntu 22.04 / Python 3.10.x).
# DO NOT run on the Windows host — pip will collect Windows-only wheels.
#
# Outputs into the same directory as this script:
#   - ArtificiallyUnintelligent.tar.gz   (repo snapshot)
#   - best.pt                            (copied from ../models/best.pt)
#   - wheels/*.whl                       (offline pip deps)
#
# These are gitignored — safe to rebuild as often as needed.

set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"
TARBALL="$HERE/ArtificiallyUnintelligent.tar.gz"
WEIGHTS_DST="$HERE/best.pt"
WHEELS_DIR="$HERE/wheels"

echo "==== Building thumbdrive contents ===="
echo "  repo root: $REPO_ROOT"
echo "  output:    $HERE"
echo

# -------- 1. Snapshot repo (excluding bulk + thumbdrive itself) --------
echo "[1/3] tarballing repo..."
# Exclude:
#   - thumbdrive/  (recursion prevention)
#   - vm/, info_*/, learning/*.mp4, discord_watcher/{profile,logs}
#     (all gitignored, no need to ship)
#   - dataset_v1/  (huge, not needed at qualifier — controller doesn't read it)
#   - .git/        (history not needed for runtime)
#   - pastproject/ (historical reference, not needed)
#   - __pycache__/, *.pyc
tar --exclude='./thumbdrive' \
    --exclude='./vm' \
    --exclude='./info_*' \
    --exclude='./learning/*.mp4' \
    --exclude='./discord_watcher/profile' \
    --exclude='./discord_watcher/logs' \
    --exclude='./dataset_v1' \
    --exclude='./.git' \
    --exclude='./pastproject' \
    --exclude='**/__pycache__' \
    --exclude='*.pyc' \
    -czf "$TARBALL" \
    -C "$REPO_ROOT" .
echo "       wrote $(du -h "$TARBALL" | cut -f1) $TARBALL"

# -------- 2. Copy weights --------
echo "[2/3] copying weights..."
if [ -f "$REPO_ROOT/models/best.pt" ]; then
    cp "$REPO_ROOT/models/best.pt" "$WEIGHTS_DST"
    echo "       $(du -h "$WEIGHTS_DST" | cut -f1) $WEIGHTS_DST"
else
    echo "       WARNING: $REPO_ROOT/models/best.pt missing — skipping"
fi

# -------- 3. Collect offline pip wheels --------
echo "[3/3] downloading offline pip wheels..."
mkdir -p "$WHEELS_DIR"

# Deps we need that aren't pre-installed on the v3 VM:
#   - pymavlink  (Phase 6 fake-GCS heartbeat)
#
# Deps we KNOW are pre-installed on v3 VM (don't re-bundle):
#   - mavsdk, ultralytics, torch, opencv-python, numpy, matplotlib,
#     gz-transport13, gz-msgs10
#
# If we discover other gaps during Wed/Thu testing, add to this list.
PIP_DEPS=(
    pymavlink
)

# --python-version + --platform pin the wheels to Ubuntu 22.04 / Python 3.10
# even if this script runs on a slightly different env. The v3 VM is
# Ubuntu 22.04 LTS = Python 3.10.x by default.
python3 -m pip download \
    --dest "$WHEELS_DIR" \
    --python-version 310 \
    --platform manylinux2014_x86_64 \
    --only-binary=:all: \
    "${PIP_DEPS[@]}" 2>&1 | tail -10 || {
        echo "       WARNING: --platform-pinned download failed."
        echo "       Falling back to current-env download (may not match VM)..."
        python3 -m pip download --dest "$WHEELS_DIR" "${PIP_DEPS[@]}" 2>&1 | tail -10
    }

echo "       collected $(ls "$WHEELS_DIR" | wc -l) wheel files"

echo
echo "==== DONE ===="
echo "Contents of $HERE:"
ls -lh "$HERE" 2>&1 | tail -20
echo
echo "Next: copy this entire folder to a USB stick (and a second backup stick)."
echo "Test on a fresh v3 VM by running: bash setup.sh"

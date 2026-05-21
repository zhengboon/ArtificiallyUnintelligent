#!/bin/bash
#
# setup.sh — Install ArtificiallyUnintelligent's code into the org's v3 VM.
#
# Runs at the qualifier (Fri 22 May 14:00 SGT) on a fresh org-provided
# Ubuntu 22.04 VM. Goal: get from "USB plugged in" to "ready to run the
# controller" in under 5 minutes, with NO internet.
#
# Usage (from inside the VM, after copying thumbdrive/ to home dir):
#   cd ~/thumbdrive && bash setup.sh
#
# What this does NOT do (do these by hand per runbook.md):
#   - Start the PX4 sim (~/start_px4.sh)
#   - Set the EKF origin (commander set_ekf_origin ... in pxh> console)
#
# Exit codes:
#   0 = success, controller is ready to run
#   1 = pre-flight check failed (likely env mismatch)
#   2 = extraction or copy step failed
#   3 = pip install failed
#

set -e   # stop on first error

HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/ArtificiallyUnintelligent"
TARBALL="$HERE/ArtificiallyUnintelligent.tar.gz"
WEIGHTS="$HERE/best.pt"
WHEELS_DIR="$HERE/wheels"

echo "==== AU setup.sh ===="
echo "  source: $HERE"
echo "  dest:   $DEST"
echo

# -------- 1. Sanity checks --------
echo "[1/4] sanity checks..."
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 not found. This script needs Python 3 (v3 VM has it pre-installed)."
    exit 1
fi
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "       python3 = $PY_VER"

if [ ! -f "$TARBALL" ]; then
    echo "ERROR: tarball missing: $TARBALL"
    echo "       did you run make_thumbdrive.sh before copying to USB?"
    exit 1
fi
if [ ! -f "$WEIGHTS" ]; then
    echo "WARNING: best.pt missing: $WEIGHTS"
    echo "         controller will fall back to whatever weights are in the tarball."
fi
if [ ! -d "$WHEELS_DIR" ]; then
    echo "WARNING: wheels/ dir missing — pip install step will be skipped."
    echo "         If the VM is missing any deps, --no-X flags can degrade features."
fi

# -------- 2. Extract repo --------
echo "[2/4] extracting repo to $DEST..."
if [ -d "$DEST" ]; then
    echo "       $DEST already exists — backing up to ${DEST}.bak.$(date +%s)"
    mv "$DEST" "${DEST}.bak.$(date +%s)"
fi
mkdir -p "$DEST"
tar -xzf "$TARBALL" -C "$DEST" --strip-components=1 || {
    echo "ERROR: tar extraction failed"
    exit 2
}
echo "       extracted $(find "$DEST" -type f | wc -l) files"

# -------- 3. Drop in K's weights --------
if [ -f "$WEIGHTS" ]; then
    echo "[3/4] copying K's weights..."
    mkdir -p "$DEST/models"
    cp "$WEIGHTS" "$DEST/models/best.pt" || {
        echo "ERROR: could not copy best.pt"
        exit 2
    }
    echo "       $DEST/models/best.pt ($(stat -c%s "$DEST/models/best.pt") bytes)"
else
    echo "[3/4] skipped (no best.pt on USB)"
fi

# -------- 4. Install offline wheels --------
if [ -d "$WHEELS_DIR" ] && [ -n "$(ls -A "$WHEELS_DIR" 2>/dev/null)" ]; then
    echo "[4/4] installing offline pip wheels..."
    pip install --user --no-index --find-links="$WHEELS_DIR" "$WHEELS_DIR"/*.whl 2>&1 | tail -5 || {
        echo "ERROR: pip install failed"
        exit 3
    }
else
    echo "[4/4] no wheels to install (skipped)"
fi

echo
echo "==== SETUP COMPLETE ===="
echo
echo "Next steps (do these by hand — see runbook.md for full version):"
echo
echo "  1. Start the sim:"
echo "       ~/start_px4.sh"
echo "       (pick 1 for x500_vision, then roboverse)"
echo
echo "  2. When the pxh> prompt shows, type:"
echo "       commander set_ekf_origin 47.397742 8.545594 488.0"
echo
echo "  3. In another terminal, smoke-test:"
echo "       cd $DEST/searchctl && python3 controller.py --no-detect --no-map"
echo "       (33-second 2m square, confirms PX4 + MAVSDK + fake-GCS work)"
echo
echo "  4. If smoke test passes, the real run:"
echo "       python3 controller.py"
echo
echo "Outputs land in $DEST/searchctl/logs/run_<ts>/"

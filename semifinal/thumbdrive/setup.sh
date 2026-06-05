#!/usr/bin/env bash
# setup.sh — Bootstrap the C2 Terminal for the finals.
# Run inside the org-provided Ubuntu 22.04 VM after copying USB contents.
#
# Usage:
#   bash setup.sh

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/brainhack"

echo "==== Finals setup ===="
echo "  source: $HERE"
echo "  dest:   $DEST"

# -------- 1. Sanity checks --------
echo "[1/4] sanity checks..."
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 missing on this VM"; exit 1; }
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "       python3 = $PY_VER"

# -------- 2. Copy code + docs + models --------
echo "[2/4] copying tree to $DEST..."
mkdir -p "$DEST"
cp -r "$HERE"/{controllers,models,docs,prototypes,learning_material_3_uwb,learning_material_4_realsense,learning_material_5_yolo_rknn} "$DEST/" 2>/dev/null || true
if [ -f "$HERE/Train_YOLO_Models_new.ipynb" ]; then
    cp "$HERE/Train_YOLO_Models_new.ipynb" "$DEST/"
fi
echo "       copied $(find "$DEST" -type f | wc -l) files"

# -------- 3. Verify Python deps are present --------
echo "[3/4] verifying Python deps..."
MISSING=()
for mod in numpy cv2 mavsdk pyrealsense2; do
    if ! python3 -c "import $mod" 2>/dev/null; then
        MISSING+=("$mod")
    fi
done
# Optional: rknn-toolkit2, rknnlite, rclpy — check but don't fail
for mod in rknn rknnlite rclpy; do
    if ! python3 -c "import $mod" 2>/dev/null; then
        echo "       NOTE: $mod not importable (expected on some envs)"
    fi
done
if [ ${#MISSING[@]} -ne 0 ]; then
    echo "       WARNING: missing modules: ${MISSING[*]}"
    echo "       Ask org coordinator to install OR run:"
    echo "         pip install --user ${MISSING[*]}"
fi

# -------- 4. Smoke test the mapping drone controller (mock mode) --------
echo "[4/4] smoke test (mock mode, no drone needed)..."
cd "$DEST/controllers"
if python3 -c "from mapping_drone import controller; print('import ok')" 2>/dev/null; then
    echo "       mapping_drone import: OK"
else
    echo "       mapping_drone import: FAILED"
fi

echo ""
echo "==== SETUP COMPLETE ===="
echo ""
echo "Quick test (mock mapping mission, ~45s):"
echo "  cd $DEST/controllers && python3 -m mapping_drone.controller --mock-all"
echo ""
echo "Real mapping mission (drone must be ready):"
echo "  python3 -m mapping_drone.controller --real --waypoints ../configs/arena_waypoints_safe.json"
echo ""
echo "Hula swarm Challenge 2A (after Challenge 1 produces landing pad list):"
echo "  python3 swarm_controller.py --task 2a --pads_file runs/run_*/landing_pads.json"
echo ""
echo "Hula swarm Challenge 2B (RoboMaster hunt):"
echo "  python3 swarm_controller.py --task 2b --search-pattern lawnmower-3way"
echo ""
echo "Outputs land at: $DEST/controllers/runs/run_<ts>/"
echo "  STATUS.txt          <- live status (judge-readable)"
echo "  top_down.png        <- show judge"
echo "  landing_pads.json   <- show judge"
echo "  markers/*.jpg       <- show judge"
echo "  run_summary.json    <- machine-readable artifact"

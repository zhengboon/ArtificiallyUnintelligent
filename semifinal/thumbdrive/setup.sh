#!/usr/bin/env bash
# setup.sh — Bootstrap the Ubuntu 22.04 VM on the C2 Terminal (mapping-drone side).
# Run inside the org-provided Ubuntu 22.04 VM after copying USB contents into ~/brainhack/.
#
# NOTE: The Hula swarm half (pyhulax + UWBParserThread.py @ 921600 baud) runs on the
# C2 Terminal's Windows side and is set up separately (manual copy of USB to
# C:\brainhack\ per README); this script does NOT configure that side.
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
cp -r "$HERE"/{controllers,models,docs,prototypes,configs,learning_material_3_uwb,learning_material_4_realsense,learning_material_5_yolo_rknn,uwb_api_hula_swarm} "$DEST/" 2>/dev/null || true
# configs/ is fully populated (waypoints_2x2_default.json + arena_NxN.json templates,
# all at 4.0 m above the 3.5 m org floor). The trailing `|| true` is just defensive.
# Sanity-check after copy:
if [ ! -f "$DEST/configs/waypoints_2x2_default.json" ]; then
    echo "       WARN: $DEST/configs/waypoints_2x2_default.json missing — re-stage USB"
fi
if [ ! -f "$DEST/uwb_api_hula_swarm/UWBParserThread.py" ]; then
    echo "       WARN: $DEST/uwb_api_hula_swarm/UWBParserThread.py missing — re-stage USB"
fi
# YOLOv11 retraining notebook (base = yolo11n.pt, use _2.py convert scripts).
# Insurance only — RoboMaster detection is ArUco-based (dictionary announced Day-1 by org).
if [ -f "$HERE/Train_YOLO_Models_new.ipynb" ]; then
    cp "$HERE/Train_YOLO_Models_new.ipynb" "$DEST/"
fi
echo "       copied $(find "$DEST" -type f | wc -l) files"

# -------- 3. Verify Python deps are present --------
echo "[3/4] verifying Python deps..."
# Map import name -> PyPI package name. cv2 ships as opencv-contrib-python because
# we need cv2.aruco.ArucoDetector (mapping.py + prototypes); plain opencv-python
# omits the contrib modules.
declare -A PIP_NAMES=(
    [numpy]="numpy"
    [cv2]="opencv-contrib-python"
    [mavsdk]="mavsdk"
    [pyrealsense2]="pyrealsense2"
)
MISSING_IMPORTS=()
MISSING_PIPS=()
for mod in numpy cv2 mavsdk pyrealsense2; do
    if ! python3 -c "import $mod" 2>/dev/null; then
        MISSING_IMPORTS+=("$mod")
        MISSING_PIPS+=("${PIP_NAMES[$mod]}")
    fi
done
# rknn / rknnlite / rclpy live on the mapping drone (Rockchip NPU + ROS2 onboard),
# not on this x86 C2 VM — the VM reaches them via NoMachine, not local imports.
if [ ${#MISSING_IMPORTS[@]} -ne 0 ]; then
    echo "       WARNING: missing modules: ${MISSING_IMPORTS[*]}"
    echo "       Ask org coordinator to install OR run:"
    echo "         pip install --user ${MISSING_PIPS[*]}"
fi

# -------- 4. Smoke test the mapping drone controller (mock mode) --------
echo "[4/4] smoke test (mock mode, no drone needed)..."
if [ -d "$DEST/controllers" ]; then
    cd "$DEST/controllers"
    if python3 -c "from mapping_drone import controller; print('import ok')"; then
        echo "       mapping_drone import: OK"
    else
        echo "       mapping_drone import: FAILED (see traceback above)"
    fi
else
    echo "       SKIP: $DEST/controllers missing — was the USB copied correctly?"
    echo "       Check the cp on the copy step — sources may not exist on this thumbdrive."
fi

echo ""
echo "==== SETUP COMPLETE ===="
echo ""
echo "IMPORTANT: org will NOT provide a map layout — Challenge 1 must discover"
echo "the arena live (obstacles + landing pads). Pre-staged templates"
echo "(configs/waypoints_2x2_default.json + configs/arena_NxN.json) are all at 4.0 m"
echo "above the 3.5 m floor; pick the nearest arena size or populate"
echo "configs/waypoints_<DATE>.json after the arena walk BEFORE the real run."
echo ""
echo "Quick test (mock mapping mission, ~45s):"
echo "  cd $DEST/controllers && python3 -m mapping_drone.controller --mock"
echo ""
echo "Real mapping mission (drone must be ready; real mode is default, no flag needed):"
echo "  python3 -m mapping_drone.controller --waypoints-from-json ../configs/arena_4x4.json"
echo ""
# -------- Hula swarm Challenge 2A/2B --------
# Hula swarm runs on the C2 Terminal WINDOWS side (pyhulax SDK + UWBParserThread.py
# via pyserial @ 921600 baud), NOT inside this Ubuntu VM. See uwb_api_hula_swarm/README.md.
# swarm_controller.py currently ships as a stub (prints 'NOT YET BUILT' and exits 1);
# the content probe below skips the live-invocation block until K replaces the stub.
# NOTE: ArUco dictionary is announced Day-1 (org 2026-06-06: "exact dictionary will be
# announced on the day"); the 2B comment below must read whatever org publishes, not a
# hardcoded value.
if [ -f "$DEST/controllers/swarm_controller.py" ] && ! grep -q "NOT YET BUILT" "$DEST/controllers/swarm_controller.py" 2>/dev/null; then
    echo "Hula swarm Challenge 2A (run on C2 Windows side; landing coords come from Discord per org slide 6, NOT from our C1 output):"
    echo "  python swarm_controller.py --task 2a --landing-coords <FROM_DISCORD>"
    echo ""
    echo "Hula swarm Challenge 2B (RoboMaster hunt):"
    echo "  # RoboMasters carry ArUco markers — ArUco is the primary detector (dictionary"
    echo "  # announced Day-1 by org); YOLOv11 (models/best.rknn) is insurance/backup only."
    echo "  python swarm_controller.py --task 2b --search-pattern lawnmower-3way"
else
    echo "Hula swarm controller (swarm_controller.py) NOT YET BUILT — current file is a stub."
    echo "  Hula swarm runs on the C2 Terminal Windows side using pyhulax + UWBParserThread.py."
    echo "  C2A landing coords come from Discord (org-provided), NOT our C1 output."
    echo "  RoboMaster detection (2B) is ArUco-based (dictionary announced Day-1); YOLO is insurance only."
    echo "  If a controller is ready by event day, copy it to the Windows side and run from there."
fi
echo ""
echo "Outputs land at: $DEST/controllers/mapping_drone/runs/run_<ts>/"
echo "  STATUS.txt          <- live status (judge-readable)"
echo "  top_down.png        <- show judge"
echo "  landing_pads.json   <- show judge"
echo "  markers/*.jpg       <- show judge"
echo "  run_summary.json    <- machine-readable artifact"
echo ""
echo "==== EVENT-DAY REMINDER ===="
echo "  Finals: Wed 10 June + Thu 11 June 2026, both days"
echo "  Venue:  Marina Bay Sands Expo & Convention Centre, Level 4"
echo "  Reg:    10 June 7:30 am — bring Photo ID + confirmation email"
echo "  Dress:  smart casual, no slippers / uncovered footwear"
echo "  Bring:  laptop + mouse + charger + this thumbdrive"
echo "  Team:   all 3 members expected on BOTH days"
echo "============================"

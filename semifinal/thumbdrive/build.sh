#!/usr/bin/env bash
# build.sh — Stage USB contents under ../thumbdrive_build/. Run on dev laptop.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
OUT="$REPO/thumbdrive_build"

echo "==== Staging USB contents ===="
echo "  repo: $REPO"
echo "  out:  $OUT"
echo ""

rm -rf "$OUT"
mkdir -p "$OUT/controllers" "$OUT/models" "$OUT/docs" "$OUT/prototypes" \
         "$OUT/learning_material_3_uwb" "$OUT/learning_material_4_realsense" \
         "$OUT/learning_material_5_yolo_rknn" "$OUT/configs"

# Controllers
echo "[1/8] controllers..."
cp -r "$REPO/semifinal/mapping_drone" "$OUT/controllers/" 2>/dev/null || true
if [ -f "$REPO/semifinal/swarm_controller.py" ]; then
    cp "$REPO/semifinal/swarm_controller.py" "$OUT/controllers/"
fi

# Models
echo "[2/8] models..."
cp "$REPO/models/best.pt" "$OUT/models/" 2>/dev/null || echo "       (no best.pt yet)"
cp "$REPO/models/best.onnx" "$OUT/models/" 2>/dev/null || echo "       (no best.onnx yet — A produces by T-2)"

# Docs
echo "[3/8] docs..."
cp "$REPO/semifinal/CHALLENGE_BREAKDOWN.md" "$OUT/docs/"
cp "$REPO/semifinal/FINALS_PLAN.md" "$OUT/docs/"
cp "$REPO/semifinal/runbook.md" "$OUT/docs/"
cp "$REPO/semifinal/learning_materials_and_others.md" "$OUT/docs/"
cp "$REPO/semifinal/final_challenge_slides.pdf" "$OUT/docs/" 2>/dev/null || true
cp -r "$REPO/semifinal/docs/pyhulax" "$OUT/docs/"

# Prototypes
echo "[4/8] prototypes..."
cp -r "$REPO/semifinal/prototypes" "$OUT/"

# Learning materials
echo "[5/8] learning materials..."
cp -r "$REPO/semifinal/learning_material_3_uwb"/* "$OUT/learning_material_3_uwb/"
cp -r "$REPO/semifinal/learning_material_4_realsense"/* "$OUT/learning_material_4_realsense/"
cp -r "$REPO/semifinal/learning_material_5_yolo_rknn"/* "$OUT/learning_material_5_yolo_rknn/"

# Notebook
echo "[6/8] training notebook..."
cp "$REPO/semifinal/Train_YOLO_Models_new.ipynb" "$OUT/" 2>/dev/null || true

# Configs (waypoints, etc.) — create starter
echo "[7/8] configs..."
cat > "$OUT/configs/arena_waypoints_safe.json" <<'EOF'
{
  "_comment": "Safe default waypoints — overwrite with real arena coords on Day 1 after the arena tour.",
  "_format": "list of [north_m, east_m, altitude_m] in UWB world frame",
  "waypoints": [
    [0.0, 0.0, 1.5],
    [3.0, 0.0, 1.5],
    [3.0, 3.0, 1.5],
    [0.0, 3.0, 1.5],
    [0.0, 0.0, 1.0]
  ]
}
EOF

cat > "$OUT/configs/arena_waypoints_aggressive.json" <<'EOF'
{
  "_comment": "Aggressive waypoints — fewer + further apart, higher altitude for faster mapping.",
  "_format": "list of [north_m, east_m, altitude_m] in UWB world frame",
  "waypoints": [
    [0.0, 0.0, 2.0],
    [4.0, 0.0, 2.0],
    [4.0, 4.0, 2.0],
    [0.0, 4.0, 2.0]
  ]
}
EOF

# Setup script
echo "[8/8] setup script..."
cp "$HERE/setup.sh" "$OUT/"
cp "$HERE/README.md" "$OUT/"

echo ""
echo "==== STAGED ===="
echo "  Files: $(find "$OUT" -type f | wc -l)"
echo "  Size:  $(du -sh "$OUT" | cut -f1)"
echo ""
echo "Next: copy $OUT/* to USB stick #1 and USB stick #2 (identical contents)."
echo "  Verify by re-running this script and confirming no diff."

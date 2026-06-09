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
         "$OUT/learning_material_5_yolo_rknn" "$OUT/uwb_api_hula_swarm" "$OUT/configs"

# Controllers
echo "[1/9] controllers..."
# Challenge 1 entrypoint — fail loudly if source is missing.
if [ ! -d "$REPO/semifinal/mapping_drone" ]; then
    echo "ERROR: $REPO/semifinal/mapping_drone missing — cannot stage Challenge 1 controllers" >&2
    exit 1
fi
cp -r "$REPO/semifinal/mapping_drone" "$OUT/controllers/"
# Strip internal scratch docs from the staged mapping_drone/ tree (we want these OFF the USB).
rm -f "$OUT/controllers/mapping_drone/FIX_SUMMARY.md" \
      "$OUT/controllers/mapping_drone/FIX_V3_SUMMARY.md" \
      "$OUT/controllers/mapping_drone/REVIEW_SUMMARY.md"
# Belt-and-braces: nuke any other FIX_*.md or REVIEW_SUMMARY.md that slipped in (e.g. nested dirs).
find "$OUT/controllers/mapping_drone" -type f \( -name 'FIX_*.md' -o -name 'REVIEW_SUMMARY.md' \) -delete
# Hula swarm code that actually exists in the repo (swarm_controller.py NOT YET BUILT — placeholder).
cp "$REPO/semifinal/dola.py" "$OUT/controllers/"
cp "$REPO/semifinal/huladola.py" "$OUT/controllers/"
if [ -f "$REPO/semifinal/swarm_controller.py" ]; then
    cp "$REPO/semifinal/swarm_controller.py" "$OUT/controllers/"
else
    echo "       WARNING: swarm_controller.py NOT FOUND (TODO: file does not exist) — using dola.py/huladola.py as Hula stack" >&2
fi

# Models
echo "[2/9] models..."
cp "$REPO/models/best.pt" "$OUT/models/" 2>/dev/null || echo "       (no best.pt yet)"
cp "$REPO/models/best.onnx" "$OUT/models/" 2>/dev/null || echo "       (no best.onnx — A's YOLO is now backup/insurance only; ArUco is primary per 2026-06-06)"

# Docs
echo "[3/9] docs..."
cp "$REPO/semifinal/CHALLENGE_BREAKDOWN.md" "$OUT/docs/"
cp "$REPO/semifinal/FINALS_PLAN.md" "$OUT/docs/"
cp "$REPO/semifinal/runbook.md" "$OUT/docs/"
cp "$REPO/semifinal/learning_materials_and_others.md" "$OUT/docs/"
# Authoritative org pptx extract (received 2026-06-09) — most-authoritative document.
cp "$REPO/semifinal/finals_brief_extracted.md" "$OUT/docs/"
# Day-1 operations library — operator on C2 Terminal needs offline copies at the venue.
for f in DAY1_RUNBOOK.md DAY1_POCKET_CARD.md DAY1_SETUP_SEQUENCE.md \
         SCORING_PLAYBOOK.md HANDOFF_C1_TO_C2.md CONVOY_OPPONENT_ROLE.md \
         D430_RGB_RISK.md ORG_TICKETS_DRAFT.md README.md; do
    cp "$REPO/semifinal/$f" "$OUT/docs/"
done
cp "$REPO/semifinal/final_challenge_slides.pdf" "$OUT/docs/" 2>/dev/null || true
cp -r "$REPO/semifinal/docs/pyhulax" "$OUT/docs/"

# Prototypes
echo "[4/9] prototypes..."
cp -r "$REPO/semifinal/prototypes" "$OUT/"

# Learning materials
echo "[5/9] learning materials..."
cp -r "$REPO/semifinal/learning_material_3_uwb"/* "$OUT/learning_material_3_uwb/"
cp -r "$REPO/semifinal/learning_material_4_realsense"/* "$OUT/learning_material_4_realsense/"
cp -r "$REPO/semifinal/learning_material_5_yolo_rknn"/* "$OUT/learning_material_5_yolo_rknn/"

# UWB API for Hula swarm (org-released 2026-06-06, runs on C2 Terminal Windows side)
echo "[6/9] uwb_api_hula_swarm..."
cp -r "$REPO/semifinal/uwb_api_hula_swarm"/* "$OUT/uwb_api_hula_swarm/"

# Notebook
echo "[7/9] training notebook..."
# Train_YOLO_Models_new.ipynb lives under learning_material_5_yolo_rknn/ and is already staged
# by step [5/9]. No top-level copy — A killed YOLO training 2026-06-06, notebook is historical only.

# Configs (waypoints, validity templates) — copy the real curated files at 4.0m (above the 3.5m floor).
# Inline heredocs were removed: they wrote {waypoints:[...]} dict-wrapped JSON, but controller.py's
# _parse_waypoints_json expects a bare list [[n,e,alt],...] so loads would have died with
# ValueError: expected a JSON list, got dict. The real configs (arena_NxN.json,
# waypoints_2x2_default.json, valid_ids_*.json) are already at 4.0m and the correct schema.
echo "[8/9] configs..."
if [ ! -d "$REPO/semifinal/configs" ]; then
    echo "ERROR: $REPO/semifinal/configs missing — cannot stage waypoint/validity templates" >&2
    exit 1
fi
cp -r "$REPO/semifinal/configs"/* "$OUT/configs/"

# Setup script
echo "[9/9] setup script..."
cp "$HERE/setup.sh" "$OUT/"
cp "$HERE/README.md" "$OUT/"

echo ""
echo "==== STAGED ===="
echo "  Files: $(find "$OUT" -type f | wc -l)"
echo "  Size:  $(du -sh "$OUT" | cut -f1)"
echo ""
echo "Next: copy $OUT/* to USB stick #1 and USB stick #2 (identical contents)."
echo "  Verify by re-running this script and confirming no diff."

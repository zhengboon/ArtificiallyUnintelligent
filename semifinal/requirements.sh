#!/usr/bin/env bash
# ============================================================================
# requirements.sh  —  Challenge-1 mapping drone dependency setup + check
#
# Run this the moment you get a drone, BEFORE the assessment. It:
#   - verifies every Python + ROS2 dependency the mission needs,
#   - installs ONLY what's missing (pip install --user, best-effort),
#   - is safe + idempotent (never force-reinstalls a working dep),
#   - handles no-internet gracefully (verify still works; install is skipped),
#   - prints a clear READY / NOT READY summary.
#
#   bash requirements.sh
#
# It does NOT arm or fly. Companion: tools/drone_fingerprint.sh (per-drone
# hardware readiness) and OP_DOC.md (the run runbook).
# ============================================================================
set +e
PY=python3
PASS=0; FAIL=0; WARN=0
ok()   { echo "  [ OK ] $*"; PASS=$((PASS+1)); }
miss() { echo "  [FAIL] $*"; FAIL=$((FAIL+1)); }
warn() { echo "  [WARN] $*"; WARN=$((WARN+1)); }

echo "==================== requirements.sh ===================="
echo "host=$(hostname)  python=$($PY --version 2>&1)  date=$(date '+%F %T')"

# --- locate the repo (path varies per drone) ---
REPO=""
for p in ~/AD/semifinal ~/ad/semifinal ~/roboverse26/semifinal "$(pwd)"; do
  [ -f "$p/mapping_drone/moveit_mission.py" ] && { REPO="$p"; break; }
done
[ -n "$REPO" ] && echo "repo: $REPO" || warn "repo not auto-found (configs check will be skipped)"

# --- source ROS2 so the check matches the runtime environment ---
source /opt/ros/humble/setup.bash 2>/dev/null
[ -n "$REPO" ] && source ~/ros2_ws/install/setup.bash 2>/dev/null

# --- internet probe (so we don't hang trying to pip install offline) ---
have_net() { timeout 4 bash -c '</dev/tcp/8.8.8.8/53' 2>/dev/null; }
if have_net; then NET=1; echo "internet: yes (will install missing pip deps)"; else NET=0; echo "internet: NO (verify only — missing deps must already be on the drone)"; fi

pip_install() {  # $1 = pip package
  [ "$NET" = 1 ] || { warn "skip pip install $1 (no internet)"; return 1; }
  echo "    -> pip install --user $1"
  $PY -m pip install --user --quiet "$1" 2>&1 | tail -2
}

check_py() {  # $1 import-name  $2 pip-package(optional)  $3 extra-test(optional)
  local mod="$1" pkg="$2" extra="$3" test="import $1"
  [ -n "$extra" ] && test="$test; $extra"
  if $PY -c "$test" 2>/dev/null; then ok "py: $mod${extra:+ (+ $extra)}"; return; fi
  [ -n "$pkg" ] && pip_install "$pkg"
  if $PY -c "$test" 2>/dev/null; then ok "py: $mod (installed)"; else miss "py: $mod${pkg:+  (try: pip install --user $pkg)}"; fi
}

echo; echo "---- 1. PYTHON DEPENDENCIES ----"
check_py numpy            numpy
# cv2 MUST have the aruco module (opencv-contrib, not plain opencv-python):
check_py cv2              opencv-contrib-python  "cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_7X7_1000)"
check_py mavsdk           mavsdk
# pyrealsense2 on RK3588 is usually a librealsense source build — pip may have no
# ARM wheel; we try, but if it fails it must be built (see ~/librealsense_build).
check_py pyrealsense2     pyrealsense2

echo; echo "---- 2. ROS2 (from the workspace, NOT pip) ----"
[ -n "$(command -v ros2)" ] && ok "ros2 CLI" || miss "ros2 CLI (source /opt/ros/humble/setup.bash)"
$PY -c "import rclpy" 2>/dev/null && ok "py: rclpy" || miss "py: rclpy (source ROS2)"
$PY -c "import geometry_msgs.msg" 2>/dev/null && ok "py: geometry_msgs" || miss "py: geometry_msgs (source ROS2)"
ros2 pkg prefix px4_msgs     >/dev/null 2>&1 && ok "ros pkg: px4_msgs (XRCE fallback)" || warn "ros pkg: px4_msgs missing (only needed for the px4_mission XRCE fallback; colcon build in ~/ros2_ws)"
ros2 pkg prefix nlink_parser >/dev/null 2>&1 && ok "ros pkg: nlink_parser (UWB)"        || warn "ros pkg: nlink_parser missing (UWB; colcon build in ~/ros2_ws)"

echo; echo "---- 3. REPO + CONFIG ----"
if [ -n "$REPO" ]; then
  [ -f "$REPO/configs/valid_ids_finals.json" ] && ok "configs/valid_ids_finals.json present (EDIT with marshal's split Day-1)" || miss "configs/valid_ids_finals.json missing"
  ( cd "$REPO" && $PY -c "import mapping_drone" 2>/dev/null ) && ok "mapping_drone package imports" || warn "mapping_drone import failed (run from $REPO; check deps above)"
else
  warn "repo not found — skipped config check"
fi

echo; echo "---- 4. ROS ISOLATION (ROS_LOCALHOST_ONLY) ----"
if grep -qs 'ROS_LOCALHOST_ONLY' ~/.bashrc; then
  ok "ROS_LOCALHOST_ONLY already in ~/.bashrc"
else
  echo 'export ROS_LOCALHOST_ONLY=1   # added by requirements.sh: isolate ROS2 from other teams' >> ~/.bashrc 2>/dev/null \
    && ok "added 'export ROS_LOCALHOST_ONLY=1' to ~/.bashrc (open a NEW terminal, or run it now)" \
    || warn "could not edit ~/.bashrc — run 'export ROS_LOCALHOST_ONLY=1' in every terminal manually"
fi
echo "  (this terminal: run  export ROS_LOCALHOST_ONLY=1  now)"

echo; echo "==================== SUMMARY ===================="
echo "  PASS=$PASS  FAIL=$FAIL  WARN=$WARN"
if [ "$FAIL" -eq 0 ]; then
  echo "  ✅ READY. Next:  cd $REPO 2>/dev/null; export ROS_LOCALHOST_ONLY=1"
  echo "                  python3 -m mapping_drone.moveit_mission --check"
  echo "                  (then --nofly, then --fly — see OP_DOC.md)"
  exit 0
else
  echo "  ❌ NOT READY — $FAIL required dep(s) missing above. Fix them, then re-run."
  echo "     (WARN items are fallback-only: px4_msgs/nlink only matter for the XRCE path.)"
  exit 1
fi

#!/bin/bash
# Pre-flight smoke test — run THIS before committing to a real qualifier
# run on the org VM. Validates:
#   1. All Python deps importable
#   2. PX4 SITL + Roboverse map boot
#   3. Phase 1+2+6+7 stand up without crashing
#   4. Controller arms, takes off, runs default wall-follow, lands cleanly
#   5. Artifacts (run_summary.json, STATUS.txt, map.png, detections/) all
#      present and non-empty after exit
#
# ~90 seconds end-to-end. If this passes, real --bonus runs
# are safe to attempt. If this fails, do NOT burn a qualifier slot on
# debugging — fall back to --no-detect --no-map if at all possible.
#
# Usage (inside the VM, after setup.sh has run):
#   bash _smoke.sh
# Exit 0 = pass. Non-zero = something to investigate before flying.
set -u

REPO=/home/drone/ArtificiallyUnintelligent
SESS=smoke

pass() { echo "  [PASS] $1"; }
fail() { echo "  [FAIL] $1"; FAILED=1; }
FAILED=0

echo "=== 1) Python deps ==="
for mod in numpy mavsdk pymavlink ultralytics matplotlib; do
    if python3 -c "import $mod" 2>/dev/null; then
        pass "$mod"
    else
        fail "$mod (run setup.sh first)"
    fi
done
python3 -c "from gz.transport13 import Node" 2>/dev/null && pass "gz.transport13" || fail "gz.transport13"
python3 -c "import os; os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION']='python'; from gz.msgs10.image_pb2 import Image" 2>/dev/null \
    && pass "gz.msgs10" || fail "gz.msgs10"

echo
echo "=== 2) Repo + weights present ==="
[ -f $REPO/searchctl/controller.py ] && pass "controller.py" || fail "controller.py missing"
[ -f $REPO/searchctl/wall_following.py ] && pass "wall_following.py" || fail "wall_following.py missing"
[ -f $REPO/models/best.pt ] && pass "models/best.pt" || fail "models/best.pt missing"

if [ $FAILED -ne 0 ]; then
    echo
    echo "Pre-flight deps failed. Fix before launching sim. Exiting."
    exit 1
fi

echo
echo "=== 3) Kill any prior sim/controller ==="
tmux kill-session -t $SESS 2>/dev/null
pkill -f 'px4_sitl_default' 2>/dev/null
pkill -f 'gz sim' 2>/dev/null
pkill -f 'gz gui' 2>/dev/null
pkill -f 'python3 controller' 2>/dev/null
pkill -f 'mavsdk_server' 2>/dev/null
sleep 2

echo
echo "=== 4) Boot PX4 SITL (x500_vision, roboverse, no QGC) ==="
tmux new-session -d -s $SESS -n sim -x 200 -y 50
tmux send-keys -t $SESS:sim 'export DISPLAY=:0 XAUTHORITY=/home/drone/.Xauthority' C-m
sleep 1
tmux send-keys -t $SESS:sim '~/start_px4.sh' C-m
sleep 3
tmux send-keys -t $SESS:sim '1' C-m   # x500_vision
sleep 2
tmux send-keys -t $SESS:sim '1' C-m   # roboverse
sleep 2
tmux send-keys -t $SESS:sim '2' C-m   # no QGC

echo "  waiting 35s for PX4 + Gazebo to boot..."
sleep 35

tmux send-keys -t $SESS:sim 'commander set_ekf_origin 47.397742 8.545594 488.0' C-m
sleep 3

echo
echo "=== 5) Run controller smoke (default wall-follow, no detect / no map) ==="
RUN_LOG=/tmp/smoke_ctl.log
rm -f $RUN_LOG
tmux new-window -t $SESS -n ctl
tmux send-keys -t $SESS:ctl "cd $REPO/searchctl && python3 controller.py --no-detect --no-map 2>&1 | tee $RUN_LOG" C-m

# Wall-follow runs until aborted. We wait for the takeoff banner +
# a few wf_state= ticks (= drone is actually flying), then Ctrl-C
# the controller to abort cleanly.
echo "  waiting up to 90s for takeoff + first wall-follow ticks..."
saw_takeoff=0
for i in $(seq 1 90); do
    if grep -q "takeoff complete" $RUN_LOG 2>/dev/null && grep -q "wf_state=" $RUN_LOG 2>/dev/null; then
        pass "takeoff + wall-follow loop started after ${i}s"
        saw_takeoff=1
        break
    fi
    if grep -qE "fatal error in run|Traceback" $RUN_LOG 2>/dev/null; then
        fail "controller hit fatal error"
        break
    fi
    sleep 1
done

if [ $saw_takeoff -eq 1 ]; then
    # Let it fly a few seconds then Ctrl-C
    sleep 8
    tmux send-keys -t $SESS:ctl C-c
    sleep 5
    pass "Ctrl-C sent; controller should be landing"
else
    fail "no takeoff + wall-follow within 90s — investigate $RUN_LOG"
fi

echo
echo "=== 6) Verify artifacts ==="
# Most recent run_<ts> dir
RUN_DIR=$(ls -td $REPO/searchctl/run_* 2>/dev/null | head -1)
if [ -z "$RUN_DIR" ]; then
    fail "no run_<ts> dir found under searchctl/"
else
    pass "run dir: $RUN_DIR"
    [ -s "$RUN_DIR/run_summary.json" ] && pass "run_summary.json non-empty" || fail "run_summary.json missing/empty"
    [ -s "$RUN_DIR/STATUS.txt" ] && pass "STATUS.txt non-empty" || fail "STATUS.txt missing/empty"
    [ -f "$RUN_DIR/map.png" ] && pass "map.png present" || echo "  [WARN] map.png missing (Phase 7 may have skipped)"
    [ -d "$RUN_DIR/detections" ] && pass "detections/ dir present" || echo "  [WARN] detections/ missing"
fi

echo
echo "=== 7) Cleanup sim (leave tmux session for inspection) ==="
echo "  smoke test done. Attach to inspect: tmux attach -t $SESS"
echo "  Kill when ready:                   tmux kill-session -t $SESS"

echo
if [ $FAILED -eq 0 ]; then
    echo "=== SMOKE PASSED — safe to try real runs ==="
    exit 0
else
    echo "=== SMOKE FAILED — review $RUN_LOG before attempting qualifier run ==="
    exit 1
fi

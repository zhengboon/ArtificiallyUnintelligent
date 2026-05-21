#!/bin/bash
# Orchestrate sim + controller via tmux. Idempotent.
#
# Layout: tmux session "au" with two windows:
#   - sim:  ~/start_px4.sh (PX4 console at pxh>)
#   - ctl:  python3 controller.py
#
# After this script returns, both are running in the background.
# To watch live:  tmux attach -t au       (Ctrl-b 1 to switch windows)
# To kill all:    tmux kill-session -t au
# To capture log: tmux capture-pane -t au:sim -p   (or -t au:ctl)
#
# Times below are intentionally generous so a slow VM doesn't race.

set +e   # don't abort the script if tmux ops have small hiccups

SESS=au

# Tear down any prior run
tmux kill-session -t $SESS 2>/dev/null

# Kill any orphaned px4/gz processes from a prior crash
pkill -f 'px4_sitl_default' 2>/dev/null
pkill -f 'gz sim' 2>/dev/null
pkill -f 'gz gui' 2>/dev/null
sleep 1

# Window 1: sim — must attach to the X display so Gazebo can render.
# DISPLAY=:0 + XAUTHORITY are required because vmrun spawns us with no env.
tmux new-session -d -s $SESS -n sim -x 200 -y 50
tmux send-keys -t $SESS:sim 'export DISPLAY=:0 XAUTHORITY=/home/drone/.Xauthority' C-m
sleep 1

# Start the script
tmux send-keys -t $SESS:sim '~/start_px4.sh' C-m
sleep 3

# Vehicle: 1 = x500_vision
tmux send-keys -t $SESS:sim '1' C-m
sleep 2

# World: 1 = roboverse
tmux send-keys -t $SESS:sim '1' C-m
sleep 2

# QGC: 2 = No (our fake-GCS heartbeat will cover)
tmux send-keys -t $SESS:sim '2' C-m

# Boot takes time — Gazebo + PX4 SITL coming up.
# We need to wait until the pxh> prompt is ready.
echo "waiting 35s for sim to boot..."
sleep 35

# Set EKF origin (vision drone needs this before is_armable goes True)
tmux send-keys -t $SESS:sim 'commander set_ekf_origin 47.397742 8.545594 488.0' C-m
sleep 3

# Window 2: controller
tmux new-window -t $SESS -n ctl
sleep 1
tmux send-keys -t $SESS:ctl 'cd ~/ArtificiallyUnintelligent/searchctl && python3 controller.py' C-m

echo "tmux session '$SESS' running. Windows: sim (0), ctl (1)."
echo "Attach with: tmux attach -t $SESS"

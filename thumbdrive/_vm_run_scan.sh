#!/bin/bash
# Variant of _vm_run_sim.sh but uses --pattern scan in the ctl window.
set +e
SESS=au
tmux kill-session -t $SESS 2>/dev/null
pkill -f 'px4_sitl_default' 2>/dev/null
pkill -f 'gz sim' 2>/dev/null
pkill -f 'gz gui' 2>/dev/null
pkill -f 'python3 controller' 2>/dev/null
pkill -f 'mavsdk_server' 2>/dev/null
sleep 2

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

echo "waiting 35s for sim to boot..."
sleep 35

tmux send-keys -t $SESS:sim 'commander set_ekf_origin 47.397742 8.545594 488.0' C-m
sleep 3

tmux new-window -t $SESS -n ctl
sleep 1
tmux send-keys -t $SESS:ctl 'cd ~/ArtificiallyUnintelligent/searchctl && python3 controller.py --pattern scan' C-m

echo "tmux session '$SESS' running with --pattern scan."
echo "Attach: tmux attach -t $SESS"

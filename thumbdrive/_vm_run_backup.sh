#!/bin/bash
# BACKUP NAV: scan-and-walk explorer.
# Use this if K's primary wall-follow misbehaves (gets stuck, EKF
# diverges, fails to find both colours) or didn't find a yellow
# barrel. Different algo entirely — covers arena interior instead
# of perimeter walls.
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
tmux send-keys -t $SESS:ctl 'cd ~/ArtificiallyUnintelligent/searchctl && python3 controller.py --backup --bonus' C-m

echo "tmux session '$SESS' running with --backup --bonus (scan-and-walk explorer)."
echo "Attach: tmux attach -t $SESS"
echo "Expected: hover+scan, walk forward 10s, repeat. Hard-land at 4:20."

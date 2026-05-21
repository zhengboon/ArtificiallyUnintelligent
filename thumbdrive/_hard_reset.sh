#!/bin/bash
# HARD reset: kill all sim/controller processes + clean stale tmp.
set +e
echo "=== killing processes ==="
pkill -9 -f 'python3 controller' 2>/dev/null
pkill -9 -f mavsdk_server 2>/dev/null
pkill -9 -f px4_sitl 2>/dev/null
pkill -9 -f 'px4 ' 2>/dev/null
pkill -9 -f 'gz sim' 2>/dev/null
pkill -9 -f 'gz gui' 2>/dev/null
pkill -9 -f gz_bridge 2>/dev/null
tmux kill-server 2>/dev/null
sleep 3
echo "=== after kill ==="
ps -ef | grep -E "python3 controller|mavsdk|px4_sitl|gz sim|gz gui|gz_bridge" | grep -v grep
echo "=== disk free ==="
df -h / | tail -1
echo "=== clean PX4 logs (free disk for fresh run) ==="
rm -rf ~/PX4-Autopilot/build/px4_sitl_default/rootfs/log/* 2>/dev/null
echo "  cleared. now:"
df -h / | tail -1

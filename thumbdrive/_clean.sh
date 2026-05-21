#!/bin/bash
pkill -9 -f "python3 controller" 2>/dev/null
pkill -9 -f mavsdk_server 2>/dev/null
pkill -9 -f px4 2>/dev/null
pkill -9 -f "gz sim" 2>/dev/null
pkill -9 -f "gz gui" 2>/dev/null
tmux kill-server 2>/dev/null
sleep 2
echo "==== remaining ===="
ps -ef | grep -E "python3 controller|mavsdk|px4_sitl|gz sim" | grep -v grep
echo "==== tmux ===="
tmux ls 2>&1
echo "==== disk ===="
df -h / | tail -1
echo "==== AU latest ===="
ls -la /home/drone/ArtificiallyUnintelligent/searchctl/controller.py 2>&1
ls -la /home/drone/ArtificiallyUnintelligent/models/ 2>&1

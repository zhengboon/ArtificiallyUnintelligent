#!/bin/bash
# Disk audit — what's taking space in the v3 VM.
# Run in any VM terminal. Paste the entire output back.

echo "==== OVERALL DISK ===="
df -h /

echo
echo "==== HOME DIR (top 20 biggest) ===="
du -sh ~/.??* ~/* 2>/dev/null | sort -hr | head -20

echo
echo "==== PX4 LOGS (the known offender) ===="
PX4_LOGS=~/PX4-Autopilot/build/px4_sitl_default/rootfs/log
if [ -d "$PX4_LOGS" ]; then
    du -sh "$PX4_LOGS"
    echo "Number of log files: $(find "$PX4_LOGS" -type f | wc -l)"
fi

echo
echo "==== OUR DEPLOY (~/ArtificiallyUnintelligent) ===="
AU=~/ArtificiallyUnintelligent
if [ -d "$AU" ]; then
    du -sh "$AU"
    du -sh "$AU"/* 2>/dev/null | sort -hr | head -10
fi

echo
echo "==== OUR RUN DIRS (logs/run_* + run_*) ===="
if [ -d ~/ArtificiallyUnintelligent/searchctl ]; then
    du -sh ~/ArtificiallyUnintelligent/searchctl/logs 2>/dev/null
    du -sh ~/ArtificiallyUnintelligent/searchctl/run_* 2>/dev/null
fi

echo
echo "==== WORKSHOP CODES (~/Desktop/codes) ===="
[ -d ~/Desktop/codes ] && du -sh ~/Desktop/codes

echo
echo "==== APT CACHE + PIP CACHE ===="
[ -d /var/cache/apt/archives ] && sudo du -sh /var/cache/apt/archives 2>/dev/null
[ -d ~/.cache/pip ] && du -sh ~/.cache/pip

echo
echo "==== PIP USER PACKAGES (the big ones) ===="
du -sh ~/.local/lib/python*/site-packages 2>/dev/null
du -sh ~/.local/lib/python*/site-packages/* 2>/dev/null | sort -hr | head -10

echo
echo "==== TOTAL FREE ===="
df -h / | tail -1

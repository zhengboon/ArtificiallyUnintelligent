#!/bin/bash
echo "================ SIM WINDOW ================"
tmux capture-pane -t au:sim -p -S -200 2>&1 || echo "(sim window not capturable)"
echo
echo "================ CTL WINDOW ================"
tmux capture-pane -t au:ctl -p -S -200 2>&1 || echo "(ctl window not capturable)"
echo
echo "================ TMUX STATUS ================"
tmux list-sessions 2>&1
tmux list-windows -t au 2>&1
echo
echo "================ CONTROLLER LOG ================"
ls -la /home/drone/ArtificiallyUnintelligent/searchctl/logs/ 2>&1 | tail -5
LATEST=$(ls -t /home/drone/ArtificiallyUnintelligent/searchctl/logs/run_*.log 2>/dev/null | head -1)
if [ -n "$LATEST" ]; then
    echo "--- last 50 lines of $LATEST ---"
    tail -50 "$LATEST"
fi

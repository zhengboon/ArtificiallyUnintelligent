#!/usr/bin/env bash
# wrap.sh — run any command and broadcast its stdout+stderr to log_sink on
# the desktop over Tailscale. Lines also show locally as normal.
#
# Setup:
#   1. Set the env var DESKTOP_HOST to the desktop's tailnet hostname or IP.
#      Once: export DESKTOP_HOST=desktop-zheng        (put in ~/.bashrc)
#      Or:   export DESKTOP_HOST=100.x.y.z
#   2. Ensure log_sink.py is running on the desktop (port 9999).
#
# Usage:
#   ./wrap.sh <tag> <command...>
#
# Examples:
#   ./wrap.sh hula_smoke python3 hula_smoke_test.py
#   ./wrap.sh arr_test   python3 -c "import time; [print(i) or time.sleep(0.5) for i in range(20)]"
#
# Each line is POSTed to http://$DESKTOP_HOST:9999/<tag>
# Desktop appends to D:/hackerverse/laptop_logs/<tag>.log

set -u

DESKTOP_HOST="${DESKTOP_HOST:-}"
PORT="${LOG_SINK_PORT:-9999}"

if [[ -z "$DESKTOP_HOST" ]]; then
  echo "wrap.sh: error: set DESKTOP_HOST to the desktop's tailnet name or IP" >&2
  echo "  export DESKTOP_HOST=desktop-name" >&2
  exit 1
fi

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <tag> <command...>" >&2
  exit 1
fi

TAG="$1"; shift
URL="http://${DESKTOP_HOST}:${PORT}/${TAG}"

# Pre-flight health check (1s timeout). Warn but don't abort.
if command -v curl >/dev/null; then
  if ! curl -sS --max-time 1 "http://${DESKTOP_HOST}:${PORT}/_health" >/dev/null 2>&1; then
    echo "wrap.sh: WARN: log_sink not reachable at ${DESKTOP_HOST}:${PORT}, continuing anyway" >&2
  fi
fi

# Run the command, tee output locally + POST each line to sink.
# Use stdbuf to avoid pipe buffering (lines stream immediately).
exec stdbuf -oL -eL "$@" 2>&1 | while IFS= read -r line; do
  printf '%s\n' "$line"                                                # local
  curl -sS --max-time 2 -X POST --data-binary "$line" "$URL" >/dev/null 2>&1 || true
done

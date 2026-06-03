# Log Broadcaster

Stream a laptop process's stdout/stderr to the desktop in real time over Tailscale, so the desktop assistant can read it like a file.

## Pieces

| File | Runs on | Purpose |
|---|---|---|
| `log_sink.py` | desktop | HTTP server, POST `/tag` → appends to `laptop_logs/tag.log` |
| `wrap.sh` | laptop | Wraps any command, POSTs every output line to the sink |

## Setup

### On the desktop (one-time)
```bash
# Start the sink (port 9999, default dir D:/hackerverse/laptop_logs/)
python3 D:/hackerverse/tools/log_broadcaster/log_sink.py

# Optional: change port or output dir
python3 .../log_sink.py --port 8888 --dir D:/some/other/dir
```

Leave it running in a terminal (or daemonise via Task Scheduler / NSSM).

Test it works:
```bash
curl http://localhost:9999/_health         # → ok
curl -X POST -d "hello" http://localhost:9999/test
cat D:/hackerverse/laptop_logs/test.log    # → 2026-06-03T20:00:00  hello
```

### On the laptop (one-time)
```bash
# Tell wrap.sh where the desktop lives on Tailscale
export DESKTOP_HOST=<desktop-tailnet-name-or-ip>     # e.g. desktop-zheng or 100.x.y.z
# Make it permanent
echo 'export DESKTOP_HOST=<your-desktop>' >> ~/.bashrc

# Smoke test the sink connection
curl http://$DESKTOP_HOST:9999/_health     # → ok
```

## Usage

On the laptop:
```bash
# General form:
./wrap.sh <tag> <command>

# Examples:
./wrap.sh hula_smoke      python3 hula_smoke_test.py
./wrap.sh aruco_test      python3 aruco_test.py
./wrap.sh swarm_run_1     python3 semifinal/controller.py
```

Each line appears:
- locally on the laptop terminal (just like normal output)
- on the desktop at `D:/hackerverse/laptop_logs/<tag>.log`, with a server timestamp prefix

## How the desktop assistant uses it

The assistant reads from `D:/hackerverse/laptop_logs/` directly. To monitor a live run, the assistant can `tail -f` (or just read the file again whenever asked).

## Caveats

- One HTTP call per output line. Fine for normal logs. For very chatty streams (>100 Hz), batch first (e.g., `pv -L 50` or write to a file and tail).
- Tailscale offline → POSTs fail silently, lines still print locally. Drone unaffected.
- No auth — Tailnet membership is the auth. Don't expose port 9999 publicly.
- Lines >1MB will work but waste bandwidth. Truncate or chunk.

## Disabling

Just stop using `wrap.sh`. There's no daemon on the laptop. The sink on the desktop can stay running idle.

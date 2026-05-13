# searchctl — RoboVerse search controller

Our own controller, replacing the workshop's `avoid.py`. Built for
reliability: independent setpoint-pumper task, watchdog, emergency-land
on any failure path, file-based logs.

## Phases

| Phase | Status | Scope |
|---|---|---|
| **1** | **building now** | Heartbeat + scripted-waypoint smoke flight. No detection. Goal: prove the offboard heartbeat survives a full flight. |
| 2 | next | Add YOLO detector as a background task. Print detections. |
| 3 | next next | Lawnmower search strategy across the 40×40 arena, 2-altitude passes. |
| 4 | later | Detection dedup by NED position; restart-resilient state. |
| 5 | later | Frontier exploration (port from `pastproject/`) for irregular maps. |

## Prereqs (one-time in the VM)

1. **The sim must be running.** Open a terminal in the VM:
   ```
   ~/start_px4.sh
   ```
   Pick `1` (x500_vision), pick `roboverse`, pick `1` (Yes) for QGC.
2. **EKF origin must be set in the PX4 console** (the same terminal where
   `start_px4.sh` is running, at the `pxh>` prompt):
   ```
   commander set_ekf_origin 47.397742 8.545594 488.0
   ```
   This is the one preflight step the controller *can't* do itself —
   `commander` is a PX4 shell command, not a MAVLink message.

   The battery/supply-check workarounds (`CBRK_SUPPLY_CHK`,
   `SIM_BAT_MIN_PCT`) are now done automatically by the controller via
   MAVSDK's param plugin. No need to type them manually.

## Running

From inside the VM:

```bash
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python  # only needed when we add gz-transport in Phase 2
cd ~/searchctl
python3 controller.py
```

You can pass `--log-level DEBUG` to see the setpoint pumper's debug
messages.

## What Phase 1 does

The drone:
1. Connects to PX4 SITL on UDP 14540
2. Sets `CBRK_SUPPLY_CHK=894281` and `SIM_BAT_MIN_PCT=100` via MAVSDK
3. Waits until `is_armable=True` (max 45 s)
4. Arms, takes off to 2 m altitude
5. Enters offboard mode
6. Background tasks start: setpoint pumper @ 10 Hz, telemetry monitor, 30-s watchdog
7. Flies a 4×4 m square at 2 m alt, rotating to face each leg:
   ```
   N4 → E4 → S4 → W4 → home
   ```
   ~30 s of flight total
8. Lands, disarms, exits

## Reliability features

| Feature | Why |
|---|---|
| **Setpoint pumper is its own asyncio task** | Sends the current target at 10 Hz no matter what the planner is doing. PX4's 0.5-s heartbeat timeout never fires. This is the exact thing the workshop's `avoid.py` doesn't do. |
| **Watchdog task** | If the planner makes no progress for 30 s, sets `abort_requested=True` → all tasks unwind → emergency land. |
| **`emergency_land` on any failure path** | KeyboardInterrupt, watchdog trip, fatal exception — all funnel through the same land+disarm coroutine. Drone won't be left armed in the air. |
| **Signal handlers** | SIGINT/SIGTERM flip the abort flag the same way the watchdog does. |
| **File logs** | Every run logs to `searchctl/logs/run_<timestamp>.log`. Survives terminal closure / crash. |
| **No `time.sleep`** | Only `await asyncio.sleep`. Never blocks the asyncio loop → heartbeat is always serviced. |
| **Preflight done in code, not human typing** | Battery params applied via MAVSDK before arming. One less thing to forget at the qualifier. |

## Files

| Path | What |
|---|---|
| `controller.py` | The whole thing for now. Will split as it grows. |
| `logs/` | One file per run. Gitignored in the parent `.gitignore`. |
| `README.md` | This file. |

## Deploy to the VM

The Python script lives on the Windows host (in this folder). To run it
inside the VM, copy it over via `vmrun`:

```powershell
$vmrun = "C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe"
$vmx = "D:\hackerverse\vm\Drone-Ubuntu-22.04\Drone-Ubuntu-22.04.vmx"

# Ensure the dest dir exists, then copy the file
& $vmrun -T ws -gu drone -gp password runScriptInGuest $vmx /bin/bash "mkdir -p /home/drone/searchctl"
& $vmrun -T ws -gu drone -gp password copyFileFromHostToGuest $vmx `
    "D:\hackerverse\searchctl\controller.py" `
    "/home/drone/searchctl/controller.py"
```

Then either run it via vmrun (no GUI feedback) or open a VM terminal and
run it directly:

```bash
cd ~/searchctl
python3 controller.py
```

## When this Phase 1 works

You'll see in the log:
```
==== searchctl controller v0.1 ====
PX4 connected
CBRK_SUPPLY_CHK set to 894281 (supply check bypassed)
SIM_BAT_MIN_PCT set to 100.0 (battery pinned full)
is_armable=True; OK to arm
arming
takeoff to 2.0 m
takeoff complete
offboard mode started
WP 1/6 — hover above start ...
  arrived (pos err=0.12 m, yaw err=2.1 deg)
  holding 3.0 s
WP 2/6 — forward 4 m, facing N ...
  ...
landing
on ground; disarming
run finished cleanly
```

And the drone in Gazebo will have actually flown the square. If any
step prints `emergency_land triggered`, we have something to debug —
the log file at `logs/run_*.log` will say what.

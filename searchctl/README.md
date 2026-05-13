# searchctl — RoboVerse search controller

Our own controller, replacing the workshop's `avoid.py`. Built for
reliability: independent setpoint-pumper task, watchdog, emergency-land
on any failure path, file-based logs.

## Phases

| Phase | Status | Scope |
|---|---|---|
| **1** | **✅ DONE 2026-05-13** | Heartbeat + scripted-waypoint smoke flight. v2: yaw locked at 0°, 2 m moves, divergence watchdog. Flew clean 5-WP square in 33 s, sub-0.5 m pos err on every WP. |
| **2** | **next** | Add YOLO detector as a background task using `gzphotodetectorsaver.py`'s pattern. Print detections with NED position. |
| 3 | next next | Lawnmower search strategy across the 40×40 arena, 2-altitude passes (1 m for yellow, 3.5 m for red). |
| 4 | later | Detection dedup by NED position; restart-resilient state (persist found barrels to disk). |
| 5 | later | Frontier exploration (port from `pastproject/`) for irregular maps. |
| 6 | qualifier prep | Pymavlink fake-GCS heartbeat (no QGC dependency); 10-min dry-run validation. |

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

## What Phase 1 does (v2, the version that works)

The drone:
1. Connects to PX4 SITL on UDP 14540
2. Sets `CBRK_SUPPLY_CHK=894281` and `SIM_BAT_MIN_PCT=100` via MAVSDK
3. Waits until `is_armable=True` (max 45 s; usually 1–2 s)
4. Arms, takes off to 2 m altitude
5. Enters offboard mode
6. Background tasks start: setpoint pumper @ 10 Hz, telemetry monitor, 30-s watchdog, **divergence watchdog** (aborts on `|pos − target| > 5 m` sustained for 3 s)
7. Flies a **2 m × 2 m square at constant yaw=0°** (no rotation between legs — lateral flight only):
   ```
   start → N2 → +E2 → -N2 → -E2 → start
   ```
   ~33 s of flight total
8. Lands, disarms, exits

### Why yaw=0 throughout

v1 of the controller tried to rotate the drone to face each direction of
motion (N→E→S→W with yaw stepping 0→90→180→270). On waypoint 3 the drone
flew **104 m off-target** — the EKF vision odometry lost tracking during
the simultaneous yaw rotation + translation.

v2 fixes this by keeping yaw constant. The drone flies sideways/backward
when needed instead of rotating. PX4 handles lateral flight just fine.

Lesson for Phases 3+: **don't combine yaw and position changes in the
same setpoint**. If we need to rotate (e.g. to point the camera in a
specific direction during search), do it as a separate move:
1. Hold position, rotate to target yaw, wait for yaw arrival
2. Then translate to next position holding that yaw

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

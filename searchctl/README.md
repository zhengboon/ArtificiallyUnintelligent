# searchctl — RoboVerse search controller

Our own controller, replacing the workshop's `avoid.py`. Built for
reliability: independent setpoint-pumper task, watchdog, emergency-land
on any failure path, file-based logs.

## Phases

| Phase | Status | Scope |
|---|---|---|
| **1** | **✅ DONE 2026-05-13** | Heartbeat + scripted-waypoint smoke flight. v2: yaw locked at 0°, 2 m moves, divergence watchdog. Flew clean 5-WP square in 33 s, sub-0.5 m pos err on every WP. |
| **2** | **scaffolding done 2026-05-13; integration test pending** | YOLO detector running in a worker thread. Subscribes to IMX214 camera via gz-transport, frames stamped with NED pose, annotated `.jpg`s saved per run, detections logged. Opt-out via `--no-detect`. **Next:** verify a full run with detection on. |
| 3 | next next | Lawnmower search strategy across the 40×40 arena, 2-altitude passes (1 m for yellow, 3.5 m for red). |
| 4 | later | Detection dedup by NED position; restart-resilient state (persist found barrels to disk). |
| 5 | later | Frontier exploration (port from `pastproject/`) for irregular maps. |
| **6** | **scaffolding done 2026-05-15; needs end-to-end test** | Pymavlink fake-GCS heartbeat — sends MAV_TYPE_GCS on UDP 14550 @ 1 Hz so PX4's preflight passes without QGC. Auto-skips if QGC is already binding 14550. Opt-out via `--no-fake-gcs`. |

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
cd ~/searchctl
python3 controller.py                  # all features ON (detection + fake-GCS)
python3 controller.py --no-detect      # flight only, no YOLO
python3 controller.py --no-fake-gcs    # rely on QGC for the GCS link
python3 controller.py --log-level DEBUG
```

The controller auto-sets `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python`
internally for the gz.msgs10 import — no need to pre-export it.

**Phase 2 deps** (must be installed in the VM):
- `ultralytics` (pip — installed 2026-05-13, see VM setup guide §6)
- `python3-gz-transport13`, `python3-gz-msgs10` (apt — present in v3 VM)
- The workshop's `Detector.py` at `~/Desktop/codes/Detector.py` (present in v3 VM)
- `yolov10n.pt` weights at `~/Desktop/codes/yolov10n.pt` (present in v3 VM)

**Phase 6 dep** (optional but recommended):
- `pymavlink` (pip — `pip install --user pymavlink`)

If any of these is missing, the controller logs a warning and runs the
features it can. Flight is never blocked by a missing optional dep.

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
WP 1/5 — hover above start ...
  arrived (pos err=0.08 m, yaw err=6.3 deg)
  holding 3.0 s
WP 2/5 — forward 2 m ...
  arrived (pos err=0.23 m, yaw err=1.0 deg)
  ...
WP 5/5 — left 2 m, back to start ...
landing
on ground; disarming
run finished cleanly
```

And the drone in Gazebo will have actually flown the 2 m square. If any
step prints `emergency_land triggered`, we have something to debug —
the log file at `logs/run_*.log` will say what.

**Why 5 WPs not 6**: Phase 1 v1 had 6 WPs including yaw rotation between
legs — that combination caused EKF vision-odometry to drift 104 m on
WP3 (see `guides/vm_from_zero_to_flight.md` § 2026-05-13 verification log).
v2 keeps yaw=0 throughout and uses 5 WPs (hover + 4 lateral moves).

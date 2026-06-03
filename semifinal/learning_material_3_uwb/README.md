# Learning Material 3 — UWB + MAVSDK Mapping Drone

Source: org's `BH2026ROBOVERSE` Discord channel, 2026-06-03 22:23.
Drive folder: https://drive.google.com/drive/folders/1H6H6E06RHp5r97ch2_ZA1-rEIuHQHbxO

Contains one file: [`kolomee.py`](kolomee.py) (407 lines, 12.9 KB).

---

## What this material reveals

The semi-final involves **two drone platforms**, not one:

1. **Hula swarm** — multiple drones, `pyhulax` SDK (covered by L1 + L2)
2. **Mapping drone** — single drone, MAVSDK + UWB tag + Realsense + onboard NPU (covered by L3 + L4 + L5)

This file is the **canonical pattern** for controlling the mapping drone.

---

## `kolomee.py` — what it does

A self-contained reference script for flying the mapping drone two waypoints and landing. Demonstrates:

### Architecture
- **MAVSDK** for drone control (not pyhulax). Familiar territory from qualifier.
- **ROS2** (`rclpy`) subscriber for UWB position. Topic: `uwb_tag`, message type: `geometry_msgs/msg/PoseStamped`.
- **asyncio** main loop (like our qualifier controller).
- **Threaded ROS2 spin** so it doesn't block the asyncio loop.

### Position source
The UWB tag pose comes in as `PoseStamped` via ROS2. Note the **axis swap** in the callback:
```python
self.n = msg.pose.position.y    # N (north) <- ROS y
self.e = msg.pose.position.x    # E (east)  <- ROS x
```
ROS uses ENU (East-North-Up); MAVSDK uses NED (North-East-Down). So the script maps ROS `y → N`, ROS `x → E`.

Altitude comes from PX4 telemetry's `position_velocity_ned.position.down_m`, NOT from UWB. So UWB is XY only — height is from PX4 EKF / barometer / ToF.

### Control approach
**Position commands are disabled for safety** (per the org). The pattern instead:

```python
async def fly_to_position_velocity(target_n, target_e, target_d):
    while True:
        cur_n, cur_e, _ = get_uwb_position()
        cur_d = get_current_height()
        err_n = target_n - cur_n
        err_e = target_e - cur_e
        err_d = target_d - cur_d

        if abs(err_n) < THRESHOLD and abs(err_e) < THRESHOLD:
            await send_velocity(0, 0, 0)   # arrived
            return

        vn = KP_XY * err_n          # P controller, KP_XY = 0.1
        ve = KP_XY * err_e
        vd = KP_Z  * err_d          # KP_Z = 0.1

        # Saturate
        if hypot(vn, ve) > MAX_VEL_XY: scale to MAX_VEL_XY
        if abs(vd) > MAX_VEL_Z:        clamp to MAX_VEL_Z

        await send_velocity(vn, ve, vd)
        await asyncio.sleep(0.1)        # 10 Hz loop
```

`send_velocity(vn, ve, vd)` calls `drone.offboard.set_velocity_ned(VelocityNedYaw(vn, ve, vd, takeoff_yaw))`. Yaw is locked at takeoff heading — no yaw control mid-flight in this example.

### Hover with active drift correction
```python
async def hover(seconds, ignore_height=False):
    # snapshot current UWB pose as the hover target
    # loop: P-controlled velocity back toward snapshot
    # with HOVER_DEADBAND (3cm) so we don't twitch on noise
```

### Connection
`drone.connect(system_address="serial:///dev/ttyS6:921600")` — **serial, not UDP**. The script runs **on the compute module mounted on the drone itself** (Rockchip SoC), connected to the PX4 flight controller via UART.

This is a major architecture difference: for the mapping drone, the orchestrator process runs **on the drone**, not on our laptop. The laptop only talks to it over the network (probably SSH + maybe a custom command channel).

### Tuning parameters (org's defaults)
| Param | Value | Meaning |
|---|---|---|
| `TAKEOFF_HEIGHT` | 0.8 m | Above ground |
| `KP_XY` | 0.1 | XY P-gain (cm/cm/s, i.e. 1 m of error → 0.1 m/s command) |
| `KP_Z` | 0.1 | Z P-gain |
| `MAX_VEL_XY` | 0.5 m/s | XY velocity cap |
| `MAX_VEL_Z` | 0.3 m/s | Z velocity cap |
| `MAX_HOVER_XY` | 0.15 m/s | Hover XY cap (gentler than nav) |
| `MAX_HOVER_Z` | 0.10 m/s | Hover Z cap |
| `WAYPOINT_THRESHOLD` | 0.20 m | "Arrived" tolerance |
| `N/E/D_THRESHOLD` | 0.1 m | Per-axis tolerance |
| `HOVER_DEADBAND` | 0.03 m | Hover skip-correction window |

Conservative gains — 1 m of error gives 0.1 m/s command (10 sec to converge if unsaturated). The cap clamps at 0.5 m/s. Designed for safety in a confined arena.

### Pre-flight + arming sequence
1. Start ROS2 thread, wait for UWB ready
2. Connect MAVSDK, wait for `is_local_position_ok`
3. Snapshot home position + lock takeoff yaw
4. **Interactive `y/n` prompt** to proceed (manual safety gate)
5. `drone.action.arm()`
6. Send 20 frames of zero velocity (offboard pre-warm)
7. `drone.offboard.start()`
8. Waypoint sequence via `fly_to_position_velocity()`
9. `drone.offboard.stop()` + `drone.action.land()` + `drone.action.disarm()`

The pre-warm pattern is identical to what our qualifier controller did (lesson learned: PX4 wants seed setpoints before accepting offboard mode).

---

## What this means for our code

### Carry over from qualifier (mostly)
- MAVSDK async patterns — same as qualifier
- Offboard pre-warm pattern — same
- Velocity setpoint control — same
- Watchdog + emergency-land pattern — same
- Run summary + STATUS.txt writer — same

### New for mapping drone
- ROS2 (`rclpy`) subscriber for UWB pose — **new dependency** (`pip install rclpy` won't work, need a ROS2 install on the compute module — likely already there if the SBC image is ROS2-based)
- ENU → NED axis swap in the UWB callback — **gotcha to remember**
- Serial MAVSDK connection (`serial:///dev/ttyS6:921600`) instead of UDP
- The orchestrator process runs **on the drone**, not the laptop

### Things kolomee.py does NOT show us
- How to integrate Realsense capture (covered by L4)
- How to run YOLO inference onboard via NPU (covered by L5)
- How to coordinate the mapping drone with the Hula swarm
- How yaw control works (yaw is locked at takeoff in this example)
- Map-building / occupancy grid construction (this is "mapping drone" but the file doesn't build a map — just navigates waypoints)

---

## Open questions

1. **What does "mapping" actually entail?** Build a top-down map from Realsense depth? Build a point cloud? Photogrammetry? The scoring rubric will tell us what artifact to produce.
2. **Is the mapping drone provided?** Or do we BYO compute module + flight controller + UWB tag?
3. **What's the UWB anchor layout in the arena?** Affects accuracy + dead zones.
4. **Does the Hula swarm see the UWB data too**, or is UWB exclusive to the mapping drone? If shared, we could fuse it as a position prior for the Hulas.
5. **What's the SBC model?** RK3588 (Orange Pi 5) vs RK3568 (slower NPU) changes inference speed. L5 will likely clarify.
6. **What ROS2 distro?** Affects which `rclpy` API we target. Probably Humble or Jazzy.

# INTEGRATION COMPLETE — wall-following wired (Thu 21 May ~22:30 SGT)

## What got added to `searchctl/controller.py`

### 1. SharedState fields (around line ~95)
```python
velocity_mode: bool = False
vel_fwd: float = 0.0       # body-frame forward m/s
vel_right: float = 0.0     # body-frame right m/s (positive = strafe right)
vel_down: float = 0.0      # body-frame down m/s
yaw_rate_deg: float = 0.0  # deg/s
```

### 2. Import
```python
from mavsdk.offboard import OffboardError, PositionNedYaw, VelocityNedYaw, VelocityBodyYawspeed
```

### 3. Setpoint pumper branch
```python
if state.velocity_mode:
    await drone.drone.offboard.set_velocity_body(VelocityBodyYawspeed(...))
else:
    await drone.drone.offboard.set_position_ned(PositionNedYaw(...))
```

### 4. `_depth_to_points_3d(depth, K, np_mod, stride=2)`
Same projection as workshop's `depthcloud.PointCloud.convert`. Output is Nx3 camera-optical-frame (x-right, y-down, z-forward) — what K's `get_wall_distances` expects.

### 5. `planner_wall(state, map_handle)`
Async function. Reads depth from mapping pipeline's `latest` dict, calls K's `WallFollower.compute()` at 10 Hz, smooths via K's `VelocitySmoother`, converts yaw_rate rad/s → deg/s, writes to state, flips `velocity_mode=True`. Time-capped at 8 min via `WALL_FOLLOW_BUDGET_S`. On exit: zeroes velocity, holds current position, flips `velocity_mode=False`.

### 6. CLI: `--pattern {square, scan, wall}`
With validation: if `wall` AND `--no-map`, error out (wall needs depth source).

### 7. `run()` dispatch
```python
if pattern == "wall":
    await planner_wall(state, map_handle)
else:
    await planner(state)
```

## Deployment status

- **Host**: `D:\hackerverse\searchctl\controller.py` (1438 lines, ~60 KB)
- **VM**: `/home/drone/ArtificiallyUnintelligent/searchctl/controller.py` deployed (timestamp Mei 21 21:26)
- **VM verification**: parses OK, wall_following imports OK, K's FSM responds correctly to synthetic input
- **NOT committed yet** — Z to commit after recording finishes / test passes

## How to test (manual, in VM)

Three patterns now selectable:
- `python3 controller.py --pattern square` — known-good baseline
- `python3 controller.py --pattern scan` — yaw 360° at spawn
- `python3 controller.py --pattern wall` — K's wall-follow (NEW)

For all three, prereqs are:
1. `~/start_px4.sh` → 1, 1, 2 (vision, roboverse, no QGC)
2. `commander set_ekf_origin 47.397742 8.545594 488.0` at pxh>

## What might go wrong (in order of likelihood)

1. **EKF blow-up during wall-mode velocity setpoints** — pure yaw at fixed XY caused 100m drift on Phase 1 v1. K's wall-follow does yaw + forward velocity simultaneously. Risk: similar issue. Mitigation: divergence_watchdog catches >5m sustained drift, emergency-lands.
2. **K's `z > 1.5` filter in `get_wall_distances`** drops everything closer than 1.5m forward — so if drone is RIGHT next to a wall, K's code thinks "front=10.0 (no obstacle)". This could cause it to fly INTO the wall thinking it's clear. Wall-collision = no penalty per org, so survivable.
3. **MAVSDK setpoint-type switch** mid-offboard. Should work (MAVSDK is forgiving) but untested. If it fails, drone may briefly fly to wrong position before next setpoint corrects it.
4. **VelocityBodyYawspeed direction signs** — PX4 body frame: x=forward, y=right, z=down (FRD). K's frame matches. OK.

## After tonight's recording

Block C of the plan: commit + push. Suggested commit message:

```
Wall-following integration as --pattern wall (K's algorithm)

* SharedState gains velocity_mode + body-frame velocity fields
* setpoint_pumper branches on velocity_mode: VelocityBodyYawspeed
  (forward, right, down, yawrate) when wall-mode is active,
  PositionNedYaw otherwise
* _depth_to_points_3d(): projects HxW depth -> Nx3 camera-frame
  cloud (same math as workshop's depthcloud.PointCloud.convert)
  for K's get_wall_distances() which expects Nx3 input
* planner_wall(): async loop calling K's WallFollower.compute()
  at 10 Hz, smoothed via K's VelocitySmoother. Reads depth from
  the Phase 7 mapping pipeline's latest_lock-protected buffer
  (no second depth subscription). Time-capped at 8 min so we
  always land within the 10-min run budget. Exits cleanly:
  zeros velocity, holds current pose, flips velocity_mode=False.
* --pattern wall added; main() validates that --no-map is NOT
  passed (wall needs the mapping pipeline as its depth source).
* Threaded `pattern` through to run() with dispatch on the value.

K's wall_following.py module unchanged. Confidence threshold also
lowered 0.5 -> 0.35 in this commit because org confirmed no
penalty for incorrect detections (21/5).
```

Then rebuild thumbdrive tarball:
```bash
cd /d/hackerverse
tar --exclude=... -czf thumbdrive/ArtificiallyUnintelligent.tar.gz .
```

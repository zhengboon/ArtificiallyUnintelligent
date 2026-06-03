# Mapping Drone — Stack Analysis

Sister document to [`pyhulax_analysis.md`](pyhulax_analysis.md). This one covers the **mapping drone** stack: MAVSDK + ROS2 UWB + PX4 + Realsense + onboard NPU. Built from:
- Org's Discord posts (`semifinal/semifinal_scrape.md` L3 + L4 + L5)
- Org's reference code `kolomee.py` ([`semifinal/learning_material_3_uwb/kolomee.py`](../learning_material_3_uwb/kolomee.py))
- Our qualifier MAVSDK experience

This is internal cheat-sheet form — what's there, what's important, what the gotchas are.

---

## 1. TL;DR — what makes this drone different

1. **It's a separate drone from the Hula swarm.** Different SDK, different position source, different orchestrator runs on the drone itself.
2. **UWB tag for indoor position** (real-time, anchor-based). Replaces GPS, replaces optical-flow drift, replaces VIO calibration faff.
3. **Position commands are disabled by the org for safety.** Control is via **velocity setpoints** in a closed-loop P-controller — exactly like our qualifier offboard mode, except the position feedback comes from UWB instead of EKF/Gazebo truth.
4. **The compute runs ON the drone** (Rockchip SBC with NPU), connected to PX4 via UART (`/dev/ttyS6:921600`). Our laptop talks to the drone over the network, not to the flight controller directly.
5. **Detection is NPU-accelerated** via RKNN format. K's `best.pt` must be converted `.pt → .onnx → .rknn` before deployment.
6. **Realsense D430/D450 onboard** provides depth + RGB for mapping + photos.
7. **NED coordinate system + ENU UWB axis swap.** UWB publishes `PoseStamped` in ENU; the script swaps `ros.y → N, ros.x → E` when reading. **One of the most error-prone things in the file.**

---

## 2. Stack layers

```
┌─────────────────────────────────────────────┐
│            On the mapping drone             │
│                                             │
│  ┌────────────────────────────────────┐     │
│  │  Our orchestrator (Python asyncio) │     │
│  │  - subscribe UWB (ROS2 rclpy)      │     │
│  │  - send velocity setpts (MAVSDK)   │     │
│  │  - run YOLO via RKNN on NPU        │     │
│  │  - capture from Realsense          │     │
│  │  - build map artifact              │     │
│  └────────┬────────────────┬──────────┘     │
│           │                │                │
│           ▼                ▼                │
│  ┌──────────────┐  ┌────────────────────┐   │
│  │ ROS2 node    │  │ MAVSDK over serial │   │
│  │ topic:       │  │ /dev/ttyS6:921600  │   │
│  │  uwb_tag     │  │                    │   │
│  └──────┬───────┘  └─────────┬──────────┘   │
│         │                    │              │
│         ▼                    ▼              │
│  ┌──────────────┐  ┌────────────────────┐   │
│  │ UWB receiver │  │ PX4 flight ctrl    │   │
│  │ on the drone │  │ (autopilot)        │   │
│  └──────────────┘  └────────────────────┘   │
└─────────────────────────────────────────────┘
         ▲                                       ▲
         │ UWB anchors in venue                  │ Realsense USB
         │                                       │
   (Arena infra)                          ┌──────┴──────┐
                                          │ D430/D450    │
                                          └──────────────┘
```

---

## 3. The position story (the most important diagram)

```
                  ARENA (anchors at known positions)
                      ▲
                      │ UWB ranging (m precision)
                      ▼
              ┌──────────────┐
              │  UWB tag     │
              │  on drone    │
              └──────┬───────┘
                     │ ROS2 over IPC
                     ▼
       ┌──────────────────────────────┐
       │ ROS2 publisher (provided)    │
       │  topic: uwb_tag              │
       │  msg: PoseStamped            │
       │  frame: ENU (ROS standard)   │
       │     pose.position.x → East   │
       │     pose.position.y → North  │
       │     pose.position.z → Up     │
       └──────────────┬───────────────┘
                      │ rclpy subscribe
                      ▼
       ┌──────────────────────────────┐
       │  Our subscriber (UwbNode)    │
       │  AXIS SWAP for NED:          │
       │     self.n = msg.pose.y  ←ENU y→N
       │     self.e = msg.pose.x  ←ENU x→E
       │  (NOT touching z — see next) │
       └──────────────┬───────────────┘
                      │
                      ▼
            n, e = get_uwb_position()
```

For **Z (altitude)** — `kolomee.py` uses PX4 NED telemetry, NOT UWB:
```
async for pos in drone.telemetry.position_velocity_ned():
    current_d = pos.position.down_m    # negative = above ground
```

So **XY from UWB** + **Z from PX4 EKF (probably barometer + IMU + ToF if present)**.

NB: NED's `down_m` is negative when airborne (altitude 1.5m → down_m = -1.5).

---

## 4. The control loop — the canonical pattern from `kolomee.py`

```python
KP_XY = 0.1
KP_Z  = 0.1
MAX_VEL_XY = 0.5
MAX_VEL_Z  = 0.3
N_THRESHOLD = E_THRESHOLD = D_THRESHOLD = 0.1   # m

async def fly_to_position_velocity(target_n, target_e, target_d, ignore_height=True):
    while True:
        cur_n, cur_e, _ = get_uwb_position()
        cur_d = get_current_height()
        err_n = target_n - cur_n
        err_e = target_e - cur_e
        err_d = target_d - cur_d

        # convergence check
        if ignore_height:
            if abs(err_n) < N_THRESHOLD and abs(err_e) < E_THRESHOLD:
                await send_velocity(0, 0, 0); return
        else:
            if all axes < threshold: ... return

        vn = KP_XY * err_n if abs(err_n) >= N_THRESHOLD else 0.0
        ve = KP_XY * err_e if abs(err_e) >= E_THRESHOLD else 0.0
        vd = KP_Z  * err_d if abs(err_d) >= D_THRESHOLD else 0.0

        # saturate
        h_speed = hypot(vn, ve)
        if h_speed > MAX_VEL_XY:
            scale = MAX_VEL_XY / h_speed
            vn, ve = vn*scale, ve*scale
        vd = clamp(vd, -MAX_VEL_Z, +MAX_VEL_Z)

        if ignore_height: vd = 0

        await send_velocity(vn, ve, vd)
        await asyncio.sleep(0.1)   # 10 Hz
```

`send_velocity(vn, ve, vd)` is:
```python
await drone.offboard.set_velocity_ned(VelocityNedYaw(vn, ve, vd, takeoff_yaw))
```

Yaw is **locked at takeoff heading**. No mid-flight yaw control in the org's example. We may need to add it (rotate to face a target before photographing it, for instance).

### Hover with active drift correction
```python
async def hover(seconds, ignore_height=False):
    hover_n, hover_e, _ = get_uwb_position()    # snapshot
    hover_d = get_current_height()
    end = loop.time() + seconds
    while loop.time() < end:
        cur = read_uwb + height
        err = hover - cur
        # P controller with HOVER_DEADBAND=0.03 m and MAX_HOVER_XY=0.15 m/s
        vn, ve, vd = controller(err)
        await send_velocity(vn, ve, vd)
        await asyncio.sleep(0.1)
```

Hover gains are **gentler** than waypoint nav (`MAX_HOVER_XY=0.15` vs `MAX_VEL_XY=0.5`) so it doesn't twitch on UWB noise. The 3cm deadband does the same — below 3cm of error, command zero.

### Tuning values
| Param | Value | Reasoning |
|---|---|---|
| `KP_XY` / `KP_Z` | 0.1 | Gentle: 1m error → 0.1 m/s command. ~10s to converge if unsaturated. |
| `MAX_VEL_XY` | 0.5 m/s | Safe in indoor arena |
| `MAX_VEL_Z` | 0.3 m/s | Vertical safety |
| `MAX_HOVER_XY` | 0.15 m/s | 3× slower than nav |
| `HOVER_DEADBAND` | 0.03 m | 3cm = UWB noise floor |
| `WAYPOINT_THRESHOLD` | 0.20 m | "Arrived" tolerance |
| Loop rate | 10 Hz | Plenty for indoor speeds |

These are org-provided defaults. For competition we'll likely tune `KP_XY` up to `0.3` or so to be faster, depending on arena size + UWB latency.

---

## 5. Boot + flight sequence (the canonical pattern)

```
1. start_ros2_thread()                  # rclpy.init + spawn UwbNode + spin in daemon thread
2. await UWB ready (loop until first PoseStamped arrives)
3. drone = System(); await drone.connect("serial:///dev/ttyS6:921600")
4. spawn telemetry tasks: attitude_task, pos_task, battery_task
5. await drone.telemetry.health() until is_local_position_ok
6. takeoff_yaw = current_yaw_deg  # lock heading
7. await drone.action.set_takeoff_altitude(TAKEOFF_HEIGHT)  # 0.8m default
8. INTERACTIVE y/n prompt (safety gate)
9. await drone.action.arm()
10. send 20× zero-velocity setpoints (offboard pre-warm)
11. await drone.offboard.start()
12. waypoints: fly_to_position_velocity(target_n, target_e, target_d)
13. await drone.offboard.stop()
14. await drone.action.land()
15. wait for in_air → False
16. await drone.action.disarm()
17. rclpy.shutdown()
```

Step 8 (interactive `y/n`) is **operator safety** — verify the home position looks right before arming. For our orchestrator we'll likely keep this but maybe make it a config flag for "I trust the position, go".

Step 10 (20× zero setpoints before `offboard.start`) is identical to our qualifier — PX4 won't enter offboard without a seed setpoint stream. Don't skip this.

---

## 6. Carry-over from qualifier

This is MUCH bigger than I initially estimated. The mapping drone stack is essentially a refined version of our qualifier controller:

| Qualifier asset | Reuse on mapping drone? |
|---|---|
| Asyncio main loop | ✅ Identical pattern |
| MAVSDK System() + connect | ✅ Same (different address: serial vs UDP) |
| Offboard pre-warm (zero setpoints before `offboard.start()`) | ✅ Identical |
| Velocity setpoint control (`set_velocity_ned`) | ✅ Identical |
| Telemetry tasks (`telemetry.attitude_euler`, `position_velocity_ned`, `battery`, `in_air`) | ✅ Identical |
| Watchdog (`last_planner_progress` timeout) | ✅ Reuse |
| `emergency_land()` + try/finally land + disarm | ✅ Reuse |
| `arm_and_takeoff` waiting for altitude (95% target settling) | ✅ Reuse — but `kolomee.py` uses simpler take_off + sleep |
| Run summary / STATUS.txt writer | ✅ Reuse |
| Wall-following | ❌ Not relevant — we navigate by waypoint, not by wall |

So the mapping drone orchestrator is basically our qualifier `controller.py` + the L3 UWB integration + the L4 Realsense integration + the L5 RKNN inference.

---

## 7. What's NEW for us

### 7.1 ROS2 (`rclpy`)
We've never used ROS2 in this project. The pattern is:
- `rclpy.init()`
- Create a node (subclass `rclpy.node.Node`)
- Subscribe to a topic with a callback
- Run `rclpy.spin(node)` in a daemon thread (so asyncio main loop isn't blocked)
- Read latest data via a thread-safe getter

`kolomee.py` has the entire skeleton. Reuse verbatim.

Dependency: `rclpy` is not a `pip install` — it ships with the ROS2 distro installed on the drone's SBC. We don't install it ourselves. We just `import rclpy` and use it.

### 7.2 UWB integration
- Subscribe to topic `uwb_tag` with msg type `geometry_msgs.msg.PoseStamped`
- Use `QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, depth=10)` — UWB data is high-rate, can drop a few
- **AXIS SWAP**: `n = msg.pose.position.y; e = msg.pose.position.x`
- Z from UWB is **ignored** — use PX4 telemetry's `down_m` instead

### 7.3 Serial MAVSDK connection
- `await drone.connect(system_address="serial:///dev/ttyS6:921600")` — not UDP
- Means the orchestrator runs ON the drone (the SBC), not on the laptop
- Means we ssh into the drone to launch + debug
- Means our laptop talks to the drone over the network (some custom channel or just SSH)

### 7.4 RKNN inference
- Convert `.pt → .onnx → .rknn` once, on a host (x86 Linux)
- Run with `rknnlite` on the drone (already installed on the SBC image)
- ~60-120 FPS YOLOv8n on RK3588 NPU (quantised int8)
- See [`learning_material_5_yolo_rknn/README.md`](../learning_material_5_yolo_rknn/README.md) for conversion details

### 7.5 Realsense onboard
- `pyrealsense2` works identically to laptop install (our `prototypes/aruco_realsense.py` patterns reuse)
- Mount means stable known offset from drone frame to camera frame → can build globally-consistent map
- See [`prototypes/aruco_realsense.py`](../prototypes/aruco_realsense.py) for the canonical depth+ArUco pattern

---

## 8. Things we still don't know

These determine the implementation:

1. **What "mapping" produces.** Top-down PNG? Point cloud .ply? Occupancy grid? Need scoring rubric.
2. **What target classes K should train for.** Probably yellow/red barrels + maybe fiducials, but org hasn't released the target list.
3. **Whether the Hula swarm + mapping drone need to coordinate** (e.g., swarm finds candidate, mapping drone goes confirm at high resolution) or operate independently.
4. **Whether we get to bring the mapping drone home** or can only touch it at the venue / on physical run days.
5. **UWB anchor positions + arena dimensions** → drives mission planning.

Items 1-3 are the most blocking. File as support tickets ASAP.

---

## 9. Suggested skeleton for `semifinal/mapping_drone/controller.py`

Adapt `kolomee.py` + add the Realsense + RKNN layers. Sketch:

```python
import asyncio, math, threading
from mavsdk import System
from mavsdk.offboard import VelocityNedYaw
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from geometry_msgs.msg import PoseStamped
import pyrealsense2 as rs
import cv2, numpy as np

# UWB subscriber (kolomee.py pattern, verbatim)
class UwbNode(Node):
    def __init__(self):
        super().__init__('uwb_listener')
        qos = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, depth=10)
        self.create_subscription(PoseStamped, 'uwb_tag', self._cb, qos)
        self.n = self.e = 0.0; self.ready = False
    def _cb(self, msg):
        self.n = msg.pose.position.y     # ENU y -> N
        self.e = msg.pose.position.x     # ENU x -> E
        self.ready = True

# Realsense setup (once at startup)
def start_realsense():
    pipe = rs.pipeline()
    cfg = rs.config()
    cfg.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
    cfg.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
    profile = pipe.start(cfg)
    align = rs.align(rs.stream.color)
    intr = profile.get_stream(rs.stream.color).as_video_stream_profile().get_intrinsics()
    return pipe, align, intr

# RKNN model (once)
def load_rknn(path="best.rknn"):
    from rknnlite.api import RKNNLite
    rknn = RKNNLite(); rknn.load_rknn(path)
    rknn.init_runtime(core_mask=RKNNLite.NPU_CORE_AUTO)
    return rknn

# Detection inside the main loop
def detect_in_frame(rknn_model, color_img, depth_img, intr):
    output = rknn_model.inference(inputs=[color_img])
    # ... parse boxes, get center (u,v) ...
    # Z = depth_img[v, u] / 1000.0
    # X = (u - intr.ppx) * Z / intr.fx
    # Y = (v - intr.ppy) * Z / intr.fy
    # return list of (class, conf, camera_xyz)
    return []

# Main mission loop
async def mission(drone, uwb, rs_pipe, rs_align, rs_intr, rknn_model):
    waypoints = [...]   # absolute UWB coords
    found = {}          # target_id -> world_xyz, photo_path

    for wp in waypoints:
        await fly_to_position_velocity(*wp)
        # at waypoint: capture + detect
        frames = rs_align.process(rs_pipe.wait_for_frames())
        color = np.asanyarray(frames.get_color_frame().get_data())
        depth = np.asanyarray(frames.get_depth_frame().get_data())
        dets = detect_in_frame(rknn_model, color, depth, rs_intr)
        for d in dets:
            # Camera frame -> drone body -> world (NED via UWB pose)
            world_xyz = body_to_world(d.cam_xyz, drone_pose=(get_uwb_n(), get_uwb_e()))
            if d.cls not in found:
                found[d.cls] = world_xyz
                # save photo
        # build map increment
        update_occupancy_grid(depth, drone_pose)

    save_artifacts(found, occupancy_grid)
    return found
```

This is a sketch. Real impl will need:
- The body→world transform (depends on camera mount orientation on the drone)
- Occupancy-grid update logic (Supplementary 2 covers this)
- Per-target dedup
- Battery/connection watchdogs
- Run summary + STATUS.txt writer (carry over from qualifier)

---

## 10. Risks + mitigations (mapping-drone-specific)

| Risk | Mitigation |
|---|---|
| UWB dead zone or signal loss mid-flight | Failsafe: if `uwb.ready` goes False for >1s, command zero velocity + hold. If sustained, land. |
| Position commands tempting (faster than P-ctrl) but org disabled them | Just don't. Stick to velocity setpoints. P=0.3 max if we tune up. |
| ENU↔NED axis swap silently wrong | Drone won't fly direction you expect. Test on the ground first — command "+N 1m" and see if it tries to go in the right direction before unlocking. |
| RKNN conversion fails on K's specific YOLO architecture | Have a Plan B: do detection on the host (laptop) by streaming Realsense over the network. Slower but simpler. |
| Serial MAVSDK at 921600 baud drops messages under load | Reduce telemetry rates if needed (`set_rate_*` methods in MAVSDK). |
| ROS2 spin thread blocks Python GC | Daemon thread + sane callback work. Don't do heavy work in the UWB callback. |
| Manual y/n prompt blocks if we're remote | Replace with config flag for headless operation, but keep operator confirmation when at venue. |
| Mapping drone runs out of compute (NPU + Realsense + ROS2 + MAVSDK + asyncio competing) | Profile early. Reduce Realsense resolution. Lower YOLO input size. |

---

## 11. Action items

1. ⏳ Wait for L4 + L5 unlocked Drive folders
2. ⏳ Wait for org clarification on mapping drone provision (BYO or supplied)
3. ⏳ K starts on Hula side smoke (no mapping drone needed)
4. ⏳ A finishes YOLO training, exports ONNX
5. ⏳ Z drafts `semifinal/mapping_drone/controller.py` skeleton from §9 + carry-over from qualifier
6. ⏳ Plan SSH/log access path to the mapping drone for the 10/11 June physical run

---

*Last updated: 2026-06-03 (after L3 + L4 + L5 announcement).*

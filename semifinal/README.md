# BrainHack 2026 RoboVerse — Finals Prep

**Status:** Advanced to FINALS 2026-06-03 (skipped semifinal tier). Category: University (confirmed 2026-06-05).
**Finals: 2026-06-10 + 2026-06-11, 9am-6pm, Marina Bay Sands Expo & Convention Centre Level 4.** All 3 team members should attend both days (per org 2026-06-05 22:22). Registration 10 June 7:30am — bring Photo ID + confirmation email; smart casual, no slippers.
**Scope shift:** Sim → real hardware. TWO drone platforms (Hula swarm + mapping drone).

> **T-1 to finals (10-11 June 2026, Marina Bay Sands Expo & Convention Centre, Level 4).** Day-of plan: see [`DAY1_RUNBOOK.md`](DAY1_RUNBOOK.md) + [`DAY1_SETUP_SEQUENCE.md`](DAY1_SETUP_SEQUENCE.md). §17 below kept as historical checklist (most items completed; remaining T-1 items called out).
> **Major update 2026-06-03:** Org released L3 (UWB), and L4 + L5 are now Pulled into-tree (`learning_material_4_realsense/` + `learning_material_5_yolo_rknn/`). Revealed a SECOND drone (the "mapping drone") with UWB + MAVSDK + Realsense + onboard NPU, distinct from the Hula swarm.

> **2026-06-03:** Team bumped straight to FINALS (skipping semifinal tier). Finals are 2026-06-10/11, 9am-6pm both days at Marina Bay Sands Expo L4. All 3 members should attend both days (per org 2026-06-05 22:22).
> **2026-06-05:** University category confirmed. YOLOv11 base required (`yolo11n.pt`); use `_2.py` variants of convert scripts. Mapping drone: Ubuntu 22.04 + ROS2 + OpenCV + RKNN NPU @ ~50 FPS. C2 Terminal = Windows + Ubuntu 22.04 VM; access mapping drone via NoMachine from C2.
> **2026-06-06 05:00:** "Hula drone to detect aruco marker on ground robots." Detection of RoboMaster ground robots is **ArUco-based, not YOLO**. A's YOLO is insurance/backup only.
> **2026-06-06 11:28:** New Hula-swarm UWB API: `UWBParserThread.py` over pyserial @ 921600 baud (see `uwb_api_hula_swarm/`). DIFFERENT transport from mapping drone's ROS2 `uwb_tag` topic.
> **2026-06-06 11:40:** Map layout will NOT be provided — discover via Challenge 1.
> **2026-06-06 21:32 PM (captured 2026-06-07 AM):** ArUco markers are **20cm x 20cm** physical size. **EXACT dictionary will be announced on the day** — code must accept a runtime dict choice (NOT pre-confirmed as DICT_6X6_250). Could be any of 16 ArUco sizes (4X4/5X5/6X6/7X7 × 50/100/250/1000) or 4 AprilTag variants (16h5, 25h9, 36h10, 36h11). See §6b #13 + §3.4.
> **2026-06-06 21:34 PM (captured 2026-06-07 AM):** ArUco markers are placed near **Challenge 2 landing pads ALSO** (not just Challenge 1's landing pads). Same ArUco-aided landing pattern for BOTH challenges; Hula side uses `cv2.aruco` rather than the pyhulax landing-marker auto-land helper. Source: BH2026ROBOVERSE in reply to FlyingExplorers 2026-06-06 14:50.
> ~~**2026-06-06 21:47 PM (captured 2026-06-07 AM):** Org ticket etiquette — close old support tickets and open fresh ones for new questions so the queue stays prioritised. Any still-open question we have should be filed as a NEW ticket.~~ **STALE per user 2026-06-09:** ticket path is dead this close to Day-1 — ask org marshal verbally at the venue on Day-1 morning instead.
> **2026-06-06 PM (team chat):** ArUco beside Hula pads + 20cm + dictionary TBD Day-1 (org drops captured above). Team consequences: §3.4 audit shows current `mapping_drone/mapping.py:_ARUCO_DICTS` rejects ~55% of possible Day-1 announcements — pre-venue expansion to all 20 dicts is the top blocker.
> **2026-06-07 AM (team chat):** A killed the YOLO track (6/6 22:13 "Nope not using yolo" — TF/ImageAI/OpenCV may be explored but exploratory only). K is on Hula swarm SEARCH ALGORITHM tonight (6/6 21:36). Z secured a backup Intel depth camera from a friend (close-to-D435, not exact) for redundancy. A's laptop is unreliable (7/6 00:13 — "It's been repeating quite often"); Day-1 reliability risk for anything that must run off A's laptop.
>
> **2026-06-09 — AUTHORITATIVE SOURCE for finals rules + schedule + scoring: [`finals_brief_extracted.md`](finals_brief_extracted.md)** (extracted from org pptx, T-1 evening). Earlier slides + Discord drops are subsumed by this brief.

## Finals logistics (org confirmations 2026-06-05 / 2026-06-06)
- **Event:** FINALS (we skipped semi-final tier — confirmed 2026-06-03), University category (2026-06-05).
- **Dates:** Wed 10 Jun + Thu 11 Jun 2026, 9am-6pm both days.
- **Venue:** Marina Bay Sands Expo & Convention Centre, **Level 4**.
- **Registration:** 10 Jun, 7:30 am — bring **Photo ID + confirmation email**.
- **Dress:** smart casual, **NO slippers / uncovered footwear**.
- **Bring:** personal laptop + mouse + charger + thumbdrive.
- **Attendance:** All 3 members should attend BOTH days (org guidance 2026-06-05 22:22).

This is the working knowledge base for the finals. Everything we know so far, organised so any team member can pick up where another left off. (Note: directory name `semifinal/` and any lingering "semi-final" wording are historical — we advanced straight to finals.)

---

## 0. TL;DR — what changed

### Two drone platforms, not one

The finals involve **TWO distinct drone systems** working together:

| | **Hula swarm** | **Mapping drone** |
|---|---|---|
| Quantity | Multiple (count TBC) | One |
| SDK | `pyhulax` | `mavsdk` (Python) |
| Position source | Optical flow + optional QR mat + **UWB via UWBParserThread (pyserial @ 921600)** | **UWB tag** (real-time XY), PX4 NED (Z) |
| Position interface | `drone.get_position()` | **ROS2 topic `uwb_tag`** (`PoseStamped`) |
| Control style | High-level `move_to(x,y,z)` (blocks) | **Velocity-setpoint P-controller** at 10Hz |
| Depth camera | Built-in optical flow | **Realsense D430/D450/D435** (`pyrealsense2`) |
| Compute location | On host laptop | **On the drone itself** (Rockchip SBC with NPU) |
| Detection model | **ArUco** (`DICT_6X6_250`) primary; YOLO via `pyhulax.video.YOLODetector` as backup | **YOLO via RKNN** (`.pt → .onnx → .rknn`, NPU-accelerated) |
| Connection | TCP/UDP over WiFi | **Serial** (`/dev/ttyS6:921600`) |
| Carry over from qualifier | Asyncio patterns, depth math, run summary | **MUCH more** — asyncio, MAVSDK, offboard pre-warm, velocity control, watchdog |

*Note: per 2026-06-06 org clarification ("hula drone to detect aruco marker on ground robots"), Hula detection of RoboMaster ground robots is ArUco-based. A's YOLO pipeline is retained as insurance/backup only. Hula swarm now also has UWB via `UWBParserThread.py` (pyserial @ 921600 baud) running on C2 Terminal Windows side — see `uwb_api_hula_swarm/`. This is a different transport from the mapping drone's ROS2-based UWB on `/dev/ttyS6`.*

### Likely role split (our hypothesis until org clarifies)
- **Hula swarm**: broad-area parallel searching, find target candidates fast across the arena
- **Mapping drone**: careful precision work — build the actual map (layout NOT given — must be discovered), photograph high-value targets, position-accurate via UWB

### What changed vs qualifier
| | Qualifier (sim) | Finals (real hardware) |
|---|---|---|
| Platform | x500_vision in PX4 SITL + Gazebo Harmonic | **Real Hula drones (swarm) + real mapping drone** |
| SDKs | MAVSDK only | **pyhulax (Hulas)** + **MAVSDK (mapping drone)** |
| Pose source | Gazebo simulation truth + PX4 EKF | **VIO/optical flow (Hulas)** + **UWB tag (mapping drone)** |
| Camera (RGB) | Gazebo IMX214 via `gz.transport13` | **Hula's onboard camera** + **Realsense on mapping drone** |
| Depth sensor | Sim depth camera | **Realsense D435** (we have one) via `pyrealsense2` |
| Targets | Yellow + red barrels | 5 RoboMaster ground robots carrying ArUco markers (DICT_6X6_250). Primary detection = ArUco (org-confirmed 2026-06-06). YOLO retained as insurance only. |
| Control loop | Asyncio + offboard velocity setpoints | **pyhulax: blocking calls** + **mapping: asyncio + velocity P-ctrl** |
| Coordination | Single drone | **Multiple platforms, multiple processes** |
| ML deployment | YOLO `.pt` on laptop | **YOLO `.pt → .onnx → .rknn` on NPU** for mapping drone, `.pt` for Hulas |
| Map layout | Provided as occupancy grid / known arena | **NOT provided — discover via Challenge 1** (org 2026-06-06 11:40) |
| Compute setup | Org laptop + Ubuntu VM | **C2 Terminal = Windows host + Ubuntu 22.04 VM**; access mapping drone via **NoMachine** from C2 (org 2026-06-05 PM) |

**The good news:** ~70% of our qualifier code carries over for the mapping drone (MAVSDK + asyncio + offboard pre-warm + velocity ctrl + watchdog + run summary). The Hula side gets a lot for free from the SDK.

**The bad news:** there are now **two completely separate code paths** to build, two platforms to debug, and an NPU conversion pipeline (`.pt → .onnx → .rknn`) that has notoriously version-sensitive tooling.

---

## 1. What we have already (from qualifier)

| Asset | Where | Hula swarm | Mapping drone |
|---|---|---|---|
| YOLO training pipeline (`best.pt`, qualifier YOLOv8 — retrain on YOLOv11 base `yolo11n.pt` per org 2026-06-05; insurance/backup only since ArUco is primary RoboMaster detector per 2026-06-06) | `models/best.pt` | ✅ Use as backup via `YOLODetector` | ⚠️ Convert `.pt → .onnx → .rknn` for NPU |
| Depth → 3D unprojection math | `searchctl/controller.py` mapping section | N/A (use drone cam) | ✅ Identical formula for Realsense |
| Top-down occupancy mapping | `searchctl/controller.py:457-687` | N/A | ✅ Pattern fully reuses with Realsense+UWB |
| Asyncio + signal-handling scaffolding | `searchctl/controller.py:765-942` | ⚠️ Partial (pyhulax is sync, use threads) | ✅ Direct reuse |
| MAVSDK offboard pre-warm pattern | qualifier `controller.py` | N/A | ✅ Identical (kolomee.py confirms it) |
| MAVSDK velocity setpoints | qualifier `controller.py` | N/A | ✅ Identical |
| Watchdog + emergency-land | qualifier `controller.py` | ✅ Reuse | ✅ Reuse |
| Run-summary + STATUS.txt writer | qualifier `controller.py` | ✅ Reuse | ✅ Reuse |
| Wall-follow FSM | `searchctl/wall_following.py` | ❌ Hula has `set_barrier_mode()` built-in | ❌ Mapping drone explores then navigates by waypoint (see note below) |

> **Note (org 2026-06-06 11:40):** Map layout is **NOT provided** — Challenge 1 is to discover the arena layout. Default waypoints in `mapping_drone/controller.py` (`[(0,0,4.0),(2,0,4.0),(2,2,4.0),(0,2,4.0)]`, above the 3.5 m floor) assume the arena is already known; we need an exploration pre-pass (e.g. frontier-based or expanding lawnmower seeded by UWB anchor positions) before locking in fixed waypoints. Wall-follow is still wrong for the mapping drone, but pure waypoint nav is also insufficient until exploration is done.

---

## 2. Hardware stack (finals)

### 2.1 Hula drones (swarm, count TBD)
- **WiFi-networked** — laptop and drones must share the network
- Sends discovery broadcasts on UDP port **8668** (44-byte MAVLink-like packets, msg ID 232)
- Onboard: camera + tiltable gimbal, VIO (pre-calibrated), IR/ToF obstacle sensors, LEDs, payload (electromagnet/clamp), optional laser
- SDK abstraction: one `DroneAPI()` per drone, addressed by IP
- **Critical:** do NOT bump or remount the camera — VIO calibration depends on physical placement
- Default battery refusal: <20% (configurable but be careful)

### 2.2 Mapping drone (single, separate platform)
- **Onboard SBC**: Ubuntu 22.04 + ROS2 + OpenCV + RKNN NPU @ ~50 FPS (org-confirmed 2026-06-05)
- **Access**: NoMachine from the C2 Terminal (Windows host + Ubuntu 22.04 VM)
- **PX4 flight controller** connected via UART → `/dev/ttyS6` at 921600 baud
- **UWB tag** for indoor XY position, real-time via UWB anchors in the arena
- **Realsense D430 / D450** depth camera (functionally equivalent to our D435)
- **The orchestrator runs ON the drone**, not on our laptop
- Position interface is a **ROS2 topic** (`uwb_tag`, `geometry_msgs/PoseStamped`)
- Height interface is **PX4 telemetry** (`position_velocity_ned.position.down_m`)
- **Position commands disabled** (per org safety policy) — control via velocity setpoints only

### 2.3 Our Realsense D435
- Owned, ready to test
- Functionally equivalent to D430 (D435 = D430 module + RGB + housing)
- `pyrealsense2` API identical across the D4xx family
- All our `semifinal/prototypes/*.py` use it

### 2.4 Host computer (our laptop)
- Runs the **Hula swarm orchestrator** (Python, one process, N threads)
- Talks to the mapping drone over the network (likely SSH + maybe a custom command channel — TBC)
- Receives logs/data from both platforms
- Must stay on the venue WiFi for the entire mission

---

## 3. Software stack

> Two parallel stacks, one per drone platform.

### 3.0 Mapping drone (MAVSDK + ROS2 + Realsense + RKNN)

| Layer | Library | Notes |
|---|---|---|
| Flight control | `mavsdk` (Python) | Same as qualifier. Connection: `serial:///dev/ttyS6:921600` |
| Position (XY) | `rclpy` (ROS2) | Subscribe to topic `uwb_tag`, msg `geometry_msgs/PoseStamped`. ENU→NED swap (ROS x→E, ROS y→N) |
| Position (Z) | MAVSDK telemetry | `drone.telemetry.position_velocity_ned()` → `pos.position.down_m` |
| Depth + RGB | `pyrealsense2` | Same SDK we already prototyped against. Mount on drone, USB into SBC |
| Detection | `rknnlite` (on-drone runtime) | Convert `.pt → .onnx → .rknn` via `rknn-toolkit2` on a host first |
| Mapping | TBC — likely `pyrealsense2.pointcloud()` + custom occupancy grid | L4 reference code will clarify |

Reference: [`semifinal/learning_material_3_uwb/kolomee.py`](learning_material_3_uwb/kolomee.py) (org's canonical example) + [`learning_material_3_uwb/README.md`](learning_material_3_uwb/README.md) (our analysis).

### 3.1 Hula swarm — pyhulax SDK
Docs: **https://pyhulax.xenops.ae** (mirror the site if no internet at venue)

Key methods we'll use:

| Category | Methods | Notes |
|---|---|---|
| Connection | `connect(ip)`, `disconnect()`, `robust_connect(verbose=True)` | Each drone is one DroneAPI |
| Flight | `takeoff(height_cm, blocking=True)`, `land()`, `hover(seconds)`, `arm()`, `disarm()` | Blocking by default |
| Movement | `move(direction, distance_cm, speed=VelocityLevel.ZOOM)`, `rotate(angle_degrees)`, `move_to()`, `curve_to()`, `circle()` | Discrete steps, not velocity |
| Velocity-style | `send_manual_control()`, `manual_fly()`, `stop_manual_control()` | Joystick-style continuous control if needed |
| Camera | `set_camera_angle(pitch_deg)` | **Gimbal tilt — set to face down for floor-level targets** |
| Video stream | `create_video_stream()`, `set_video_stream(True)`, `start_video_stream()` | Returns frames you read in a loop |
| State | `get_position()` → Vector3, `get_state()` → DroneState, `get_battery()`, `get_obstacles()`, `get_altitude()` | Read whenever |
| Avoidance | `set_barrier_mode(True)`, `set_avoidance_direction(...)` | **Built-in obstacle avoidance — turn it on!** |
| Detection helpers | `recognize_target()`, `recognize_qr()`, `track_qr()`, `detect_qr()` | Built-in QR/AI — saves writing OpenCV pipelines |
| QR localisation | `set_qr_localization(True)` | **Absolute positioning via QR — game-changer if arena has QR markers** |
| Media | `take_photo()`, `list_photos()`, `download_photo()` | Photos on drone SD card, pull at end |
| LED | `set_led(color, mode)`, `enable_led()`, `disable_led()` | Drone status indication |
| WiFi | `set_wifi_mode/band/power/channel/ap_mode()` | Venue WiFi tuning |

### 3.2 dola — drone discovery
Already bundled at [`semifinal/dola.py`](dola.py). Self-contained UDP listener:

```python
from dola import Dola
dola = Dola()
dola.start()
ips = dola.get_all_ips(listen_seconds=5)   # {plane_id: ip}
dola.stop()
```

**Packet format (for reference):** 44 bytes, MAVLink-style. STX 0xFE, msg ID 232, payload: `serial(16) + ip_str(16) + plane_id(1) + wifi_mode(1) + bind_client(1) + wifi_power(1)`.

### 3.3 pyrealsense2 — depth camera
```python
import pyrealsense2 as rs
pipe = rs.pipeline()
cfg = rs.config()
cfg.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
cfg.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
profile = pipe.start(cfg)
intr = profile.get_stream(rs.stream.depth).as_video_stream_profile().get_intrinsics()
fx, fy, cx, cy = intr.fx, intr.fy, intr.ppx, intr.ppy

while True:
    frames = pipe.wait_for_frames()
    depth = np.asanyarray(frames.get_depth_frame().get_data())  # uint16, mm
    color = np.asanyarray(frames.get_color_frame().get_data())  # uint8, BGR
```

Depth values in mm. Convert pixel `(u, v)` + depth `d` (mm) to 3D:
```python
X = (u - cx) * d / fx / 1000.0   # metres
Y = (v - cy) * d / fy / 1000.0
Z = d / 1000.0
```

### 3.4 OpenCV ArUco — fiducial marker detection
```python
import cv2
arucoDict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
params = cv2.aruco.DetectorParameters()
detector = cv2.aruco.ArucoDetector(arucoDict, params)

corners, ids, _ = detector.detectMarkers(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
if ids is not None:
    for marker_corners, marker_id in zip(corners, ids.flatten()):
        c = marker_corners.reshape((4, 2))
        cx_px = int((c[0][0] + c[2][0]) / 2)     # marker centre pixel
        cy_px = int((c[0][1] + c[2][1]) / 2)
        # → unproject via depth/intrinsics to get 3D position
```

Dictionary `DICT_6X6_250` is the org's example and the default used by `mapping_drone/mapping.py:ArucoDetector`. **Per org 2026-06-06 PM the EXACT dictionary will be announced on the day** — code must accept a runtime dict choice via `controller.py --aruco-dict <name>`.

**Runtime override surface (audited 2026-06-07 against `mapping_drone/mapping.py:_ARUCO_DICTS`):**
- Accepted today (9 values, uppercase short-form, exact match): `4X4_50`, `4X4_100`, `4X4_250`, `5X5_250`, `6X6_50`, `6X6_100`, `6X6_250`, `6X6_1000`, `7X7_250`.
- **NOT accepted today** (will raise `ValueError` from `mapping.py` line 63-64): `4X4_1000`, `5X5_50`, `5X5_100`, `5X5_1000`, `7X7_50`, `7X7_100`, `7X7_1000`, all 4 AprilTag variants (`APRILTAG_16h5`, `APRILTAG_25h9`, `APRILTAG_36h10`, `APRILTAG_36h11`), lowercase short-form (`6x6_250`), long-form (`DICT_6X6_250`).
- Org could announce any of 16 ArUco sizes + 4 AprilTag variants → roughly half of the possible announcements are rejected by the current code. Expand `_ARUCO_DICTS` + normalise case + strip `DICT_` prefix before the venue.

### 3.5 QR / AprilTag (other fiducials)
- QR: `pyzbar` or `cv2.QRCodeDetector` or **drone's built-in `recognize_qr()`**
- AprilTag: `pip install apriltag` (or `pupil-apriltags`), API similar to ArUco

---

## 4. Likely architecture (proposal — confirm when more info lands)

```
┌──────────────────────────────────────────────────────────────────┐
│                    Host laptop orchestrator                      │
│                                                                  │
│  ┌────────┐   ┌────────────────────────────────────────┐         │
│  │ Dola   │──▶│  Swarm registry  {plane_id: DroneAPI}  │         │
│  └────────┘   └──────────────────────┬─────────────────┘         │
│                                      │                           │
│  ┌───────────────────────────────────┼──────────────────────┐    │
│  │             Per-drone task threads (one per drone)       │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │    │
│  │  │ Drone 1  │  │ Drone 2  │  │ Drone 3  │  │ Drone N  │  │    │
│  │  │ FSM      │  │ FSM      │  │ FSM      │  │ FSM      │  │    │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │    │
│  └───────┼─────────────┼─────────────┼─────────────┼────────┘    │
│          │             │             │             │             │
│          ▼             ▼             ▼             ▼             │
│   ┌─────────────────────────────────────────────────────┐        │
│   │  Detection workers (per drone video stream)          │        │
│   │  YOLO + ArUco + QR → world coords via depth + pose   │        │
│   └─────────────────────────────────────────────────────┘        │
│                                                                  │
│   ┌─────────────────────────────────────────────────────┐        │
│   │  Realsense pipeline (host-side depth, if applicable)│        │
│   └─────────────────────────────────────────────────────┘        │
│                                                                  │
│   ┌─────────────────────────────────────────────────────┐        │
│   │  Shared world map + target registry + scoring        │        │
│   └─────────────────────────────────────────────────────┘        │
│                                                                  │
│   ┌─────────────────────────────────────────────────────┐        │
│   │  Mission planner (area partition, waypoint assignment│        │
│   │  per drone, replanning on detection)                 │        │
│   └─────────────────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────────────┘
                              │ WiFi
                              ▼
                  ┌─────────────────────┐
                  │  N Hula drones      │
                  │  (own VIO, own      │
                  │   barrier mode,     │
                  │   own video stream) │
                  └─────────────────────┘
```

**Design principles:**
- One thread per drone for control (pyhulax is blocking)
- Detection pipeline is shared (consumes all video streams)
- World map + target list is the single shared state — careful locking
- Mission planner can be a separate thread; produces per-drone waypoints
- Graceful land on Ctrl-C, low battery, or any uncaught exception

---

## 5. What we need to build vs what we get for free

### Build ourselves
- [ ] Multi-drone orchestrator (threads + shared state + locks)
- [ ] Per-drone FSM (takeoff → cruise → detect → return → land)
- [ ] Mission planner / area partitioning (lawnmower, divide-and-conquer)
- [ ] Detection pipeline that consumes multiple video streams
- [ ] Realsense host-side depth integration (if needed)
- [ ] Target dedup across drones — RoboMasters are MOVING ground robots; dedup by ArUco ID (DICT_6X6_250), not by world-position clustering, since position will drift between sightings.
- [ ] Run summary + judge artifacts (carry over from qualifier)
- [ ] STATUS.txt live status across all drones
- [ ] WiFi diagnostic / health check at startup
- [ ] Emergency-land-all on Ctrl-C / battery low
- [ ] Per-drone heartbeat/timeout watchdog
- [ ] ~~YOLO retraining for any new target classes (K) — INSURANCE ONLY; primary RoboMaster detection is ArUco (DICT_6X6_250) per 2026-06-06 Discord ("hula drone to detect aruco marker on ground robots")~~ **OBSOLETED 2026-06-06: A confirmed not training YOLO** (6/6 22:13 "Nope not using yolo"; A may explore TensorFlow/ImageAI/OpenCV alternatives but exploratory only)
- [ ] ArUco DICT_6X6_250 detection pipeline on Hula video streams → RoboMaster IDs + world coords (PRIMARY target detection)
- [ ] UWBParserThread.py integration on C2 Terminal (Windows side) for Hula swarm UWB (pyserial @ 921600 baud — see `uwb_api_hula_swarm/`)
- [ ] NoMachine session setup from C2 Terminal to mapping drone (access path per org 2026-06-05)
- [ ] C2 split: mapping drone code runs in C2's Ubuntu 22.04 VM (ROS2 side); Hula swarm code runs on C2 Windows side

### Get for free from SDK
- ✅ Drone discovery (`dola.py`)
- ✅ Onboard obstacle avoidance (`set_barrier_mode(True)`)
- ✅ VIO position estimation (calibrated)
- ✅ Built-in QR detection (`recognize_qr()`, `track_qr()`, `detect_qr()`)
- ✅ AI target recognition (`recognize_target()` — explore what this does)
- ✅ QR-based absolute localisation (`set_qr_localization()` — game-changer if arena has QR landmarks)
- ✅ Photo capture on drone SD (`take_photo()`)
- ✅ Battery telemetry + safety
- ✅ Discrete movement primitives (`move`, `rotate`, `circle`, etc)

---

## 6. Open questions for the org (Day-1 morning verbal asks to org marshal)

> **2026-06-09 status:** Discord ticket path is dead this close to Day-1 (user instruction). Treat each item below as a verbal Q&A item to raise with the org marshal in person on Day-1 morning. Do NOT file new tickets.

### 6a. Still open

**Mapping drone (highest priority)**
1. **Is the mapping drone provided?** Or BYO compute module + flight controller + UWB tag + Realsense + chassis?
2. **What's the SBC?** RK3588 (Orange Pi 5) vs RK3568 changes RKNN inference speed.
3. **What's the UWB anchor layout?** Anchor count + positions + arena dimensions → accuracy + dead zones.
4. **What does "mapping" output look like for the judge?** Top-down PNG, point cloud .ply, occupancy grid .npy, or all three?
5. **UWBParserThread serial port path on C2 Terminal Windows** — which COM port does the pyserial @ 921600 baud connection use? Will org pre-configure or do we probe?
6. **Are the 5 RoboMaster ArUco IDs (DICT_6X6_250) known in advance** and mapped to specific robots, or must we discover the ID→robot mapping at run time?

**Hula swarm**

7. **How many Hula drones in the swarm?** Affects parallelisation, WiFi load, code complexity.
8. **Are there QR landmarks in the arena for `set_qr_localization()`?** If yes, absolute positioning is free for the swarm too.

**Both / general**

9. **What's the scoring rubric?** Per-marker points? Coverage points? Time bonus? Like qualifier?
10. **WiFi setup at venue?** Shared SSID for all teams' drones? Per-team? Bandwidth concerns?
11. ~~**Do Challenges 1 and 2 run in parallel or sequentially?**~~ **RESOLVED by finals_brief_extracted.md slide 12:** C1 runs Day 1 (Wed 10 Jun 1430-1800, Uni only); C2 runs Day 2 (Thu 11 Jun 1330-1600). Sequential across days, no parallel-within-slot. We are slot #3 on Day 1 and operate the convoy at slot #24 on Day 2.

### 6b. Resolved / partially resolved

12. **What ROS2 distro on the drone?** — Ubuntu 22.04 confirmed by org 2026-06-05, so almost certainly ROS2 Humble; one detail to confirm at venue.
13. **Does the Hula swarm see UWB data too?** Partially answered 2026-06-06: Hulas now have their own UWB via `UWBParserThread.py` (pyserial @ 921600 baud) — a **separate transport** from the mapping drone's ROS2-based UWB on `/dev/ttyS6`. Fusion would require bridging two different UWB stacks.
14. **What ArUco dictionary?** **RE-OPENED / DEFERRED to Day-1 (org 2026-06-06 21:32 PM, captured 2026-06-07 AM):** the EXACT dictionary will be announced on the day. DICT_6X6_250 remains the working default. `mapping_drone/mapping.py` was patched 2026-06-07 to accept any of 16 ArUco sizes + 4 AprilTag variants via case-insensitive `--aruco-dict` (smoke-tested, 20/20). No pre-venue code work needed.
15. **ArUco beside Hula (Challenge 2) landing pads?** **RESOLVED 2026-06-06 21:34 PM (captured 2026-06-07 AM):** Yes — ArUco markers are placed near Challenge 2 landing pads as well as Challenge 1's landing pads. Hula uses `cv2.aruco` for the landing aid (NOT the pyhulax landing-marker auto-land helper, which is a different marker).
16. **ArUco physical size?** **RESOLVED 2026-06-06 21:32 PM (captured 2026-06-07 AM):** **20cm x 20cm.** Implication: with D435 RGB 640x480 / ~70° HFOV, a 20cm marker subtends a few hundred px at 1m and drops toward ~30 px around 5-6m where detection gets unreliable — tune the mapping-drone flight altitude so markers stay in the reliable detection range.
17. ~~What's the target set?~~ **Resolved 2026-06-06:** 5 RoboMaster ground robots carrying ArUco markers. Hula drones detect via ArUco; A's YOLO track was killed by A on 2026-06-06 22:13 ("Nope not using yolo").
18. **Slot duration?** Confirmed 2026-06-05: Finals run 9am-6pm on both 10 + 11 June 2026 at Marina Bay Sands Expo & Convention Centre Level 4. All 3 team members should attend both days.
19. **VM still mandatory?** Confirmed 2026-06-05: C2 Terminal is Windows + Ubuntu 22.04 VM; mapping drone is accessed from C2 via NoMachine.
20. ~~L4 + L5 Drive folders not publicly accessible~~ — L5 resolved: org released yolo11n.pt + _2.py convert scripts 2026-06-05 and we pulled them into `learning_material_5_yolo_rknn/`. L4 (Realsense) — pulled into `learning_material_4_realsense/`.

---

## 7. Learning materials index

| File | Topic | Status |
|---|---|---|
| [`semifinal/huladola.py`](huladola.py) | **L1**: org's swarm example — discovery + control + video | ✅ Reviewed |
| [`semifinal/dola.py`](dola.py) | **L1**: drone discovery library (UDP 8668) | ✅ Reviewed |
| Sample code in [`semifinal_scrape.md`](semifinal_scrape.md) | **L2**: ArUco detection + pixel→3D | ✅ Reviewed |
| [`semifinal/learning_material_3_uwb/kolomee.py`](learning_material_3_uwb/kolomee.py) | **L3**: UWB + MAVSDK mapping drone control (MAVSDK-based reference for mapping drone only — Hula UWB now uses different transport) | ✅ Pulled + analysed ([README](learning_material_3_uwb/README.md)) |
| [`semifinal/learning_material_4_realsense/`](learning_material_4_realsense/) | **L4**: Realsense reference code | ✅ Pulled (generateTopDown.py, getDepth.py, getDepthAndDetect.py, getDepthPointCloud.py, getInfra.py, getRGB.py, getSyncDepthColor.py, rknndecoder.py) |
| [`semifinal/learning_material_5_yolo_rknn/`](learning_material_5_yolo_rknn/) | **L5**: YOLO `.pt → .onnx → .rknn` + RKNN detection | ✅ Pulled — convert/ (convertyolotoonnx.py + _2.py, convertrknn.py + convertrknn2.py) and detection/ (getDepthAndDetect.py, rknndecoder.py, testrknn_with_display.py); YOLOv11 base (`yolo11n.pt`) per 2026-06-05 org clarification — use _2.py variants |
| [`semifinal/mapping_drone/`](mapping_drone/) | Z's mapping-drone stack (controller, mapping, realsense, uwb, run_writer, validity) — post-v3 stable | ✅ In-tree |
| [`semifinal/uwb_api_hula_swarm/`](uwb_api_hula_swarm/) | **NEW 2026-06-06**: Hula swarm UWB via pyserial @ 921600 (UWBParserThread.py) — runs on C2 Terminal Windows side | ✅ In-tree |
| `learning/Supplementary1.pdf` | VIO (Visual-Inertial Odometry) | ✅ Reviewed |
| `learning/Supplementary2.pdf` | Search + Map + YOLO + Occupancy Grid | ✅ Reviewed |
| https://pyhulax.xenops.ae | pyhulax SDK reference | ✅ Mirrored at [`docs/pyhulax/`](docs/pyhulax/) + analysed at [`docs/pyhulax_analysis.md`](docs/pyhulax_analysis.md) |
| https://docs.openvins.com | OpenVINS (underlying VIO) | Optional — drone is pre-calibrated |
| https://learnopencv.com/monocular-slam-in-python/ | SLAM background | Optional |
| RKNN-toolkit2 docs | Will need to mirror for offline RKNN conversion | ⏳ Pending — once L5 unblocked |
| pyrealsense2 docs | https://intelrealsense.github.io/librealsense/python_docs/ | ⏳ Should mirror offline before venue |

---

## 8. Detection target preparation

**Per org Learning Material 2:** likely targets include fiducial markers. Prepare for any combination:

### ArUco markers
- Library: `cv2.aruco` (already in OpenCV — no extra install)
- Default dict: `DICT_6X6_250` (org sample)
- Detection: ~5 lines of code (see §3.4)
- 3D unprojection: depth at marker centre × intrinsic formula
- Speed: very fast (real-time on CPU)

### QR codes
- **Option A:** drone's built-in `recognize_qr()` / `track_qr()` / `detect_qr()` — try this first
- **Option B:** `pip install pyzbar` (Python wrapper for libzbar) — robust, handles damaged codes
- **Option C:** OpenCV `cv2.QRCodeDetector` — built in, slightly slower than pyzbar
- Payload can carry semantic data (e.g. "target_1", coordinates, instructions)

### AprilTag
- `pip install pupil-apriltags` (or `apriltag` legacy)
- Used by OpenVINS for calibration — drone might have one mounted for reference
- Detection slower than ArUco but more robust to occlusion

### Barrels (carry-over from qualifier)
- K's `best.pt` model already trained; retrain with finals dataset when org provides
- May need new classes if targets differ
- Inference: Ultralytics YOLO, same pipeline as qualifier

---

## 9. Suggested per-member tracks (when work starts)

### A (ML — already on it)
- Train YOLO on whatever images exist; **target output: ONNX-ready**
- When K's `best.pt` is ready, run `model.export(format='onnx', imgsz=640, opset=12, simplify=True)`
- Set up `rknn-toolkit2` on a Linux host (x86) for `.onnx → .rknn` conversion (notoriously version-pinned — pin Python 3.8-3.11)
- Sample a small calibration image set (~100 frames) from training data
- When L5 is unlocked, run the org's conversion code and produce `best.rknn` for the mapping drone

### K (Hula swarm + flight)
- **Hula side:** stand up a single Hula drone, get `connect → takeoff → hover → land` working
- Profile `set_barrier_mode` — aggressive? reliable? false positives?
- Test `set_camera_angle(DOWN_ABSOLUTE, 45)` — gimbal range + lag
- Test `recognize_target()`, `recognize_qr()`, `set_qr_localization()` — observe actual returns
- **Mapping side (when hardware available):** test the kolomee.py pattern, validate UWB integration

### Z (orchestration + Realsense + mapping drone code)
- **Hula swarm orchestrator** — one thread per drone, shared state, per-drone FSM (skeleton in §10). NOT YET BUILT — `swarm_controller.py` placeholder, see §14 layout for target path.
- **Mapping drone stack (post-v3 stable):** code lives at `mapping_drone/` — `controller.py` (MAVSDK waypoint runner, reads `pvn.position.down_m`, subscribes to `attitude_euler` for `drone_yaw`, pumps mock UWB when MockUWB+MockMAVSDK active), `mapping.py` (camera→world corrected: `x_b=cp*z_c+sp*y_c, y_b=x_c, z_b=sp*z_c-cp*y_c`), `run_writer.py` (`save_marker_image` accepts `bbox_xyxy`), `realsense.py`, `uwb.py` (ROS2 `uwb_tag` PoseStamped subscriber), `validity.py` (`decide_landing_validity(aruco_id)` with `MAPPING_DRONE_VALIDITY` env override).
- Default waypoints: `[(0,0,4.0),(2,0,4.0),(2,2,4.0),(0,2,4.0)]` (above the 3.5 m org floor), `--gimbal-pitch=-90`, `runs_dir='mapping_drone/runs'` (relative — avoids double-path).
- Realsense pipeline + intrinsics + depth-aware ArUco (already prototyped in [`prototypes/aruco_realsense.py`](prototypes/aruco_realsense.py))
- Run-summary / STATUS.txt writer (carry over from qualifier)
- Emergency-land-all + Ctrl-C across BOTH platforms
- Log broadcaster integration so the assistant can monitor in real time

---

## 10. Skeleton code (starting point)

A minimal swarm controller, ready to extend:

```python
"""
Swarm controller skeleton — multi-Hula orchestrator.
One thread per drone. Shared state under a lock.
"""

import threading
import time
import cv2
import numpy as np

from pyhulax import DroneAPI
from pyhulax.core import Direction, VelocityLevel
from dola import Dola

# -- Shared state --------------------------------------------------
class WorldState:
    def __init__(self):
        self.lock = threading.Lock()
        self.targets_found = {}        # {target_id: (x, y, z, drone_id, ts)}
        self.drones = {}               # {ip: DroneAPI}
        self.drone_state = {}          # {ip: 'idle'|'cruising'|'detecting'|'returning'|'landed'}
        self.abort = False

world = WorldState()

# -- Per-drone FSM thread ------------------------------------------
def drone_worker(ip, plane_id):
    drone = world.drones[ip]
    state = 'takeoff'
    while not world.abort:
        try:
            if state == 'takeoff':
                drone.takeoff(height_cm=100, blocking=True)
                drone.set_barrier_mode(True)
                drone.set_camera_angle(-45)  # tilt down 45°
                state = 'cruise'
            elif state == 'cruise':
                # TODO: get next waypoint from mission planner
                drone.move(Direction.FORWARD, 100)
                state = 'detect_check'
            elif state == 'detect_check':
                # TODO: query world.targets_found
                state = 'cruise'
            elif state == 'return':
                # TODO: navigate to spawn
                drone.land(blocking=True)
                state = 'landed'
            elif state == 'landed':
                break
            with world.lock:
                world.drone_state[ip] = state
        except Exception as e:
            print(f"[{plane_id}] error: {e} — emergency land")
            try: drone.land(blocking=True)
            except: pass
            break

# -- Detection thread ----------------------------------------------
arucoDict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
arucoDet  = cv2.aruco.ArucoDetector(arucoDict, cv2.aruco.DetectorParameters())

def detection_worker(ip, stream, plane_id):
    while not world.abort:
        f = stream.latest_frame
        if f is None:
            time.sleep(0.05); continue
        img = f.to_rgb()
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = arucoDet.detectMarkers(gray)
        if ids is not None:
            for mc, mid in zip(corners, ids.flatten()):
                c = mc.reshape((4, 2))
                cx_px = int((c[0][0] + c[2][0]) / 2)
                cy_px = int((c[0][1] + c[2][1]) / 2)
                with world.lock:
                    if mid not in world.targets_found:
                        # TODO: get pose, depth → world coord
                        world.targets_found[int(mid)] = (cx_px, cy_px, plane_id, time.time())
                        print(f"[{plane_id}] new ArUco {mid} at pixel ({cx_px},{cy_px})")
        time.sleep(0.05)

# -- Main ----------------------------------------------------------
def main():
    dola = Dola(); dola.start()
    try:
        ips = dola.get_all_ips(listen_seconds=5)
    finally:
        dola.stop()
    print(f"Discovered {len(ips)} drones: {ips}")

    threads = []
    for plane_id, ip in ips.items():
        api = DroneAPI(); api.connect(ip)
        world.drones[ip] = api
        stream = api.create_video_stream(); api.set_video_stream(True); stream.start()
        threads.append(threading.Thread(target=drone_worker,    args=(ip, plane_id), daemon=True))
        threads.append(threading.Thread(target=detection_worker, args=(ip, stream, plane_id), daemon=True))

    for t in threads: t.start()

    try:
        while any(t.is_alive() for t in threads):
            time.sleep(1)
    except KeyboardInterrupt:
        print("Ctrl-C: aborting all drones")
        world.abort = True
        for ip, api in world.drones.items():
            try: api.land(blocking=False)
            except: pass

if __name__ == "__main__":
    main()
```

This is a starting point only — needs: shared mission planner, real waypoint logic, depth fusion, target dedup, run summary writer, proper LED status, battery monitoring, etc.

---

## 11. WiFi / venue considerations

- All drones must share a network with the laptop
- Dola broadcasts on UDP 8668 — make sure no firewall blocks it
- Each video stream is bandwidth-heavy — N drones = N × bitrate. Consider reducing resolution (`set_video_resolution(VideoResolution.LOW)`)
- WiFi interference at venue is real (other teams' drones, audience phones). Test with a single drone first.
- The drone exposes WiFi config methods (`set_wifi_channel`, `set_wifi_power`, etc) — may help at venue

---

## 12. Risks + mitigations

| Risk | Mitigation |
|---|---|
| VIO drift mid-mission | Initialise carefully (gentle 3-axis hand rotation before takeoff). Use `set_qr_localization()` if available. |
| WiFi packet loss | Reduce video resolution. Per-drone heartbeat timeout. Land-on-loss safety. |
| Battery dies mid-flight | Poll `get_battery()` regularly. Auto-return + land at 30%. |
| Drone collision with arena / each other | `set_barrier_mode(True)` on all drones. Plan altitudes per drone so they don't share space. |
| Multiple drones see same target → double-count | Target dedup by (id, world position cluster ≤ N cm). Lock around `targets_found`. |
| One drone wedges, others wait | Per-drone timeout + graceful skip. Don't block the swarm on one stuck unit. |
| WiFi network goes down mid-run | Auto-land on `dola` heartbeat timeout. Log everything to local disk continuously. |
| Code crashes on host | Wrap `main()` in try/finally that lands all drones unconditionally. |

---

## 13. Pre-venue checklist (build this out closer to the date)

- [ ] All drones charged + spare batteries
- [ ] Realsense camera + USB-C cable
- [ ] Laptop charged + power adapter
- [ ] WiFi router (if BYO) + ethernet + power
- [ ] USB stick × 2 with code + setup script
- [ ] Printed runbook
- [ ] pyhulax + pyrealsense2 + cv2 + numpy installed and tested
- [ ] Dry-run completed with ≥2 drones in a room
- [ ] Emergency-land hotkey tested
- [ ] All artifacts go to local disk (not just network)

---

## 14. Where to put new files

```
semifinal/
├── README.md              ← this file
├── huladola.py            ← org's example (read-only reference)
├── dola.py                ← discovery library (read-only reference)
├── mapping_drone/         ← Z's mapping-drone stack (post-v3 stable: controller.py,
│                            mapping.py, run_writer.py, realsense.py, uwb.py, validity.py)
├── uwb_api_hula_swarm/    ← NEW 2026-06-06: UWBParserThread.py for Hula UWB (pyserial @ 921600)
├── swarm_controller.py    ← our swarm orchestrator (NOT YET BUILT — placeholder)
├── detection.py           ← detection pipeline (NOT YET BUILT — placeholder)
├── planner.py             ← mission planner (NOT YET BUILT — placeholder)
├── realsense_node.py      ← Realsense host-side wrapper (NOT YET BUILT — placeholder)
├── world_state.py         ← shared state + targets registry (NOT YET BUILT — placeholder)
├── tests/                 ← unit tests, mocks
├── logs/                  ← runtime logs
├── runs/                  ← per-mission artifact directories
└── thumbdrive/            ← venue USB contents
```

---

## 15. Reference links

- Hula SDK: https://pyhulax.xenops.ae
- pyrealsense2: https://github.com/IntelRealSense/librealsense/tree/master/wrappers/python
- OpenCV ArUco: https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html
- OpenVINS: https://docs.openvins.com/
- AprilTag: https://github.com/AprilRobotics/apriltag
- pyzbar (QR): https://pypi.org/project/pyzbar/
- Qualifier repo state: commit `3c4f6c7` (v0.7.2) on `zb` branch (sim-era reference only)
- Finals repo (this directory): `mapping_drone/` post-v3 stable stack (controller.py + mapping.py with corrected camera_to_world, run_writer.py, realsense.py, uwb.py, validity.py); `uwb_api_hula_swarm/` added 2026-06-06 (UWBParserThread.py for Hula swarm UWB on C2 Terminal Windows via pyserial @ 921600)
- Drive folder (Hula examples): https://drive.google.com/drive/folders/19ni5GmRy8cBzX98TybsToQa4a17LbYi5

---

## 17. Pre-physical-run checklist (historical — T-1 status below)

Physical run sessions: **2026-06-10** + **2026-06-11** (both days, all 3 members per org guidance 2026-06-05 22:22). Today is **T-1 (2026-06-09)** — the day-of operational source of truth is now [`DAY1_RUNBOOK.md`](DAY1_RUNBOOK.md) + [`DAY1_SETUP_SEQUENCE.md`](DAY1_SETUP_SEQUENCE.md). The buckets below are kept as a historical preparation log; remaining T-1 items are called out at the bottom.

### Historical: by T-4 (Sat 6 Jun) — software that needs no drone
- [x] Laptop on the team's WiFi/Tailscale + log_broadcaster reaching the desktop sink
- [x] `pip install "pyhulax[all]"` + `pyrealsense2` + `opencv-contrib-python` + `numpy` clean install on the laptop
- [x] Smoke import: `python3 -c "from pyhulax import DroneAPI; from pyhulax.video import YOLODetector; import pyrealsense2; import cv2; print('OK')"`
- [x] Realsense D435 hardware verified (the verify script in `semifinal/README.md` §3.3 — prints intrinsics + a sample depth value). NOTE: D435 was our DEV camera only; venue mapping drone ships with D430/D450 (no RGB by default).
- [x] ArUco prototype script working: webcam → detect with default dict → pixel→3D unproject using webcam calibration. NOTE: exact dictionary is announced Day-1; code accepts any of 16 ArUco sizes + 4 AprilTag variants at runtime.
- [x] K's `best.pt` confirmed loadable by `pyhulax.video.YOLODetector` (or convert to ONNX for `ONNXDetector`) — (insurance only — primary detection is ArUco). Base model: YOLOv11 (`yolo11n.pt`) per 2026-06-05 PM org clarification.
- [x] Print test ArUco markers (3-4 IDs at 10cm, 20cm sizes) — tape around a room
- [x] UWBParserThread.py landed at `uwb_api_hula_swarm/` (2026-06-06 org release)

### Historical: by T-2 (Mon 8 Jun) — swarm orchestrator skeleton
- [ ] `semifinal/swarm_controller.py` skeleton from [§10 code skeleton above](#10-skeleton-code-starting-point) compiles + runs against mock drones (NOTE: `swarm_controller.py` is STILL a stub — see file header)
- [ ] State machine per drone: idle → takeoff → cruise → detect_check → return → land
- [ ] Shared target registry with dedup logic (unit-tested without drones) — dedup by ArUco ID (RoboMasters are moving)
- [x] Run summary writer (carry over from qualifier — `run_writer.py` in `mapping_drone/`)
- [x] STATUS.txt live status (mapping_drone side)
- [ ] Emergency-land-all on Ctrl-C / battery low — tested with mock drones throwing errors

### T-1 (Tue 9 Jun) — TODAY, last-mile integration
- [ ] NoMachine access to mapping drone verified from C2 Terminal (Day-1 morning task)
- [ ] Both Windows + Ubuntu 22.04 VM sides of C2 Terminal smoke-tested (Day-1 morning task)
- [ ] UWBParserThread.py verified @ 921600 baud on actual C2 hardware (COM port confirmed) (Day-1 morning task)
- [ ] Map-discovery (Challenge 1) plan rehearsed — "Map layout will not be provided" (org 2026-06-06 11:40)
- [ ] Thumbdrive packed with code + offline docs (mark stub/NOT-YET-BUILT items clearly)
- [ ] USB-stick packed; sleep early; smart-casual ready for 7:30am registration tomorrow

### On the day of (10/11 Jun)
- [ ] Photo ID + confirmation email on hand (registration 10 Jun 7:30am at Marina Bay Sands Expo Level 4)
- [ ] Smart casual dress — NO slippers / uncovered footwear
- [ ] Personal laptop + mouse + charger + thumbdrive
- [ ] All 3 members present both days
- [ ] Drones charged + spare batteries
- [ ] D435 + USB-C cable
- [ ] Laptop charged + power adapter
- [ ] WiFi router config tested (if BYO)
- [ ] Printed ArUco markers + measuring tape
- [ ] Notebook for jotting drone IPs, plane IDs, observed quirks
- [ ] Log broadcaster running on desktop for real-time monitoring

### What we want to validate on the physical run
1. Drone discovery (Dola broadcasts arrive, all drones enumerate)
2. Single-drone smoke (connect → takeoff → hover → land)
3. Multi-drone simultaneous control (no command collision)
4. VIO init pattern (hand-rotate 3 axes, watch `get_position()` settle)
5. `set_barrier_mode(True)` behaviour — how aggressive? cleared distance? false positives?
6. `set_camera_angle(DOWN_ABSOLUTE, 45)` — range, lag, stability
7. `set_qr_localization(True)` — does the arena/room have a QR mat for it?
8. `recognize_qr()` + `track_qr()` + `recognize_target()` — what do they actually return?
9. Video stream pipeline end-to-end (drone camera → callback → YOLO → display + record)
10. Realsense + drone video fusion (if Realsense is mounted on a drone, sync of streams)
11. WiFi load with N drones streaming video — does bandwidth hold?
12. Battery duration — minutes per drone before failsafe
13. `move_to(x, y, z)` accuracy without QR loc (drift over time)
14. `move_to(x, y, z)` accuracy with QR loc (if available)

### What we want to AVOID on the physical run
- Wasting hardware time on Python install issues
- Discovering the laptop's WiFi can't reach the drones
- Realising the YOLO model needs format conversion
- Finding out the camera mount blocks the gimbal range
- Spending hours on a single drone before testing the swarm

The whole point of arriving prepared is: by the time we have drones in hand, every line of code that touches the drone should already exist. The physical run is for tuning, not authoring.

---

*Last updated: 2026-06-09 (T-1 to finals — Marina Bay Sands Expo & Convention Centre, Level 4). Day-of source of truth is `DAY1_RUNBOOK.md` + `DAY1_SETUP_SEQUENCE.md`; this README is the background knowledge base.*
*Update this file every time new info lands — it's the single source of truth for the team.*

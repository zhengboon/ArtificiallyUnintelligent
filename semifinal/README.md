# BrainHack 2026 RoboVerse — Semi-Final Prep

**Status:** Qualified 2026-05-22 (top 26 of ~70 teams advance). Semi-final date TBA.
**Physical run sessions: 2026-06-10 and 2026-06-11** — hands-on hardware time.
**Scope shift:** Sim → real hardware. Single drone → swarm. MAVSDK → pyhulax. New SDK, new sensors, new targets.

> **T-7 / T-8 to physical run.** Prep plan: see [§17 below](#17-pre-physical-run-checklist-t-7).

This is the working knowledge base for the semi-final. Everything we know so far, organised so any team member can pick up where another left off.

---

## 0. TL;DR — what changed

| | Qualifier (sim) | Semi-final (real hardware) |
|---|---|---|
| Platform | x500_vision in PX4 SITL + Gazebo Harmonic | **Real Hula drones** (multiple) |
| SDK | MAVSDK (`mavsdk-python`) | **pyhulax** (`from pyhulax import DroneAPI`) — MAVSDK does **NOT** work |
| Pose source | Gazebo simulation truth + PX4 EKF | **VIO** (pre-calibrated on drone) + optional QR-based absolute positioning |
| Camera (RGB) | Gazebo IMX214 via `gz.transport13` | Hula's onboard camera, accessed via `DroneAPI.create_video_stream()` |
| Depth sensor | Sim depth camera | **Realsense D430 / D450** via `pyrealsense2` (host-side, separate from drone) |
| Targets | Yellow + red barrels (plain, no toxic) | Likely barrels + **fiducial markers** (ArUco / QR / AprilTag) — unconfirmed |
| Control loop | Asyncio + offboard velocity setpoints | **Synchronous, blocking** `move(direction, distance_cm)` per drone |
| Coordination | Single drone | **N drones, one orchestrator process** on the host laptop |

**The good news:** the SDK does a LOT for us — onboard obstacle avoidance, built-in QR detection, AI target recognition, optional QR localisation. We don't have to write low-level control.

**The bad news:** real hardware, no sim safety net. VIO drift, WiFi flakiness, battery limits, physical crashes.

---

## 1. What we have already (from qualifier)

Reusable as-is or with minor changes:

| Asset | Where | Reusability |
|---|---|---|
| YOLOv8 training pipeline (`best.pt`) | `models/best.pt` | **Yes** — retrain on whatever semi-final targets are |
| Depth → 3D unprojection math | `searchctl/controller.py` mapping section | **Yes** — same formula `X = (u-cx)*Z/fx, Y = (v-cy)*Z/fy, Z = depth_m` works for Realsense |
| Top-down occupancy mapping | `searchctl/controller.py:457-687` | **Maybe** — concept transfers, but need to fuse Realsense + drone pose differently |
| Asyncio + signal-handling scaffolding | `searchctl/controller.py:765-942` | **Partial** — pyhulax is sync, but multi-drone orchestration may still benefit from threads/async |
| Run-summary + STATUS.txt writer | `searchctl/controller.py:692-838` | **Yes** — judges want artifacts |
| Wall-follow FSM | `searchctl/wall_following.py` | **No** — drone has built-in `set_barrier_mode()` |

---

## 2. Hardware stack (semi-final)

### 2.1 Hula drone (per drone, swarm count TBD)
- **WiFi-networked** — both laptop and drones must be on the same WiFi network
- Sends discovery broadcasts on UDP port **8668** every few seconds (44-byte packet, MAVLink-like, msg ID 232)
- Onboard: camera (with **tiltable gimbal** — code-controlled), VIO (pre-calibrated), obstacle sensors, LEDs, payload devices (electromagnet/clamp), optional laser
- SDK abstraction: one `DroneAPI()` instance per drone, addressed by IP
- **Critical:** do NOT bump or remount the camera — VIO calibration depends on physical placement

### 2.2 Realsense Depth Camera (D430 / D450)
- Accessed via `pyrealsense2` Python SDK
- Provides RGB + depth stream + camera intrinsics
- **Mount location unconfirmed** — could be on a drone, could be static (ground/tripod). Affects everything.
- Likely used for HOST-side depth processing on either the drone's video feed or a fixed observation point

### 2.3 Host computer (our laptop)
- Runs the orchestrator (Python, one process)
- Holds N `DroneAPI` instances + N video stream consumers + Realsense pipeline + detection pipeline + planner
- Must stay on the drones' WiFi network for the entire mission

---

## 3. Software stack

### 3.1 pyhulax SDK — control library
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

Dictionary `DICT_6X6_250` is the org's example — confirm at venue if they use a different one.

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
- [ ] Target deduplication across drones (don't double-count same QR)
- [ ] Run summary + judge artifacts (carry over from qualifier)
- [ ] STATUS.txt live status across all drones
- [ ] WiFi diagnostic / health check at startup
- [ ] Emergency-land-all on Ctrl-C / battery low
- [ ] Per-drone heartbeat/timeout watchdog
- [ ] YOLO retraining for any new target classes (K)

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

## 6. Open questions for the org (file as Discord support tickets)

1. **How many drones in the swarm?** (Affects parallelisation, WiFi load, complexity)
2. **Is the Realsense mounted on a drone or static?** Drone-mounted = onboard depth; static = observation post pattern.
3. **Are there QR landmarks in the arena for `set_qr_localization()`?** If yes, absolute positioning is free.
4. **What's the target set?** Same barrels? ArUco markers? AprilTags? QR with payloads? Mix?
5. **What ArUco dictionary?** Org sample used `DICT_6X6_250` — confirm.
6. **What's the scoring rubric?** Per-marker points? Coverage points? Time bonus? Like qualifier?
7. **WiFi setup at venue?** Will all teams share one network? Per-team SSID? Bandwidth concerns?
8. **Slot duration?** Qualifier was 40 min including setup. Semi-final probably similar.
9. **Hardware borrow / supply?** Are drones + Realsense provided at venue, or do we bring our own?
10. **VM still mandatory?** Qualifier required org laptop+VM. Same for semi-final?

---

## 7. Learning materials index

| File | Topic | Status |
|---|---|---|
| [`semifinal/huladola.py`](huladola.py) | Org's swarm example — discovery + control + video | ✅ Reviewed |
| [`semifinal/dola.py`](dola.py) | Drone discovery library (44-byte UDP packets on port 8668) | ✅ Reviewed |
| `learning/Supplementary1.pdf` | Visual-Inertial Odometry (VIO) | ✅ Reviewed |
| `learning/Supplementary2.pdf` | Search + Map + YOLO + Occupancy Grid | ✅ Reviewed |
| https://pyhulax.xenops.ae | pyhulax SDK reference | ⚠️ Skim only — needs full mirror before venue |
| https://docs.openvins.com | OpenVINS (underlying VIO) | Optional — drone is pre-calibrated |
| https://learnopencv.com/monocular-slam-in-python/ | SLAM background (org reference) | Optional |
| TBA | Realsense pyrealsense2 docs (org will post) | ⏳ Waiting |
| TBA | Swarm control deeper material (org will post) | ⏳ Waiting |
| TBA | Object detection model training (org will post) | ⏳ Waiting |

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
- K's `best.pt` model already trained; retrain with semi-final dataset when org provides
- May need new classes if targets differ
- Inference: Ultralytics YOLO, same pipeline as qualifier

---

## 9. Suggested per-member tracks (when work starts)

### K (drone tuning + ML)
- Stand up a single Hula drone, get `connect → takeoff → hover → land` working
- Profile `set_barrier_mode` behaviour — how aggressive, how reliable?
- Test `set_camera_angle` for gimbal tilt — what range works?
- Investigate `recognize_target()` and `set_qr_localization()` — what do they actually do?
- Retrain YOLO model when org releases semi-final dataset

### Z (orchestration + integration)
- Build swarm orchestrator skeleton (one thread per drone, shared state, FSM)
- Carry over run-summary / STATUS.txt writer to multi-drone
- Wire Realsense `pyrealsense2` pipeline + intrinsics fetch
- Build detection-fusion layer (drone video + Realsense depth + ArUco)
- Emergency-land-all + Ctrl-C handling

### A (testing + ops)
- Set up venue-WiFi simulation at home (router config)
- Test multi-drone discovery with Dola (need ≥2 drones)
- Diagnostic + monitoring dashboards
- Trial runs against mock targets (printed ArUco markers, taped barrels)

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
├── controller.py          ← our swarm orchestrator (to be built)
├── detection.py           ← detection pipeline (to be built)
├── planner.py             ← mission planner (to be built)
├── realsense_node.py      ← Realsense host-side wrapper (to be built)
├── world_state.py         ← shared state + targets registry (to be built)
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
- Our qualifier repo state: commit `3c4f6c7` (v0.7.2) on `zb` branch
- Drive folder (Hula examples): https://drive.google.com/drive/folders/19ni5GmRy8cBzX98TybsToQa4a17LbYi5

---

## 17. Pre-physical-run checklist (T-7)

Physical run sessions: **2026-06-10** + **2026-06-11**. Goal: arrive with everything that doesn't need drone-in-hand already working, so the physical time is spent on hardware integration, not setup.

### By T-5 (Wed 5 Jun) — software that needs no drone
- [ ] Laptop on the team's WiFi/Tailscale + log_broadcaster reaching the desktop sink
- [ ] `pip install "pyhulax[all]"` + `pyrealsense2` + `opencv-contrib-python` + `numpy` clean install on the laptop
- [ ] Smoke import: `python3 -c "from pyhulax import DroneAPI; from pyhulax.video import YOLODetector; import pyrealsense2; import cv2; print('OK')"`
- [ ] Realsense D435 hardware verified (the verify script in `semifinal/README.md` §3.3 — prints intrinsics + a sample depth value)
- [ ] ArUco prototype script working: webcam → detect `DICT_6X6_250` → pixel→3D unproject using webcam calibration
- [ ] K's `best.pt` confirmed loadable by `pyhulax.video.YOLODetector` (or convert to ONNX for `ONNXDetector`)
- [ ] Print test ArUco markers (3-4 IDs at 10cm, 20cm sizes) — tape around a room

### By T-2 (Sun 8 Jun) — swarm orchestrator skeleton
- [ ] `semifinal/controller.py` skeleton from [§10 code skeleton above](#10-skeleton-code-starting-point) compiles + runs against mock drones
- [ ] State machine per drone: idle → takeoff → cruise → detect_check → return → land
- [ ] Shared target registry with dedup logic (unit-tested without drones)
- [ ] Run summary writer (carry over from qualifier)
- [ ] STATUS.txt live status across all drones
- [ ] Emergency-land-all on Ctrl-C / battery low — tested with mock drones throwing errors

### On the day of (10/11 Jun)
- [ ] Drones charged + spare batteries
- [ ] D435 + USB-C cable
- [ ] Laptop charged + power adapter
- [ ] WiFi router config tested (if BYO)
- [ ] Printed ArUco markers + measuring tape
- [ ] Notebook for jotting drone IPs, plane IDs, observed quirks
- [ ] Log broadcaster running on desktop so this assistant can watch in real time

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

*Last updated: 2026-06-03 (T-7 to physical run sessions).*
*Update this file every time new info lands — it's the single source of truth for the team.*

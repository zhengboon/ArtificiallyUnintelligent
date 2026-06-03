# pyhulax SDK — Full Analysis

Built from a complete read of the mirrored docs at [`semifinal/docs/pyhulax/`](pyhulax/). This is our internal cheat-sheet — what's there, what's important, what the gotchas are, what we'll actually use.

The drone platform is **HG-Fly F09-lite / Hula**. pyhulax is a clean modern reimplementation of the original Python 3.6 / Windows-only `pyhula` library.

> **NOTE (2026-06-03):** This SDK is ONLY for the **Hula swarm** drones. The semi-final also has a **separate mapping drone** (MAVSDK + UWB + Realsense + onboard NPU) — covered in the sister doc [`mapping_drone_analysis.md`](mapping_drone_analysis.md). When org's L3 + L4 + L5 dropped, it became clear the two platforms are independent. **Most of this document does NOT apply to the mapping drone.**

---

## 1. TL;DR — what changes how we work

1. **Coordinate system is different from MAVSDK / NED.** Hula uses cm and a right-handed frame: **x = right (cm), y = forward (cm), z = up (cm)**, origin at takeoff point. Don't mix with NED.
2. **All API is synchronous + blocking.** No asyncio. `move()`, `rotate()`, `takeoff()` block until done unless you pass `blocking=False`.
3. **QR localization is a game-changer.** `drone.set_qr_localization(True)` turns the arena into an absolute-coordinate system based on QR codes on the floor. `get_position()` returns absolute coords; `move_to(x,y,z)` flies to absolute coords. Solves "where am I?" entirely for the swarm.
4. **Built-in onboard obstacle avoidance.** `drone.set_barrier_mode(True)` — drone dodges things itself using its IR/ToF sensors. Cuts out most of our wall-follow FSM work.
5. **Built-in QR detection.** `drone.detect_qr(qr_id)`, `recognize_qr(qr_id)`, `track_qr(qr_id, duration)` — no OpenCV needed for QR.
6. **Built-in target recognition.** `drone.recognize_target(AIRecognitionTarget.DIGIT_5)` — drone has on-board digit/arrow/letter classifier.
7. **`pyhulax.video` ships with `ONNXDetector` and `YOLODetector` classes.** We can drop K's `best.pt` straight into the SDK's frame-callback pipeline. No custom inference loop required.
8. **Discrete move + continuous manual control are separate code paths.** `move(Direction, dist)` is blocking step movement. `manual_fly(duration, forward, right, up, rotate)` is joystick-style continuous control — needed for simultaneous xyz+yaw.
9. **Need `set_app_mode(1)` (Aerial) BEFORE takeoff** to use manual control. Default is `2` (Program / autonomous).
10. **`ManualFlightController`** = built-in PD controller that does closed-loop xyz+yaw via MANUAL_CONTROL messages at 20Hz. We probably don't need to write our own controller.

---

## 2. Package layout

```
pyhulax/                       # base install (`pip install pyhulax`)
├── DroneAPI                   # the high-level entry point
├── pyhulax.core               # enums + Pydantic models + exceptions
├── pyhulax.control            # closed-loop PD flight controller
├── pyhulax.logging            # file + DB logging (SQLite default, Postgres extra)
├── pyhulax.config             # configuration models (NetworkConfig etc.)
├── pyhulax.fylo               # runtime internals (don't touch)
└── pyhulax.system             # runtime internals (don't touch)

Optional extras (install with [video], [vision], [web], [db], [all]):
├── pyhulax.video              # streaming, display, recording, detection helpers
│   ├── VideoStream / RTSPStream / VideoStreamSimple
│   ├── VideoDisplay / show_frame
│   ├── VideoRecorder / SegmentedRecorder
│   ├── ONNXDetector / YOLODetector / YOLOSegmentDetector
│   ├── DrawDetections / DetectionLogger / FilterDetector
│   └── MJPEGStreamer / WebStreamServer
└── pyhulax.logging.PostgresLogger  (with [db])
```

For semi-final we install: `pip install "pyhulax[all]"` — gives us everything.

---

## 3. Network + protocol details (matters for swarm WiFi setup)

| Port | Type | Purpose | Default |
|---|---|---|---|
| 8888 | TCP | Command channel | TCP per drone |
| 8085 | UDP | Command port | shared per drone |
| 8668 | UDP | Status (used by `dola.py` for discovery broadcasts) | broadcast |
| 8688 | UDP | OptiTrack — external mocap input port | broadcast |
| 9000+ | UDP | RTP video base port | per-drone offsets |
| 5000 | TCP | Web stream server (when enabled) | host |
| 12346 | TCP/HTTP | Media file server on the drone | per drone |

Default drone IP: `192.168.100.1` (the drone is itself an AP, OR connected to our network). The OptiTrack port hint is interesting — Hula has an external-pose-input pathway. The arena might have OptiTrack/Vicon mounted. **Worth asking the org.**

Protocol: TCP for commands by default. MAVLink underneath (system_id=1, component_id=2). Serial fallback at 921600 baud (we don't need it).

---

## 4. Quick start (the canonical pattern)

```python
from pyhulax import DroneAPI
from pyhulax.core import Direction

with DroneAPI() as drone:
    if not drone.robust_connect(verbose=True):
        raise SystemExit("Wi-Fi check")

    if drone.get_battery() < 20:
        raise SystemExit("Battery too low")

    drone.set_barrier_mode(enabled=True)          # built-in obstacle avoidance
    drone.set_qr_localization(enabled=True)       # absolute positioning via QR mat

    try:
        drone.takeoff(height_cm=100)
        drone.move(Direction.FORWARD, 100)
        print(drone.get_position(), drone.get_battery())
    finally:
        drone.land()
```

This is the shape every script will take. `with DroneAPI() as drone:` is the safe pattern — disconnects + cleans up even on exceptions.

For swarm: instantiate **one `DroneAPI()` per drone**, addressed by IP from `Dola().get_all_ips()`.

---

## 5. DroneAPI — methods that matter (semi-final lens)

Organised by what we'll actually use, not alphabetically.

### 5.1 Connection lifecycle

| Method | Notes |
|---|---|
| `DroneAPI(config=DroneConfig(...))` | Construct. Pass `enable_command_logging=False` if you don't want a logs/ dir |
| `connect(ip=None, timeout=5.0)` | Raises `DroneConnectionError` on failure. Uses `config.network.drone_ip` if no IP |
| `robust_connect(ip=None, timeout=5.0, verbose=True) → bool` | **Prefer this.** Returns False instead of raising. Logs diagnostics |
| `disconnect()` | Releases socket. Context manager calls this for you |
| `.is_connected` (property) | Use as a guard before sending commands |

### 5.2 Flight lifecycle

| Method | Notes |
|---|---|
| `takeoff(height_cm=100, flags=TakeoffFlags.NONE, blocking=True)` | `TakeoffFlags.WITH_LOAD` for carrying a payload, `RESET_YAW` to zero heading |
| `land(blocking=True)` | Always wrap in `try/finally` |
| `hover(duration_seconds, blocking=True)` | Holds position for N seconds |
| `arm()` / `disarm()` | Low-level. Usually you don't call these — takeoff/land do |
| `set_land_speed(fast=False)` | Fast lands quicker but less stable. Use slow for precision |
| `enable_battery_failsafe()` / `disable_battery_failsafe()` | **Enable failsafe — auto-lands on critical battery** |

### 5.3 Discrete movement (blocking)

These complete one motion at a time and return.

| Method | Notes |
|---|---|
| `move(direction, distance_cm, speed=VelocityLevel.ZOOM, blocking=True)` | `Direction.{FORWARD,BACK,LEFT,RIGHT,UP,DOWN}` |
| `rotate(angle_degrees, blocking=True)` | Positive = CCW (left), Negative = CW (right) |
| `move_to(x, y, z, speed=VelocityLevel.ZOOM, blocking=True)` | **Absolute position in cm.** With QR loc enabled = QR mat coords. Without = relative to takeoff origin |
| `curve_to(x, y, z, ccw=True, blocking=True)` | Curved path to position |
| `circle(radius_cm, blocking=True)` | Positive radius = CCW, negative = CW |
| `vertical_circle(radius_cm, blocking=True)` | Requires altitude ≥ 0.35m |
| `flip(direction)` / `spin(rotations)` / `bounce(frequency, height_cm)` | Stunts — probably not useful for us |

**Speed control on `move()` / `move_to()`** uses `VelocityLevel` enum:
- `SLOW`, `MEDIUM`, `ZOOM` (default, 100), `TURBO`
- This is the **P-gain** for the position controller, NOT a velocity cap

### 5.4 Continuous control (joystick / closed-loop)

These give you simultaneous xyz+yaw — discrete movement can't.

| Method | Notes |
|---|---|
| `send_manual_control(forward, right, up, rotate)` | Single 50ms frame, values in [-1.0, +1.0]. Call at ~20Hz |
| `manual_fly(duration_sec, forward, right, up, rotate, rate_hz=20, on_frame=None)` | Auto-loop wrapper for the above |
| `stop_manual_control()` | Send zero inputs to halt |
| `send_app_heartbeat(user_mode=1)` | Aerial mode heartbeat. Auto-called by `manual_fly()` |
| `set_app_mode(1)` | **CALL BEFORE TAKEOFF if you want to use manual control** |
| `set_velocity_level(level_cms, blocking=True)` | RC velocity cap (100/200/300 cm/s) for manual control only |
| `set_yaw_rate_level(level)` | RC yaw rate cap |
| `create_flight_controller(config=None) → ManualFlightController` | **PD controller using MANUAL_CONTROL under the hood. Default 20Hz** |

`ManualFlightController` usage:
```python
ctrl = drone.create_flight_controller()
ctrl.configure(kp_xy=2.5, position_tolerance_cm=3.0)
result = ctrl.fly_to(x=100, y=200, z=120, yaw=90)
# or manual loop:
ctrl.set_target(x=50, y=50, z=100, yaw=180)
while not ctrl.has_converged():
    ctrl.update(); time.sleep(0.05)
ctrl.stop()
```

This is what we'll probably use for non-trivial mission paths. Default gains: `kp_xy=2.0, kd_xy=0.5, kp_z=3.0, kd_z=0.8, kp_yaw=5.0, kd_yaw=1.0, 20Hz`.

### 5.5 Telemetry (read whenever)

| Method | Returns | Notes |
|---|---|---|
| `get_state() → DroneState` | Full snapshot (position, orientation, battery, obstacles) | Cheap to call |
| `get_position() → Vector3` | (x, y, z) cm | Absolute if QR loc enabled |
| `get_orientation() → Orientation` | (yaw, pitch, roll) degrees | |
| `get_battery() → int` | 0-100 | Poll periodically for safety |
| `get_altitude() → float` | ToF altitude cm | |
| `get_velocity() → Vector3` | cm/s | |
| `get_acceleration() → Vector3` | cm/s² | |
| `get_obstacles() → Obstacles` | Which IR/ToF directions are blocked | Replaces our depth-sector wall-follow |
| `get_flight_data() → FlightData` | Everything in one object | Use this for logging |
| `get_drone_id() → int|None` | Drone hardware ID | Useful in swarm to identify which physical unit |

Raises `TelemetryUnavailable` if no data yet.

### 5.6 Built-in vision (saves us writing OpenCV)

| Method | Notes |
|---|---|
| `recognize_target(target)` | On-board AI for digit (0-9), arrow (L/R/U/D), letter (A-Z via ASCII), END_TASK marker. Returns `AIResult` |
| `recognize_qr(qr_id, mode=VisionMode.OPTICAL_FLOW, timeout=10.0)` | Finds + **aligns** drone to QR code |
| `track_qr(qr_id, duration, mode=VisionMode.OPTICAL_FLOW)` | Tracks QR for N seconds |
| `detect_qr(qr_id, mode=VisionMode.OPTICAL_FLOW)` | Detects QR + returns position, no alignment. Cheaper than recognize_qr |
| `get_color(mode=1) → ColorResult` | Dominant colour |
| `follow_line(distance_cm, line_color=LineColor.BLACK)` | Follows a coloured line on the ground using optical flow camera |

VisionMode: `OPTICAL_FLOW` (down-facing camera) or `FRONT_CAMERA` (forward-facing).

**For ArUco / AprilTag** — the SDK doesn't have built-in support. Use our own OpenCV pipeline against the video stream (see §5.10).

### 5.7 Camera + gimbal

| Method | Notes |
|---|---|
| `set_camera_angle(mode, angle=0)` | `CameraPitchMode.DOWN_ABSOLUTE` + `angle=45` tilts down 45° |
| `set_video_stream(enabled)` | Turns RTP stream on/off. **Required before take_photo** |
| `set_video_resolution(resolution)` | `VideoResolution.LOW` = 640x480 (AI mode), `MEDIUM` = 720p, `HIGH` = 1080p |
| `set_video(recording)` | Records to drone SD |
| `take_photo(download=True, save_path=None)` | Captures + optionally downloads. Requires `set_video_stream(True)` first |
| `flip_video()` | Flips orientation (if camera is mounted upside-down) |
| `set_anti_flicker(hz_50=True)` | 50Hz for Asia/EU, 60Hz for US |

**Important:** for our use case set `VideoResolution.LOW` before enabling RTP — it keeps QR detection rate up (otherwise QR drops to 5Hz when RTP is on).

### 5.8 Video stream pipeline (frame callbacks)

The killer feature. Once a video stream is started, you add callbacks that process each frame:

```python
from pyhulax.video import VideoStream, VideoDisplay, YOLODetector, DrawDetections, VideoRecorder

stream = drone.start_video_stream(display=False, web_server=True)
detector = YOLODetector(model_path="models/best.pt", confidence=0.5)
recorder = VideoRecorder("output.mp4", draw_detections=True)

stream.add_callback(detector)          # writes detections into frame.metadata
stream.add_callback(DrawDetections())  # renders boxes on the frame
stream.add_callback(recorder)          # saves to disk

stream.start()
stream.wait()                          # blocks until interrupted
stream.stop()
```

Custom callbacks just need `__call__(frame) → Frame|None`. Return `None` to drop a frame.

Built-in detectors:
- `ONNXDetector(model_path, class_names, confidence)` — generic ONNX
- `YOLODetector(model_path, confidence)` — Ultralytics YOLO
- `YOLOSegmentDetector` — segmentation variant
- `BaseDetector` — subclass for custom

Filters/helpers:
- `DrawDetections` — bbox overlays
- `DetectionLogger` — log detections to file
- `FilterDetector` — drop frames with no detections
- `FrameCrop` — crop region of interest
- `SaveDetectionCrop` — save cropped detections as separate files

Streamers:
- `MJPEGStreamer` — browser-viewable
- `WebStreamServer` — full HTTP server

### 5.9 QR localization (the absolute-positioning trick)

```python
drone.set_qr_localization(enabled=True)
```

What changes:
- `get_position()` returns **absolute** coords in the QR mat coord system (not relative to takeoff)
- `move_to(x, y, z)` flies to **absolute** position on the QR mat
- `curve_to()` uses **absolute** target coords
- Enables `recognize_qr()`, `track_qr()`, QR-based precision landing
- **Required for accurate multi-drone formation flight**

If disabled (default), positions are relative to takeoff origin, tracked by optical flow (drifts).

**This is what we ask the org first.** If the semi-final arena has a QR mat, our mission planner becomes trivial — just `move_to(x, y, z)` for every waypoint with absolute coords.

### 5.10 Obstacle avoidance (built-in)

`set_barrier_mode(enabled=True)` enables on-board IR/ToF obstacle avoidance. Drone dodges things itself.

`set_avoidance_direction(direction, distance_cm, barrier_mask)` is a **conditional** move — drone moves in `direction` IF a sensor in `barrier_mask` reports an obstacle. Useful for "if blocked in front, strafe right":

```python
drone.set_avoidance_direction(Direction.LEFT, 30, BarrierMask.FRONT | BarrierMask.RIGHT)
```

`get_obstacles()` returns the current per-direction blocked state (Obstacles model).

### 5.11 Payload + LEDs (probably not needed but available)

- `set_electromagnet(on)` — magnet for pickup
- `set_clamp(is_open=True/False, angle=N)` — gripper, 0-180°
- `fire_laser(mode, frequency, ammo)` / `is_laser_hit()` — battle mode
- `set_led(LEDColor.RED)` / `set_led(LEDConfig.rgb(r,g,b, LEDMode.BLINK))` / `enable_led()` / `disable_led()`
- `set_rgb_brightness(level)`

Use LEDs for swarm status visualisation (green = OK, red = error, blinking = busy).

### 5.12 Media management

| Method | Notes |
|---|---|
| `list_photos(page=0) → list[MediaFile]` | Newest first |
| `list_videos()` / `list_logs()` | Same shape |
| `download_photo(photo, save_dir=None) → Path` | Single |
| `download_all_photos(save_dir=None) → list[Path]` | Bulk |
| `download_video(...)` / `download_log(...)` | Same shape |
| `delete_photo/video/log()` / `delete_all_*()` / `delete_all_media()` | Clean up between runs |
| `get_photo_url(photo) → str` | Direct HTTP url like `http://192.168.100.1:12346/picture/<filename>` |
| `get_storage_capacity()` | Check SD card space before long sessions |

### 5.13 WiFi tuning (for venue)

| Method | Notes |
|---|---|
| `set_wifi_band(band_5ghz=True)` | 5GHz less congested at venue |
| `set_wifi_power(high=True)` | High power = longer range, more interference |
| `set_wifi_channel(manual=True, channel_id=N)` | Pick a clear channel |
| `set_wifi_broadcast(enabled=False)` | Hide SSID |
| `set_wifi_ap_mode()` | Drone becomes AP (each drone its own network) |
| `set_wifi_mode(WiFiMode.XYZ, channel_id=N)` | Low-level |

### 5.14 System

`shutdown()`, `reboot()`, `sync_time()`, `get_firmware_version()`, `get_mcu_version()`, `set_parameters(velocity, yaw_rate, brightness, avoidance, battery_failsafe, fast_land)` (bulk setter for efficiency).

`set_operate_status(status)` — flagged as "formation flight coordination". Possibly relevant for swarm sync.

---

## 6. Configuration deep-dive

`DroneConfig` composes 9 sub-configs. All defaults below:

### NetworkConfig
- `drone_ip="192.168.100.1"`, `tcp_port=8888`, `udp_command_port=8085`
- `udp_status_port=8668`, `udp_optitrack_port=8688`, `rtp_base_port=9000`
- `web_port=5000`, `http_port=12346`

### ProtocolConfig
- `command_protocol="tcp"`, `serial_baudrate=921600`
- `mavlink_system_id=1`, `mavlink_component_id=2`, `mavlink_component_file_id=1`

### DronePhysicsConfig
- `drone_width_cm=18.93`, `drone_depth_cm=18.46`
- `min_altitude_cm=30.0`, `max_altitude_cm=200.0`

So the drone is ~19cm square, can hover from 30cm to 2m altitude.

### FlightConfig
- `default_takeoff_height_cm=80`, `default_flight_height_cm=100`
- `default_speed_cms=100` (1.0 m/s)
- `position_tolerance_cm=5.0`, `yaw_tolerance_deg=3.0`

### ControllerConfig (PD controller defaults)
- `kp_xy=2.0`, `kd_xy=0.5`
- `kp_z=3.0`, `kd_z=0.8`
- `kp_yaw=5.0`, `kd_yaw=1.0`
- `max_horizontal_output=800`, `max_vertical_output=600`, `max_yaw_output=500`
- `control_rate_hz=20.0`

### VideoConfig
- `timeout_sec=30.0`, `buffer_size=10`
- `jpeg_quality=80`, `max_fps=30.0`
- `detection_confidence=0.5`, `nms_iou_threshold=0.45`

### TimeoutConfig
- `command_timeout_sec=4.0`
- `tcp_connect_timeout_sec=5.0`, `tcp_recv_timeout_sec=1.0`, `udp_timeout_sec=1.0`
- `fly_to_timeout_sec=30.0`

### BatteryConfig
- `warning_threshold=15`, `critical_threshold=10`, `min_operational_threshold=20`

So the drone WILL refuse takeoff below 20%, warn at 15%, critical at 10%. Bake these into our pre-flight checks.

### MediaConfig
- `base_dir="media"`, `photo_dir/video_dir/log_dir = None` (defaults to `base_dir/<type>/`)

### Construction
Sparse overrides:
```python
from pyhulax import DroneConfig, NetworkConfig
config = DroneConfig(network=NetworkConfig(drone_ip="192.168.100.42"))
# all other fields use defaults
```

Pass to `DroneAPI(config=config)`. Single config object, predictable runtime behaviour.

---

## 7. Core types + models (`pyhulax.core`)

### Movement enums
- `Direction` — `FORWARD, BACK, LEFT, RIGHT, UP, DOWN`
- `Rotation` — for rotational direction
- `FlipDirection` — `FORWARD, BACK, LEFT, RIGHT`
- `VelocityLevel` — `SLOW, MEDIUM, ZOOM, TURBO` (P-gain for `move()`)
- `TakeoffFlags` — `NONE, RESET_YAW (1), WITH_LOAD (2)` (bitmask)

### LED + payload enums
- `LEDMode` — `CONSTANT, BLINK, BREATHING, ...`
- `LEDColor` — predefined `LEDColor.RED, BLUE, GREEN, ...`
- `LEDConfig` — `LEDConfig.rgb(r, g, b, mode=LEDMode.BLINK)`
- `ClampMode`, `ElectromagnetMode`, `LaserMode`

### Vision enums
- `VisionMode` — `OPTICAL_FLOW` (down camera), `FRONT_CAMERA`
- `AIRecognitionTarget` — `DIGIT_0` through `DIGIT_9`, `ARROW_LEFT/RIGHT/UP/DOWN`, `END_TASK`, plus integer 65-90 for letters
- `CameraMode`, `CameraPitchMode` — `UP_ABSOLUTE, DOWN_ABSOLUTE, CALIBRATE`
- `VideoMode`, `VideoResolution` — `HIGH (1080p), MEDIUM (720p), LOW (640x480)`
- `VideoStreamMode`, `QRLocalizationMode`

### Navigation enums
- `BarrierMode` — overall mode for `set_barrier_mode`
- `BarrierMask` — `FRONT, BACK, LEFT, RIGHT, UP, DOWN, HORIZONTAL, ALL` (bitmask)
- `LineColor` — `BLACK, WHITE`
- `LineFollowResult` — `FAILED (0), SUCCESS (1), INTERSECTION (2)`

### System enums
- `DroneStatus`, `CommandResult`, `MediaType`, `WiFiMode`

### Geometry + state models
- `Vector3(x, y, z)` — cm or cm/s depending on context
- `Orientation(yaw, pitch, roll)` — degrees
- `DroneState` — full snapshot: `position, orientation, battery_percent, obstacles, ...`
- `FlightData` — all sensor values: `position, velocity, orientation, altitude_tof, ...`
- `Obstacles` — per-direction obstacle flags (front/back/left/right/up/down)

### Vision result models
- `AIResult` — `success, position (Vector3), angle, qr_id, ...`
- `ColorResult` — RGB
- `MediaFile` — `name, size, date, ...`

### Exceptions
Base: `DroneError`
- `DroneConnectionError` — couldn't connect
- `CommandTimeout` — command didn't ACK
- `CommandRejected` — drone refused
- `NotReady` — drone not in valid state
- `LowBattery` — below threshold
- `TelemetryUnavailable` — no data yet
- `InvalidParameter`, `OperationInProgress`

---

## 8. Controller types (`pyhulax.control`)

Exports:
- `ManualFlightController` — the PD controller
- `ControllerConfig` — tunable gains
- `ControllerResult` — return type from `fly_to()`
- `FlightState` — internal state

`ManualFlightController.fly_to(x, y, z, yaw)` → `ControllerResult(success, error_position_cm, reason)`.

Manual loop pattern:
```python
ctrl.set_target(x=50, y=50, z=100, yaw=180)
while not ctrl.has_converged():
    ctrl.update()
    time.sleep(0.05)
ctrl.stop()
```

For semi-final this is probably overkill unless we want non-trivial trajectories. `move_to()` is simpler for waypoint nav.

---

## 9. Logging (`pyhulax.logging`)

Three logger families:

**`FileLoggerMiddleware`** — parsed MAVLink + state traffic, JSONL daily rotation (`logs/drone_YYYY-MM-DD.jsonl`). Enabled via `DroneAPI(enable_file_logging=True)`.

**`CommandLogger`** — outgoing API method calls. JSONL daily rotation (`logs/commands_YYYY-MM-DD.jsonl`). Enabled via `DroneAPI(enable_command_logging=True)`. Skips high-frequency getters (`get_position()` etc) to keep logs readable.

**`FlightLogger`** (interface) with backends:
- `SQLiteLogger("flights.db")` — sync, local
- `PostgresLogger(...)` — requires `[db]` extra

Usage:
```python
from pyhulax.logging import SQLiteLogger
logger = SQLiteLogger("flights.db")
drone = DroneAPI(flight_logger=logger)
# Or manually:
session_id = logger.start_session(drone_id=1, notes="Test run")
logger.log_telemetry(session_id, drone.get_flight_data())
logger.end_session(session_id)
```

For our purposes: enable file logging + command logging during dev (rich debug data), add SQLite flight logger if we want session-level analysis.

---

## 10. Comparison: pyhulax vs MAVSDK (what we knew vs what we know now)

| | MAVSDK (qualifier) | pyhulax (semi-final) |
|---|---|---|
| Style | Asyncio | Synchronous, blocking |
| Connection | UDP `udp://:14540` | TCP `tcp://drone_ip:8888` |
| Discovery | Single drone | Multi-drone via Dola broadcast |
| Coordinate frame | NED (north, east, down) in metres | x=right, y=forward, z=up in cm |
| Position estimation | EKF + GPS or VIO | Optical flow OR QR localization |
| Setpoint pumper needed | Yes (for offboard) | No, commands block |
| Manual control | Custom offboard loop | Built-in `manual_fly()` + `ManualFlightController` |
| Obstacle avoidance | We wrote our own (wall_following.py) | Built-in `set_barrier_mode()` |
| QR detection | We'd write OpenCV | Built-in `detect_qr()` / `recognize_qr()` |
| Object detection | We integrated YOLO ourselves | `pyhulax.video.YOLODetector` ready |
| Video stream | Gazebo gz.transport subscribe | `drone.start_video_stream()` + callback pipeline |
| Logging | We wrote run_summary.json | Built-in `FlightLogger` + `CommandLogger` |
| Battery failsafe | We'd write it | `enable_battery_failsafe()` |
| Gimbal | Fixed | `set_camera_angle(DOWN_ABSOLUTE, 45)` |

**Net:** pyhulax does ~70% of what we wrote from scratch in the qualifier. Our value-add in the semi-final is mostly the swarm orchestration layer + ArUco/Realsense integration.

---

## 11. Open questions for the org (file in `#support-ticket`)

These are SDK-specific gotchas we need org clarity on:

1. **Does the arena have a QR mat for `set_qr_localization()`?** If yes, mission planning becomes trivial absolute-coord waypoints.
2. **Is there OptiTrack/mocap at the venue?** Port 8688 (`udp_optitrack_port`) hints at it. If so, drones get external position fix.
3. **Drone WiFi mode at venue** — is each drone an AP, or do they connect to a shared SSID? Affects whether all drones share one IP space.
4. **`set_app_mode(1)` (Aerial) required for manual control** — does this conflict with formation/autonomous behaviour?
5. **`set_operate_status(status)`** — what values does this take for formation coordination?
6. **K's `best.pt` model** — does it just work with `pyhulax.video.YOLODetector` or do we need to convert to ONNX for `ONNXDetector`?
7. **Video resolution + QR rate tradeoff** — docs say enabling RTP drops QR to 5Hz. What rate do we get at `VideoResolution.LOW`?
8. **`fire_laser` + `is_laser_hit`** — anything in semi-final use this, or is it battle-mode only?

---

## 12. Reusable code patterns for `semifinal/controller.py`

### 12.1 Safe single-drone pattern
```python
from pyhulax import DroneAPI, DroneConfig, NetworkConfig
from pyhulax.core import LowBattery, NotReady, DroneConnectionError

def fly_one(ip: str):
    config = DroneConfig(network=NetworkConfig(drone_ip=ip))
    try:
        with DroneAPI(config=config) as drone:
            if not drone.robust_connect(verbose=True):
                return False
            drone.enable_battery_failsafe()
            drone.set_barrier_mode(enabled=True)
            drone.set_qr_localization(enabled=True)  # if arena has QR
            drone.set_camera_angle(CameraPitchMode.DOWN_ABSOLUTE, 45)
            drone.set_video_resolution(VideoResolution.LOW)
            try:
                drone.takeoff(height_cm=100)
                # ... mission ...
            finally:
                drone.land()
            return True
    except (DroneConnectionError, LowBattery, NotReady) as e:
        print(f"{ip}: {e}")
        return False
```

### 12.2 Swarm pattern (one thread per drone)
```python
import threading
from dola import Dola
from pyhulax import DroneAPI

def drone_thread(ip, plane_id, world_state):
    with DroneAPI() as drone:
        drone.connect(ip)
        # ... per-drone FSM ...

dola = Dola(); dola.start()
ips = dola.get_all_ips(listen_seconds=5)
dola.stop()

threads = [threading.Thread(target=drone_thread, args=(ip, pid, ws))
           for pid, ip in ips.items()]
for t in threads: t.start()
for t in threads: t.join()
```

### 12.3 Detection pipeline (drop in K's model)
```python
from pyhulax.video import YOLODetector, DrawDetections, DetectionLogger, VideoRecorder

stream = drone.start_video_stream(display=False, web_server=True)
stream.add_callback(YOLODetector("models/best.pt", confidence=0.5))
stream.add_callback(DrawDetections())
stream.add_callback(DetectionLogger("logs/detections.jsonl"))
stream.add_callback(VideoRecorder("output.mp4", draw_detections=True))
stream.start()
```

### 12.4 ArUco detection callback (custom, not built in)
```python
import cv2
from pyhulax.video import Frame

aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
aruco_det = cv2.aruco.ArucoDetector(aruco_dict, cv2.aruco.DetectorParameters())

def aruco_callback(frame: Frame) -> Frame:
    gray = cv2.cvtColor(frame.image, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = aruco_det.detectMarkers(gray)
    if ids is not None:
        cv2.aruco.drawDetectedMarkers(frame.image, corners, ids)
        frame.metadata["aruco_ids"] = ids.flatten().tolist()
        frame.metadata["aruco_corners"] = [c.tolist() for c in corners]
    return frame

stream.add_callback(aruco_callback)
```

### 12.5 QR-localised waypoint mission
```python
WAYPOINTS = [(100, 100, 100), (200, 100, 100), (200, 200, 100), (100, 200, 100)]

drone.set_qr_localization(enabled=True)
drone.takeoff(height_cm=100)
for x, y, z in WAYPOINTS:
    drone.move_to(x, y, z, speed=VelocityLevel.ZOOM)
    drone.hover(duration_seconds=1.0)
    # detection happens via stream callbacks, no per-waypoint work needed
drone.land()
```

### 12.6 Closed-loop control with simultaneous yaw
```python
ctrl = drone.create_flight_controller()
result = ctrl.fly_to(x=150, y=200, z=100, yaw=45)
print(f"Arrived: {result.success}, error: {result.error_position_cm}cm")
```

---

## 13. Risks + mitigations (SDK-specific)

| Risk | Mitigation |
|---|---|
| Blocking API stalls swarm if one drone hangs | Each drone in its own thread. Use `blocking=False` and poll if needed. Per-drone timeouts |
| QR localization not enabled → drift | Always `set_qr_localization(True)` at startup if arena supports it |
| RTP video stream drops QR rate to 5Hz | Use `VideoResolution.LOW` before enabling RTP |
| `set_app_mode(1)` forgotten → manual control silently no-ops | Always set before takeoff in any script using manual_fly |
| Battery 19% rejects takeoff (`min_operational_threshold=20`) | Pre-flight check, swap battery |
| `set_video_stream(True)` forgotten → `take_photo` fails | Always enable stream early |
| All drones default to `192.168.100.1` if not configured per-unit | Use Dola discovery to get real IPs, don't rely on default |
| WiFi congestion at venue (20+ teams' drones) | `set_wifi_band(5ghz=True)`, `set_wifi_channel(manual=True, channel_id=…)`, reduce video resolution |
| Drone disconnects mid-flight | Battery failsafe + try/finally land + reconnect retry loop |

---

## 14. Action items derived from this analysis

1. ✅ Mirror docs offline (done)
2. ⏳ K: install `pyhulax` on a laptop, run `quick_start` against one drone, verify connection
3. ⏳ Z: write `semifinal/controller.py` using the Swarm + Detection patterns in §12
4. ⏳ Test if K's `best.pt` plugs into `YOLODetector` cleanly (no ONNX conversion needed)
5. ⏳ Wait for org clarification on QR mat presence — drives whole architecture
6. ⏳ Wait for org's `pyrealsense2` learning material — fuses with Hula video stream for depth-aware detection
7. ⏳ Update `semifinal/README.md` §6 (open questions) with the 8 SDK-specific items in §11 above

---

*Sources: all 18 mirrored pages at [`semifinal/docs/pyhulax/`](pyhulax/). Last analysed: 2026-06-03.*
*Refresh by re-running [`semifinal/docs/_mirror_pyhulax.py`](docs/_mirror_pyhulax.py) and re-reading.*

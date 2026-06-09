# mapping_drone

Challenge 1 (Reconnaissance) deliverable for BrainHack 2026 RoboVerse Final
Challenge, University category. Marina Bay Sands Expo, Level 4, 10-11 June 2026.

## Purpose

A mapping drone surveys the arena from above, builds a top-down depth /
occupancy grid, detects every ArUco landing-pad marker it sees, fuses each
marker into world-frame coordinates, and reports per-pad validity. All
artifacts are written to a timestamped run directory so the judges (and us)
have a single folder to inspect after the run.

Concretely, every flight produces:

- A judge-readable `STATUS.txt` updated every 5 s during flight.
- A machine-readable `run_summary.json` with full timing, sightings, pose log.
- `top_down.png` + `top_down.npy` of the occupancy grid with pads marked.
- `landing_pads.json` listing every unique ArUco ID with world coords + validity.
- `markers/marker_<id>_<seq>.jpg` bbox-overlaid frames of each sighting.
- `log.txt` controller log (includes the active validity rule line — see below).

## Architecture

One module per concern. Every module honours the interface contract in the
top-level project description so mocks and real adapters are drop-in.

| Module          | Responsibility                                                                 |
| --------------- | ------------------------------------------------------------------------------ |
| `uwb.py`        | UWB adapter. Real impl subs to ROS2 `uwb_tag` PoseStamped; mock is programmable. |
| `realsense.py`  | RealSense adapter. Real impl wraps `pyrealsense2`; mock synthesises depth+RGB. |
| `mapping.py`    | `ArucoDetector`, `OccupancyGrid`, `camera_to_world` helper.                    |
| `validity.py`   | `decide_landing_validity(id)` + `describe_rule()` (see below).                 |
| `run_writer.py` | `RunWriter` owns the run directory and all output files.                       |
| `controller.py` | `main()` — argparse, asyncio loop, MAVSDK velocity controller, integration.    |

Flow per loop iteration (10 Hz):

1. Pull latest UWB north/east + PX4 NED `down_m` → drone pose.
2. Grab a `RealsenseFrame` (color + aligned depth + intrinsics).
3. `ArucoDetector.detect_in_frame` → list of (id, center, bbox).
4. For each detection: depth at center → `deproject_pixel_to_camera_xyz` →
   `camera_to_world` using drone pose + gimbal pitch → record sighting.
5. `OccupancyGrid.integrate` the depth frame for the top-down map.
6. Step the waypoint P-controller (matches `kolomee.py` defaults).
7. Every 5 s: `RunWriter.write_status`.

### Coordinate-frame callout: PX4 NED `down_m` vs world Up

```
+-----------------------------------------------------------------------+
|  IMPORTANT — sign of vertical axis                                    |
|                                                                       |
|  PX4 telemetry delivers altitude as `down_m` in the NED frame:        |
|      pvn = await drone.telemetry.position_velocity_ned()              |
|      down_m = pvn.position.down_m   # NESTED, matches kolomee.py      |
|                                                                       |
|  In NED, `down_m` is NEGATIVE when the drone is airborne              |
|  (e.g. at 1.5 m altitude, down_m == -1.5).                            |
|                                                                       |
|  The mapping pipeline works in the world ENU frame where U (Up) is    |
|  POSITIVE when airborne. The conversion is a simple negation:         |
|      alt_up_m = -down_m                                               |
|                                                                       |
|  WHERE THIS MATTERS:                                                  |
|    * `OccupancyGrid.integrate(frame, pose, gimbal_pitch)` performs    |
|      the negation internally when projecting depth pixels to world    |
|      coordinates. Callers pass `down_m` straight through inside       |
|      `pose`.                                                          |
|    * Any DIRECT caller of `camera_to_world(...)` MUST pass            |
|      `drone_alt_m` as Up (positive airborne). The controller already  |
|      does this via `-self.state.drone_down`.                          |
|                                                                       |
|  If you ever see landing pads plotted UNDER the ground plane or       |
|  altitudes that decrease as the drone climbs, you have almost         |
|  certainly forgotten this negation.                                   |
+-----------------------------------------------------------------------+
```

Yaw follows MAVSDK convention (degrees clockwise from north) and comes from
`telemetry.attitude_euler().yaw_deg` — same pattern as kolomee.py's
`attitude_task`.

## Install

The drone (Ubuntu 22.04 + ROS2 + OpenCV pre-installed) only needs the Python
deps. For laptop dev with mocks you do **not** need ROS2 or `pyrealsense2`.

Drone (full real run):

```
pip install pyrealsense2 opencv-contrib-python numpy mavsdk
# ROS2 + rclpy come pre-installed in the org image; do NOT pip-install rclpy.
```

Laptop dev (mocks only):

```
pip install opencv-contrib-python numpy
# mavsdk + pyrealsense2 + rclpy are optional — modules degrade gracefully.
```

`opencv-contrib-python` (not `opencv-python`) is required for the
`cv2.aruco` module.

## Run modes

```
python -m mapping_drone.controller [flags]
```

| Flag                  | Meaning                                                                       |
| --------------------- | ----------------------------------------------------------------------------- |
| `--real`              | Real UWB + real MAVSDK + real RealSense. Default at the venue.                |
| `--mock-uwb`          | Use programmable mock UWB. Skips ROS2 import.                                 |
| `--mock-mavsdk`       | Mock flight controller. No serial port required.                              |
| `--mock-realsense`    | Synthetic depth + RGB frames. No camera required.                             |
| `--mock-all`          | All three mocks. Pure laptop run, no hardware.                                |
| `--waypoints PATH`    | JSON list of `[n_m, e_m, alt_m]`. Default = 4-pt demo square.                 |
| `--gimbal-pitch DEG`  | Gimbal tilt; `-90` = straight down (DEFAULT, canonical down-facing mapping).  |
| `--aruco-dict NAME`   | ArUco/AprilTag dictionary name (e.g. `6X6_250` [default], `4X4_50`, `APRILTAG_36h11`). Case-insensitive, optional `DICT_` prefix. See below. |
| `--max-flight-time-s` | Hard cap before forced land. Default `240` s.                                 |
| `--mavsdk-address ADDR` | MAVSDK system address (single). Default `serial:///dev/ttyS6:921600`.       |
| `--mavsdk-addresses A,B,C` | Comma-separated fallback list; tried in order with 5 s per-address connect timeout. Wins over `--mavsdk-address` when both present. See below. |
| `--runs-dir DIR`      | Parent directory for `run_<ts>` output dirs. Default `mapping_drone/runs` (relative to CWD). |
| `--log-level`         | `INFO` (default) or `DEBUG`.                                                  |

### `--gimbal-pitch`

The mapping drone is configured for top-down survey: the gimbal default is
`-90` degrees (straight down). The `camera_to_world` and
`OccupancyGrid.integrate` helpers were derived under this assumption (see
`generateTopDown.py` for the canonical down-facing camera frame: Z forward,
X right, Y down). Override only if you are doing an oblique pass — most of
the occupancy-grid maths assumes a nadir view.

### `--aruco-dict`

Selects which OpenCV ArUco/AprilTag dictionary the detector tries against
incoming frames. Default is `6X6_250` (i.e. `cv2.aruco.DICT_6X6_250`) for
prototyping; the actual dictionary will be announced by org Day-1 and can
be overridden via `--aruco-dict` at runtime (case-insensitive, any of the
20 supported). Per the org Discord (2026-06-06 21:32):

> ArUco markers are 20cm x 20cm. Exact dictionary will be announced
> Day-1.

The same markers sit next to both Challenge 1 and Challenge 2 (Hula)
landing pads, so the mapping drone's detector has to cope with whatever
size/count combination drops on the day.

Accepted names (20 total — 16 ArUco sizes + 4 AprilTag variants), all
keyed in `mapping._ARUCO_DICTS`:

- ArUco 4x4: `4X4_50`, `4X4_100`, `4X4_250`, `4X4_1000`
- ArUco 5x5: `5X5_50`, `5X5_100`, `5X5_250`, `5X5_1000`
- ArUco 6x6: `6X6_50`, `6X6_100`, `6X6_250` (default), `6X6_1000`
- ArUco 7x7: `7X7_50`, `7X7_100`, `7X7_250`, `7X7_1000`
- AprilTag: `APRILTAG_16h5`, `APRILTAG_25h9`, `APRILTAG_36h10`, `APRILTAG_36h11`

The lookup is case-insensitive and tolerates an optional `DICT_` prefix,
so `6x6_250`, `DICT_6X6_250`, `dict_apriltag_36h11`, and
`APRILTAG_36H11` all resolve to the same dictionary. AprilTag suffixes
are internally normalised to the lowercase-`h` spelling OpenCV uses
(`36h11`, not `36H11`) — pass them in any case, the detector reconciles.
Unknown names raise `ValueError` with the full list of 20 accepted keys
in the message.

Examples:

```
# Laptop smoke test, no hardware (uses default -90 gimbal pitch)
python -m mapping_drone.controller --mock-all --log-level DEBUG

# Drone bench test with mock flight + real camera
python -m mapping_drone.controller --mock-uwb --mock-mavsdk

# Real run (gimbal pitch defaults to -90; shown explicitly for clarity)
python -m mapping_drone.controller --real --gimbal-pitch -90 --waypoints arena.json

# Real run with a different printed-marker dictionary
python -m mapping_drone.controller --real --aruco-dict 5X5_250 --waypoints arena.json
```

## Output artifacts

Everything lands under:

```
<cwd>/mapping_drone/runs/run_<YYYYMMDD_HHMMSS>/
  STATUS.txt              # plaintext, refreshed every 5 s
  run_summary.json        # full machine-readable record
  top_down.png            # final occupancy grid visualisation
  top_down.npy            # raw grid array
  landing_pads.json       # unique pads + world coords + validity
  log.txt                 # controller log
  markers/
    marker_<id>_<seq>.jpg
```

Note: `--runs-dir` defaults to `mapping_drone/runs` (relative to the
directory you launch from). On the drone we launch from inside
`semifinal/`, so artifacts land in `semifinal/mapping_drone/runs/...`. If
you launch from elsewhere, pass `--runs-dir <abs-path>`.

`STATUS.txt` is the file to hand a judge mid-flight: state, seconds airborne,
pose, sightings so far, unique pad list with validity, battery percent.

## Validity rule

`validity.decide_landing_validity(aruco_id)` is currently a **placeholder**:
even IDs are valid, odd IDs are invalid. Org has not published the actual
rule.

When org publishes it, replace **only** the body of that function. The rest
of the pipeline already records every ID, image, and world position
regardless, so no other code needs to change.

### Startup banner: `describe_rule()`

`validity.describe_rule()` returns a one-line human-readable string naming
the active rule and whether it came from the default or from the env
override. The controller logs it at startup so the run's `log.txt` always
records exactly which classification was applied. Look for a line like:

```
INFO mapping_drone.controller: current validity rule: even (default) — even ArUco IDs valid, odd IDs invalid (PLACEHOLDER — org has not published the real rule)
```

If you ever doubt which rule a past run used, `grep "current validity rule"
log.txt` in that run directory.

### Env-var override: `MAPPING_DRONE_VALIDITY`

You can swap the active rule at startup without touching code by setting the
`MAPPING_DRONE_VALIDITY` environment variable before launching the
controller. Accepted values (case-insensitive):

| Value          | Meaning                                                |
| -------------- | ------------------------------------------------------ |
| `even`         | Even ArUco IDs valid, odd IDs invalid (DEFAULT).       |
| `odd`          | Odd ArUco IDs valid, even IDs invalid.                 |
| `all_valid`    | Every detected landing pad classified valid.           |
| `all_invalid`  | Every detected landing pad classified invalid.        |
| `id_below_50`  | IDs < 50 valid, IDs >= 50 invalid.                     |

Any other value falls back to `even` and logs a warning.

Examples:

```
# Force every detected pad to be reported valid (useful for sanity-checking
# that detection itself is working in the field):
MAPPING_DRONE_VALIDITY=all_valid python -m mapping_drone.controller --real

# Force every detection invalid (useful for a dry pass that only exercises
# mapping, not landing selection):
MAPPING_DRONE_VALIDITY=all_invalid python -m mapping_drone.controller --real

# If org announces "ID >= 50 are obstacles, ID < 50 are landing pads",
# flip to that rule with one shell variable:
MAPPING_DRONE_VALIDITY=id_below_50 python -m mapping_drone.controller --real

# Flip the parity of the placeholder:
MAPPING_DRONE_VALIDITY=odd python -m mapping_drone.controller --real

# Or be explicit about the default:
MAPPING_DRONE_VALIDITY=even python -m mapping_drone.controller --real
```

On Windows PowerShell the equivalent is:

```
$env:MAPPING_DRONE_VALIDITY = "all_valid"
python -m mapping_drone.controller --mock-all
```

## Where to integrate K's RKNN YOLO model later

The current `ArucoDetector` uses OpenCV's `cv2.aruco` only — it is robust
enough for the marker detection that Challenge 1 actually requires.

If we want K's RKNN YOLO model (yolo11n, ~50 FPS on the RK3588 NPU) on top
— e.g. for non-marker obstacle classification or as a secondary detector —
add a `--detector {aruco,yolo,both}` flag to `controller.py` and wire a new
class that mirrors the `ArucoDetector.detect_in_frame` signature. The
canonical RKNN post-processing already lives in
`learning_material_4_realsense/rknndecoder.py` and the depth-aware detect
loop in `getDepthAndDetect.py` — port from those, do not rewrite.

This is intentionally not built yet; Challenge 1 scoring rewards mapping +
marker reporting, not obstacle classification.

## Troubleshooting

**UWB not ready.**  `STATUS.txt` shows `state=WAIT_UWB`. The ROS2 `uwb_tag`
topic has not published yet. Check `ros2 topic echo /uwb_tag` on the drone.
The watchdog will hold position 1 s on intermittent loss and land if the
fix is gone for >5 s. For laptop dev use `--mock-uwb`.

**RealSense not detected.**  `RuntimeError: No device connected`. Replug
the USB-C cable (must be USB 3.x — the supplied cables are colour-coded).
`realsense-viewer` from `librealsense` confirms the device is alive. For
dev without hardware use `--mock-realsense`.

**RealSense `pipeline.start()` fails on every PROFILE_CANDIDATES entry,
all with "stream not supported" or similar around `rs.stream.color`.**
The drone is almost certainly a **D430 or D450** instead of a D435. Both
of those modules are depth-only (stereo IR + IR projector) and have NO
RGB sensor — every entry in `PROFILE_CANDIDATES` enables `rs.stream.color`,
so they all raise. Apply the `--use-ir-for-aruco` patch (sketch in
`semifinal/D430_RGB_RISK.md` and as a TODO block at the top of
`realsense.py`): stream `rs.stream.infrared` index 1 instead, turn the
emitter off so the projector dot pattern doesn't degrade ArUco, and
synthesise a 3-channel BGR from the IR grayscale so `ArucoDetector`
needs no edit. Day-1 morning fix, ~1-2h with hardware in hand. Org
confirmed the module family in BH2026ROBOVERSE Discord on
2026-06-08 12:18.

**MAVSDK serial port.**  Default is `serial:///dev/ttyS6:921600`. If you
see `MAVSDK: connection failed` check `dmesg | tail` for the actual ttyS
port and pass it via `--mavsdk-address` (e.g.
`--mavsdk-address serial:///dev/ttyAMA0:921600`). The org PX4 build
sometimes enumerates as `/dev/ttyAMA0` on a fresh boot.

### `--mavsdk-addresses` (Day-1 fallback walker)

When the PX4 enumerates as a different port between boots (we've observed
`ttyS6` / `ttyACM0` / `ttyUSB0` all on the same hardware over the course
of qualifier week) the single-address `--mavsdk-address` flag forces the
operator to know which port is live before launching the controller.

`--mavsdk-addresses` accepts a comma-separated list and tries each entry
in order with a 5 s per-address connect timeout, logging every attempt
and (on success) the line `connected via <addr>`. On all-failed it
raises `RuntimeError`. When BOTH flags are present `--mavsdk-addresses`
wins; the single-address path is preserved unchanged for back-compat
with existing scripts and the operator runbook.

The canonical Day-1 list is defined in `controller.py` as
`DAY1_MAVSDK_TRY_ORDER`:

```
serial:///dev/ttyS6:921600
serial:///dev/ttyACM0:115200
serial:///dev/ttyUSB0:57600
udp://:14540
udp://:14550
```

Three serial ports (covering every PX4 enumeration we've seen) plus the
two standard SITL UDP ports so a bench laptop running PX4 SITL or
jMAVSim also connects with the same one-liner.

Examples:

```
# Day-1 walk: try all 5 canonical addresses
python -m mapping_drone.controller --real \
    --mavsdk-addresses "serial:///dev/ttyS6:921600,serial:///dev/ttyACM0:115200,serial:///dev/ttyUSB0:57600,udp://:14540,udp://:14550"

# Two-address cycle (USB serial OR SITL UDP)
python -m mapping_drone.controller --real \
    --mavsdk-addresses "serial:///dev/ttyACM0:115200,udp://:14540"

# Original single-address behaviour (unchanged)
python -m mapping_drone.controller --real \
    --mavsdk-address serial:///dev/ttyAMA0:921600
```

Worst-case wall-clock when every address fails is ~25 s
(5 entries x 5 s timeout) — fits inside the operator's patience budget
between hitting Enter and deciding the PX4 is genuinely dead.

**NoMachine lag at the venue.**  The C2 Terminal pushes frames over wifi.
Run the controller in a `tmux` session so the flight survives a NoMachine
disconnect. STATUS.txt is updated on disk regardless of GUI — judges can
also `cat` it from a second terminal.

**Position-stuck watchdog fires.**  If the drone hasn't moved >0.3 m in
20 s after the grace period it lands. Usually means waypoints are unreachable
(altitude too low, UWB anchor outside expected volume) or P-gains too soft
for the current battery. Thresholds were tuned against qualifier-era mocks;
revalidate against finals waypoints if the arena geometry differs from our
2x2 m test square, and consider relaxing the 0.3 m / 20 s threshold if the
finals arena is smaller or UWB noise is higher.

**`cv2.aruco` not found.**  You installed `opencv-python` instead of
`opencv-contrib-python`. Uninstall both then reinstall contrib.

**Wrong ArUco dictionary.**  Detection rate suddenly drops to zero on
markers you printed yourself. The marker dictionary in `--aruco-dict` must
match the one used to generate the printed tags. Re-generate the tags from
`cv2.aruco.getPredefinedDictionary(cv2.aruco.<NAME>)` using the same name
you pass on the CLI.

The exact ArUco dictionary will be announced by org on Day-1. The default
is `DICT_6X6_250` for prototyping but can be overridden via `--aruco-dict`
at runtime (case-insensitive, any of the 20 supported). The full accepted
set — built programmatically by `mapping._build_aruco_dict_table()` and
exposed as `mapping.ALL_SUPPORTED_DICT_NAMES` — is all 16 ArUco
size/count combinations (`4X4`/`5X5`/`6X6`/`7X7` x `50`/`100`/`250`/`1000`)
plus the 4 AprilTag variants (`APRILTAG_16h5`, `APRILTAG_25h9`,
`APRILTAG_36h10`, `APRILTAG_36h11`). The detector normalises the
incoming name: case is ignored and a leading `DICT_` is stripped, so
`6x6_250`, `DICT_6X6_250`, and `APRILTAG_36H11` all resolve correctly.
Any name outside the 20 raises `ValueError` at construction time with the
full supported list in the error message — no silent fallback. (The old
9-entry hardcoded literal in `mapping._ARUCO_DICTS` has been retired; no
patch should be needed regardless of which dict org picks Day-1.)

Marker physical size is 20 cm x 20 cm. Per the org Discord
(2026-06-06 21:32):

> ArUco markers are 20cm x 20cm.

On the D435 RGB stream (640x480, ~70 deg HFOV) a 20 cm marker subtends
roughly a few hundred px at 1 m and drops below ~30 px at 5-6 m where
detection becomes unreliable. Pick mapping-drone flight altitude so the
markers stay well above that lower bound while still covering the survey
area. Same markers are placed near both Challenge 1 and Challenge 2
landing pads (org, 2026-06-06) — the mapping drone only needs to detect
them, not auto-land on them (the pyhulax landing-marker helper is a
separate mechanism on the Hula side).

**Landing pads appear under the floor / altitudes go negative airborne.**
You bypassed `OccupancyGrid.integrate` and called `camera_to_world`
directly with `down_m` instead of `-down_m`. See the coordinate-frame
callout above; the world frame is ENU (Up positive) and the negation is
the caller's responsibility.

**Validity column in `landing_pads.json` looks wrong.**  Check the startup
line `current validity rule: ...` in `log.txt`. The
`MAPPING_DRONE_VALIDITY` env var may have been set in the shell that
launched the controller; `unset MAPPING_DRONE_VALIDITY` (or
`Remove-Item Env:MAPPING_DRONE_VALIDITY` on PowerShell) restores the
default.

## Safety

Every command path includes:

- `try/finally` land + disarm
- MAVSDK battery failsafe subscription
- UWB-loss watchdog (hold 1 s, land at >5 s)
- `Ctrl-C` triggers the `emergency_land` coroutine
- Position-stuck watchdog (>0.3 m movement required per 20 s after grace)

## Style and conventions

Python 3.10+, asyncio main loop, type hints throughout, `dataclass` for
structured records, `logging` (not `print`), no emojis in code or filenames.
Module interfaces are frozen by the contract in the project root; do not
rename methods without updating every implementer.

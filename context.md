# RoboVerse 2026 — Project Context

**Last updated:** 2026-05-08 (maze generator built)
**User email:** e1408861@u.nus.edu
**Workspace root:** `/home/jugaad/zbstuff/hackerverse/`

---

## What this is

BrainHack 2026 RoboVerse Flight Challenge. Autonomous drone Qualifier on **22–23 May 2026** at Grand Court Hotel Orchard. Top 26 teams advance to Final on 10–11 June 2026 at Marina Bay Sands.

## Qualifier Spec (the hard constraints)

- **Arena:** 40 m × 40 m × 8 m indoor space port. Grid cells ≈ 4 m × 4 m (so 10×10). Irregular walls (not a rectangle — L-shaped sections per the brief image).
- **Drone:** `x500_vision` only. **GNSS-denied** — no GPS allowed. RGB cam + depth cam.
- **Time:** 10 minutes per run, multiple attempts allowed, **best score counts**. Code crashes do NOT stop the clock; only hardware faults do.
- **Targets:**
  - Yellow barrels: 50 pts each, **ground level only**.
  - Red barrels: 100 pts each, **never on ground** (placed in shelves / elevated platforms).
  - Toxic-sign barrels: distractors, **NOT** to be detected.
  - Each barrel counts only once.
- **Eligibility:** University category needs ≥1 yellow AND ≥1 red. Pre-U needs ≥1 of either.
- **Speed bonus:** 20 pts per 30 s under 5 min if all of one color found.
- **Submission:** image file with bbox (e.g. `detectx.jpg`) and/or live bbox display, ≥50% of barrel inside box. Both is allowed.
- **DQ rules:** any keyboard/joystick/gamepad/mouse manual control = disqualified.
- **Map note:** "Locations of objects and grid layout may be different. The actual map will be released 1 day before the Qualifier."
- **Logistics:** organizer's laptop available; bring code on USB; 15 min setup window before clock starts.

## Dev Environment

Two machines in play (decided 2026-05-08):

**Primary: Windows laptop with VMware**
- Guest: Ubuntu 22.04 inside VMware Workstation Pro (free for personal use via Broadcom).
- Path: workshop-provided **v3 VM image** (codes pre-installed) — see Discord link in [setup_guide.md](setup_guide.md) §2.1.
- User explicitly ruled out: dual-booting on the Windows laptop, running the VM on this Linux box, native install on Ubuntu 24.04.
- WSL2 considered and rejected; VMware is the official supported path.
- Setup: [setup_guide.md](setup_guide.md).

**Secondary: old computer being revived**
- Bare-metal native Ubuntu 22.04 install (no VM, no dual-boot — single-purpose machine).
- Workflow intent: use Windows VM for fast iteration (cheap snapshots); use this old box for native-perf testing (real GPU, no VM overhead).
- Setup: [setup_guide_part2.md](setup_guide_part2.md) — covers OS install, GPU drivers, bare-metal-specific gotchas (sleep, wifi, thermals), then jumps back to setup_guide.md §3.3 for the workshop install.

Both eventually run the same Option B steps and end up at the same `~/start_px4.sh` flow.

## Tech Stack

- Ubuntu 22.04 (24.04+ break Gazebo). VM provided.
- PX4 Autopilot SITL + Gazebo Harmonic
- MAVSDK Python (UDP `udpin://0.0.0.0:14540`)
- gz-transport (Python: `gz.transport13`, `gz.msgs10`) for sensor topics
- QGroundControl
- YOLO via Ultralytics (`yolov10n.pt` provided; barrel-tuned model "coming on Discord")
- OpenCV / numpy

## Critical Gotchas (record these — they will burn time if forgotten)

1. **EKF origin trick:** vision drone won't arm without an origin. Run `commander set_ekf_origin 47.397742 8.545594 488.0` in PX4 console, OR use "Set Estimator Origin" in QGC. After this, `is_global_position_ok` will *never* be True — comment that check out, keep `is_home_position_ok`. (LearningMaterial2 slide 14.)
2. **Modified `x500_vision/model.sdf` required.** Stock PX4 model lacks a depth camera. File at `optionB/x500_vision_model.sdf` (in this workspace).
3. **Offboard setpoint deadline = 500 ms.** Send a setpoint at least every 0.5 s or PX4 fails over. Never `time.sleep` (blocks asyncio → heartbeat dies). Always `await asyncio.sleep`.
4. **Coordinate frames:** camera (X-right, Y-down, Z-forward) ≠ body FRD ≠ world NED. Transform depends on yaw. The provided `AvoidancePlanner.py:camera_to_ned` does this. Most failures in this domain are frame-mismatch bugs.
5. **No native "arrived" callback.** Poll `drone.telemetry.position()` and compute distance manually.
6. **Red barrels are elevated.** A single-altitude lawnmower will miss them. Need vertical search.
7. **Detection dedup.** Same barrel seen from two angles must not double-count. Cluster by NED position.
8. **Toxic barrels look similar.** YOLO must have toxic-sign negatives in training set.
9. **Restart-resilience.** Wrap `asyncio.run` in try/except; persist visited cells / found barrels to disk; quick re-launch script.

## Workspace Layout

```
hackerverse/
├── README.md            — file manifest + reminders
├── context.md           — this file
├── learning/            — Lecture 1–3 PDFs + MP4s, Supplementary 1–2 PDFs + MP4s
├── challenge/           — Qualifier.pdf, WorkshopLaptopRequirements.docx, OptionB.docx
├── codes/Codes/         — 39 reference scripts mirrored from Drive (incl. yolov10n.pt, *_new.py updated copies)
├── optionB/             — start_px4.sh, roboverse.sdf, base6.glb, modified x500_vision model.sdf
└── pastproject/         — clone of github.com/hong-yiii/CDE2310_System_Design (CDE2310 TurtleBot3 frontier explorer)
```

**Intentionally NOT downloaded:** VM v3 image, VMware Fusion Pro installer (Mac-only), `vionode` (Drive perm error; not needed for Qualifier).

## Reference Code Map (RoboVerse-provided, in `codes/Codes/`)

| File | Purpose |
|---|---|
| `takeoff_and_land.py` | minimal sanity check |
| `basic_offboard.py` | offboard mode demo |
| `drone_control.py` / `drone_control_new.py` | wraps MAVSDK: arm, takeoff, land, send_position_setpoint, PID `rotate_to_yaw` |
| `depth_receiver.py` | thread-safe gz-transport subscriber → latest depth frame (float32 meters) |
| `AvoidancePlanner.py` | depth → histogram → next NED waypoint + `{blocked, environment, clearance}` info dict |
| `avoid.py` | main reactive loop. **Lines 139–143 are where the search strategy goes.** |
| `get_position_with_task.py` | async pose+yaw monitor with shared state pattern |
| `Detector.py` | YOLO encapsulation: `submit_image()` queues, saves annotated `.jpg` on detect |
| `UseDetectorExample.py` | how to wire Detector to gz-transport image topic |
| `top_down.py` | `depth_to_xy_map` — depth → top-down obstacle XY in camera frame |
| `GlobalMapper_new.py` | stitches `top_down` outputs into NED occupancy map |
| `RRTStarPlanner.py`, `VelocityPlanner.py`, `PointCloudPlanner.py` | additional planners |
| `keyboardcontrol.py` | manual control — for OpenVINS movement registration only, **do NOT use in challenge runs** |
| `Train_YOLO_Models.ipynb` | Colab to train custom barrel detector (Ultralytics YOLOv8) |
| `save_photo.py` | capture training images by subscribing to image topic |

Prefer `*_new.py` versions where they exist — they're the updated copies.

## Past Project (`pastproject/`)

CDE2310 ROS2/Nav2 TurtleBot3 maze explorer with thermal-source detection. Mission shape ≈ Qualifier (explore + detect + record). **No maze generator in the repo** — it's just navigation + detection.

Useful pieces to port (all in `pastproject/remote_laptop_src/nodes/global_controller.py`, 1608 lines):

- `detect_closest_frontier_outside` (line 746) — frontier search; better than lawnmower for irregular maps.
- `occ_callback` (line 499) — occupancy grid filtering: pad obstacles 3 cells, mark visited frontiers as free, skip cell-under-robot.
- `calculate_heat_world` (line 909) + `find_centers` (line 837) — angle+distance+pose → world coords + KMeans clustering. Direct analog for barrel detection dedup.
- `State` enum + `set_state` (lines 51, 1147) — clean FSM skeleton: `Init → Exploratory_Mapping → Goal_Navigation → ...`

Key lesson from their `improvements.md`: their "fully scan then cluster" strategy was time-inefficient. Post-mortem says: prefer reactive — confirm-and-record at first high-confidence detection. **For our 10-min cap, this matters.**

## Random Maze Generator — DONE (2026-05-08)

Built at `hackerverse/maze_gen/` — see its `README.md` for usage.

- **Algorithm:** polyomino wall placement (1×1, 2×1, 3×1, 4×1, L, T, 2×2 shapes with random rotation), BFS connectivity-checked after each placement, rejected if it disconnects. Shelf cells placed second, re-validated for ground-level connectivity.
- **Drone spawn:** central 2×2 (cells 4–5 on each axis) is kept clear so spawn at world (0, 0, 0) always lands on OPEN.
- **Walls:** 6 m tall procedural boxes (drone can technically fly over but it's hard); 4 perimeter walls enforce the 40×40 boundary.
- **Shelves:** 1.5 m × 1.5 m × 2 m boxes (smaller than the cell so drone can fly past); red barrels sit on top at z = 2.4.
- **Barrels:** flat-colored cylinders (yellow, red, orange-toxic). Not textured GLBs — visual fidelity is intentionally lower than the real `base6.glb` since the point is layout variety for testing the search controller, not perceptual realism. Train YOLO on real-world screenshots before the qualifier.
- **Output per run:** `maze_<seed>.sdf` (Gazebo Harmonic, drop-in for PX4 worlds dir, default `<world name='roboverse'>`), `maze_<seed>.json` (ground-truth barrel coords for offline scoring), `maze_<seed>.png` (matplotlib top-down preview).
- **Reproducible:** `--seed N` flag.

### Drop-in usage

```bash
cp hackerverse/maze_gen/output/maze_42.sdf ~/PX4-Autopilot/Tools/simulation/gz/worlds/
~/start_px4.sh   # pick x500_vision, then roboverse
```

To keep multiple worlds available, pass `--world-name maze42` and select that from the menu.

### Known limitations / future polish

- ASCII preview shows `[]` for shelves regardless of whether the elevated thing is a red barrel or a toxic distractor; PNG distinguishes them. Acceptable.
- Barrel materials are flat colors; if YOLO trained on these doesn't transfer to the baked `base6.glb` look, fine-tune on real-world screenshots.
- No "shelf with multiple cubbies" geometry like the brief's reference pillars — single-tier platform only. Could be added if needed.
- Walls are at 6 m; if testing absolute confinement, set `WALL_HEIGHT = 8.0` in `generate_maze.py`.

---

## Next Concrete Steps (when work resumes)

1. Stand up the PX4 SITL + Gazebo environment somewhere (VM or Option B host) and verify a generated maze loads. If it does, lock in the SDF format. If it errors, iterate on `emit_sdf()`.
2. Port frontier exploration + detection clustering from `pastproject/remote_laptop_src/nodes/global_controller.py` into a new search controller (likely a new file alongside `codes/Codes/avoid.py`, not modifying the reference).
3. Wire `Detector.py` into the loop with detection deduplication keyed on NED position.
4. Add 2-altitude search (low pass for yellow at ~1 m, high pass for red at ~3.5 m).
5. Robustness pass: try/except around `asyncio.run`, persist found-barrels to disk for restart-resume.
6. Train custom YOLO on screenshots from real `base6.glb` world (with toxic-sign barrels as negatives) once the official barrel-tuned model drops on Discord — compare and pick the better one.

# Challenge 1 — Mapping Drone — MASTER OP DOC

**This is the single doc to run the mapping drone on the day.** It is a
**decision tree**: do each step in order; if a step fails, follow its lettered
fallback (`→ 1a`, `→ 1b`) until it passes, then continue. Every command is
written out in full — copy/paste them exactly.

> Consolidates and supersedes: START_HERE_BEGINNER, DAY1_RUNBOOK, runbook,
> MAPPING_DRONE_RUN_GUIDE, CODEBASE_ANALYSIS_10JUN, HANDOFF_C1_TO_C2,
> ORG_TICKETS_DRAFT (see the bottom "Retired docs" list).

---

## 0. Golden rules (read once)

- **OFFBOARD only.** The org requires offboard-mode control (slide 10). Our code does this.
- **You launch from the floor and must NOT touch the drone in flight.** So any "survey" is floor-reading or an autonomous probe — never carrying it (see Step 3).
- **Isolate ROS2 in EVERY terminal:** `export ROS_LOCALHOST_ONLY=1`. Another team on the shared network (default `ROS_DOMAIN_ID=0`) is what made topics read empty last time. Our code now also forces this, but set it in the shell too.
- **One process per terminal.** `start_micro.sh` and `start_uwb.sh` each flood their terminal — give each its own.
- **Repo path varies per drone** — run `ls ~` first. Seen: `~/AD/semifinal`, `~/ad/semifinal`, `~/roboverse26/semifinal`.
- **Kill nlink with** `pkill -f px4_ros2_node` (NOT `nlink_ros2_node` — that matches nothing).
- The harmless `ImportError: sys.meta_path is None` on MAVSDK shutdown — **ignore it.**

## What we know (and what we DON'T)

| Fact | Source | Confidence |
|---|---|---|
| Arena 5.5 m (wide) × 11 m (long), corners (0,0)(0,11)(5.5,11)(5.5,0) | teammate | **confirm w/ marshal** |
| Fly with 0.7 m wall margin | team plan | our choice |
| Walls are see-through net (don't trust obstacle detection) | observed | medium |
| ArUco **DICT_7X7_1000**, marker IDs **11/45/51/67/101** | Discord/marshal | **confirm w/ marshal** |
| Marker is placed **BESIDE** the pad, not on it | official slides | high |
| UWB gives **North-East (x-y) only — no altitude** | official slides | high |
| Altitude must come from the FC (or depth) | derived | high |
| Control = offboard; NED position OR velocity+UWB ("more efficient") | official slides | high |
| Scoring = concept + **mapping speed** + valid/invalid **accuracy** (no numbers published) | official slides | high |
| MAVSDK on `serial:///dev/ttyS6:921600` works (arm/offboard/takeoff) | live test | high |
| `/uwb_tag` QoS is BEST_EFFORT/VOLATILE (matches our subscriber) | live test | high |
| Validity split (which IDs are valid vs invalid) | — | **ASK MARSHAL — edit configs/valid_ids_finals.json** |
| Arena→NED frame mapping (where (0,0) is, which way N points) | — | **MEASURE on the day (Step 3)** |

---

## Redundancy matrix — every subsystem has a fallback

We don't fully trust any single path, so each one has a backup. Most switch
**automatically**; a few you flip with a flag.

| Subsystem | Primary | Fallback(s) | How to switch |
|---|---|---|---|
| **Control transport** | MAVSDK on `ttyS6` (`moveit_mission`) | PX4-ROS2 / XRCE (`px4_mission`); then RC manual | run `px4_mission` if MAVSDK is dead (Step 5z) |
| **Pose (horizontal)** | FC fused NED | `/uwb_tag` arena frame → then hold-in-place | **automatic** with `--pose auto` (default) |
| **Altitude** | FC `down_m` | `--takeoff-alt` assumed value | automatic |
| **Camera / ArUco input** | RGB color (D435) | left-IR → synth-BGR (D450) | **automatic** color→IR fallback in `RealsenseNode` |
| **ArUco dictionary** | `7X7_1000` | `6X6_250` (both scanned every frame) | add more via `--aruco-dict a,b,c` |
| **Validity rule** | lookup `valid_ids_finals.json` | env rules (odd/even/all); else `None`=unknown | `MAPPING_DRONE_VALIDITY=...` |
| **Coverage / frame** | surveyed waypoints (`--pose uwb`, arena coords) | takeoff-relative NED (`--pose fc`); else tiny demo | `--waypoints-from-json` + `--pose` |
| **Safety** | watchdogs auto-land (battery/pose/stuck/setpoint) | Ctrl-C → land+disarm | RC **kill switch** (always in hand) |

`--pose auto` means: use the FC's fused NED; the instant it goes stale, fall
back to `/uwb_tag`; if both are gone, hold position. You get FC's DDS-immunity
**and** UWB's arena frame without choosing up front.

---

## STEP 0 — Pick a drone and fingerprint it

Drones are **not identical** (different camera, packages, paths). The moment you get one:

```bash
ls ~                                  # find the repo: AD / ad / roboverse26
cd ~/AD/semifinal                     # adjust to whatever you found
bash requirements.sh                  # verify+install deps; prints READY / NOT READY
bash tools/drone_fingerprint.sh       # ~30s, read-only, NEVER arms (hardware readiness)
```
`requirements.sh` checks/installs the Python + ROS deps and confirms the package
imports; `drone_fingerprint.sh` checks the hardware (camera, FC, serial, UWB).
Both are read-only re: flight (never arm).
Read the output:
- **Everything `ok`** → go to Step 1.
- **Any `MISSING` in section 2/3 (px4_msgs, nlink_parser, mavsdk, pyrealsense2)** → this drone has a setup problem, NOT interference → **`→ 0a`**.
- **Camera line shows `RGB=NO (D450?)`** → remember to add `--use-ir-for-aruco` in Steps 2/4/5.
- **No `MAVSDK CONNECTED` line** → FC link problem → **`→ 0b`**.

**→ 0a (missing package):** try another drone if available. If not: for `nlink_parser`/`px4_msgs` you need a `colcon build` in `~/ros2_ws` (ask the marshal — usually pre-built). For `mavsdk`/`pyrealsense2`: `pip install mavsdk` / install librealsense. Re-run the fingerprint.

**→ 0b (FC not reachable):** check the FC is powered and `/dev/ttyS6` exists (`ls -l /dev/ttyS6`). Power-cycle the FC. If still dead, the MAVSDK path is out — you'd fall back to `px4_mission` (Step 5, fallback 5z).

---

## STEP 1 — Bring up the sensors (3 terminals)

**Terminal A — micro-XRCE agent (bridges the FC, feeds UWB→EKF):**
```bash
export ROS_LOCALHOST_ONLY=1
pkill -f px4_ros2_node; pkill -f MicroXRCEAgent; sleep 2
bash ~/start_micro.sh
```
Leave it. Watch for it to show a session/connection.

**Terminal B — UWB / nlink:**
```bash
export ROS_LOCALHOST_ONLY=1
bash ~/start_uwb.sh
```
At the prompts type `0.0` then `0.0` (see **bottom-right calibration** below for the real values). Leave it; you should see `Started Rotated Nooploop PX4 ROS2 Node`.

**Terminal C — checks (this is your working terminal):**
```bash
export ROS_LOCALHOST_ONLY=1
cd ~/AD/semifinal
source ~/ros2_ws/install/setup.bash
ros2 topic list | grep -E "uwb|fmu"        # sanity: do the topics exist?
```
- Topics listed → go to Step 2.
- `ros2: command not found` or no topics → **`→ 1a`**.

**→ 1a (no ros2 / no topics):** you didn't source, or wrong workspace. `source /opt/ros/humble/setup.bash; source ~/ros2_ws/install/setup.bash`. Re-run `ros2 topic list`.

**→ 1b (`/uwb_tag` not listed):** nlink didn't start. In Terminal B check for errors; make sure you typed `0.0` (with the `.0`, not `0`). Confirm one and only one nlink: `ps aux | grep px4_ros2_node | grep -v grep` (should be 1). If duplicates: `pkill -f px4_ros2_node` and restart Terminal B.

### bottom-right calibration (what `start_uwb` is asking)
`start_uwb` asks for the **bottom-right corner** n/e. This re-zeros `/uwb_tag` so a known landmark becomes (0,0): it computes `final_north = raw_y − br_n`, `final_east = raw_x − br_e`. **Ask the marshal where the arena origin is.** To set it: place the drone at that landmark, read raw `/uwb_tag` (Step 3), then enter `br_n = raw_y`, `br_e = raw_x`. Entering `0.0/0.0` means "use raw UWB coords unchanged."

---

## STEP 2 — `--check` (connect + see pose, NEVER arms)

```bash
# Terminal C (sensors A+B still running)
export ROS_LOCALHOST_ONLY=1
cd ~/AD/semifinal
source ~/ros2_ws/install/setup.bash
python3 -m mapping_drone.moveit_mission --check
# D450 (no-RGB) camera? add:  --use-ir-for-aruco
```
Look for: `MAVSDK connected`, a pose line, and `VALIDITY of org IDs ... -> {11: True, 45: True, ...}`.
- All good → Step 3.
- `mavsdk ... not importable` or no MAVSDK connect → **`→ 2a`**.
- RealSense error → **`→ 2b`**.
- `VALIDITY ... -> {11: False, ...}` (all False) or all `None` → **`→ 2c`**.

**→ 2a (MAVSDK):** confirm `/dev/ttyS6` exists; try `python3 tools/mavsdk_probe.py`. If the FC needs a different port, pass `--mavsdk-address serial:///dev/ttyS6:921600` explicitly. If MAVSDK is truly unavailable, use the XRCE fallback (5z).

**→ 2b (camera):** `--check` tolerates a missing camera and continues. If you'll fly, the camera must work: check USB (`rs-enumerate-devices` — want USB **3.x**), replug into a blue USB3 port. If the camera has no RGB (D450), add `--use-ir-for-aruco`.

**→ 2c (validity):** the lookup table wasn't found or is wrong. You MUST be in `semifinal/` (the table is `configs/valid_ids_finals.json`). Confirm it: `cat configs/valid_ids_finals.json`. **Edit it with the marshal's real split** — move INVALID ids into `invalid_ids`. To force it explicitly: `export MAPPING_DRONE_VALIDITY=lookup MAPPING_DRONE_VALIDITY_LOOKUP=$PWD/configs/valid_ids_finals.json`.

---

## STEP 3 — Establish the flyable box (the frame)

You can't carry the drone, so we **measure the frame**, not guess it. **Decision:**

**Does `/uwb_tag` stream reliably now (with isolation on)?**
```bash
timeout 10 ros2 topic echo /uwb_tag --qos-reliability best_effort   # watch ~10s
```
- **Streams steadily → use the UWB/arena frame (cleanest).** Path **3-UWB**.
- **Empty/erratic → use the FC frame.** Path **3-FC**.

### Path 3-UWB (preferred when /uwb_tag is clean)
`/uwb_tag` gives the **absolute UWB/arena frame**, so the drone flies to absolute
coords no matter where it launches. ⚠️ **The origin (0,0) is the arena CENTRE, not a
corner** (observed 2026-06-11 — entering `0.0/0.0` at `start_uwb` leaves the anchor
centroid at the middle). So waypoints span **negative→positive**, centred on (0,0):
1. Read the floor position: `ros2 topic echo /uwb_tag --qos-reliability best_effort --once`. Note the value — near the centre it reads near (0,0); near a wall it reads ≈ ±2.75 (width) / ±5.5 (length).
2. **Confirm which axis is which** by moving the drone toward the long wall and watching which number grows — that axis is the 11 m length.
3. Waypoints are **centred** (0.7 m margin): width lanes at ≈ {−2.05, 0, +2.05}, sweep length −4.8 ↔ +4.8, at 2.5 m. Use `configs/waypoints_centered.json` (edit if the axes are swapped) with `--pose uwb` in Step 5.
4. No `br_n/br_e` shift is needed for a centred sweep — leave `start_uwb` at `0.0/0.0`. (Only calibrate `br` if the marshal wants a corner-origin convention.)

### Path 3-FC (when /uwb_tag is unreliable)
The FC's NED origin is the **takeoff point**, NED-North is the FC's fixed heading reference. So waypoints are **relative to where you launch**.
- Read the FC's idea of "north": `python3 /tmp/fc.py` won't move it; the cleanest is a **conservative autonomous frame-probe** (takeoff 1.2 m → +1.5 m N → pause → +1.5 m E → pause → land, logging position) to learn how NED lines up with the arena. *(This probe flight is the recommended next tool to add; until then, lay out a relative lawnmower from a corner launch and verify direction in Step 5's first low pass.)*
- Use `--pose fc` (default) in Step 5.

> **Why this matters:** the map is dead-reckoned onto whatever pose you feed it — wrong frame = wrong map and possible wall contact. Nail Step 3 before any real sweep.

---

## STEP 4 — `--nofly` ground test (camera + detect + map, NEVER arms)

Put a printed **7X7_1000** marker (id 11/45/51/67/101) in front of the camera.
```bash
export ROS_LOCALHOST_ONLY=1
cd ~/AD/semifinal
source ~/ros2_ws/install/setup.bash
python3 -m mapping_drone.moveit_mission --nofly --max-flight-time-s 60
#   add --use-ir-for-aruco for a D450 (no-RGB) camera
```
Watch for `sighting id=<one of 11/45/51/67/101> ... valid=True`.
- Sightings appear + `valid=True` for valid ids → Step 5.
- No sightings → **`→ 4a`**.
- Sightings but `valid=None`/wrong → **`→ 4b`** (= 2c: fix the lookup table).

**→ 4a (no detections):** wrong dict or no frames. Confirm the marker is 7X7_1000. Confirm frames flow (Step 2b). Lighting/focus — fill more of the frame with the marker.

Artifacts land in `mapping_drone/runs/run_<timestamp>/` — check `landing_pads.json` exists.

---

## STEP 5 — `--fly` (autonomous sweep) — the scored run

**Altitude:** the **cage ceiling (net) is 3.5 m**, so the default is **2.5 m** and the
code **hard-caps any altitude at 3.2 m** (the `--takeoff-alt` value, per-waypoint `z`,
and typos all clamp) — it will never fly into the net. Use **`--takeoff-alt 3.0`** for
the higher option. Trade-off: **higher = wider footprint (fewer lanes, faster) but
smaller markers**; **lower = sharper ArUco (better valid/invalid accuracy = points) but
more lanes**. D455 footprint ≈ `1.9·h × 1.1·h` (2.5 m ≈ 4.75×2.75 m; 3 m ≈ 5.7×3.3 m).

Pre-flight: battery charged, props clear, **RC kill-switch in hand**, marshal go.
```bash
export ROS_LOCALHOST_ONLY=1
cd ~/AD/semifinal
source ~/ros2_ws/install/setup.bash

# DEFAULT (recommended) — --pose auto (FC, auto-fallback to /uwb_tag) and the
# camera auto-falls back color->IR, so no camera flag is needed:
python3 -m mapping_drone.moveit_mission --fly \
    --waypoints-from-json configs/waypoints_surveyed.json \
    --takeoff-alt 2.5 --max-flight-time-s 420

# Force a single pose source if needed:
#   --pose uwb   (waypoints are ARENA coords, Path 3-UWB)
#   --pose fc    (waypoints are TAKEOFF-RELATIVE NED, Path 3-FC)
# Force IR camera (only if auto-detect picked wrong): --use-ir-for-aruco
```
Expected: connects → local position OK → arms → offboard → takeoff → flies waypoints (closed-loop) → scans at each → lands → disarms (only after `in_air=False`).

- Flies the pattern and lands cleanly → Step 6.
- "refusing to fly / no local position" → **`→ 5a`**.
- Flies but **not straight / drifts** → **`→ 5b`**.
- Camera stalls mid-flight → **`→ 5c`**.
- Aborts mid-flight ("SAFETY ABORT: …") → **`→ 5d`**.
- MAVSDK unavailable entirely → **`→ 5z`**.

**→ 5a (won't arm/fly):** the FC has no local position. Sensors (A+B) must be up so UWB feeds the EKF. Re-check `--check` shows `local position OK`. Don't fly without it.

**→ 5b (not straight / drift):** the pose feedback is wrong or in the wrong frame. If on `--pose uwb` and `/uwb_tag` is dropping, switch to `--pose fc`. If on `--pose fc`, your waypoints' frame doesn't match takeoff (re-do Step 3). Lower `--takeoff-alt` for tighter control. (The org sample flew "not straight" because it was open-loop; ours is closed-loop, so drift = bad pose, not the controller.)

**→ 5c (camera frame timeout):** our code tolerates dropped frames (won't crash like the org `imshow` sample). If frames stop entirely: USB power/bandwidth — ensure USB3, don't run other heavy processes. The mission keeps flying; you may just get a sparse map.

**→ 5d (safety abort):** read the reason — `battery <15%` (land, swap battery), `position fix stale` (pose source dropped — see 5b), `position-stuck` (offboard glitch — re-arm), `offboard setpoint failures` (link issue). The drone auto-lands; this is the watchdog doing its job.

**→ 5z (MAVSDK dead — XRCE fallback):** needs `px4_msgs` matching FC firmware (fingerprint Step 0).
```bash
python3 -m mapping_drone.px4_mission --fly --pose px4 \
    --waypoints-from-json configs/waypoints_surveyed.json --takeoff-alt 2.5
```
If you see "Fast CDR exception", `px4_msgs` is the wrong version — rebuild it against the FC firmware (ask marshal). Otherwise `--pose uwb --assumed-alt 4.0` for a grounded test only.

---

## STEP 6 — Retrieve artifacts (the deliverable)

```bash
ls -t mapping_drone/runs/ | head -1                       # newest run dir
ls mapping_drone/runs/run_<timestamp>/
```
You want: `top_down.png` / `top_down.npy` (the map), `landing_pads.json` (ids + world xyz + valid), per-marker images, `run_summary.json`. Copy them off via NoMachine/scp. **Remember the marker is *beside* the pad** — when reading results, associate each marker to its nearest pad square in the top-down map.

---

## Appendix A — every command in one place

```bash
# fingerprint a freshly-swapped drone
bash tools/drone_fingerprint.sh

# sensors (3 terminals, each: export ROS_LOCALHOST_ONLY=1 first)
pkill -f px4_ros2_node; pkill -f MicroXRCEAgent; sleep 2; bash ~/start_micro.sh   # A
bash ~/start_uwb.sh                                                              # B (0.0/0.0)
source ~/ros2_ws/install/setup.bash                                              # C

# check / nofly / fly
python3 -m mapping_drone.moveit_mission --check
python3 -m mapping_drone.moveit_mission --nofly --max-flight-time-s 60
python3 -m mapping_drone.moveit_mission --fly --waypoints-from-json configs/waypoints_surveyed.json --takeoff-alt 2.5   # --pose auto + auto-IR (default)
#   force a path:  --pose fc | --pose uwb   |   force IR cam: --use-ir-for-aruco
#   scan more dicts: --aruco-dict 7X7_1000,6X6_250,5X5_250

# survey the box (NOTE: corner-walk mode needs carrying — unusable; use floor read / probe per Step 3)
python3 tools/survey_box.py --margin 0.7 --lanes 3 --alt 4.0 --out configs/waypoints_surveyed.json

# diagnostics
timeout 10 ros2 topic echo /uwb_tag --qos-reliability best_effort
ros2 topic info -v /uwb_tag
python3 /tmp/fc.py            # read-only FC NED (no arm)

# XRCE fallback
python3 -m mapping_drone.px4_mission --fly --pose px4 --waypoints-from-json configs/waypoints_surveyed.json --takeoff-alt 2.5
```

## Appendix B — lawnmower layout (5.5 × 11 m, 0.7 m margin)
Usable interior ≈ 4.1 m (width) × 9.6 m (length), at **2.5 m** altitude (cage 3.5 m; lower alt = sharper markers but needs more lanes; D455 footprint ≈ 1.9·h × 1.1·h). **The UWB origin (0,0) is the arena CENTRE, not a corner** (see Step 3), so in the UWB frame the lanes are centred: e.g. 3 lanes at width ≈ {−2.05, 0, +2.05}, sweeping length −4.8 ↔ +4.8. `survey_box.py`/`waypoints_centered.json` produce this.

## Appendix C — confirm with the marshal on the day
1. **Validity split** — which marker IDs are valid vs invalid → edit `configs/valid_ids_finals.json`.
2. **Arena origin** for the `br_n/br_e` UWB calibration.
3. Arena dimensions (we assume 5.5 × 11 m).
4. ArUco dictionary + ID list (we assume 7X7_1000, 11/45/51/67/101).
5. Required output/deliverable format and any time limit.

---

## Retired / merged docs
Folded into this op doc (kept on disk for history, but **use this doc**):
START_HERE_BEGINNER.md, DAY1_RUNBOOK.md, runbook.md, MAPPING_DRONE_RUN_GUIDE.md,
CODEBASE_ANALYSIS_10JUN.md, HANDOFF_C1_TO_C2.md, ORG_TICKETS_DRAFT.md.
Kept as standalone references: finals_brief_extracted.md, DRONE_STACK_ANALYSIS.md,
SCORING_PLAYBOOK.md, D430_RGB_RISK.md, FINALS_PLAN.md, CONVOY_OPPONENT_ROLE.md (C2),
MAPPING_DRONE_SETUP_GUIDE.md, DAY1_SETUP_SEQUENCE.md, DAY1_POCKET_CARD.md.
Deleted as fully stale: semifinal_scrape.md (historical qualifier scrape).

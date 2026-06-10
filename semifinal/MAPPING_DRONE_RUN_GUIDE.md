# Mapping Drone — Run Guide (Non-Fly + Fly)

**The single authoritative procedure for Challenge 1 on the real drone.** Covers ground testing
(non-fly) and the autonomous scored run (fly). Reflects the code as of 2026-06-10 PM (post deep-review
fixes). Background: [`DRONE_STACK_ANALYSIS.md`](DRONE_STACK_ANALYSIS.md). Beginner version:
[`START_HERE_BEGINNER.md`](START_HERE_BEGINNER.md).

---

## 0. TL;DR (the commands, in order)

```bash
cd ~/AD/semifinal && git pull
source ~/ros2_ws/install/setup.bash
pkill -f MicroXRCEAgent; bash ~/start_micro.sh &     # FC <-> ROS2 bridge (gives the FC its UWB position)
sleep 4
bash ~/start_uwb.sh                                   # UWB -> /uwb_tag (enter br_n / br_e, e.g. 0.0 / 0.0)
# --- pick control path ---
python3 -m mapping_drone.moveit_mission --check       # MAVSDK on ttyS6 connects? -> use moveit (primary)
#   if MAVSDK times out -> use px4_mission instead (PX4-ROS2 fallback; needs the px4_msgs build)
# --- NON-FLY (no arm) ---
python3 -m mapping_drone.moveit_mission --nofly
# --- FLY (scored, after editing configs/valid_ids_finals.json + confirming waypoints) ---
MAPPING_DRONE_VALIDITY=lookup MAPPING_DRONE_VALIDITY_LOOKUP=configs/valid_ids_finals.json \
python3 -m mapping_drone.moveit_mission --fly \
  --waypoints-from-json configs/waypoints_10jun.json --takeoff-alt 4.0
```
`Ctrl-C` lands+disarms — **but keep a human on the RC kill switch** (see §8).

---

## 1. Two control paths — pick one with `--check`

| | **`moveit_mission`** (PRIMARY) | **`px4_mission`** (FALLBACK) |
|---|---|---|
| Transport | MAVSDK / MAVLink on `serial:///dev/ttyS6:921600` | PX4-ROS2 (micro-XRCE-DDS), `/fmu/*` |
| When | the org's official path (move_it4.py); use if `--check` connects MAVSDK on ttyS6 | use only if MAVSDK gets **no heartbeat** on ttyS6 |
| px4_msgs CDR issue | **immune** (uses MAVLink; FC gets UWB via the C++ nlink node) | **blocked** until you build matching px4_msgs (see §7) |
| Modes | `--check` / `--nofly` / `--fly` | `--check` / `--nofly` / `--fly` + `--pose px4\|uwb` |

Both share the same camera / UWB / ArUco / artifact code. **Decision rule: run `moveit_mission --check`; if MAVSDK
connects, fly `moveit_mission`. If it times out, fly `px4_mission`.**

Modes (both modules):
- **`--check`** — connect + print pose/status. Never arms. Confirms the link + UWB.
- **`--nofly`** — full camera + ArUco + map + judge artifacts, in place. **Never arms/moves.** Ground test, and the
  complete deliverable if the drone is flown manually.
- **`--fly`** — autonomous: arm → offboard → fly waypoints (scan each) → land → disarm.

---

## 2. One-time setup on the drone (every fresh boot)

```bash
cd ~/AD/semifinal
git pull                                              # latest code (the fixes)
source ~/ros2_ws/install/setup.bash                   # REQUIRED: loads px4_msgs / geometry_msgs
pkill -f MicroXRCEAgent; bash ~/start_micro.sh &      # ONE XRCE agent on /dev/ttyS1 — feeds UWB into the FC's EKF
sleep 4
bash ~/start_uwb.sh                                    # nlink: /uwb_tag (+ /fmu/in/vehicle_visual_odometry)
```
- Enter `br_n` / `br_e` at the `start_uwb.sh` prompt as **decimals** (`0.0` / `0.0` for raw, or the marshal's
  takeoff-corner values to make takeoff read 0,0).
- **Do NOT run `start_rs.sh`** — the mission opens the RealSense itself; the ROS2 node would fight it for the USB.
- The XRCE agent is needed even on the MAVSDK path: it's how the UWB position reaches the flight controller so it
  can hold offboard. `start_uwb.sh` runs in the foreground — leave it open; run the mission in another terminal.

Confirm UWB is live (a sourced terminal):
```bash
ros2 topic echo /uwb_tag --once --qos-reliability best_effort   # must print a pose with real numbers
```
No data → no UWB fix (you must be **in the arena** with anchors powered). UWB is unrelated to arming.

---

## 3. Config you MUST set before a scored run

1. **ArUco dict** — default is now `7X7_1000` (the org markers). Override only if the marshal announces different:
   `--aruco-dict <NAME>`.
2. **Validity** — edit [`configs/valid_ids_finals.json`](configs/valid_ids_finals.json): it ships with all five IDs
   (11/45/51/67/101) as **valid (placeholder)**. **Move the invalid ones into `invalid_ids` once the marshal
   announces the rule.** Launch with `MAPPING_DRONE_VALIDITY=lookup MAPPING_DRONE_VALIDITY_LOOKUP=configs/valid_ids_finals.json`.
   The mission **logs the classification of all five IDs at startup** — read that line; if it says all INVALID, stop.
3. **Waypoints** — [`configs/waypoints_10jun.json`](configs/waypoints_10jun.json) is a **template**: a serpentine
   sweep over a ~4.4 × 7.85 m rectangle at z = 4.0 m, format `[north, east, alt]`. **Verify it matches the real
   arena** (origin, orientation, size) using `--nofly` (§5) before flying. Each row's `alt` column is now honoured.

---

## 4. STEP A — Bring-up & gate (`--check`, never arms)

```bash
python3 -m mapping_drone.moveit_mission --check
```
- **MAVSDK connects** (`MAVSDK connected via serial:///dev/ttyS6:921600`) **and** the UWB pose prints with real,
  changing numbers when you move the drone → ✅ use `moveit_mission`. Proceed.
- **MAVSDK times out** → that drone is XRCE-only. Switch to the fallback:
  ```bash
  python3 -m mapping_drone.px4_mission --check --pose px4    # must show valid=True (needs px4_msgs build, §7)
  python3 -m mapping_drone.px4_mission --check --pose uwb    # /uwb_tag works regardless
  ```

---

## 5. STEP B — NON-FLY (`--nofly`) — full pipeline, drone stays grounded 🛑

Runs camera + ArUco + occupancy map + **all judge artifacts** using real UWB position, but **never arms or moves.**
This is your ground test AND the complete Challenge-1 deliverable if the drone is flown manually.

```bash
# org path (no MAVSDK needed for --nofly; just /uwb_tag + camera):
python3 -m mapping_drone.moveit_mission --nofly --max-flight-time-s 90
# XRCE fallback equivalent:
python3 -m mapping_drone.px4_mission --nofly --pose uwb --max-flight-time-s 90
```
- Point the camera **down** at the printed `7X7_1000` markers (hand-carry to simulate the sweep). Watch for
  `sighting id=… world=(…) valid=…`.
- **Verify the arena frame here:** move the drone north/east and confirm the reported pose increases the right way
  (North = `pose.y`, East = `pose.x`) and that detected `world` coords land near the known marker positions
  (id 11 ≈ N 4.4 / E 1.35, etc.). This is how you confirm the waypoint rectangle + the sign conventions before flying.
- Check the bundle:
  ```bash
  cat mapping_drone/runs/run_*/landing_pads.json     # IDs + world coords + valid/invalid
  ls  mapping_drone/runs/run_*/markers/              # one image per marker
  ls  mapping_drone/runs/run_*/                       # STATUS.txt, top_down.png/.npy, run_summary.json
  ```
- If every pad reads INVALID → you didn't set the validity rule (§3.2).

---

## 6. STEP C — FLY (`--fly`) — autonomous scored run ✈️

Only after `--check` and `--nofly` both look right, **with a human on the RC kill switch**, area clear.
**Treat the first `--fly` as a maiden flight: few waypoints, low, short — then the full sweep.**

```bash
MAPPING_DRONE_VALIDITY=lookup MAPPING_DRONE_VALIDITY_LOOKUP=configs/valid_ids_finals.json \
python3 -m mapping_drone.moveit_mission --fly \
  --waypoints-from-json configs/waypoints_10jun.json \
  --takeoff-alt 4.0 --aruco-dict 7X7_1000 --max-flight-time-s 420
```
Sequence the mission runs: connect MAVSDK → wait `is_local_position_ok` → arm → pre-stream setpoint → **offboard
start** → climb to `--takeoff-alt` → for each waypoint: velocity-profiled approach (UWB feedback) → hold + scan →
land → **disarm only after confirming `in_air=False`** (the airborne-disarm bug is fixed).

XRCE fallback (only if on the px4 path; forces `--pose px4`, needs the px4_msgs build):
```bash
MAPPING_DRONE_VALIDITY=lookup MAPPING_DRONE_VALIDITY_LOOKUP=configs/valid_ids_finals.json \
python3 -m mapping_drone.px4_mission --fly \
  --waypoints-from-json configs/waypoints_10jun.json --takeoff-alt 4.0 --aruco-dict 7X7_1000
```

**First-flight checklist before you hit Enter:**
- [ ] In the arena, `/uwb_tag` streaming, `--check` good.
- [ ] `--nofly` confirmed detection + correct N/E directions + sensible world coords.
- [ ] `configs/valid_ids_finals.json` edited to the marshal's real split (startup log not all-INVALID).
- [ ] Waypoints match the arena; first attempt trimmed to a few low waypoints.
- [ ] Camera is **D435** (RGB). A D450 (no RGB) detects nothing.
- [ ] Battery healthy; **RC kill switch in hand** (the auto battery/UWB-loss watchdogs are NOT yet in moveit/px4 — see §8).
- [ ] Run inside `tmux` so a NoMachine drop doesn't kill the flight.

---

## 7. px4_msgs fix (only for the px4_mission fallback)

`px4_mission --pose px4` / `--fly` needs the Python `px4_msgs` to match the flashed firmware, or `/fmu/*` throws a
"Fast CDR exception" and pose stays invalid. (`moveit_mission` does NOT need this — it uses MAVLink.) On the drone:
```bash
cd ~/ros2_ws/src && rm -rf px4_msgs
git clone --depth 1 --single-branch -b release/1.15 https://github.com/PX4/px4_msgs.git   # MATCH firmware (ver all)
cd ~/ros2_ws && colcon build --packages-select px4_msgs nlink_parser && source install/setup.bash
# verify: ros2 topic echo /fmu/out/vehicle_local_position --once --qos-reliability best_effort  (no CDR error)
```

---

## 8. Known gaps & safety (READ before flying)

- **No in-flight watchdogs yet** in `moveit_mission`/`px4_mission`: no automatic battery failsafe, no UWB-loss-abort,
  no position-stuck abort (legacy `controller.py` has these; not yet ported). **Mitigation: a human on the RC kill
  switch is mandatory.** Watch battery yourself.
- **Ctrl-C is slow** during takeoff/scan in `moveit_mission` (a few seconds). Do **not** rely on it — use RC override.
- **UWB-loss in flight**: `moveit_mission` holds position and retries indefinitely (armed). If UWB drops, take manual control.
- **Altitude**: world-Z / map heights use `--takeoff-alt` when UWB carries no z. Set `--takeoff-alt` to the real flight altitude.
- **First flight is untested in air** — both flight modules have flown only in mock. Be conservative.

---

## 9. Reading the judge artifacts

Everything lands in `mapping_drone/runs/run_<timestamp>/`:
- `landing_pads.json` — unique ArUco IDs + world coords + valid/invalid (the scored output).
- `top_down.png` + `top_down.npy` — occupancy / top-down depth map.
- `markers/marker_<id>_<seq>.jpg` — annotated image per sighting.
- `STATUS.txt` — live human-readable status (state, pose, sightings).
- `run_summary.json` — full machine-readable record.
- `log.txt` (controller path) / stdout — includes the active validity rule + the 5-ID classification line.

Copy the whole `run_<ts>/` dir off the drone to USB after every run (drones are shared; never overwrite).

---

## 10. Day-1 must-checks (cannot be fixed in code)
1. Firmware version (`ver all`) → matching `px4_msgs` branch (only if using px4_mission).
2. ArUco dict (pads vs robots) + the real **validity rule** + the valid/invalid IDs.
3. Camera model per handoff: **D435 (RGB) vs D450 (no RGB → zero detections; IR fallback is unimplemented).**
4. Arena dimensions / origin / compass alignment → set `br_n`/`br_e` + the waypoint rectangle.
5. Is autonomous offboard allowed + the altitude floor/ceiling (config wants 4.0 m).

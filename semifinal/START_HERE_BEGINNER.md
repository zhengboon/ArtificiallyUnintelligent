<!--OPDOC-BANNER-->
> ⚠️ **SUPERSEDED — to run the mapping drone use [OP_DOC.md](OP_DOC.md).** This file is kept for historical detail only; the live decision-tree runbook is OP_DOC.md.

# Start Here — Mapping Drone (Challenge 1), for a beginner

You don't need to understand the whole codebase. The code is **already written**. Your job is to
**run it in the right order** on the drone and read the results.

> **Big truth (read this once):** the organiser's official sample (`move_it4.py`, 10 Jun) flies the drone
> with **MAVSDK over `serial:///dev/ttyS6:921600`** — so the **org-blessed path is
> `python3 -m mapping_drone.moveit_mission`** (`--check` / `--nofly` / `--fly`), aligned to that sample.
> If a given drone only exposes the **PX4-ROS2 (micro-XRCE-DDS)** link instead — as our test unit "three"
> did — use the equivalent **`px4_mission`** (same modes, `--pose px4|uwb`) as a fallback. Both share the
> same camera / UWB / artifact code; only the *flight transport* differs. Either way, do **NOT** use the old
> `controller.py`. Reasoning: [`DRONE_STACK_ANALYSIS.md`](DRONE_STACK_ANALYSIS.md). Operator detail:
> [`MAPPING_DRONE_SETUP_GUIDE.md`](MAPPING_DRONE_SETUP_GUIDE.md). (The commands below show `px4_mission`;
> for the MAVSDK path just swap in `moveit_mission` — same `--check`/`--nofly`/`--fly`/`--aruco-dict`.)

## 1. What are we doing? (Challenge 1)

The drone looks **straight down**, finds the **ArUco markers** (printed square barcodes) on the landing
pads, works out **where** each one is, builds a **top-down map**, and saves one **folder of results** for
the judges. All of that is coded — you run one command and a `run_<timestamp>/` folder appears.

## 2. Words you'll see

| Word | Plain meaning |
|------|---------------|
| **mapping drone** | the single PX4 drone (an Orange Pi computer + a PX4 flight controller) |
| **ArUco marker** | printed black-and-white square the drone detects (dictionary announced by judges, e.g. `7X7_1000`) |
| **PX4** | the flight-controller software that actually flies the drone |
| **micro-XRCE agent** | the bridge that lets your ROS2 code talk to PX4 (`start_micro.sh`) — **must be running** |
| **`/fmu/...` topics** | the ROS2 channels PX4 talks on (pose, status, commands) |
| **px4_msgs** | the message definitions; **must match the PX4 firmware version** or nothing decodes (see §6) |
| **UWB** | indoor "GPS"; publishes the drone's position on `/uwb_tag` (`start_uwb.sh`) |
| **RealSense** | the depth camera (D435 = has colour; D450 = no colour — see troubleshooting) |
| **offboard** | the PX4 mode where *your code* commands the drone's position |
| **run folder** | `mapping_drone/runs/run_<date_time>/` — where results are saved |

## 3. The 3 modes (always go in this order)

| Mode | Command | Arms? Flies? |
|------|---------|-------------|
| **Check** | `px4_mission --check` | no — just reads pose/status |
| **No-Fly** | `px4_mission --nofly` | **no** — full detect/map, drone never moves |
| **Fly** | `px4_mission --fly` | **yes** — autonomous offboard survey |

Each also takes `--pose px4` (uses PX4's own position) or `--pose uwb` (uses `/uwb_tag` directly).

---

## 4. Setup on the drone (every fresh boot)

```bash
cd ~/AD/semifinal
git pull                                            # get the latest code
source ~/ros2_ws/install/setup.bash                 # REQUIRED — loads px4_msgs
pkill -f MicroXRCEAgent; bash ~/start_micro.sh &    # exactly ONE agent (PX4 bridge)
sleep 4
bash ~/start_uwb.sh                                  # UWB → /uwb_tag; enter 0.0 then 0.0
```
Do **not** run `start_rs.sh` — `px4_mission` opens the RealSense camera itself.

## 5. Check mode — confirm the link + pose (never arms)

```bash
python3 -m mapping_drone.px4_mission --check --pose px4
```
Expect lines like `pose n=… e=… down=… valid=True`. **Lift/tilt the drone** and watch the numbers change.
- `valid=False` / no pose → almost always the **px4_msgs version mismatch** (see §6). Try `--check --pose uwb`
  instead (uses `/uwb_tag`, which always works).

---

## 6. ⚠️ The one gotcha — "Fast CDR exception" / pose never valid

If `--pose px4` never shows `valid=True` and you see **`Fast CDR exception`**, the `px4_msgs` on the drone
doesn't match the PX4 firmware version. Fix (one-time, on the drone):
```bash
cd ~/ros2_ws/src && rm -rf px4_msgs
git clone -b release/1.15 https://github.com/PX4/px4_msgs.git    # MATCH the firmware version exactly
cd ~/ros2_ws && colcon build --packages-select px4_msgs && source install/setup.bash
```
(Find the firmware version with `ver all` in the PX4 shell. If you can't fix it in time, use **`--pose uwb`**
for No-Fly mapping — but Fly mode needs `--pose px4` working.)

---

## 7. NO-FLY MODE — full pipeline, drone stays on the ground 🛑

This runs the **complete Challenge-1 pipeline** (camera + ArUco + map + judge artifacts) using **real
position**, but **never arms, takes off, or moves**. It's how you test everything safely, and it's the
whole deliverable if the drone is flown **manually**.

```bash
python3 -m mapping_drone.px4_mission --nofly --pose px4 --aruco-dict 7X7_1000 --max-flight-time-s 90
# if px4 pose won't decode, use UWB position instead:
python3 -m mapping_drone.px4_mission --nofly --pose uwb --aruco-dict 7X7_1000 --max-flight-time-s 90
```
**Hand-carry** the drone ~0.5–1.5 m above the markers, camera down. Watch for `sighting id=… world=(…)`.
Then check the results:
```bash
cat mapping_drone/runs/run_*/landing_pads.json     # marker IDs + world coords + valid/invalid
ls  mapping_drone/runs/run_*/markers/              # a snapshot per marker
```
Because the position is real, the `world` coords should track where you held the drone. Props never spin in
this mode — it's safe to hold (keep fingers clear as habit).

⚠️ **Validity:** the real IDs (11/45/51/67/101) are all **odd**, and the default rule marks odd = invalid.
For a scored run set the real rule first: `MAPPING_DRONE_VALIDITY=lookup MAPPING_DRONE_VALIDITY_LOOKUP=configs/valid_ids_10jun.json python3 -m mapping_drone.px4_mission ...`
(or `MAPPING_DRONE_VALIDITY=all_valid` just to confirm detection works).

---

## 8. FLY MODE — autonomous offboard survey ✈️

Only after Check + No-Fly look good, **with a human on a kill switch**, and `--pose px4` showing `valid=True`.
Fly mode **arms the drone, takes off, flies the waypoints (scanning each), then lands and disarms**.

```bash
python3 -m mapping_drone.px4_mission --fly --aruco-dict 7X7_1000 \
  --takeoff-alt 4.0 --waypoints-from-json configs/waypoints_10jun.json
```
What happens, in order: streams setpoints → engages **offboard** → **arms** → climbs to `--takeoff-alt` →
flies each waypoint and scans → **lands + disarms**. `Ctrl-C` lands and disarms immediately.
- `--fly` forces `--pose px4` (autonomous flight must use the flight controller's own position) — so the
  px4_msgs fix in §6 must be done first.
- Build the waypoints file for the real arena (markers span ~4.4 × 7.85 m): copy `configs/arena_8x8.json` to
  `configs/waypoints_10jun.json` and edit it to a serpentine sweep at z = 4.0 m. **Untested in the air — treat
  the first `--fly` as a real first flight: low, short, kill-switch ready.**

---

## 9. If something breaks

| You see | Means | Do |
|---------|-------|-----|
| `Fast CDR exception` / pose `valid=False` | px4_msgs ≠ firmware | §6 fix, or use `--pose uwb` |
| `px4_msgs/rclpy not importable` | env not sourced | `source ~/ros2_ws/install/setup.bash` |
| `--pose uwb` pose `valid=False` | UWB not publishing | run `start_uwb.sh` (enter `0.0`/`0.0`); `ros2 topic echo /uwb_tag --once` |
| 0 markers detected | wrong dict, or no-RGB camera | pass the announced `--aruco-dict`; if it's a **D450** (no colour) see [`D430_RGB_RISK.md`](D430_RGB_RISK.md) |
| every pad `valid=False` | default `even` rule | set `MAPPING_DRONE_VALIDITY` (§7) |
| `RealSense ... pipeline.start() failed` | D450 has no colour | get a D435, or apply the IR fallback patch |
| many XRCE agents / weird behaviour | more than one `MicroXRCEAgent` | `pkill -f MicroXRCEAgent` then start ONE |

## 10. Where to go next
- Why the architecture is what it is + the finals plan: [`DRONE_STACK_ANALYSIS.md`](DRONE_STACK_ANALYSIS.md)
- Every flag and operator detail: [`MAPPING_DRONE_SETUP_GUIDE.md`](MAPPING_DRONE_SETUP_GUIDE.md)
- The actual flight code: [`mapping_drone/px4_ros.py`](mapping_drone/px4_ros.py) + [`mapping_drone/px4_mission.py`](mapping_drone/px4_mission.py)

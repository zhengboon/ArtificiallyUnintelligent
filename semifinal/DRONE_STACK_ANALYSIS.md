# Drone-stack analysis (10 June 2026) — what flies the real finals drone

Analysis of the full drone file dump (`zbstuff/drone files.zip` → the team's `roboverse26`
stack + `ros2_ws/src`), cross-checked against our `semifinal/` code. Produced by a 9-agent
audit. **Bottom line (updated): the org's official sample (`move_it4.py`) flies via MAVSDK on
`serial:///dev/ttyS6:921600`, so `mapping_drone/moveit_mission.py` is now THE primary flight
path (entry point: `python3 -m mapping_drone`). `mapping_drone/px4_ros.py` + `px4_mission.py`
(PX4-ROS2 / micro-XRCE-DDS) are kept as the FALLBACK. `controller.py` is RETIRED legacy (not an
entry point). The PX4/XRCE analysis below stays valid for that fallback path.**

> **Runbook:** procedures live in [`OP_DOC.md`](OP_DOC.md) — a decision tree (Step 0 fingerprint
> → 1 sensors → 2 check → 3 frame → 4 nofly → 5 fly → 6 artifacts, with lettered fallbacks).
> This file is the stack *analysis*; go to OP_DOC.md to actually run the drone.

---

## 1. Control architecture

> **Updated:** the org's official sample (`move_it4.py`) talks **MAVSDK/MAVLink on
> `serial:///dev/ttyS6:921600`**, so that is now the **primary** path
> ([`mapping_drone/moveit_mission.py`](mapping_drone/moveit_mission.py); entry point
> `python3 -m mapping_drone`). The PX4-ROS2 / micro-XRCE-DDS path documented in the rest of this
> section is retained as the **FALLBACK** ([`mapping_drone/px4_mission.py`](mapping_drone/px4_mission.py)).
> Confirm per-drone which transport is live with `tools/drone_fingerprint.sh` (see OP_DOC.md Step 0).

**Fallback (PX4-ROS2 / XRCE):** on a drone with no MAVLink heartbeat, control is **PX4-ROS2
OFFBOARD over micro-XRCE-DDS**. There, `MicroXRCEAgent serial -D /dev/ttyS1 -b 921600`
(`start_micro.sh`) brings up the `/fmu/*` topics.

Fallback interface (implemented in [`mapping_drone/px4_ros.py`](mapping_drone/px4_ros.py)):
- **Publish:** `/fmu/in/offboard_control_mode`, `/fmu/in/trajectory_setpoint`, `/fmu/in/vehicle_command`
- **Subscribe:** `/fmu/out/vehicle_local_position`, `/fmu/out/vehicle_status`
- **QoS (load-bearing): BEST_EFFORT + VOLATILE + KEEP_LAST.** RELIABLE silently fails to match
  PX4's BEST_EFFORT publishers → zero pose. (Our code uses VOLATILE depth 10 pub / 5 sub — correct.
  The stock `offboard_control.py` uses depth 1; either works.)
- **Offboard engage sequence:** set initial setpoint at current pose → stream OffboardControlMode +
  TrajectorySetpoint at ≥10 Hz (we do 20 Hz) **before** arming → `VEHICLE_CMD_DO_SET_MODE(1,6)` then
  `VEHICLE_CMD_COMPONENT_ARM_DISARM(1)` → confirm `arming_state==2` AND `nav_state==14` → stream NED
  position setpoints (x=N, y=E, z=Down; alt_up → z=−alt) → `VEHICLE_CMD_NAV_LAND` → disarm.
- VehicleCommand: `target_system=1, target_component=1, source_system=1, source_component=1, from_external=True`.

**Sim/qualifier-only (do NOT use on the real drone):** anything binding MAVSDK to `udp:14540`
(all `roboverse26/qualifs/*`, `drone_control_new.py`, `autonomous_explorer.py`, `runningv9.py`).
Note `serial:///dev/ttyS6` is NOT sim-only — it is the org's official MAVSDK transport and is now
our primary path (`moveit_mission.py`); `roboverse26/nav_controller.py` and our own `controller.py`
both used it but `controller.py` is RETIRED legacy (not an entry point). The Hula swarm is a third,
separate path (pyhulax over WiFi) — unaffected by any PX4/XRCE concern.

## 2. The blocker: px4_msgs ↔ firmware version mismatch

`/fmu/*` decode fails with **"Fast CDR exception"** because the companion's `px4_msgs` doesn't
byte-match the `.msg` definitions compiled into the flashed PX4 firmware (PX4 uses per-message
versioning — `VehicleLocalPosition.msg` has `MESSAGE_VERSION = 1`). The extracted `ros2_ws/src/px4_msgs`
is unusable (msg-only, no `package.xml`/`CMakeLists`, mixed MESSAGE_VERSIONs). **Fix, in order:**
1. Find the exact firmware version (`ver all` in the PX4 shell, or the flashed build tag; `px4_ros_com`
   here is pinned to release/1.15–1.16 → strong hint).
2. On the drone: `git clone -b release/1.15 https://github.com/PX4/px4_msgs.git ~/ros2_ws/src/px4_msgs`
   (match the version EXACTLY), replacing the msg-only dir.
3. `colcon build --packages-select px4_msgs && source install/setup.bash`.
4. Verify: `python3 -m mapping_drone.px4_mission --check --pose px4` must report a valid pose with no
   CDR exception.

**Workaround (mapping only):** `--pose uwb` uses `/uwb_tag` (standard `geometry_msgs/PoseStamped`,
CDR-immune). But `--pose uwb` cannot drive autonomous `--fly` (no FC position estimate) — a scored
autonomous run REQUIRES the matched px4_msgs build.

## 3. UWB config (real values)

- Topic **`/uwb_tag`**, type `geometry_msgs/PoseStamped`, published by **nlink `nlink_ros2_node`** (NOT by
  any Python) on serial **`/dev/ttyS4` @921600** (Nooploop LinkTrack). QoS BEST_EFFORT depth 10.
- **Axis mapping (load-bearing): NORTH = `pose.position.y`, EAST = `pose.position.x`, ALT = `pose.position.z`
  (ENU z-up).** Our `uwb.py` does exactly this (now also reads z — fixed today). Do NOT "fix" the y→N/x→E swap.
- `br_n`/`br_e` (nlink ROS params, default 0) re-zero the UWB origin onto your takeoff point:
  `east = raw_x − br_e`, `north = raw_y − br_n`. `yaw_alignment_offset` aligns room axis to compass north.
- **Field cal:** at the arena origin, read `/uwb_tag`, set `br_n`/`br_e` so takeoff reads (0,0); verify
  N=+pose.y and E=+pose.x increase in the right physical directions.

## 4. Finals-ready vs sim (verdict)

| File / module | Status |
|---|---|
| `semifinal/mapping_drone/moveit_mission.py` (MoveItMission) | **PRIMARY, real-drone-ready** — org-aligned MAVSDK on `serial:///dev/ttyS6:921600`; `--check`/`--nofly`/`--fly`, `--pose auto\|fc\|uwb`; set dict + validity |
| `semifinal/mapping_drone/px4_ros.py` (Px4Ros2Flight) | **FALLBACK** — correct offboard adapter; only needs matched px4_msgs |
| `semifinal/mapping_drone/px4_mission.py` | **FALLBACK** (PX4-ROS2/XRCE) — `--check`/`--nofly`/`--fly`, `--pose px4\|uwb`; set dict + validity |
| `semifinal/mapping_drone/{mapping,realsense,uwb,run_writer,validity}.py` | **platform-agnostic** — reuse as-is (validity default now `lookup`→`configs/valid_ids_finals.json`; D450 color→IR fallback now implemented in RealsenseNode) |
| `ros2_ws/src/nlink_parser` | **real-drone-ready** — the UWB→/uwb_tag + →/fmu/in/vehicle_visual_odometry bridge |
| `ros2_ws/src/px4_msgs` (extracted) | **incomplete** — msg-only; replace with full checkout at firmware tag (fallback path only) |
| `px4_ros_com/.../offboard_control.py` | transport template only (arms blindly, climbs to z=−5) — superseded by our px4_ros.py |
| `roboverse26/qualifs/v4_latest.py` (A* + guards) | **sim-only** — good *algorithm* to port for obstacle-aware waypoints |
| `roboverse26/nav_controller.py` | **sim-only** (MAVSDK udp) |
| our `mapping_drone/controller.py` | **RETIRED legacy** (MAVSDK ttyS6) — not an entry point; superseded by `moveit_mission.py` |
| `roboverse26/detection/robomaster_aruco_tagger.py` | reusable for Challenge-2 tag evidence |

## 5. Challenge plans

**Challenge 1:** fly with the **primary** `python3 -m mapping_drone` → `moveit_mission.py` (MAVSDK
on `serial:///dev/ttyS6:921600`; needs NO XRCE agent, but DOES need `start_uwb.sh` → `/uwb_tag`).
Mode flow is `--check` (connect + pose, no arm) → `--nofly` (UWB + camera + scan/detect/map/artifacts,
no arm) → `--fly` (autonomous). Pose default `--pose auto` = MAVSDK FC fused NED, auto-fallback to
`/uwb_tag`; altitude always from the FC. The PX4-ROS2/XRCE `px4_mission.py` is the **fallback** if no
MAVLink heartbeat (then build matched px4_msgs and use `--pose px4`/`uwb`). MUST pass the judge dict and
set the validity rule before scoring. Artifacts via `run_writer`. **Step-by-step procedure lives in
[`OP_DOC.md`](OP_DOC.md)** (Step 0 fingerprint → 6 artifacts) — follow that, do not duplicate here.

**Challenge 2 (Hula swarm):** separate platform (pyhulax/WiFi), planning brain built but **nothing wired
to live hardware** (everything hits MockHula). Lower priority. Needs: live DroneAPI glue (huladola UDP
discovery — verify port 8668 vs the 8688 in a docstring → connect → hand DroneAPI to
`bayesian_search` + `collision_avoidance_v3`), fill `HULA_UWB_TAG_IDS` + `UWB_SERIAL_PORT`, measure Hula
`move/move_to` units+frame, wire `safe_path_planner` (no flying over obstacles) + `robomaster_aruco_tagger`.

## 6. Prioritized actions

- **P0** Edit `configs/valid_ids_finals.json` with the marshal's real valid/invalid split *before* any scored run. Default rule is already `lookup` (NOT `even`); override via `MAPPING_DRONE_VALIDITY`/`MAPPING_DRONE_VALIDITY_LOOKUP` only if needed.
- **P0** Confirm the judge-announced **ArUco dict** with the marshal (org markers assumed `DICT_7X7_1000`, IDs 11/45/51/67/101). Default `--aruco-dict` is now `7X7_1000,6X6_250` and BOTH are scanned every frame, so no flag change is needed unless the announced dict is neither of these.
- **P0** Confirm **RealSense model per handoff** — D435 (RGB) vs D450 (no RGB). RealsenseNode now AUTO-falls-back color→IR (no flag); `--use-ir-for-aruco` forces IR.
- **P1** Build `px4_msgs` against the exact flashed firmware *only if* falling back to XRCE; verify with `px4_mission --check --pose px4`.
- **P1** Field-calibrate UWB (`br_n`/`br_e`, axis signs, `yaw_alignment_offset`); confirm `gimbal_pitch=-90`.
- **P1** Dry-run `--nofly` then a short low `--fly`; validate engage/arm latch + camera→world transform.
- **P1** Build the finals **waypoint rectangle** (~4.4×7.85 m; no shipped square config matches) at alt ≥4.0 m.
- **P2** Challenge-2 live-hardware glue. **P2** Treat `semifinal/` as source of truth; `roboverse26` extract as reference.

## 7. Open questions for the marshal
Firmware version/tag · ArUco dict (pads vs robots) · validity rule + valid/invalid IDs + pad coords ·
RealSense model per drone · is `/uwb_tag` (nlink) live on the assigned drone · arena dims/origin + takeoff
NED origin + compass alignment · is autonomous offboard allowed + altitude ceiling (config caps 3.3/3.5 m
but mapping wants 4.0 m) · Hula discovery port (8668 vs 8688) + per-drone UWB tag IDs/serial.

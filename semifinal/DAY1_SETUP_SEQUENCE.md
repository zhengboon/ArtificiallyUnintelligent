# Day-1 Setup Sequence — 7:30am to 9:00am

Companion to `OP_DOC.md` (THE runbook — the decision-tree that covers execution + fallbacks; supersedes the retired DAY1_RUNBOOK.md). This file covers the SETUP phase only: arrival → first scored slot ready. One page. Print on paper. For any actual run procedure, go to `OP_DOC.md`.

> **Path varies per drone** — run `ls ~` first; seen `~/AD/semifinal`, `~/ad/semifinal`, `~/roboverse26/semifinal`. Adjust the `cd` paths below to whatever you find.
> **Isolate ROS2 in EVERY terminal:** `export ROS_LOCALHOST_ONLY=1` (another team on the shared `ROS_DOMAIN_ID=0` is what made topics read empty last time; our code also forces it, but set it in the shell too).

---

## 7:30 — Arrival + registration

- Photo ID + confirmation email in hand at the door.
- **A** collects lanyards at registration desk (talker role).
- **K + Z** head straight to assigned setup zone with gear cart. Do not wait for A.

---

## 7:45-8:15 — Hardware setup

- [ ] **Mapping drone camera reachability**: confirm the mapping drone has booted and is reachable via NoMachine from the C2 Terminal — the drone's onboard D430/D450 (no RGB) will be queried during the 8:35-8:50 validation block. The USB-3 type-descriptor one-liner (see step 4 of the validation block below) runs inside the NoMachine session against the drone's pyrealsense2, not against the C2 Terminal. Our D435 stays in the bag (dev fallback only; venue uses D430/D450).
- [ ] **Mapping drone radio link**: 5.88 GHz link to GCS. Org will likely walk us through pairing — K stays at the drone, follows org instructions, confirms link LED solid.
- [ ] **Hula drones**: power on, join the venue 5 GHz WiFi SSID announced at briefing. K confirms each drone visible to the swarm controller before handing off.

---

## 8:15-8:35 — Code transfer (USB → C2 Terminal → VM)

Copy these 3 trees from USB to `C:\team\semifinal\` on the Windows host:

1. `semifinal/` — full tree (mapping_drone, tools, configs, tests, runbooks).
2. `models/` — currently empty; YOLO path killed per `runbook.md`. Skip if absent.
3. `configs/` — already inside `semifinal/`, but re-verify `valid_ids_finals.json` (the default validity lookup table the code reads) and the `arena_*x*.json` / `waypoints_2x2_default.json` templates are present.

Then load into the Ubuntu 22.04 VM. Primary mechanism: VirtualBox/VMware shared folder mount (see `thumbdrive/README.md` → "VM <-> host file transfer" → Option A). Verify on VM with `ls /media/sf_brainhack` (VBox) or `ls /mnt/hgfs/brainhack` (VMware). If Option A fails, fall back to Option B (USB passthrough) per the same doc.

---

## 8:35-8:50 — Environment validation (run from `semifinal/` on the VM)

Single command per check (`export ROS_LOCALHOST_ONLY=1` first in this terminal). If any fails, fix before proceeding. For the full readiness check on the actual drone, prefer `bash tools/drone_fingerprint.sh` (~30s, read-only, never arms — see OP_DOC.md Step 0).

- [ ] `python3 -m mapping_drone.moveit_mission --help` — primary entry-point CLI parses. Modes `--check` / `--nofly` / `--fly` plus `--pose {auto,fc,uwb}`, `--use-ir-for-aruco`, `--aruco-dict`, `--mavsdk-address` (serial:///dev/ttyS6:921600), `--waypoints-from-json`, `--takeoff-alt`, `--gimbal-pitch`, `--max-flight-time-s` all listed. `python3 -m mapping_drone` (no submodule) dispatches to `moveit_mission`; `controller.py` is RETIRED (not an entry point); `px4_mission` is the PX4-ROS2/XRCE FALLBACK only.
- [ ] `python3 -c "from mapping_drone.mapping import ALL_SUPPORTED_DICT_NAMES; print(len(ALL_SUPPORTED_DICT_NAMES))"` — must print `20`.
- [ ] `python3 tools/uwb_sniffer.py` for 10 s — confirm `uwb_tag` topic publishes; NED axes match (n=pose.y, e=pose.x, alt=-pose.z). Ctrl-C to stop.
- [ ] `python3 -c "import pyrealsense2 as rs; print(rs.context().query_devices()[0].get_info(rs.camera_info.usb_type_descriptor))"` — must print a `3.x` string. If `2.x` → wrong USB port, replug. (RealsenseNode auto-falls back color→IR on a no-RGB D450; `--use-ir-for-aruco` forces IR.)

---

## 8:50-9:00 — First-run prep

- [ ] Read briefing materials handed out at registration. Capture (these are the marshal-confirm items in OP_DOC.md Appendix C):
  - Announced ArUco dict name (verbatim, including underscores/case). We assume **DICT_7X7_1000**, IDs 11/45/51/67/101; the `--aruco-dict` default is `7X7_1000,6X6_250` and BOTH dicts are scanned every frame.
  - Validity split (which IDs are valid vs invalid).
  - Arena dimensions (we assume 5.5 m wide × 11 m long, 0.7 m wall margin) + arena origin for the UWB `br_n/br_e` calibration + ceiling/net height.
- [ ] **Validity:** the default rule is `lookup` → `configs/valid_ids_finals.json`. Edit that file with the marshal's real valid/invalid split (move INVALID ids into `invalid_ids`). Env override if needed: `MAPPING_DRONE_VALIDITY` / `MAPPING_DRONE_VALIDITY_LOOKUP`.
- [ ] **Waypoints:** build the survey box for the measured frame — `python3 tools/survey_box.py --margin 0.7 --lanes 3 --alt 2.5 --out configs/waypoints_surveyed.json`, then launch with `--waypoints-from-json configs/waypoints_surveyed.json`. (NOTE: survey_box's corner-walk mode is UNUSABLE if you can't touch the drone.) Frame measurement (Path 3-UWB vs 3-FC) and the run command live in **OP_DOC.md Step 3 / Step 5** — go there for the procedure, don't duplicate it here.

---

## Role assignments during 7:30-9:00

- **K** — hardware: drone batteries, USB connections, mapping drone radio link, Hula WiFi join.
- **Z** — software: USB → VM transfer, environment validation, config file staging.
- **A** — comms: registration, briefing notes, capture org's Day-1 announcements (dict + validity rule + arena dims), photo-log the arena for post-run review.

---

## Operator gotchas (carry into the run)
- Repo path varies per drone — `ls ~` first (`~/AD` vs `~/ad` vs `~/roboverse26`).
- `export ROS_LOCALHOST_ONLY=1` in every terminal; one process per terminal.
- Kill nlink with `pkill -f px4_ros2_node` (NOT `nlink_ros2_node` — matches nothing).
- `start_uwb.sh` prompts for bottom-right corner n/e — enter `0.0` then `0.0` (with the `.0`) for raw UWB coords; see OP_DOC.md Step 1 for the real calibration values.

---

*Day-1 Setup Sequence v1. Hands off to `OP_DOC.md` (THE runbook) at 9:00am sharp.*

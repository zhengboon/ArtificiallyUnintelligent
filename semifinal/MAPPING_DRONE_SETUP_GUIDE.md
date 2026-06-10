# Mapping-drone setup guide (Challenge 1) — reconciled with 10-June org guidance

> **⚠️ UPDATE — the primary entry point is now `python3 -m mapping_drone` → `moveit_mission`** (MAVSDK on
> `serial:///dev/ttyS6:921600`, matching the org's official `move_it4.py` sample). The legacy MAVSDK
> `controller.py` flow described in this guide is **RETIRED as an entry point** (kept only as legacy code);
> `px4_mission` is the **PX4-ROS2 / micro-XRCE-DDS (`/fmu/*`) FALLBACK only** (`python3 -m mapping_drone.px4_mission`).
> Modes for `moveit_mission`: `--check` (connect + pose, no arm) / `--nofly` (camera + detect + map, no arm) /
> `--fly` (autonomous, default). **The step-by-step runbook now lives in [`OP_DOC.md`](OP_DOC.md)** (a decision
> tree: Step 0 fingerprint → 1 sensors → 2 check → 3 frame → 4 nofly → 5 fly → 6 artifacts, with lettered
> fallbacks) — use it for procedures. The dict / validity / camera (D435 vs D450) / UWB / arena reference
> below still applies. Where this guide still shows `controller.py` flags or line numbers, treat them as
> legacy; the live flags are on `moveit_mission` (see [`OP_DOC.md`](OP_DOC.md)).

**Written 2026-06-10.** Grounded in the actual code (`mapping_drone/`) and the new org drops.
Source facts: [`downloaded stuff/KEY_UPDATES_for_mapping_drone.md`](downloaded%20stuff/KEY_UPDATES_for_mapping_drone.md).
This supersedes the navigation/dict assumptions in `DAY1_SETUP_SEQUENCE.md` and `runbook.md` where
they conflict (those predate the 10-June guidance — drift is called out at the bottom).

> **Where you run:** from **inside `semifinal/`** on the drone's onboard Ubuntu 22.04, reached over
> **NoMachine from the C2 Terminal**. Entry point: `python -m mapping_drone` → `moveit_mission` (`--fly`
> is the DEFAULT — no flag needed). All relative paths (`configs/`, `--runs-dir mapping_drone/runs`, the
> validity lookup) resolve against the launch CWD, so **always `cd semifinal/` first.** `ROS_LOCALHOST_ONLY=1`
> is forced at entry to avoid cross-team DDS on the shared `ROS_DOMAIN_ID=0`; also `export ROS_LOCALHOST_ONLY=1`
> in every terminal you open.

---

## Phase 0 — do this NOW, no drone needed (shared-slot prep)

The drones are shared; while another team has yours, do all the no-hardware prep so your test slot is spent
tuning, not authoring. Everything here runs on the laptop/VM (only `opencv-contrib-python` + `numpy`).

1. **Env gate** (verified 10/6 on the dev box: `cv2 4.13.0 | 20 dicts | 7X7_1000 True`):
   `python3 -c "import cv2,numpy; from mapping_drone.mapping import ALL_SUPPORTED_DICT_NAMES as D; print(len(D), '7X7_1000' in D)"`
2. **Mock pipeline check** (proves detect/map/artifacts without hardware): run the bundled smoke tests
   (item 6) — they exercise `MockRealsenseNode` + `MockUwbNode`. The `moveit_mission` entry point has no
   `--mock-all`/`--dry-run` flags (those were legacy `controller.py`-only); use the smoke tests instead.
3. **Stage configs** (procedure now in [`OP_DOC.md`](OP_DOC.md) Step 3 + Step 5): build a rectangular/serpentine
   waypoints file, and edit `configs/valid_ids_finals.json` with the marshal's real valid/invalid split (this is
   already the DEFAULT lookup table — validity defaults to `lookup`, not `even`). Confirm with
   `python3 -c "from mapping_drone.validity import describe_rule; print(describe_rule())"` (should name `lookup`).
4. **Pull from the org Drive** on the VM: the org `move_it4.py` sample + the "How to use the drones" pdf.
5. Both the auto color→IR camera fallback and `--use-ir-for-aruco` are already wired (§ P0-a); validate the
   detect/map pipeline against the bundled mock smoke tests (`MockRealsenseNode`). Only the final IR check
   needs the drone.
6. **Run the bundled smoke tests:** `python3 -m mapping_drone.tests.smoke_abort` etc. (mock-only, no hardware).
7. **Concept submission** due **11 Jun 1:30 pm** (one entry/team) — non-technical but a hard deadline.

What you CANNOT do until you have the drone: `mavsdk_probe`, `uwb_sniffer`, RealSense checks, `--check`/`--nofly`
against real hardware, and the scored run. Procedure: [`OP_DOC.md`](OP_DOC.md). Have those commands ready to paste.

### Grounded-drone bench test (`--nofly`)

If you can power the drone but it **may not take flight**, run the FULL detect/map/artifact pipeline in
place. `--nofly` brings up UWB + RealSense + MAVSDK telemetry and loops the scan/detect/occupancy/artifact
pipeline, but **never arms, takes off, goes offboard, sends a velocity/position command, or lands**:

```bash
# grounded drone, real sensors, camera pointed at the printed markers (default dict scans
# BOTH 7X7_1000 and 6X6_250, so no --aruco-dict needed; add --use-ir-for-aruco only on a D450):
python3 -m mapping_drone --nofly --max-flight-time-s 60
```

Confirm `landing_pads.json` + `markers/marker_<id>_*.jpg` populate with IDs from {11,45,51,67,101} and that
validity matches the lookup table. World coordinates are **not** physically meaningful at ground level
(the drone isn't at survey altitude), but detection, RealSense, UWB, validity, and artifact writing are all
exercised against real hardware. `Ctrl-C` stops cleanly. This is the safest way to prove the full Challenge-1
pipeline works on the actual drone before you ever get a flight slot. **Full procedure: [`OP_DOC.md`](OP_DOC.md)
Step 4.**

---

## 0. What changed today — reconciliations + standing P0s

> Most of these are now RESOLVED in the primary entry point (`moveit_mission`): it already flies the
> org-preferred position path, scans both dicts, defaults validity to `lookup`, and auto-falls-back
> color→IR. The table below is kept for context; the live runbook is [`OP_DOC.md`](OP_DOC.md).

| # | Topic | Code today | Org now wants | Your move |
|---|-------|-----------|---------------|-----------|
| 1 | **Navigation** | **RESOLVED:** `moveit_mission` flies `set_position_velocity_ned` (position target + velocity feed-forward, [moveit_mission.py:306](mapping_drone/moveit_mission.py#L306)), faithful to the org `move_it4.py`. Legacy velocity-only `controller.py` is retired. | position-based per the org sample | None — the primary entry point already does this. §1 below is legacy (controller.py). |
| 2 | **ArUco dict** | default `7X7_1000,6X6_250` ([moveit_mission.py:561](mapping_drone/moveit_mission.py#L561)); BOTH dicts scanned every frame | `DICT_7X7_1000`, IDs 11/45/51/67/101 (CONFIRM with marshal — 7X7 was only guessed from Discord) | Default already hedges both. No flag needed; `detect_in_frame` logs which dict matched. |
| 3 | **Validity** | default rule `lookup` → `configs/valid_ids_finals.json` ([validity.py:61](mapping_drone/validity.py#L61)); NOT `even` | not published | Edit `configs/valid_ids_finals.json` with the marshal's real valid/invalid split. (`even` was retired — it marked every ODD org ID invalid.) Env override: `MAPPING_DRONE_VALIDITY` / `MAPPING_DRONE_VALIDITY_LOOKUP`. |
| 4 | **Arena/waypoints** | 2×2 m default; all configs square | markers span x≈4.4 m, y≈7.85 m | Build a rectangular waypoints file ([`OP_DOC.md`](OP_DOC.md) Step 3/5). Don't use the 2×2 default. |
| P0-a | **Camera** | `RealsenseNode` AUTO-falls-back color→IR if all colour profiles fail ([realsense.py:125](mapping_drone/realsense.py#L125)) | **confirmed: fleet is D435 + D450 (mixed)** | **D435 (RGB) and D450 (no-RGB) both work with NO flag** — the color→IR fallback is automatic. `--use-ir-for-aruco` forces IR if auto-detect picks wrong. Identify your camera ([`OP_DOC.md`](OP_DOC.md) Step 0/1). |
| P0-b | **MAVSDK connect** | default `--mavsdk-address serial:///dev/ttyS6:921600` (MAVSDK, MAVLink — NOT XRCE) ([moveit_mission.py:554](mapping_drone/moveit_mission.py#L554)) | — | This is a **serial port on the drone's onboard computer**, not a network address — Ethernet/NoMachine only gets you *onto* that computer; MAVSDK reaches the FC over internal serial (see §2 Transport). If the FC is unreachable, fall back to `px4_mission` (XRCE). |

---

## 1. Navigation (RESOLVED — legacy section)

This decision is closed. The primary entry point `moveit_mission` already flies the org-preferred
position path — `set_position_velocity_ned` (position target + velocity feed-forward), faithful to the
org `move_it4.py` sample — so there is no velocity-vs-position choice to make. The velocity-only
`controller.py` discussed previously is **legacy, retired as an entry point**. No `moveit.py` import or
code change is needed. For the live flight procedure see [`OP_DOC.md`](OP_DOC.md) Step 5.

---

## 2. Prerequisites

- `cd semifinal/` (launch CWD). Python 3.10+.
- `opencv-contrib-python` (needs `cv2.aruco.ArucoDetector`; plain `opencv-python` will NOT work), `numpy`.
- **Drone only:** `mavsdk`, `pyrealsense2`, and ROS2 `rclpy`+`geometry_msgs` (pre-installed in org image —
  do NOT `pip install rclpy`). Laptop/mock dev needs only opencv-contrib + numpy.
- A live ROS2 **`uwb_tag`** `PoseStamped` publisher in the arena (subscriber is hard-coded BEST_EFFORT QoS).
  Pose source is `--pose auto` (DEFAULT): MAVSDK FC fused NED, auto-fallback to `/uwb_tag`, then hold.
  `--pose fc` / `--pose uwb` force one. **Altitude is ALWAYS from the FC** (UWB gives N-E only, no Z — per
  the official slides), so `/uwb_tag` is only needed for horizontal feedback.
- Camera model confirmed (**D435** = has RGB vs **D450** = no RGB; there is no D430). The camera path is
  automatic: `RealsenseNode` falls back color→IR if all colour profiles fail, so both work with no flag;
  `--use-ir-for-aruco` forces IR.
- Gimbal physically straight down; drone **pre-yawed** toward your first-sweep direction before arming
  (takeoff point is fixed for all teams, but launch yaw is your choice). Battery ≥ 30% for a scored run.

> **Transport — read once.** The **Ethernet cable** (or NoMachine/SSH) connects you to the drone's
> **onboard computer** (the companion Ubuntu box). The **PX4 flight controller is internal to that computer
> over serial** — MAVSDK reaches it at **`serial:///dev/ttyS6:921600`** (the `--mavsdk-address` default),
> **NOT** over any network/Ethernet IP. Run `moveit_mission` *on the drone*, with the **serial** address.
> If the FC is unreachable over MAVSDK, the fallback is `px4_mission` (PX4-ROS2 / XRCE).

---

## 3. Bring-up sequence (run from `semifinal/`)

**Step 1 — env gate.** Deps import + announced dict resolves:
```bash
python3 -c "import cv2, numpy; from mapping_drone.mapping import ALL_SUPPORTED_DICT_NAMES as D; \
assert len(D)==20 and '7X7_1000' in D, D; print('deps OK, dicts:', len(D))"
python3 -m mapping_drone --help        # CLI parses (exit 0)
```

**Steps 2-9 (code transfer → MAVSDK probe → UWB axis → RealSense → stage configs → checks → scored run)
now live in [`OP_DOC.md`](OP_DOC.md)** as a decision tree (Step 0 fingerprint → 1 sensors → 2 `--check` →
3 frame → 4 `--nofly` → 5 `--fly` → 6 artifacts, each with lettered fallbacks). Follow that for the live
procedure — it uses the current `moveit_mission` flags (`--mavsdk-address`, `--pose`, `--use-ir-for-aruco`),
not the retired `controller.py` flags (`--mock-all`, `--dry-run`, `--mavsdk-addresses`, `udp://` fallbacks).
Highlights that still hold:

- **UWB axis check:** ENU→NED swap (n=pose.y, e=pose.x, alt=−pose.z); move the tag and watch the signs.
- **Camera:** identify D435 (RGB) vs D450 (no-RGB) per handoff; both work with NO flag (auto color→IR
  fallback in `RealsenseNode`). `--use-ir-for-aruco` forces IR; see [`D430_RGB_RISK.md`](D430_RGB_RISK.md).
- **Configs:** build a serpentine waypoints file passing over INTERIOR pads (a bare 4-corner perimeter
  misses them); edit `configs/valid_ids_finals.json` with the marshal's real valid/invalid split. Do **not**
  use `waypoints_unknown.json` blindly (it's a stray populated 2×2, not the documented empty fail-fast file).
- **Validity check:** `python3 -c "from mapping_drone.validity import describe_rule; print(describe_rule())"`
  should name `lookup` (the default) pointing at `configs/valid_ids_finals.json`.

---

## 4. Scored-run launch command

Validity defaults to `lookup` against `configs/valid_ids_finals.json`, so no env var is strictly needed
(set it explicitly to be safe). Pose defaults to `auto` and the camera auto-detects, so no flags for those:

```bash
cd semifinal/
export ROS_LOCALHOST_ONLY=1
MAPPING_DRONE_VALIDITY=lookup \
MAPPING_DRONE_VALIDITY_LOOKUP=configs/valid_ids_finals.json \
python3 -m mapping_drone --fly \
  --waypoints-from-json configs/waypoints_10jun.json \
  --gimbal-pitch -90 \
  --mavsdk-address serial:///dev/ttyS6:921600 \
  --max-flight-time-s 420 \
  --runs-dir mapping_drone/runs
# add --use-ir-for-aruco only on a D450 if auto color→IR picks wrong; --pose fc|uwb to force a source.
```
- `--fly` is the default mode (it can be omitted). Run inside **`tmux`** so a NoMachine drop doesn't kill the flight.
- `ROS_LOCALHOST_ONLY=1` is also forced at entry, but export it in every terminal anyway.
- This flies the org-aligned position path (`set_position_velocity_ned`) — no velocity-vs-position choice.
- **Full scored-run procedure + fallbacks: [`OP_DOC.md`](OP_DOC.md) Step 5.**

---

## 5. Preflight checks (before arming)

| Check | Command | Pass |
|-------|---------|------|
| CLI parses | `python3 -m mapping_drone --help` | exit 0 |
| 20 dicts incl. 7X7_1000 | `python3 -c "from mapping_drone.mapping import ALL_SUPPORTED_DICT_NAMES as D; print(len(D)); assert '7X7_1000' in D"` | `20`, no error |
| Validity rule is `lookup` | `python3 -c "from mapping_drone.validity import describe_rule; print(describe_rule())"` | names `lookup` (default) pointing at `valid_ids_finals.json` |
| Validity sanity on real IDs | `python3 -c "from mapping_drone.validity import decide_landing_validity as v; print({i:v(i) for i in (11,45,51,67,101)})"` | matches `configs/valid_ids_finals.json` (default: all 5 valid until the marshal moves some to invalid_ids) |
| Waypoints parse + rectangle | `python3 -c "import json;w=json.load(open('configs/waypoints_10jun.json'));assert w and all(len(p)==3 for p in w);print(len(w))"` | prints count |
| UWB axis swap | `python3 tools/uwb_sniffer.py` (move tag ~10 s) | n/e signs match room |
| RealSense USB3 + depth | step 5 commands | name printed, `3.x`, depth non-zero |
| MAVSDK link | `tools/mavsdk_probe.py` with try order | exit 0 = a link is up |

---

## 6. After takeoff — what to watch (in `runs/run_<ts>/log.txt`)

- `MAVSDK connected via <addr>` → health gate → `arm` → `set_takeoff_altitude(<--takeoff-alt>, default 4.0)`
  → pre-stream a setpoint → `offboard.start()` OK → climb → waypoint tracking (`set_position_velocity_ned`).
- Watchdogs that abort+land (`moveit_mission`): pose-loss (fix stale >5 s), never-fix >10 s airborne,
  position-stuck (<0.3 m moved over a 30 s window, 12 s grace), battery <15%, and offboard-setpoint-failure.
  **Disarm happens only after `in_air=False`** (never while airborne).
- **Artifacts** in `mapping_drone/runs/run_<ts>/`: `STATUS.txt` (`State=DONE`, not ABORTED), `landing_pads.json`
  (IDs from {11,45,51,67,101} with correct VALID/INVALID), `top_down.png`+`.npy`, `markers/marker_<id>_<seq>.jpg`,
  `run_summary.json` (`aborted=false`). If pads read the wrong VALID/INVALID, check `configs/valid_ids_finals.json`.
- **Copy the whole `run_<ts>/` dir off the drone to BOTH USBs immediately** (drones are shared; never overwrite).
- Full artifact-retrieval procedure: [`OP_DOC.md`](OP_DOC.md) Step 6.

---

## 7. Open questions for the marshal (Day-1 morning, verbal)

1. **Real validity split** for IDs 11/45/51/67/101 — which are valid vs invalid (default lookup marks all 5
   valid until you move some into `invalid_ids`; edit `configs/valid_ids_finals.json`).
2. ~~Is `set_position_ned` enabled / can we get `moveit.py`~~ **RESOLVED:** `moveit_mission` already flies the
   org-aligned position path (`set_position_velocity_ned`); no separate `moveit.py` import needed.
3. **Arena dimensions + coordinate origin + UWB anchor frame** (markers start at ~x1.3/y4.4, not 0,0 — sets
   our waypoint corners; OccupancyGrid is a fixed ±10 m about origin, points beyond are dropped).
4. ~~Camera module on the actual drone~~ **RESOLVED (user 10/6): fleet is D435 + D450**, and the camera path
   auto-falls-back color→IR so both work with no flag. Still ask: which is on *your assigned* drone, and did
   org bolt a separate RGB camera onto the D450?
5. **Depth-map metric reference point** + the **format** judges expect (our matplotlib top-down vs a raw
   stereo depth image — open since the 6/7 Q&A).
6. **Locations of id67 and id101** (unpublished). Is the gimbal fixed at −90 or software-commandable?
7. **Scored-run policy:** attempts allowed, fast-abort allowed? (Crash = no re-assessment; 8 min/480 s cap.)
8. **Testing-slot time / length / trial limit** — still UNANNOUNCED as of capture (org said "announce soon"
   twice, 7/6 & 8/6). Confirm at the briefing; assume short and that every hardware path already works.
9. **Coordinates of IDs 67 and 101** (unpublished), and WRITTEN confirmation that **Challenge 1 uses the same
   `DICT_7X7_1000`** (the post title flip-flopped Ch2&3 → Ch1 → Ch2&3).
10. **Required top-down depth-map output FORMAT** — stereo depth image vs matplotlib obstacle point-plot
    (asked 7/6, never answered). Wrong format fails the task even with correct flying.

---

## 8. Doc-drift warnings (existing repo docs that are now wrong)

- `--use-ir-for-aruco` **now EXISTS and is wired** (CLI flag on `moveit_mission`, IR path in `realsense.py`),
  and the camera also auto-falls-back color→IR. So `runbook.md`'s "add `--use-ir-for-aruco`" is now correct,
  while `DAY1_RUNBOOK.md` warnings that "argparse will reject it / NOT YET WIRED in controller.py" are STALE —
  ignore them. (Prefer section anchors over line numbers — they drift.)
- `mapping_drone/README.md` validity section lists 5 rules; there are **6** (adds `lookup` — verified in
  `validity.py`). `lookup` is now the DEFAULT (file: `configs/valid_ids_finals.json`).
- `configs/waypoints_unknown.json` documented as an empty fail-fast trap; on disk it's a stray populated 2×2.
- `DAY1_SETUP_SEQUENCE.md` / earlier docs assume velocity flying + dict-TBD + `controller.py` entry point; all
  superseded (entry point is `moveit_mission` flying the org position path; dict default scans 7X7_1000+6X6_250).
- Several runbook references call `swarm_controller.py` "NOT YET BUILT" — it is built (off today's path).

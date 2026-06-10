# Mapping-drone setup guide (Challenge 1) — reconciled with 10-June org guidance

> **⚠️ UPDATE 2026-06-10 PM — the real drone is PX4-ROS2, not MAVLink.** Confirmed on the drone: the
> finals flight controller speaks PX4 over micro-XRCE-DDS (ROS2 `/fmu/*`), so the MAVSDK `controller.py`
> flow in this guide is **simulator/qualifier-only and will NOT fly the real drone**. For the real drone
> use **`python3 -m mapping_drone.px4_mission`** (`--check` / `--nofly` / `--fly`, `--pose px4|uwb`).
> Start with [`START_HERE_BEGINNER.md`](START_HERE_BEGINNER.md) + [`DRONE_STACK_ANALYSIS.md`](DRONE_STACK_ANALYSIS.md).
> The dict / validity / camera (D435 vs D450) / UWB / arena sections below all still apply — only the
> **flight transport** changed (MAVSDK serial → PX4-ROS2 offboard).

**Written 2026-06-10.** Grounded in the actual code (`mapping_drone/`) and the new org drops.
Source facts: [`downloaded stuff/KEY_UPDATES_for_mapping_drone.md`](downloaded%20stuff/KEY_UPDATES_for_mapping_drone.md).
This supersedes the navigation/dict assumptions in `DAY1_SETUP_SEQUENCE.md` and `runbook.md` where
they conflict (those predate the 10-June guidance — drift is called out at the bottom).

> **Where you run:** from **inside `semifinal/`** on the drone's onboard Ubuntu 22.04, reached over
> **NoMachine from the C2 Terminal**. Entry point: `python -m mapping_drone` (real mode is the DEFAULT —
> no flag needed). All relative paths (`configs/`, `--runs-dir mapping_drone/runs`, the validity lookup)
> resolve against the launch CWD, so **always `cd semifinal/` first.**

---

## Phase 0 — do this NOW, no drone needed (shared-slot prep)

The drones are shared; while another team has yours, do all the no-hardware prep so your test slot is spent
tuning, not authoring. Everything here runs on the laptop/VM (only `opencv-contrib-python` + `numpy`).

1. **Env gate** (verified 10/6 on the dev box: `cv2 4.13.0 | 20 dicts | 7X7_1000 True`):
   `python3 -c "import cv2,numpy; from mapping_drone.mapping import ALL_SUPPORTED_DICT_NAMES as D; print(len(D), '7X7_1000' in D)"`
2. **Full mock mission** (proves the whole pipeline; writes every judge artifact — verified working 10/6):
   `python3 -m mapping_drone --mock-all --aruco-dict 6X6_250 --runs-dir /tmp/bh_mock` (default flight cap →
   finishes `State=DONE`; use `6X6_250` here because the mock camera draws a 6X6 marker, so you actually see
   sightings). Then `cat /tmp/bh_mock/run_*/STATUS.txt`.
3. **Stage configs** (steps 6 of §3 below): build `configs/waypoints_10jun.json` (rectangle), create
   `configs/valid_ids_10jun.json` (fill IDs once the marshal gives the rule), confirm describe_rule isn't `even`.
4. **Pull from the org Drive** on the VM: `moveit.py` (for `set_position_ned`) + the "How to use the drones" pdf.
5. **Code work that's fully mock-testable without the drone** (recommended to do now): wire the
   `--use-ir-for-aruco` D450 fallback (§ P0-a) and/or the `set_position_ned` path (§1, Option B). Both can be
   written and validated against `--mock-all` now; only the final IR/position check needs the drone.
6. **Run the bundled smoke tests:** `python3 -m mapping_drone.tests.smoke_abort` etc. (mock-only, no hardware).
7. **Concept submission** due **11 Jun 1:30 pm** (one entry/team) — non-technical but a hard deadline.

What you CANNOT do until you have the drone: `mavsdk_probe`, `uwb_sniffer`, RealSense checks, `--dry-run`
against real hardware, and the scored run (§3 steps 3-5, 8-9). Have those commands ready to paste.

### Grounded-drone bench test (`--nofly`)

If you can power the drone but it **may not take flight**, run the FULL detect/map/artifact pipeline in
place. `--nofly` brings up UWB + RealSense + MAVSDK telemetry and loops the scan/detect/occupancy/artifact
pipeline, but **never arms, takes off, goes offboard, sends a velocity/position command, or lands**
(verified: zero flight actions logged):

```bash
# grounded drone, real sensors, camera pointed at the printed 7X7_1000 markers:
python3 -m mapping_drone --nofly --aruco-dict 7X7_1000 --max-flight-time-s 60
# camera + UWB only, skip the flight controller:
python3 -m mapping_drone --nofly --mock-mavsdk --aruco-dict 7X7_1000 --max-flight-time-s 60
# pure laptop dry test of the mode:
python3 -m mapping_drone --nofly --mock-all --aruco-dict 6X6_250 --max-flight-time-s 10
```

Confirm `landing_pads.json` + `markers/marker_<id>_*.jpg` populate with IDs from {11,45,51,67,101} and that
validity matches the marshal's rule. World coordinates are **not** physically meaningful at ground level
(the drone isn't at survey altitude), but detection, RealSense, UWB, validity, and artifact writing are all
exercised against real hardware. `Ctrl-C` stops cleanly. This is the safest way to prove the full Challenge-1
pipeline works on the actual drone before you ever get a flight slot.

---

## 0. What changed today — the 4 reconciliations + 2 standing P0s

| # | Topic | Code today | Org now wants | Your move |
|---|-------|-----------|---------------|-----------|
| 1 | **Navigation** | velocity-only P-controller (`set_velocity_ned`, [controller.py:702](mapping_drone/controller.py#L702), [:815](mapping_drone/controller.py#L815)). **No `set_position_ned` anywhere.** | `set_position_ned` per `moveit.py`; "do NOT recommend velocity flying" | **Decision** — see §1. Default: fly the proven velocity path; upgrade only if `moveit.py` is in hand with time to re-test. |
| 2 | **ArUco dict** | default `6X6_250` ([controller.py:1743](mapping_drone/controller.py#L1743)) | `DICT_7X7_1000`, IDs 11/45/51/67/101 | Pass `--aruco-dict 7X7_1000`. No code change. |
| 3 | **Validity** | placeholder `even` ([validity.py:56](mapping_drone/validity.py#L56)) | not published | **All 5 IDs are ODD → `even` marks them ALL invalid.** Get the rule from the marshal, wire via env var. Never ship the default. |
| 4 | **Arena/waypoints** | 2×2 m default; all configs square | markers span x≈4.4 m, y≈7.85 m | Build a rectangular waypoints file (§ step 6). Don't use the 2×2 default. |
| P0-a | **Camera** | RGB-only pipeline | **confirmed: fleet is D435 + D450 (mixed)** | **D435 → has RGB, color path works as-is.** **D450 → no RGB**, color pipeline raises → zero ArUco. IR fallback is **docstring-only, not wired**. Identify your drone's camera (step 5); if D450, patch before flying. |
| P0-b | **MAVSDK connect** | bare default `ttyS6` **blocks forever, no timeout** ([controller.py:1283](mapping_drone/controller.py#L1283)) | — | **Always** pass `--mavsdk-addresses` (5 s/addr walker). These are **serial ports on the drone's onboard computer**, not network addresses — Ethernet/NoMachine only gets you *onto* that computer; MAVSDK reaches the FC over internal serial (see §2 Transport). |

---

## 1. Navigation decision (do this first)

The org now prefers `set_position_ned` (`moveit.py`) over velocity flying. Our controller is **100%
velocity-based** and `moveit.py` is **not in the repo** (pull from the org Drive). Two options:

- **Option A — fly velocity as-is (safe, ready now).** Works, smoke-tested, bounded by the 0.3 m/s hard
  cap and all the watchdogs. Accepts bang-bang motion + tight 0.1 m arrival thresholds. **Recommended for
  the first scored run.**
- **Option B — switch to `set_position_ned` (org-preferred, real code work).** Pull `moveit.py`, then:
  1. extend `_load_real_mavsdk` ([controller.py:396](mapping_drone/controller.py#L396)) to also import
     `PositionNedYaw` from `mavsdk.offboard`;
  2. replace the velocity command in `fly_to_position_velocity` ([controller.py:815](mapping_drone/controller.py#L815))
     with `await self.drone.offboard.set_position_ned(PositionNedYaw(n,e,down,yaw))`. **`down` is NEGATIVE when
     airborne** (4.0 m survey alt → `down = -4.0`; takeoff 3.6 m → `-3.6`); reuse the existing `alt → down`
     negation — a *positive* `down` drives the drone into the floor (sign unchanged from the velocity path);
  3. make `hover_for` hold position instead of streaming corrective velocities;
  4. change the offboard pre-warm ([controller.py:730](mapping_drone/controller.py#L730)) to stream zero-**position**
     (current pose) setpoints — PX4 needs the same setpoint type streamed before `offboard.start()`;
  5. add a mock `_MockOffboard.set_position_ned` so `--mock-all` still exercises it; re-run the mock smoke.

  **Only attempt B if `moveit.py` is in hand AND you have test-slot time to re-validate.** A half-tested
  position path on the scored run is worse than the proven velocity path. (Crash = no re-assessment.)

---

## 2. Prerequisites

- `cd semifinal/` (launch CWD). Python 3.10+.
- `opencv-contrib-python` (needs `cv2.aruco.ArucoDetector`; plain `opencv-python` will NOT work), `numpy`.
- **Drone only:** `mavsdk`, `pyrealsense2`, and ROS2 `rclpy`+`geometry_msgs` (pre-installed in org image —
  do NOT `pip install rclpy`). Laptop/mock dev needs only opencv-contrib + numpy.
- A live ROS2 **`uwb_tag`** `PoseStamped` publisher in the arena (subscriber is hard-coded BEST_EFFORT QoS).
- Camera model confirmed (**D435** = has RGB vs **D450** = no RGB; there is no D430 — changes the RGB/IR path).
- Gimbal physically straight down; drone **pre-yawed** toward your first-sweep direction before arming
  (takeoff point is fixed for all teams, but launch yaw is your choice). Battery ≥ 30% for a scored run.
- For Option B only: `moveit.py` pulled from the org Drive.

> **Transport — read once.** The **Ethernet cable** (or NoMachine/SSH) connects you to the drone's
> **onboard computer** (the companion Ubuntu box). The **PX4 flight controller is internal to that computer
> over serial** — MAVSDK reaches it at **`serial:///dev/ttyS6:921600`**, **NOT** over any network/Ethernet IP.
> The `udp://:14540` / `udp://:14550` entries in `--mavsdk-addresses` are **PX4 SITL / bench fallbacks only**
> and will never reach the real drone's FC. Run the controller *on the drone*, with **serial** addresses.

---

## 3. Bring-up sequence (run from `semifinal/`)

**Step 1 — env gate.** Deps import + announced dict resolves:
```bash
python3 -c "import cv2, numpy; from mapping_drone.mapping import ALL_SUPPORTED_DICT_NAMES as D; \
assert len(D)==20 and '7X7_1000' in D, D; print('deps OK, dicts:', len(D))"
python3 -m mapping_drone --help        # CLI parses (exit 0)
```

**Step 2 — code transfer** (if not already on the drone): USB → C2 Terminal → Ubuntu VM (shared folder /
USB passthrough per `thumbdrive/README.md`), then `bash setup.sh`. Pull `moveit.py` now if doing Option B.

**Step 3 — MAVSDK reachability, no-arm probe.** Use the fallback list so a dead/wrong `ttyS6` can't hang you:
```bash
python3 tools/mavsdk_probe.py --help     # confirm flags, then run with the canonical try order
# canonical order: serial:///dev/ttyS6:921600 , serial:///dev/ttyACM0:115200 ,
#                  serial:///dev/ttyUSB0:57600 , udp://:14540 , udp://:14550
```
The `serial://` entries are ports **on the drone's onboard computer** (FC is internal serial) — those are the
real ones at the venue. The `udp://` entries are **PX4 SITL / bench fallbacks** that cannot reach the real FC.

**Step 4 — UWB topic + axis check.** Confirm `/uwb_tag` publishes and the ENU→NED swap (n=pose.y, e=pose.x,
alt=−pose.z) matches the room. Physically move the tag and watch the signs:
```bash
python3 tools/uwb_sniffer.py    # Ctrl-C to stop
```

**Step 5 — RealSense + the no-RGB risk.** Confirm USB3 + depth:
```bash
python3 -c "import pyrealsense2 as rs; [print(d.get_info(rs.camera_info.name), \
d.get_info(rs.camera_info.usb_type_descriptor)) for d in rs.context().devices]"   # name + must read 3.x
python3 -m mapping_drone.tests.smoke_realsense_stationary --auto
```
**Confirmed fleet (user, 10/6): D435 + D450.** The `name` print tells you which one your drone has:
- **D435 → has RGB.** The existing color path works as-is. No patch. You're good.
- **D450 → no RGB.** `pipeline.start()` raises on every color profile → zero ArUco → no Challenge-1 output.
  The `--use-ir-for-aruco` fallback is **docstring-only (no CLI flag, no wiring)** — do **NOT** pass it,
  argparse will reject it. Apply the IR patch in [`D430_RGB_RISK.md`](D430_RGB_RISK.md) (infrared index 1,
  `emitter_enabled=0`, align to IR, IR intrinsics, synth grayscale→BGR) and add the flag, then re-smoke; or
  ask to be assigned a D435. (`runbook.md:120` wrongly tells you to pass the flag — ignore that line.)

Because the fleet is mixed and drones are **shared**, you may get a different camera between slots —
**re-check the model after every handoff** and keep the IR patch staged so a D450 reassignment isn't a scramble.

**Step 6 — stage dict + waypoints + validity.**
- Build the rectangular sweep (markers are offset from origin — confirm the UWB origin vs arena origin with
  the marshal first):
  ```bash
  cp configs/arena_8x8.json configs/waypoints_10jun.json
  # edit to a SERPENTINE sweep at z=4.0 m that passes over INTERIOR pads, not just the 4 corners, e.g.
  # [[0,0,4.0],[4.4,0,4.0],[4.4,1.5,4.0],[0,1.5,4.0],[0,3.0,4.0],[4.4,3.0,4.0],[4.4,4.4,4.0],[0,4.4,4.0],
  #  [0,5.9,4.0],[4.4,5.9,4.0],[4.4,7.4,4.0],[0,7.4,4.0],[0,7.85,4.0],[4.4,7.85,4.0]]
  # A bare 4-corner perimeter MISSES interior pads. Keep each leg <= ~9 m so the 30 s fly_to timeout
  # (controller.py:1069) at 0.3 m/s isn't hit mid-leg (which scans the wrong place).
  ```
  Validate it parses: `python3 -c "import json; w=json.load(open('configs/waypoints_10jun.json')); assert w and all(len(p)==3 for p in w); print(len(w),'waypoints')"`
  ⚠️ Do **not** use `waypoints_unknown.json` blindly — despite the README it's a stray populated 2×2 grid,
  not the documented empty fail-fast file.
- Wire the validity rule from the marshal (schema `{"valid_ids":[...],"invalid_ids":[...]}`):
  ```bash
  # if it's a list of valid/invalid IDs:
  cp configs/valid_ids_whitelist_example.json configs/valid_ids_10jun.json   # then edit the two lists
  export MAPPING_DRONE_VALIDITY=lookup
  export MAPPING_DRONE_VALIDITY_LOOKUP=configs/valid_ids_10jun.json
  # OR a built-in rule if it matches: MAPPING_DRONE_VALIDITY=odd|all_valid|id_below_50
  python3 -c "from mapping_drone.validity import describe_rule; print(describe_rule())"   # must NOT say 'even (default)'
  ```

**Step 7 — mock smoke (no hardware) gates the real run.**
```bash
# (a) flight-path + artifacts with the REAL dict (mock marker is 6X6 so expect 0 detections — that's OK here):
python3 -m mapping_drone --mock-all --aruco-dict 7X7_1000 \
  --waypoints-from-json configs/waypoints_10jun.json --max-flight-time-s 60 --runs-dir /tmp/bh_mock
ls /tmp/bh_mock/run_*/      # expect STATUS.txt, run_summary.json, top_down.png/.npy, landing_pads.json
# (b) detection path: the MockRealsense draws a 6X6_250 marker, so to actually see a sighting use:
python3 -m mapping_drone --mock-all --aruco-dict 6X6_250 --max-flight-time-s 30 --runs-dir /tmp/bh_mock6x6
```

**Step 8 — real subsystem health probe (NEVER arms).** The safe bring-up check the runbooks omit — exit 0 =
all three subsystems up, 2 = a failure:
```bash
python3 -m mapping_drone --dry-run --mavsdk-addresses \
"serial:///dev/ttyS6:921600,serial:///dev/ttyACM0:115200,serial:///dev/ttyUSB0:57600,udp://:14540,udp://:14550"
```
(`udp://:14540,udp://:14550` are PX4 SITL/bench fallbacks — at the venue only the `serial://` entries reach
the real FC; you can omit the udp ones on the drone.)

**Step 9 — scored run.** See §4. (The runbooks' "connect-only via `--max-flight-time-s 5`" actually ARMS
and FLIES — prefer `--dry-run` for a no-fly check.)

---

## 4. Scored-run launch command

```bash
cd semifinal/
MAPPING_DRONE_VALIDITY=lookup \
MAPPING_DRONE_VALIDITY_LOOKUP=configs/valid_ids_10jun.json \
python3 -m mapping_drone \
  --aruco-dict 7X7_1000 \
  --waypoints-from-json configs/waypoints_10jun.json \
  --gimbal-pitch -90 \
  --mavsdk-addresses "serial:///dev/ttyS6:921600,serial:///dev/ttyACM0:115200,serial:///dev/ttyUSB0:57600,udp://:14540,udp://:14550" \
  --max-flight-time-s 420 \
  --runs-dir mapping_drone/runs
```
- Real mode is implicit (no `--real` needed). Run inside **`tmux`** so a NoMachine drop doesn't kill the flight.
- Add `--tailscale` for live log fan-out to the desktop sink; `--verbose` to promote per-tick/per-leg lines.
- If the marshal gives a built-in rule, drop the lookup env and set `MAPPING_DRONE_VALIDITY=<rule>`.
- This launches the **existing velocity path** — only fly it if you did NOT swap in `set_position_ned`.
- The `udp://:14540,udp://:14550` addresses are **SITL/bench fallbacks**; on the real drone only the
  `serial://` entries reach the flight controller (FC is internal serial). Drop the udp ones at the venue.

---

## 5. Preflight checks (before arming)

| Check | Command | Pass |
|-------|---------|------|
| CLI parses | `python3 -m mapping_drone --help` | exit 0 |
| 20 dicts incl. 7X7_1000 | `python3 -c "from mapping_drone.mapping import ALL_SUPPORTED_DICT_NAMES as D; print(len(D)); assert '7X7_1000' in D"` | `20`, no error |
| Validity NOT the placeholder | `python3 -c "from mapping_drone.validity import describe_rule; print(describe_rule())"` (with env set) | names `lookup`/your rule, not `even (default)` |
| Validity sanity on real IDs | `python3 -c "from mapping_drone.validity import decide_landing_validity as v; print({i:v(i) for i in (11,45,51,67,101)})"` (with env set) | matches marshal's rule (under default `even` all 5 = False — the trap) |
| Waypoints parse + rectangle | `python3 -c "import json;w=json.load(open('configs/waypoints_10jun.json'));assert w and all(len(p)==3 for p in w);print(len(w))"` | prints count |
| UWB axis swap | `python3 tools/uwb_sniffer.py` (move tag ~10 s) | n/e signs match room |
| RealSense USB3 + depth | step 5 commands | name printed, `3.x`, depth non-zero |
| MAVSDK link | `tools/mavsdk_probe.py` with try order | exit 0 = a link is up |

---

## 6. After takeoff — what to watch (in `runs/run_<ts>/log.txt` or `--tailscale`)

- `connected via <addr>` → health gate (`is_local_position_ok` AND `is_armable`) → `arm` →
  `set_takeoff_altitude(3.6)` → `offboard.start()` OK → `MISSION` → `SCAN_WP_n` for each waypoint.
- **Per-leg "reached" vs timeout.** A `fly_to` leg that hits the hard-coded 30 s timeout returns False but
  is **not** an abort ([controller.py:1069](mapping_drone/controller.py#L1069)) — the drone then scans in the
  *wrong place*. Keep legs short enough that 30 s @ 0.3 m/s suffices (≤ ~9 m).
- Watchdogs that abort+land: UWB loss >5 s, never-fix >8 s airborne, position-stuck (>30 s & <0.3 m move,
  suppressed during scans), battery <15%, 5 consecutive `set_velocity_ned` failures.
- **Artifacts** in `mapping_drone/runs/run_<ts>/`: `STATUS.txt` (`State=DONE`, not ABORTED), `landing_pads.json`
  (IDs from {11,45,51,67,101} with correct VALID/INVALID), `top_down.png`+`.npy`, `markers/marker_<id>_<seq>.jpg`,
  `run_summary.json` (`aborted=false`). If every pad reads INVALID you shipped the `even` placeholder — re-run.
- **Copy the whole `run_<ts>/` dir off the drone to BOTH USBs immediately** (drones are shared; never overwrite).

---

## 7. Open questions for the marshal (Day-1 morning, verbal)

1. **Real validity rule** for IDs 11/45/51/67/101 (all odd — our default marks them all invalid).
2. **Is `set_position_ned` actually enabled now**, and can we get `moveit.py` from the Drive?
3. **Arena dimensions + coordinate origin + UWB anchor frame** (markers start at ~x1.3/y4.4, not 0,0 — sets
   our waypoint corners; OccupancyGrid is a fixed ±10 m about origin, points beyond are dropped).
4. ~~Camera module on the actual drone~~ **RESOLVED (user 10/6): fleet is D435 + D450.** Still ask: which is
   on *your assigned* drone (D435 = RGB OK; D450 = needs the IR patch), and did org bolt a separate RGB
   camera onto the D450?
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

- `runbook.md:120` (a SEPARATE file from `DAY1_RUNBOOK.md`) — tells you to pass `--use-ir-for-aruco`; that
  flag does **not** exist (argparse rejects it — docstring-only). `DAY1_RUNBOOK.md:39`/`:139` correctly say
  NOT to pass it. (Prefer section anchors over line numbers — they drift.)
- `mapping_drone/README.md` validity section lists 5 rules; there are **6** (adds `lookup` — verified in
  `validity.py`). Use `lookup` for an ID whitelist.
- `configs/waypoints_unknown.json` documented as an empty fail-fast trap; on disk it's a stray populated 2×2.
- `DAY1_SETUP_SEQUENCE.md` / earlier docs assume velocity flying + dict-TBD; both are now superseded
  (set_position_ned preferred; dict = 7X7_1000).
- Several runbook references call `swarm_controller.py` "NOT YET BUILT" — it is built (off today's path).

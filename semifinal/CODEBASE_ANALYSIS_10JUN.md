# semifinal/ — full-tree analysis (10 June 2026)

Produced by a 10-agent fan-out audit of every file in `semifinal/` (~110 files), reconciled against the
10-June org guidance. Companion to [`MAPPING_DRONE_SETUP_GUIDE.md`](MAPPING_DRONE_SETUP_GUIDE.md) (the
operator guide) and [`downloaded stuff/`](downloaded%20stuff/) (the org drops).

## Overview

Two independent drone systems plus heavy planning/reference scaffolding. **Today's critical path is the
Challenge-1 mapping drone** — a runnable Python package (`mapping_drone/`) that connects MAVSDK to PX4,
arms, takes off to ~4 m, flies a waypoint survey, scans RealSense frames for ArUco landing-pad markers,
builds a top-down occupancy/depth map, classifies pads valid/invalid, and writes judge artifacts under
`runs/run_<ts>/`. The second system is the **Hula swarm** (Challenge 2: `swarm_controller.py` + pyhulax +
USB-serial UWB) — built but unrun and off today's path. The dominant theme is **doc/code/guidance drift**:
the code was built against 3-June guidance, and the 10-June guidance reverses the single biggest design
decision (navigation) and announces concrete parameters (dict, IDs, arena) that none of the current
defaults or configs match. **The code is sound and well-instrumented but needs targeted reconciliation
before a scored run, and two pre-existing P0 blockers remain unresolved in source.**

## Subsystem map

| Subsystem | State | One-line |
|-----------|-------|----------|
| `mapping_drone/controller.py` (+`__main__`,`__init__`) | **built** | Full asyncio mission: MAVSDK connect/arm/takeoff (3.6 m), velocity waypoint nav, watchdogs, Ctrl-C land, argparse, MockMavsdk, `--dry-run`. **Velocity-only — zero `set_position_ned`.** Single-addr connect blocks forever w/o timeout. |
| `mapping_drone/{mapping,realsense,uwb,validity,run_writer}.py` | **built, 2 P0 stubs** | ArucoDetector (20 dicts), OccupancyGrid+camera_to_world, RealSense (RGB-only), ROS2 uwb_tag sub (ENU→NED), validity (placeholder `even`), atomic RunWriter. P0: no-RGB IR fallback is docstring-only; validity unpublished. |
| `mapping_drone/tests/` + FIX/REVIEW summaries | **built, mock-only** | 4 print-PASS smoke scripts + 3 audit logs. No pytest/CI. No `--real` / camera_to_world-pitch / yaw coverage. `smoke_realsense_stationary --auto` is the only HW test. |
| `learning_material_3_uwb/` (kolomee.py) + `tools/` | reference + **built probes** | kolomee.py = org velocity reference our controller copied (buggy as shipped, reference-only). `mavsdk_probe.py`/`uwb_sniffer.py` = bench-safe Day-1 probes. `moveit.py` (new org ref) is NOT in tree. |
| `learning_material_4_realsense/` | reference | RealSense cookbook. `generateTopDown.py` = occupancy-grid template. Most scripts enable RGB → throw on D430/D450; only `getInfra.py` + depth-only run. |
| `learning_material_5_yolo_rknn/` | reference (**dead for finals**) | PT→ONNX→RKNN + NPU YOLO. Backup-only (YOLO killed 6/6; mapping uses ArUco). Not runnable as-is (yolov8/v11 mismatch); no model artifacts. |
| `runbook.md`, `DAY1_*`, `thumbdrive/` | **built, stale content** | Day-of procedure. Drifts: calls swarm "NOT YET BUILT" (it's built), `waypoints_unknown.json` "empty trap" (it's a 2×2), `runbook.md:120` says pass `--use-ir-for-aruco` (rejected by argparse), routes to an arming smoke instead of `--dry-run`. |
| briefs/plans/risk docs | reference (no code) | `finals_brief_extracted.md` (authoritative rules/scoring), CHALLENGE_BREAKDOWN, FINALS_PLAN, SCORING_PLAYBOOK, D430_RGB_RISK, HANDOFF_C1_TO_C2. Correct in intent but predate 10-June guidance. |
| `configs/*.json` | **built, mismatched** | Waypoints (arena_3x3/4x4/6x6/8x8, 2x2_default) all square @ z=4.0; validity lookup tables. No template matches the ~4.4×7.85 m rectangle; `valid_ids_unknown.json` ships empty. |
| swarm + prototypes | **built (swarm, unrun)** / reference | `swarm_controller.py` built but never run (TODO placeholders, pyhulax not installed, import path bug). `dola.py`/`UWBParserThread.py` standalone-runnable. `prototypes/aruco_*` — webcam works; the realsense `--ir-mode` emitter-off pattern is the reference for the unbuilt mapping IR fallback. Orthogonal to today. |

## Mapping-drone readiness: NOT READY TO SCORE AS-IS

Flyable in mock today; needs these before a real scored run (full detail + commands in the setup guide):

1. **Navigation reversal (highest impact).** Org mandates `set_position_ned`; controller is 100% velocity
   (`set_velocity_ned` [controller.py:702](mapping_drone/controller.py#L702)/[:815](mapping_drone/controller.py#L815)).
   `moveit.py` not pulled. Real code change — keep velocity as the tested fallback.
2. **ArUco dict** — easy: `--aruco-dict 7X7_1000` (already supported, [controller.py:1743](mapping_drone/controller.py#L1743)).
3. **Validity broken for these markers** — default `even` ([validity.py:56](mapping_drone/validity.py#L56))
   marks all five ODD IDs INVALID. Wire the real rule via `MAPPING_DRONE_VALIDITY[/ _LOOKUP]`. **Do not fly the default.**
4. **Arena/waypoints** — markers imply ~4.4×7.85 m; no config matches. Hand-edit a rectangle from `arena_8x8.json`.
5. **Camera no-RGB (P0)** — fleet confirmed **D435 + D450** (user 10/6). **D435 has RGB → color path works.**
   **D450 has no RGB** → RGB-only pipeline raises → zero ArUco → no deliverable; IR fallback is docstring-only
   (patch per `D430_RGB_RISK.md`). Drones are shared, so re-check the model per handoff. A
   `--dry-run --mock-realsense` check is GREEN while a real D450 fails (false-confidence trap).
6. **Altitude** — already compliant (4.0 m waypoints above the 3.5 m floor; takeoff 3.6 m).

Operationally: real mode is default; reach the drone via NoMachine from C2; launch from `semifinal/`
(CWD-relative paths); **always** use `--mavsdk-addresses` (bare `ttyS6` default hangs forever). Crash = no
re-assessment, so Run 1 must be the safe config.

## What works (verified runnable)

- Mock end-to-end mission (`python3 -m mapping_drone --mock-all`) — arms, flies, scans, writes artifacts.
- Velocity flight control + P-controllers + `hover_for` (tested in mock; safe fallback).
- Safety: pre-arm health gate, 0.3 m/s hard cap, battery/UWB-loss/position-stuck watchdogs, 5-fail abort,
  Ctrl-C → emergency_land + disarm, offboard 20× zero-setpoint pre-warm.
- Multi-address MAVSDK fallback walker (5 s/addr) + `tools/mavsdk_probe.py`.
- RunWriter atomic judge artifacts (crash/SIGTERM-safe — `smoke_abort`, `smoke_kill_mid_run`).
- `--aruco-dict` accepts `7X7_1000` + all 20 dicts (case-insensitive, optional `DICT_` prefix).
- Validity swap via env var (`even`/`odd`/`all_valid`/`all_invalid`/`id_below_50`/`lookup`) — no code edit.
- Mock infra (MockMavsdk/Uwb/Realsense; Realsense draws a 6X6_250 marker) + `--dry-run` health probe.
- UWB ENU→NED handling (thread-safe, matches kolomee + sniffer). Standalone: `dola.py`, `UWBParserThread.py`,
  `prototypes/aruco_webcam.py`.

## What is stub / incomplete

- `set_position_ned` navigation — not implemented; `moveit.py` absent.
- D430/D450 IR-for-ArUco fallback — docstring-only; no flag/wiring; **no working ArUco path on a no-RGB camera.**
- Validity rule — placeholder `even`; `valid_ids_unknown.json` empty (lookup no-ops until populated).
- Rectangular arena waypoint config — does not exist; templates square/origin-anchored.
- `configs/waypoints_unknown.json` — stray populated 2×2, not the documented empty trap.
- Real-path test coverage — none for `--real`, camera_to_world pitch math (2 prior CRITICAL bugs), or yaw.
- Depth-map metric accuracy (15% of C1) — may emit camera-relative not world-frame metric depth; unverified.
- Swarm `swarm_controller.py` — built but never run (placeholders, pyhulax missing, import-path bug).
- YOLO-RKNN (L5) — dead code; not runnable as-is; no artifacts.

## Cross-cutting risks

- **Navigation reversal** vs limited shared-drone test window → high risk of running out of time; keep velocity fallback.
- **Announced markers break the default validity rule** (all odd → all invalid = worst possible 15% score).
- **P0 D430/D450 no-RGB** → false-confidence trap (mock GREEN, real FAILS); whole C1 deliverable at risk.
- **Pervasive doc/code/config drift** — operators trusting runbooks blind will hit failures.
- **Single-address MAVSDK hang** — bare `ttyS6` default blocks indefinitely; always pass `--mavsdk-addresses`.
- **Arena size/origin mismatch** — 2×2 default under-surveys; markers offset from origin → confirm UWB frame.
- **CWD-relative paths** — launch from the wrong dir scatters artifacts / breaks config resolution.
- **Coordinate-frame/yaw uncertainty** — ENU/NED + camera-down + free launch-yaw compound; pitch math untested.
- **Crash = no re-assessment + shared drones + compressed schedule** → conservatism mandatory; Run 1 = safe config.
- **Missing deps/artifacts in dev env** — pyrealsense2/pyhulax not installed; moveit.py/.rknn absent → real-path
  verification deferred to Day-1 under time pressure.
- **Top-level KeyboardInterrupt gap** — a KI escaping the SIGINT handler finalises the run but does NOT command
  a land ([controller.py:1868](mapping_drone/controller.py#L1868)); use a single clean Ctrl-C only.

---
*Audit: 10 parallel readers + 2 synthesis agents over the full tree, 10 June 2026.*

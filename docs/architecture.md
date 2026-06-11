---
layout: default
title: Architecture
---

# System architecture

> Both halves share the **same arena UWB frame** (origin = centre). Code is organised as one repository with a strict adapter boundary at every hardware dependency, so every module has a mock that lets the whole pipeline run laptop-only.

[← Back to home]({{ '/' | relative_url }})

---

## Challenge 1 — Mapping drone

`mapping_drone/` runs on the drone's onboard Orange Pi (Ubuntu 22.04 + ROS2 + MAVSDK over `serial:///dev/ttyS6:921600`).

```
                 ┌──────────── moveit_mission.py (ORCHESTRATOR, MAVSDK ttyS6) ───────────┐
                 │  arm → offboard → takeoff → lawnmower waypoints → scan → land          │
                 │  + safety watchdogs (battery / pose-loss / stuck / setpoint) + alt clamp│
                 └──────┬───────────────────────┬───────────────────────┬───────────────┘
        POSE  ◄────────┤                        │ PERCEPTION             │ OUTPUT
   ┌───────────────────┴───────┐      ┌─────────┴──────────┐    ┌────────┴───────────┐
   │ uwb.py   (/uwb_tag ENU→NED)│      │ realsense.py       │    │ run_writer.py      │
   │ px4_ros.py (/fmu local pos)│      │  RGB ↔ IR auto-fb  │    │  landing_pads.json │
   │ MAVSDK telemetry (FC NED)  │      └─────────┬──────────┘    │  top_down.png/.npy │
   │  → --pose auto (FC ↔ UWB)  │                ▼               │  STATUS, summary   │
   └────────────────────────────┘      ┌────────────────────┐   └────────────────────┘
                                       │ mapping.py         │
                                       │  multi-dict ArUco  │
                                       │  + camera → world  │
                                       │  + occupancy grid  │──► validity.py (valid / invalid / unknown)
                                       └────────────────────┘

   px4_mission.py = MAVSDK-free sibling (same vision stack, PX4-ROS2 flight).
   Tools: survey_box.py (measure frame), drone_fingerprint.sh, requirements.sh.
```

**Module roles:**

- **`moveit_mission.py`** — the orchestrator: MAVSDK offboard, the closed-loop velocity-profiled waypoint controller, per-waypoint scan, safety watchdogs, altitude clamp. `px4_mission.py` is its MAVSDK-free twin over micro-XRCE-DDS (`px4_ros.py` reads `/fmu/out/vehicle_local_position` and drives offboard via `/fmu/in/*`).
- **Pose** is abstracted so the mission consumes one `(n, e, down, yaw, ready)` tuple regardless of source. `--pose auto` prefers FC fused NED and auto-falls-back to UWB. `uwb.py` does the ENU→NED axis swap.
- **`realsense.py`** delivers frames, auto-falling back from RGB to synthesised IR-BGR for no-RGB cameras.
- **`mapping.py`** is the vision core: scans *two* ArUco dictionaries per frame, deprojects each marker + depth pixel into the world frame, and accumulates a tri-state top-down occupancy grid.
- **`validity.py`** classifies each pad via a lookup table populated from the marshal's announcement.
- **`run_writer.py`** owns the run directory and persists judge artifacts atomically on every update (`landing_pads.json`, `top_down.png`, `top_down.npy`, `STATUS.txt`, `run_summary.json`, marker JPEGs).

---

## Challenge 2 — Hula swarm

Runs on the C2 Terminal (Windows host + Ubuntu VM) talking to three Hula drones over Wi-Fi via `pyhula`.

```
 dola.py (UDP discovery: plane_id → IP)
        │
        ▼
 swarm_controller.py  ── per-drone state machine ──────────────────────────────
   Phase A (DEPLOY): UWB-guided flight to valid landing zones → land in hoop
   Phase B (HUNT):   perimeter waypoints + 360° spin-scan over the arena
        │  position from ──► UWBParserThread.py  (serial UWB: tag_id → x, y)
        │  motion via ─────► pyhula  send_manual_control
        ▼
   central video: all drones' streams aggregated on ONE computer → ArUco
   detection of the RoboMaster markers (huladola.py is the multi-stream pattern)
```

**Module roles:**

- **`dola.py`** — UDP beacon listener resolving each plane's ID to its IP before connecting.
- **`swarm_controller.py`** — the swarm brain: connects N drones, runs a per-drone state machine (deploy → hunt), and drives motion via `pyhula`.
- **`UWBParserThread.py`** — background serial thread parsing UWB packets into a `tag_id → (x, y, t)` table for arena positioning.
- **`huladola.py`** — the reference pattern for pulling every drone's video onto one machine so detection runs centrally.

---

## The C1 → C2 handoff

C1 writes `landing_pads.json` (ArUco ID, world XYZ, valid / invalid). C2A takes the org's published landing coordinates as ground truth and uses the recon artifact as the cross-check (which IDs were valid, and where).

**Both stages live in the arena UWB frame (origin = centre)** so the handoff is a coordinate lookup, not a re-survey.

---

## Development boundary

Every hardware dependency sits behind a small interface (`UwbAdapter`, `RealsenseAdapter`, a flight layer), each with a mock (`MockUwbNode`, `MockRealsenseNode`). The entire C1 pipeline runs and is regression-tested on a laptop with no drone attached, via:

```
python -m mapping_drone --mock --max-flight-time-s 30
```

Smoke tests exercise the end-to-end paths (multi-tag detection, mid-run abort, kill-mid-run finalisation) so we catch regressions off-hardware.

[Challenge 1 deep dive →]({{ '/c1-mapping' | relative_url }})
&nbsp; · &nbsp;
[Challenge 2 deep dive →]({{ '/c2-swarm' | relative_url }})

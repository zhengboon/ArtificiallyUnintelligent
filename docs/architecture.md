---
layout: default
title: Architecture
description: System architecture of the mapping drone + Hula swarm. Module-by-module module roles and the C1 → C2 handoff.
---

# System architecture

<p align="center">
<a href="{{ '/' | relative_url }}">← Home</a> &nbsp;·&nbsp;
<a href="#challenge-1--mapping-drone">C1 mapping</a> &nbsp;·&nbsp;
<a href="#challenge-2--hula-swarm">C2 swarm</a> &nbsp;·&nbsp;
<a href="#the-c1--c2-handoff">Handoff</a> &nbsp;·&nbsp;
<a href="#development-boundary">Dev boundary</a>
</p>

> Both halves share the **same arena UWB frame** (origin = centre). Every hardware dependency sits behind a small adapter interface with a mock — so the whole pipeline runs on a laptop, no drone required.

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

### Module roles

| Module | Responsibility |
|---|---|
| `moveit_mission.py` | Orchestrator — MAVSDK offboard, closed-loop velocity-profiled waypoint controller, per-waypoint scan, safety watchdogs, altitude clamp. |
| `px4_mission.py` | MAVSDK-free twin over micro-XRCE-DDS — same vision stack, PX4-ROS2 flight only. |
| `px4_ros.py` | Reads `/fmu/out/vehicle_local_position` and drives offboard via `/fmu/in/*`. |
| `uwb.py` | UWB adapter — ROS2 subscriber on `/uwb_tag`; ENU → NED axis swap (single source of truth). |
| `realsense.py` | RealSense adapter — auto-fallback from RGB to synthesised BGR-from-IR for no-RGB cameras. |
| `mapping.py` | Vision core — multi-dict ArUco, camera→world transform, occupancy grid. |
| `validity.py` | Pad classifier — lookup table populated from the marshal's announcement. |
| `run_writer.py` | Run-directory writer — atomic writes of `landing_pads.json`, `top_down.png/.npy`, `STATUS.txt`, `run_summary.json`, marker JPEGs. |

> 💡 **`--pose auto` is the killer feature.** The mission consumes one `(n, e, down, yaw, ready)` tuple regardless of source. The adapter prefers FC fused NED, auto-falls-back to UWB when the FC stream degrades, and holds position if both go stale.

---

## Challenge 2 — Hula swarm

Runs on the C2 Terminal (Windows host + Ubuntu VM) talking to three Hula drones over Wi-Fi via `pyhula`.

<p align="center">
<img src="images/swarm-controller-live.jpg" alt="Laptop screen during Day 2 — VS Code with swarm_controller.py open, the per-drone state machine printing STATE_FLY_TO_ZONE in the terminal, and an opened detection JPEG showing a green-bbox ArUco marker pinned to the side of a RoboMaster captured by the Hula's down-camera" width="720">
<br><sub><i>Day 2 · live: the swarm controller's per-drone state machine (terminal) and a fresh ArUco detection on a RoboMaster body (image preview)</i></sub>
</p>

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

### Module roles

| Module | Responsibility |
|---|---|
| `dola.py` | UDP beacon listener resolving each Hula's plane-ID to its IP before connect. |
| `swarm_controller.py` | Swarm brain — connects N drones, per-drone state machine (deploy → hunt), motion via `pyhula`. |
| `UWBParserThread.py` | Background serial thread, parses UWB packets into `tag_id → (x, y, t)` table. |
| `huladola.py` | Reference pattern for pulling every drone's video onto one machine. |

> 💡 **Why a single central detector?** Multi-stream from one machine simplifies dedup (one detection table, not three) and lets us add expensive visual sanity checks (multi-frame confirmation) cheaply.

---

## The C1 → C2 handoff

C1 writes `landing_pads.json` (ArUco ID, world XYZ, valid / invalid). C2A takes the org's published landing coordinates as ground truth and uses the recon artifact as the cross-check (which IDs were valid, and where).

> **Both stages live in the arena UWB frame (origin = centre)** so the handoff is a coordinate lookup, not a re-survey.

---

## Development boundary

Every hardware dependency sits behind a small interface (`UwbAdapter`, `RealsenseAdapter`, a flight layer), each with a mock (`MockUwbNode`, `MockRealsenseNode`). The entire C1 pipeline runs and is regression-tested on a laptop with no drone attached:

```bash
python -m mapping_drone --mock --max-flight-time-s 30
```

Smoke tests exercise the end-to-end paths — multi-tag detection, mid-run abort, kill-mid-run finalisation — so we catch regressions off-hardware.

---

<p align="center">
<a href="{{ '/' | relative_url }}">← Home</a>
&nbsp;·&nbsp;
<a href="{{ '/c1-mapping' | relative_url }}">Challenge 1 deep dive →</a>
&nbsp;·&nbsp;
<a href="{{ '/c2-swarm' | relative_url }}">Challenge 2 deep dive →</a>
</p>

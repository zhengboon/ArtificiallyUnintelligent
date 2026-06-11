# Concept Plan — ArtificiallyUnintelligent (RoboVerse Drone Challenge)

*How we think about the problem, the workflow we built around it, and the
software architecture that implements it.*

The mission is two-stage: **Reconnaissance (C1)** — autonomously map the arena
and classify landing pads — then **Deployment & Ambush (C2)** — land a Hula
swarm on the valid pads and hunt the convoy of ground robots. Our whole design
treats these as **one intelligence-driven pipeline sharing one coordinate
world**, not two separate problems.

---

## 1. How we think (design philosophy)

Five principles drove every decision:

1. **Intelligence drives the strike.** C1 isn't a standalone deliverable — its
   map + per-pad validity directly seed C2's landing targets. We designed the
   C1 output (`landing_pads.json`) as a *contract* the C2 swarm consumes.
2. **Coverage over cleverness.** Both stages use **deterministic full-coverage
   search** — a lawnmower sweep for mapping, wall-following + 360° scan for the
   hunt — instead of reactive exploration/SLAM. It's predictable, debuggable,
   and *immune to the see-through netting* that defeats depth-based obstacle
   sensing (we never rely on detecting a wall we can't see).
3. **Degrade, don't fail.** Every critical path has a fallback so a single
   sensor/link problem *downgrades* a run instead of ending it: pose (FC fused
   NED ↔ UWB), camera (RGB ↔ infrared), marker dictionary (7×7 ↔ 6×6),
   transport (MAVSDK ↔ PX4-ROS2).
4. **Safe-first, because a crash means no re-assessment.** Hard altitude cap
   below the cage net, speed caps, and in-flight watchdogs (battery / pose-loss
   / position-stuck / link-failure) that auto-land. Safety is *in the control
   loop*, not a checklist.
5. **Frame discipline.** The single hardest part of an indoor UWB mission is
   *which frame is which*. We make the coordinate model explicit everywhere
   (UWB origin = arena centre, FC-NED, ENU↔NED swap) and provide a tool to
   **measure** the frame rather than assume it.

---

## 2. Workflow

### Development workflow
- **Modular package with swappable adapters.** Every hardware dependency sits
  behind a small interface (`UwbAdapter`, `RealsenseAdapter`, a flight layer),
  each with a **mock** (`MockUwbNode`, `MockRealsenseNode`) so the entire C1
  pipeline runs and is tested on a laptop with no drone attached.
- **Smoke tests** exercise the end-to-end paths (multi-tag detection, mid-run
  abort, kill-mid-run finalisation) so we catch regressions off-hardware.
- **Adversarial review.** We hardened the code with multi-pass, line-by-line
  reviews where a second reviewer must *confirm* each finding before it's
  fixed — which is how we caught silent killers (a validity rule that marked
  every real pad invalid, a broken no-RGB camera path, an altitude default
  above the net).

### Day-of operating workflow (one loop, fail-fast)
```
requirements.sh        → deps + READY/NOT-READY
drone_fingerprint.sh   → per-drone hardware check (camera/FC/serial/UWB)
--check                → connect + pose, no arm
--nofly                → camera + ArUco + map, no arm   (proves detection works)
survey the frame       → measure arena↔NED, generate centred waypoints
--fly                  → autonomous lawnmower sweep
retrieve artifacts     → top_down.png + landing_pads.json → hand to C2
```
Each step is read-only w.r.t. the next risk, so we never arm before pose is
confirmed and never fly before detection is confirmed. (Full decision tree with
fallbacks: `OP_DOC.md`.)

---

## 3. Software architecture

### C1 — mapping drone (`mapping_drone/` package, Orange Pi, ROS2/MAVSDK)

```
                 ┌──────────── moveit_mission.py (ORCHESTRATOR, MAVSDK ttyS6) ───────────┐
                 │  arm → offboard → takeoff → lawnmower waypoints → scan → land          │
                 │  + safety watchdogs (battery/pose-loss/stuck/setpoint) + alt clamp     │
                 └──────┬───────────────────────┬───────────────────────┬───────────────┘
        POSE  ◄────────┤                        │ PERCEPTION             │ OUTPUT
   ┌───────────────────┴───────┐      ┌─────────┴──────────┐    ┌────────┴───────────┐
   │ uwb.py   (/uwb_tag ENU→NED)│      │ realsense.py       │    │ run_writer.py      │
   │ px4_ros.py (/fmu local pos)│      │  RGB↔IR auto-fallbk │    │  landing_pads.json │
   │ MAVSDK telemetry (FC NED)  │      └─────────┬──────────┘    │  top_down.png/.npy │
   │  → --pose auto (FC↔UWB)    │                ▼               │  STATUS, summary   │
   └────────────────────────────┘      ┌────────────────────┐   └────────────────────┘
                                       │ mapping.py         │
                                       │  multi-dict ArUco  │
                                       │  + camera→world    │
                                       │  + occupancy grid  │──► validity.py (valid/invalid/unknown)
                                       └────────────────────┘
   px4_mission.py = MAVSDK-free sibling (same vision stack, PX4-ROS2 flight).
   Tools: survey_box.py (measure frame), drone_fingerprint.sh, requirements.sh.
```

**Module roles:**
- **`moveit_mission.py`** — the orchestrator: MAVSDK offboard, the closed-loop
  velocity-profiled waypoint controller, per-waypoint scan, the safety
  watchdogs, and the altitude clamp. `px4_mission.py` is its MAVSDK-free
  twin over micro-XRCE-DDS (`px4_ros.py` reads `/fmu/out/vehicle_local_position`
  and drives offboard via `/fmu/in/*`).
- **Pose** is abstracted so the mission consumes one `(n,e,down,yaw,ready)`
  tuple regardless of source; `--pose auto` prefers FC fused NED and falls back
  to UWB. `uwb.py` does the ENU→NED axis swap.
- **`realsense.py`** delivers frames, auto-falling back from RGB to synthesised
  IR-BGR for no-RGB cameras. **`mapping.py`** is the vision core: scans *two*
  ArUco dictionaries per frame, deprojects each marker/depth pixel into the
  world frame, and accumulates a tri-state top-down occupancy grid.
  **`validity.py`** classifies each pad via a lookup table.
- **`run_writer.py`** owns the run directory and persists the judge artifacts
  atomically on every update.

### C2 — Hula swarm (C2 Terminal: Windows + Ubuntu VM, `pyhula`)

```
 dola.py (UDP discovery: plane_id → IP)
        │
        ▼
 swarm_controller.py  ── per-drone state machine ──────────────────────────────
   Phase A (DEPLOY): UWB-guided flight to valid landing zones → land in hoop
   Phase B (HUNT):  perimeter waypoints + 360° spin-scan over the arena
        │  position from ──► UWBParserThread.py (serial UWB: tag_id → x,y)
        │  motion via ─────► pyhula send_manual_control
        ▼
   central video: all drones' streams aggregated on ONE computer → ArUco
   detection of the RoboMaster markers (huladola.py is the multi-stream pattern)
```

**Module roles:**
- **`dola.py`** — UDP beacon listener resolving each plane's ID to its IP before
  connecting.
- **`swarm_controller.py`** — the swarm brain: connects N drones, runs a
  per-drone state machine (deploy → hunt), and drives motion via `pyhula`.
- **`UWBParserThread.py`** — background serial thread parsing UWB packets into a
  `tag_id → (x, y, t)` table for arena positioning.
- **`huladola.py`** — the reference pattern for pulling every drone's video onto
  one machine so detection runs centrally.

### The C1 → C2 handoff
C1 writes `landing_pads.json` (ArUco ID, world XYZ, valid/invalid). C2A takes the
org's Discord-published landing coordinates as ground truth and uses the recon
artifact as the cross-check (which IDs were valid, and where). **Both stages live
in the arena UWB frame (origin = centre)** so the handoff is a coordinate lookup,
not a re-survey.

---

## 4. Implementation — the algorithms

- **Coverage (C1):** a pre-planned **boustrophedon (lawnmower)** sweep — lanes
  centred on the arena origin with a wall margin; geometry guarantees full
  coverage with no wall-sensing.
- **Navigation (C1):** **closed-loop velocity control** — read pose → compute
  error to the waypoint → send a velocity-profiled NED setpoint (capped at the
  0.3 m/s limit, trapezoidal slow-down into each point). This is the
  org-recommended "poll position → velocity command" loop.
- **Mapping (C1):** per waypoint, deproject the down-facing depth point cloud
  into the world frame and bin it into a top-down occupancy grid → `top_down.png`.
- **Detection + classification (C1):** scan ArUco `DICT_7X7_1000` **and**
  `6X6_250` every frame, depth-deproject each marker to world XYZ, de-duplicate,
  and classify valid / invalid / **unknown** from the marshal's ID split.
- **Deploy (C2A):** UWB-guided positioning of each Hula over its landing zone,
  then a controlled descent with the pad's ArUco as a final visual aid.
- **Hunt (C2B):** wall-following + 360° spin-scan covers the cage without
  overflying obstacles; all video is detected centrally; 2–3 confirming frames
  per RoboMaster tag.

---

## 5. Engineering decisions & trade-offs

| Decision | Why | Trade-off accepted |
|---|---|---|
| Lawnmower / wall-follow, **not SLAM** | predictable, immune to see-through net | no adaptive re-routing |
| Pose **redundancy** (FC↔UWB, auto) | DDS/UWB can drop on a shared network | extra telemetry plumbing |
| **Scan two ArUco dicts** | the announced dict was a late, single-source fact | ~2× detect cost/frame (cheap) |
| Camera **RGB↔IR auto-fallback** | mixed fleet (D435 has RGB, D450 doesn't) | IR has no colour, fine for ArUco |
| **Hard altitude cap** below the net | crash = no re-assessment | small usable-height loss |
| Safety **watchdogs in the loop** | autonomy must self-recover | conservative early landings |
| **Measure the frame** (survey tool) | indoor UWB frame is the #1 failure mode | a setup step before flying |

---

*Team: C1 mapping (Z) · C2 swarm deploy + hunt (K) · operations + concept (A).
Single repo, one coordinate world, intelligence-driven from recon to ambush.*

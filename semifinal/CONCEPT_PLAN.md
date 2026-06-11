# RoboVerse Drone Challenge — Concept Plan (ArtificiallyUnintelligent)

*Concept explanation for submission. Mission: gather intelligence on an enemy
transport convoy (Reconnaissance), then deploy and ambush it (Deployment &
Ambush).*

---

## 1. Mission concept

The operation is a two-stage intelligence-and-strike mission against an enemy
convoy:

1. **Reconnaissance (Challenge 1)** — a single autonomous **mapping drone**
   sweeps the arena, builds a top-down map of obstacles and landing pads, and
   deciphers the ArUco marker beside each pad to decide whether the landing
   site is **valid or invalid**. This is the intelligence picture.
2. **Deployment & Ambush (Challenge 2)** — a **swarm of Hula drones**, informed
   by that intelligence, (2A) **lands precisely within the valid landing
   zones**, then (2B) **hunts the moving convoy of ground robots and ArUco-tags
   each one** for confirmation.

The two stages share one coordinate world (the arena UWB frame), so the recon
output drops directly into the strike plan.

---

## 2. System architecture

| Element | Role | Compute | Key sensors/links |
|---|---|---|---|
| **Mapping drone** (C1) | survey + classify | Orange Pi RK3588 (Ubuntu 22.04, ROS2) | RealSense depth cam, UWB tag, PX4 FC (MAVSDK offboard, 5.88 GHz) |
| **Hula swarm** (C2) | land + hunt | C2 Terminal (Windows + Ubuntu 22.04 VM) | per-drone camera, UWB tags, `pyhula` over Wi-Fi |
| **C2 Terminal** | swarm brain | one laptop | aggregates all drone video for central detection; ingests UWB + sends nav setpoints |

Remote access to the mapping drone is via **NoMachine** over the C2 terminal.

---

## 3. Challenge 1 — Reconnaissance (mapping drone)

**Goal:** a top-down depth map + per-pad ArUco imagery, each landing site
classified valid/invalid.

**Approach — systematic coverage + dead-reckoned mapping (no SLAM):**
1. **Coverage:** a pre-planned **lawnmower (serpentine) sweep** — back-and-forth
   lanes that guarantee full-arena coverage by geometry. Robust to the
   see-through-net walls precisely because it never relies on *detecting* them.
2. **Navigation:** **closed-loop offboard control** — read UWB/FC position →
   compute error to the next waypoint → send a velocity-profiled NED setpoint
   (capped at the 0.3 m/s limit, slowing into each point). This is the
   org-recommended "poll position → velocity command" loop.
3. **Mapping:** every waypoint, the down-facing depth camera's point cloud is
   deprojected into a **world-frame top-down occupancy grid** — the deliverable
   `top_down.png`, used for both the map and the obstacle/pad distance accuracy.
4. **Detection + classification:** each frame is scanned for **ArUco markers**
   (`DICT_7X7_1000`, IDs 11/45/51/67/101), each marker is depth-deprojected to
   its world XYZ, de-duplicated, and classified **valid/invalid/unknown** from
   the marshal's announced ID split.

**Output → `landing_pads.json`** (ArUco ID, world coordinate, validity) +
`top_down.png` — the intelligence handed to Challenge 2A.

**Engineering decisions that make it robust:**
- **Redundancy everywhere:** pose (FC fused-NED ↔ UWB, auto-failover); camera
  (RGB ↔ infrared auto-fallback so it works on any RealSense variant); ArUco
  (two dictionaries scanned every frame so a wrong-dictionary guess can't blind
  us).
- **Safety:** altitude hard-capped below the cage ceiling; battery / pose-loss /
  position-stuck / link-failure watchdogs that auto-land; disarm only after
  touchdown.
- **Network isolation** so a neighbouring team's traffic can't corrupt our
  positioning on the shared arena network.

---

## 4. Challenge 2A — Deployment (precision landings)

**Goal:** land the Hula swarm **inside the designated hoops** at the valid
landing zones, in the least time.

**Approach:**
- **Targets** come from the org's Discord-published landing coordinates
  (authoritative), cross-checked against the recon `landing_pads.json` (which
  IDs were valid, and where).
- **Positioning** via the arena **UWB** system (`UWBParserThread`), with a
  one-time on-pad calibration of each drone's landing-zone coordinate.
- **Control** via `pyhula`: a closed-loop XYZ+yaw flight controller positions
  each drone over its zone, then descends, using the **ArUco marker beside the
  pad as a final visual descent aid**.
- **Conservative profile:** ~1.1 m cruise, 0.3–0.4 m/s (under the 0.5 m/s cap),
  **never overflying obstacles** (a hard scoring rule). Landings are prioritised
  over speed — a missed landing costs more than a slow one.

---

## 5. Challenge 2B — Ambush (convoy hunt)

**Goal:** find and **ArUco-tag the 5 RoboMaster ground robots** with clean
snapshots, in the least time.

**Approach:**
- **Search:** a **wall-following + 360° scan** strategy — the swarm follows the
  arena boundary and obstacle edges while sweeping its camera, so the whole
  cage is covered without flying over obstacles. The arena is split between
  drones so the two halves are searched in parallel.
- **Detection:** all drone video is streamed to the **single C2 terminal**
  (`dola.py`) for centralised detection — **ArUco** for the marker tag, with the
  option of **NPU-accelerated YOLO** (`RKNN`, ~50 fps) to first *spot* a robot
  before reading its marker.
- **Confirmation:** 2–3 frames per sighting (blurred/clipped frames don't
  count); a robot is "tagged" once its ArUco ID is captured.

**Adversarial duty (slot #24):** in the opposing slot we also *operate* two
convoy robots against another team — moving continuously, hugging obstacles and
the boundary, and splitting the cage to be maximally hard to tag.

---

## 6. Why this concept

- **Intelligence drives the strike.** C1's map + validity classification isn't a
  standalone deliverable — it directly seeds C2A's landing targets, so the two
  challenges are one coherent recon-then-deploy pipeline sharing a coordinate
  frame.
- **Coverage over cleverness.** Both stages use deterministic full-coverage
  search (lawnmower for mapping, wall-follow+scan for the hunt) rather than
  reactive exploration — simpler, predictable, and immune to the see-through
  netting that defeats obstacle sensing.
- **Designed to degrade, not fail.** Redundant pose, camera, and marker paths
  plus auto-landing safety watchdogs mean a single sensor or link problem
  downgrades the run instead of crashing it — and **a crash means no
  re-assessment**, so safe-first is built in, not bolted on.

---

*Team: ArtificiallyUnintelligent — C1 mapping (Z), C2 swarm landings + convoy
hunt (K), operations + concept (A).*

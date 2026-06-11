---
layout: default
title: Home
---

# ArtificiallyUnintelligent

**RoboVerse Drone Challenge · BrainHack 2026 · University Finals · Marina Bay Sands, 10–11 June 2026**

> A two-stage autonomous drone mission. First a mapping drone surveys the arena and identifies which landing pads are valid. Then a swarm of three Hula drones lands on the valid pads and hunts a convoy of ground robots. Two challenges, one coordinate world, one intelligence-driven pipeline.

<!-- HERO_PHOTO_SLOT — drop the Day-1 venue / drone photo here once the chat export finishes -->

---

## What we built

A modular, redundant autonomy stack with two operational halves:

- **Challenge 1 — Reconnaissance.** A mapping drone (Realsense + UWB + PX4 over MAVSDK) flies a deterministic lawnmower sweep at controlled altitude, deprojects depth into a top-down occupancy grid, scans every frame for ArUco markers in two dictionaries, and writes a machine-readable `landing_pads.json` describing each pad's world coordinates and validity.
- **Challenge 2 — Deployment & Ambush.** A swarm of three Hula drones takes the recon output, lands on three valid pads, then transitions into a wall-following + 360° spin-scan hunt for five RoboMaster ground robots, each carrying an ArUco marker, with all video aggregated centrally for detection.

Both stages share the **same arena UWB frame** (origin = centre). The C1 → C2 handoff is a coordinate lookup, not a re-survey.

---

## Five design principles

1. **Intelligence drives the strike.** C1 isn't a standalone deliverable — its map seeds C2's targets.
2. **Coverage over cleverness.** Deterministic sweeps everywhere. No reactive SLAM. Immune to the see-through netting that defeats depth-based obstacle sensing.
3. **Degrade, don't fail.** Every critical path has a fallback: pose (FC fused NED ↔ UWB), camera (RGB ↔ infrared), marker dictionary (7×7 ↔ 6×6), transport (MAVSDK ↔ PX4-ROS2).
4. **Safe-first.** A crash means no re-assessment, so altitude caps and watchdogs live *inside the control loop*, not on a checklist.
5. **Frame discipline.** Indoor UWB-frame ambiguity is the #1 failure mode. We make the coordinate model explicit and provide a tool to *measure* the frame rather than assume it.

[Full design rationale → Design principles]({{ '/principles' | relative_url }})

---

## At a glance

| | Challenge 1 (mapping) | Challenge 2 (swarm) |
|---|---|---|
| Hardware | 1 mapping drone, Realsense D430/D450, UWB tag, RKNN NPU | 3 Hula drones, central video aggregation |
| Pose | FC-NED fused ↔ UWB ENU→NED (auto-switching) | UWB serial (`tag_id → x,y`) |
| Control | MAVSDK offboard, velocity setpoints at 0.3 m/s cap | pyhula `send_manual_control` |
| Detection | `cv2.aruco` (DICT_7×7_1000 + 6×6_250) on depth-deprojected frames | ArUco on aggregated drone video |
| Path | Lawnmower sweep, centred-origin waypoints | Wall-follow + 360° spin-scan |
| Output | `top_down.png` + `landing_pads.json` (judge artifact) | Snapshot per detected RoboMaster |

[System architecture diagram → Architecture]({{ '/architecture' | relative_url }})

---

## Dive deeper

- [Architecture]({{ '/architecture' | relative_url }}) — full system diagram, module-by-module
- [Challenge 1 — Mapping drone]({{ '/c1-mapping' | relative_url }}) — algorithms + flight envelope + redundancy
- [Challenge 2 — Hula swarm]({{ '/c2-swarm' | relative_url }}) — deploy + hunt + central detection
- [Design principles]({{ '/principles' | relative_url }}) — the five rules driving every decision
- [Engineering log]({{ '/engineering' | relative_url }}) — trade-offs, fixes, what we'd do differently

---

## Team

**ArtificiallyUnintelligent** — three-person team, University category.

- **Z** — Challenge 1 mapping drone, cross-platform glue, runbook
- **K** — Challenge 2 Hula swarm controller, on-day pilot
- **A** — Operations, concept submission, judge interface

---

*Source code: [github.com/zhengboon/ArtificiallyUnintelligent](https://github.com/zhengboon/ArtificiallyUnintelligent). This site is generated from `/docs` via GitHub Pages.*

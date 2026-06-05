# 08 — FINALS PREP, T-5, FULL SCOPE LANDED

**Date:** Fri 5 Jun 2026 (T-5 to finals on Wed 10 + Thu 11 Jun)
**Branch:** `zb` at `2906c61`, mirrored to `main` at `365483e`
**Status:** scoping complete, building starts now

## Pivot from qualifier

- Qualifier (Thu 22 May): top-26 with all-target detection
- Org pushed us straight to **FINALS** (skipped semi-final tier; reason unstated)
- Finals: **2026-06-10 + 2026-06-11**, both 9am-6pm, Marina Bay Sands Expo Level 4
- Smart casual + covered footwear strict. Photo ID + confirmation email required at 7:30am registration.
- Bring: personal laptop + mouse + charger + thumbdrive

## The actual challenge (revealed in slides 2026-06-05)

Scenario: enemy convoy reconnaissance + ambush.

| Stage | Who | What | Hardware |
|---|---|---|---|
| **Challenge 1 — Reconnaissance** | University ONLY | Map arena, decode ArUco markers on landing pads, classify each valid/invalid | 1 Mapping Drone w/ Realsense (5.88 GHz) |
| **Challenge 2A — Deployment** | Everyone | Pick 3 valid landing pads, launch 3 Hulas to land on them | 3 Hula drones |
| **Challenge 2B — Ambush** | Everyone | 5 RoboMaster ground robots enter and loiter; Hulas hunt + snapshot them | 3 Hula drones + 5 RoboMaster targets |

**CRITICAL UNKNOWN:** are we University or Pre-University? Determines if Challenge 1 is our problem.

Prize: $1800 / $1300 / $900 per category for top 3.

## Two-drone architecture (now fully confirmed)

```
PERSONAL LAPTOP (dev/pre-venue)
        │
        │ USB transfer at venue
        ▼
C2 TERMINAL (org-provided Windows + Ubuntu 22.04 VM)
  ├── pyhulax swarm code runs HERE (Windows side)
  ├── UWB Python class for swarm pos
  ├── rknn-toolkit2 in the Ubuntu VM (.onnx → .rknn)
  └── NoMachine session into mapping drone
        │
        │ 5.88 GHz + NoMachine
        ▼
MAPPING DRONE onboard (Ubuntu 22.04 + ROS2 + OpenCV)
  ├── mavsdk Python or ROS2 for movement
  ├── pyrealsense2 for depth camera
  ├── UWB Python class for self pos (provides N,E only)
  ├── rknnlite for NPU inference (~50 FPS)
  └── PX4 over serial /dev/ttyS6:921600
        │
        │ Hula proprietary radio
        ▼
3 × HULA DRONES (small swarm)
```

## What changed in our understanding (vs earlier plan versions)

| Was | Now |
|---|---|
| "Hula swarm or mapping drone, pick one focus" | BOTH platforms, separate codepaths |
| RKNN conversion on our laptop (risky) | RKNN conversion on org VM at venue (low risk) |
| Mapping drone runs from our laptop | Runs ON the drone, accessed via NoMachine |
| Targets = barrels (qualifier carryover) | Targets = RoboMaster ground robots (totally new training set) |
| Aruco markers in detection set | Aruco IS the Challenge 1 task (decode → validity) |
| pyhulax on our laptop | pyhulax on C2 Terminal Windows side |
| Personal laptop is THE compute | Personal laptop is dev/backup; C2 Terminal is the runtime |

## Confirmed parameters (from org reference code)

| Param | Value | Source |
|---|---|---|
| Target SoC | `rk3588` | `convertrknn.py` |
| YOLO normalization | mean=[0,0,0], std=[255,255,255] | `convertrknn*.py` |
| Quantization default | fp16 (no quant) | `convertrknn.py` line 14 |
| ONNX opset | 12 | `convertyolotoonnx.py` |
| Realsense stream | 640×480 @ 30Hz (depth + color) | all examples |
| Top-down grid | 200×200 cells @ 5cm = 10m × 10m | `generateTopDown.py` |
| Depth range | 0.2 m – 5.0 m | `generateTopDown.py` |
| YOLO input | 640×640 RGB | detection scripts |
| Default conf | 0.25, IOU 0.45 | `rknndecoder.py` |
| NPU inference | ~50 FPS | slides |
| Hula count | 3 | slides |
| RoboMaster count | 5 | slides |

## Repo state

```
hackerverse/
├── README.md (post-qualifier section + semifinal pointer)
├── semifinal/
│   ├── FINALS_PLAN.md (v2.0, per-person daily T-5 → finals)
│   ├── CHALLENGE_BREAKDOWN.md (authoritative rules from slides)
│   ├── README.md (general prep report)
│   ├── learning_materials_and_others.md (Discord scrape verbatim L1-L5 + finals announcement)
│   ├── semifinal_scrape.md (earlier Discord scrape — superseded but kept)
│   ├── final_challenge_slides.pdf (org's slide deck mirror)
│   ├── huladola.py, dola.py (L1 — Hula swarm reference)
│   ├── learning_material_3_uwb/ (L3 — kolomee.py + analysis)
│   ├── learning_material_4_realsense/ (L4 — 8 scripts + analysis README)
│   ├── learning_material_5_yolo_rknn/ (L5 — convert/ + detection/ + analysis README)
│   ├── docs/
│   │   ├── pyhulax/ (offline mirror of pyhulax.xenops.ae, 25 pages)
│   │   ├── pyhulax_analysis.md (14-section deep-dive, Hula-only)
│   │   └── mapping_drone_analysis.md (11-section deep-dive, sister to above)
│   └── prototypes/ (drone-free validation scripts)
├── tools/log_broadcaster/ (laptop → desktop log streaming over Tailscale)
├── thumbdrive/ (qualifier USB — not finals)
├── searchctl/ (qualifier controller — done, kept for reference)
└── ks_code/ (K's standalone qualifier submission — done)
```

## Per-person workload (from FINALS_PLAN v2.0)

- **A (~70%)**: pivot YOLO training to RoboMaster ground robots; export ONNX with org's settings; ready to retrain at venue
- **K (~100%)**: Hula swarm controller (3-drone coordinated) for Challenge 2A landings + 2B search/snapshot
- **Z (~100%)**: Mapping drone controller for Challenge 1 (top-down map + ArUco landing-pad classifier); fallback to Challenge 2 support if Pre-Uni

## Daily T-5 → finals

- T-5 (Fri 5 Jun) = TODAY = catch up to v2.0, start RoboMaster dataset, start swarm + mapping skeletons
- T-4 (Sat 6) = build out controllers; A first model training
- T-3 (Sun 7) = buffer / dry runs
- T-2 (Mon 8) = final training, USB packaging, runbook
- T-1 (Tue 9) = light day, last sync 21:00 SGT
- Wed 10 Jun = Day 1 finals (registration 7:30am, event 9am-6pm)
- Thu 11 Jun = Day 2 finals (8am arrive, event 9am-6pm)

## Open questions to file with org TODAY

1. **University or Pre-University?** (biggest single unknown)
2. ArUco-marker → valid/invalid encoding rule
3. RoboMaster YOLO target classes (one class, or variations)
4. Training images of RoboMaster — does org provide?
5. Time budget per challenge within the 9-hour day
6. What format does the "mapping info will be provided" come in for Pre-Uni?
7. Test access to C2 Terminal before Day 1?
8. Snapshot = single photo, video, or JSON bbox?
9. RoboMaster movement pattern (continuous patrol vs teleport)
10. Hula spawn area constraints

## Key commits

- `2906c61` zb (and mirrored as `365483e` main): "semifinal: Final Challenge slides + L4/L5 unlock + full plan rewrite v2.0"
- Previous milestones:
  - `1aa3c2f` FINALS_PLAN v1 (10/11 June @ MBS, per-person daily breakdown)
  - `cb70045` prototypes (realsense_verify, aruco_webcam, aruco_realsense)
  - `9baaf7a` log_broadcaster (laptop → desktop streaming)
  - `47680ae` pyhulax SDK docs mirror (25 pages)
  - `45413fc` pyhulax full analysis (14 sections)
  - `80a436d` L3 reveal: kolomee.py + two-drone architecture

## What to do next session (when user picks up)

Default priority order:
1. Check if user has org's answer on University vs Pre-University
2. Check if user has any drone hardware in hand
3. If A has started RoboMaster training: review dataset + suggest improvements
4. If not: start the swarm + mapping controller skeletons (Z's track) — these can run against mocks today
5. Refresh `docs/pyhulax/` mirror if org updated SDK

Standing by.

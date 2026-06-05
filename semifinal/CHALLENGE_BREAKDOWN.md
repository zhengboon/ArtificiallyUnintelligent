# Final Challenge — Rules & Technical Breakdown

Sourced directly from org's slide deck released 2026-06-05 05:07 ([`final_challenge_slides.pdf`](final_challenge_slides.pdf)). This file is the authoritative interpretation of what we have to do.

## Scenario (the storyline)

> *Your team receives intelligence of the enemy's transport convoy travelling routes. Your mission is to gather information on the convoy.*

Military-themed reconnaissance + ambush mission.

## Prize structure

| Category | 1st | 2nd | 3rd |
|---|---|---|---|
| Pre-University | $1800 | $1300 | $900 |
| University | $1800 | $1300 | $900 |

**✅ Confirmed 2026-06-05: we are University category.** Both Challenge 1 AND Challenge 2 are ours. Challenge 1 mapping is a core deliverable, not optional.

---

## Challenge One — Reconnaissance (University teams only — ✅ that's us)

### Hardware
- **1 Mapping Drone** with Intel Realsense stereo camera
- Connected to our C2 Terminal via **5.88 GHz** for control + footage

### Arena
- Obstacles + multiple **drone landing pads**
- Each landing pad has an **ArUco marker** attached beside it

### Mission
1. Mapping drone flies and surveys the arena
2. Returns a **top-down depth map**
3. Returns **images of each ArUco marker**
4. We decipher the ArUco markers to determine: **which landing pads are VALID vs INVALID for landing**

### Scoring
- Understanding of the concept
- Mapping speed
- Accuracy of identifying landing sites as valid or invalid

### Implications for our code
- The mapping pipeline is real: must build occupancy grid + identify landing pads + read ArUco IDs
- Validation logic: org will tell us what marker IDs (or some encoded property) = valid vs invalid. Not in the slides yet — likely revealed at venue or in a follow-up.
- Top-down map needs to be world-frame (fused with UWB pose), not just camera-frame snapshots

---

## Challenge Two — Deployment & Ambush (everyone)

### Part 2A — Land 3 Hulas on selected pads

#### Hardware
- **3 Hula drones** (count CONFIRMED!)
- Launched from our C2 Terminal

#### Mission
1. Based on Challenge 1 mapping output (we produce it ourselves as a University team), strategise + pick 3 valid landing zones
2. Launch all 3 Hulas to land on those zones simultaneously

#### Scoring
- Successful landings + accurate placement on designated zones + minimum time

#### Implications
- Mission planner: take mapping output → choose 3 landing zones → assign 1 Hula per zone → plan paths
- Each Hula independently navigates to its landing zone
- Coordination: stagger takeoffs / altitudes to avoid mid-air collisions
- (Pre-University teams get the mapping info provided to them; we generate it ourselves in Challenge 1 and feed it into our own Challenge 2 planner)

### Part 2B — Hunt the convoy

#### Hardware
- **5 RoboMaster ground robots** (programmed by 65Drones team as "targets")
- 3 Hula drones (same as 2A)

#### Mission
1. The 5 ground robots enter the arena and loiter
2. Launch 3 Hulas to search for them
3. **Take snapshots of each ground robot**

#### Scoring
- Successful + accurate snapshots + minimum time

#### Implications
- This is what K's YOLO model needs to detect: **RoboMaster ground robots** (not the qualifier's barrels)
- A's training set should be RoboMaster footage
- Hula camera + onboard YOLO (or stream to C2 + YOLO there) for detection
- Snapshot = `take_photo()` on the Hula when detection fires
- Hunting strategy: divide arena into 3 zones, one Hula per zone

---

## Technical infrastructure

### Mapping drone
- **Onboard computer:** Ubuntu 22.04 + ROS2 + OpenCV pre-installed
- **Control:** MAVSDK Python OR ROS2 — both supported
- **Depth camera:** Realsense via `pyrealsense2` OR ROS2
- **UWB tag:** provides North-East XY position (no Z), accessed via provided Python class OR ROS2
- **Recommended approach:** velocity commands with UWB feedback (faster than position commands, more efficient)
- **Reference code:** `kolomee.py` (pulled into `learning_material_3_uwb/`)

### Mapping drone access (CRITICAL)
- **NoMachine** session from C2 Terminal → mapping drone's onboard Ubuntu
- We `ssh`-like into the drone, execute our code there
- We do NOT control the drone from our personal laptop directly

### C2 Terminal (org-provided)
- **Hardware:** Windows laptop
- **Plus:** Ubuntu 22.04 Virtual Machine
- **Holds:** swarm control code (pyhulax + UWB lib), NoMachine session into mapping drone, RKNN conversion toolchain
- **Connection to drones:** 5.88 GHz radio for mapping drone, WiFi for Hula swarm

### Hula swarm
- **Quantity:** 3 (confirmed)
- **Control:** `pyhulax` (NOT MAVSDK)
- **UWB:** Hula drones ALSO have UWB position access via provided Python lib
- **Runs on:** C2 Terminal Windows side
- **Coordination:** one Python process orchestrates all 3 drones

### Object detection (mapping drone NPU)
- **Acceleration:** Neural Processing Unit (~50 fps)
- **Format:** RKNN (must convert from `.pt → .onnx → .rknn`)
- **Target SoC:** `rk3588` (confirmed in org's convert script)
- **Mean/std:** `[0,0,0] / [255,255,255]` (confirmed)
- **Tooling location:** on the org VM, not our laptop
- **Files we'd touch:** `convertyolotoonnx_2.py`, `convertrknn.py`, `getDepthAndDetect.py`, `rknndecoder.py` (or YOLOv8 equivalent)

---

## Per-drone code locations summary

```
┌─────────────────────────────────────────────────────────────┐
│  OUR PERSONAL LAPTOP (for dev / pre-venue prep)             │
│  - K trains YOLO model (.pt)                                │
│  - Convert to ONNX locally for testing                      │
│  - Write swarm controller (test against mocks)              │
│  - Write mapping drone controller (test against mocks)      │
│  - Realsense prototypes against our D435                    │
│  → Code + model on USB to bring to venue                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ USB transfer at venue
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  C2 TERMINAL (org-provided Windows + Ubuntu 22.04 VM)       │
│                                                             │
│  Windows side:                                              │
│    - pyhulax (swarm control)                                │
│    - UWB Python class for swarm pos                         │
│    - Our swarm_controller.py runs HERE                      │
│                                                             │
│  Ubuntu 22.04 VM side:                                      │
│    - rknn-toolkit2 (convert .onnx → .rknn)                  │
│    - NoMachine client (to mapping drone)                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 5.88 GHz + NoMachine
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  MAPPING DRONE ONBOARD COMPUTER (org-provided Ubuntu 22.04) │
│  - ROS2 + OpenCV pre-installed                              │
│  - pyrealsense2 (depth camera)                              │
│  - MAVSDK Python (control via serial → PX4)                 │
│  - rknnlite (NPU inference, ~50 fps)                        │
│  - Our mapping_drone/controller.py runs HERE                │
│  - UWB Python class for self pos                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Hula proprietary radio
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  3 × HULA DRONES (small swarm)                              │
│  - controlled from C2 Terminal via pyhulax                  │
│  - each has UWB position fix                                │
│  - each has onboard camera for snapshots                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Open questions (file with org, in priority order)

1. ~~Are we University or Pre-University?~~ **CONFIRMED University 2026-06-05**
2. **What's the encoding for ArUco-marker → valid/invalid?** Specific IDs? Even/odd? Bit pattern?
3. **What target class(es) does the RoboMaster YOLO model need?** Is "RoboMaster ground robot" the only class, or are there variations?
4. **Will training images of the RoboMaster robots be released?** Or do we have to source them?
5. **Time budget per challenge?** The day is 9hr but how is it allocated — back-to-back, separate runs, retries allowed?
6. ~~"The mapping information will be provided" format question~~ — N/A for us, we produce our own. Internal handoff format from our Challenge 1 → Challenge 2 planner is our call.
7. **Can we test against the C2 Terminal before Day 1?** Or first-time-we-see-it on Wed 10 Jun?
8. **Snapshot for Challenge 2B = a single photo, or video, or just bbox JSON?**
9. **Do the RoboMaster targets move (continuous patrol) or randomly teleport?**
10. **Is there a "spawn area" for the Hulas, or do they take off from anywhere?**

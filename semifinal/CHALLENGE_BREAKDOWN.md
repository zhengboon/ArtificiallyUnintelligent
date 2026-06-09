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

## 🎯 Authoritative facts from finals brief 2026-06-09 (supersedes earlier guesses)

Source: `Finals brief.pptx` shared by org on Telegram 2026-06-09 22:06 SGT. Extracted verbatim into [`finals_brief_extracted.md`](finals_brief_extracted.md). **This section supersedes everything below it where they conflict.** Read the extracted file for any field-by-field detail.

### Schedule (slide 12, verbatim)

**Day 1 — Wed 10 Jun (University track)**

| Time | Activity |
|---|---|
| 0930 - 1030 | Briefing |
| 1030 - 1200 | Testing (Hula or Mapping Drone — University teams choose) |
| 1200 - 1300 | Lunch (no testing) |
| 1300 - 1330 | Testing |
| 1330 - 1430 | Prep for Challenge 1 — **no flying of the Mapping Drone in this window** |
| 1430 - 1800 | Challenge 1 (scored) |

**Day 2 — Thu 11 Jun**

| Time | Activity |
|---|---|
| 0900 - 1230 | Testing |
| 1230 - 1330 | Lunch (no testing) |
| 1330 - 1600 | Challenge 2 (scored) |

### Our assessment slots (slides 13, 14)

- **Challenge 1:** ARTIFICIALLYUNINTELLIGENT = slot **#3** (after 4FINGERS → AAA → us → BOYD BUDDIES → …).
- **Challenge 2:** ARTIFICIALLYUNINTELLIGENT = slot **#3**, convoy opponent = **STD** (we control STD's 2 RoboMasters during STD's run — wait, see below).
- **Challenge 2 — we must operate 2 convoy RoboMasters at slot #24 vs THE WIENERS.** During THE WIENERS' run (slot 24), 2 of the 5 ground robots are driven by us. Plan a 3-person split: someone stays at our table to run the convoy while the others reset/pack.

### Drone sharing (slide 22)

- ARTIFICIALLYUNINTELLIGENT shares **Hula 3,4** and **Mapping 3,4** with **BOYD BUDDIES** (slot #4, immediately after us in Challenge 1).
- Means we hand the physical aircraft to BOYD BUDDIES the moment we finish C1, and reciprocally retrieve them before our slot starts. Pre-agree a handoff protocol with their captain on Day 1.

### Speed + altitude regimes (slides 5, 6)

| Drone | Max speed | Altitude | Other |
|---|---|---|---|
| Mapping Drone | **0.3 m/s** | floor 3.5 m (org 2026-06-08); we default 4.0 m | top-down depth map + Aruco snapshots |
| Hula | **0.5 m/s** | **recommended 1.1 m**; **STRICTLY NO FLYING OVER OBSTACLES** | scores invalidated on violation |

Two distinct altitude regimes — mapping drone flies *high* (above obstacles), Hula flies *low* (around obstacles). `controller.py` `MAX_VEL_XY` and any Hula speed cap in `swarm_controller.py` stub must clamp to these. Current `--max-flight-time-s` default is 420 s, sized 60 s under the org 480 s (8 min) per-attempt cap.

### Crash policy (slide 18, verbatim)

> *"Teams will not be given re-assessment attempts should the drone crash due to any reasons."*

Safe-first behaviour is mandatory. No retries. Conservative speeds, conservative altitudes, conservative tilts.

### Validity rule (slide 5)

> *"Before the assessment starts, the valid and invalid Aruco Marker IDs will be announced."*

Org confirms valid/invalid IDs are published **at the venue** before assessment. Our existing lookup-rule code path (`--valid-ids` / `--invalid-ids` CLI on `controller.py`) is the right shape — just wire it up Day-1 from whatever announcement format they use.

### C2A landing coordinates come from Discord (slide 6)

> *"Refer to Discord for the coordinates of valid landing points. Using the provided coordinates, the team will select 3 out of 5."*

**Org provides the C2A landing coordinates directly via Discord.** Our Challenge 1 mapping output does **NOT** feed C2A as a judge-required handoff. `HANDOFF_C1_TO_C2.md` remains useful for our own situational awareness (e.g. cross-checking obstacle positions for the no-fly-over-obstacles rule), but is not an artifact judges will look at.

### Logistics at our table (slides 20-22)

- 1 mapping drone (shared with BOYD BUDDIES)
- 1 Hula drone (shared with BOYD BUDDIES)
- 1 sample landing pad — physical practice pad
- 1 sample Aruco pad — physical practice marker
- 1 laptop + charger + mouse (the C2 Terminal)

### Assessment vs test cage layout (slide 5)

> *"The landing pads for the assessment will have a different configuration compared to the test set-up."*

Test-cage results do NOT transfer 1:1. Cage time is for tuning detection + flight envelope, not for memorising pad positions.

### Bonus components (slide 9)

- **S/N 5 — Counter UAS booth: 4%.** Photo of drone at the CUAS booth + screenshot of zone-explored page on Brainhack Frontier Exploration System (slide 10). Booth lives in the *Above & Beyond: Skies & Space* zone, MBS L4.
- **S/N 6 — Overall concept explanation: 7%.** Sell the architecture to the judges.

---

## 🎯 Scoring rubric (slide 9)

University track totals 100% across 6 rows. Pre-University skips C1 (44 / 44 / 4 / 8).

| S/N | Challenge | Criterion | Uni | Pre-Uni |
|---|---|---|---|---|
| 1 | Challenge 1 | Number of landing pads detected (image recognition) + Number of landing points verified (Aruco marker) + Timing | **15%** | NA |
| 2 | Challenge 1 | Accuracy of distance of obstacles / landing pads from reference point (using depth map) | **15%** | NA |
| 3 | Challenge 2 | Number of landings within hoop + Timing | **30%** | 44% |
| 4 | Challenge 2 (cont'd) | Number of Aruco detections + Timing | **30%** | 44% |
| 5 | Bonus | Completion of Counter UAS tech showcase | **4%** | 4% |
| 6 | Bonus | Overall concept explanation | **7%** | 8% |

For S/N 1, 3 & 4, *priority is in sequence (1, 2, 3)* — i.e. detection count first, verification second, timing third (per slide 9).

### ⚠️ Callout — S/N 2 (15%): depth-map accuracy from a reference point

We have **not been optimising for this**. The judges will measure how accurately our depth map reports the distance of obstacles and landing pads relative to a reference point in the arena. This is a quantitative accuracy score, not just "did you produce a map".

Implications:
- The top-down depth map needs metric calibration, not just a visualisation. World-frame coordinates (UWB-fused) with known origin, not raw camera-frame pixel depths.
- Reference point is likely an arena landmark (UWB origin, or a marked corner). Confirm Day-1 during briefing.
- Currently `mapping.py` produces a top-down plot via matplotlib. Audit whether the numeric distances in the underlying array are calibrated (UWB pose × camera intrinsics × depth) or just camera-relative. **15% of total score rides on this — sizeable.**

---

### 🗂️ Historical — pre-brief updates (superseded 2026-06-09 by finals brief above)

The sections below were written from the earlier Discord slide deck and team-chat reports. Treat as historical context where they don't conflict with the authoritative section above; defer to the brief where they do.

### Updates from 2026-06-05 evening + 2026-06-06 AM + 2026-06-06 PM + 2026-06-07 + 2026-06-08

- **All 3 team members should attend both days** (org: *"It is best that all members of team can be there on both days as there are plenty to do"*).
- **Map layout WILL NOT be provided** (org 2026-06-06 11:40). We discover dimensions + obstacle positions at venue — Challenge 1 mapping is the only way we'll know the arena.
- **Hula ground-robot detection uses ArUco markers, NOT YOLO** (org 2026-06-06 5:00 am). A's YOLO training is no longer critical-path.
- **New UWB API for Hula swarm released**: `UWBParserThread.py` via USB-serial @ 921600 baud — NOT ROS2, NOT same as mapping drone's UWB. See [`uwb_api_hula_swarm/`](uwb_api_hula_swarm/README.md). Runs on C2 Terminal Windows.
- **ArUco markers also placed next to Challenge 2 Hula landing pads** (org 2026-06-06 21:34, replying to FlyingExplorers). Same marker pattern as Challenge 1's landing pads — usable as Hula landing aid via `cv2.aruco`. NOT the pyhulax "auto-land" marker (that's a separate pyhulax feature with its own marker spec).
- **ArUco markers 20cm × 20cm, exact dictionary TBD Day-1** (org 2026-06-06 21:32). Physical size confirmed; dictionary will be announced at venue and could be any of 16 ArUco sizes or 4 AprilTag variants. Our code must accept a runtime dict override.
- **Org ticket etiquette:** close stale support tickets, open fresh ones for new questions so the queue stays prioritised (org 2026-06-06 21:47).
- **A officially killed YOLO training** (team chat 2026-06-06 22:13). Detection of ground robots is now 100% ArUco via `cv2.aruco`. A reassigned to Hula camera helper + arena scout.
- **Minimum flight height = 3.5 m** (org 2026-06-08 12:18, in reply to ROBO05_Daniel 2026-06-07 8:04 pm). All pre-staged arena templates (1.5 m / 2.5 m) are below the floor — bump to 4.0 m for margin.
- **Mapping drone cameras = Intel Realsense D430 AND D450** (org 2026-06-08 12:18). Both are depth-only stereo IR modules + IR projector; neither has an RGB sensor. P0 risk to current `ArucoDetector` (color-frame consumer). Mitigation in flight: `--use-ir-for-aruco` flag with emitter-toggle.
- **Camera mounted facing down** (org 2026-06-08 12:19) — `--gimbal-pitch -90` default confirmed.
- **Camera resolution configurable** (org 2026-06-08 12:19) — `RealsenseNode.PROFILE_CANDIDATES` fallback chain confirmed correct.
- **Launch direction is free, takeoff point is fixed** (org 2026-06-08 12:17, in reply to FlyingExplorers 2026-06-07 8:56 pm). Pre-yaw the drone toward the optimal first-scan direction before arming.

---

## Challenge One — Reconnaissance (University teams only — ✅ that's us)

### Hardware
- **1 Mapping Drone** with Intel Realsense stereo camera
- **Camera:** D430 + D450 mixed across runs (depth-only stereo IR modules; verify RGB stream availability at venue).
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
- **ArUco landing aid available:** org confirmed 2026-06-06 PM that ArUco markers are placed next to the Hula landing pads too (not only Challenge 1's landing pads). Hulas can use `cv2.aruco` on the onboard camera as a visual landing aid to refine the final descent on top of UWB-based positioning. **Important:** these ArUco markers are NOT the pyhulax "auto-land" marker — pyhulax's auto-land is a separate feature with its own marker spec. Use the same dict resolution path as the mapping drone (markers are 20cm × 20cm, exact dictionary announced Day-1).

### Part 2B — Hunt the convoy

#### Hardware
- **5 RoboMaster ground robots** (programmed by 65Drones team as "targets")
- 3 Hula drones (same as 2A)

#### Mission
1. The 5 ground robots enter the arena and loiter
2. Launch 3 Hulas to search for them
3. **Take snapshots of each ground robot**

#### Detection: ArUco, NOT YOLO (CONFIRMED 2026-06-06 5:00 am)

Org confirmed: *"hula drone to detect aruco marker on ground robots."*

The RoboMasters carry **ArUco markers**. Detection uses `cv2.aruco` (we already have it integrated for Challenge 1's landing-pad classifier) — NOT a YOLO model. This means:
- A's YOLO training task is **deprioritised** (no longer critical-path).
- K's swarm controller only needs `cv2.aruco` on the Hula camera feed.
- A YOLO backup model is still nice insurance, but optional.

#### Scoring
- Successful + accurate snapshots + minimum time

#### Implications (updated)
- Snapshot = `take_photo()` on the Hula when ArUco detection fires
- Hunting strategy: divide arena into 3 zones, one Hula per zone
- IF the RoboMasters also have UWB tags (open question), the Hulas can fly directly to each robot's reported (x, y) and visually confirm with ArUco instead of running a search pattern.

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
- **Base model:** `yolo11n.pt` — **YOLOv11 confirmed by org**, not v8
- **Target SoC:** `rk3588` (confirmed in org's convert script)
- **Mean/std:** `[0,0,0] / [255,255,255]` (confirmed)
- **Tooling location:** on the org VM, not our laptop
- **Files we'd touch:** **use the `_2.py` variants** — `convertyolotoonnx_2.py`, `convertrknn2.py`, plus `getDepthAndDetect.py`, `rknndecoder.py` (with `decode_yolov11_rknn`)

---

## Per-drone code locations summary

```
┌─────────────────────────────────────────────────────────────┐
│  OUR PERSONAL LAPTOP (for dev / pre-venue prep)             │
│  - ArUco (cv2.aruco DICT_6X6_250) prototype on Hula camera  │
│    feed — PRIMARY RoboMaster detection path                 │
│  - A trains YOLOv11 model (yolo11n.pt) — INSURANCE/BACKUP   │
│    only; convert via convertyolotoonnx_2.py for org VM      │
│  - Write swarm controller (pyhulax + UWBParserThread mocks) │
│    (NOT YET BUILT — swarm_controller.py placeholder)        │
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
│      (NOT YET BUILT — placeholder, TODO before venue)       │
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
2. **What's the encoding for ArUco-marker → valid/invalid?** Specific IDs? Even/odd? Bit pattern? (Still open as of 2026-06-07 — open a fresh ticket per org's 2026-06-06 21:47 ticket etiquette.)
3. ~~What target class(es) does the RoboMaster YOLO model need?~~ **OBSOLETED 2026-06-06: ArUco, not YOLO** — but: are different RoboMasters distinguished by different ArUco IDs, or do they all use the same?
4. ~~Will training images of the RoboMaster robots be released?~~ **OBSOLETED 2026-06-06: ArUco, not YOLO** — A's annotation pipeline still useful as YOLO backup.
5. **Time budget per challenge?** The day is 9hr but how is it allocated — back-to-back, separate runs, retries allowed? (Still open)
6. ~~"The mapping information will be provided" format question~~ — N/A for us, we produce our own.
7. **Can we test against the C2 Terminal before Day 1?** Or first-time-we-see-it on Wed 10 Jun? (Still open)
8. **Snapshot for Challenge 2B = a single photo, or video, or just bbox JSON?** (Still open — affects Hula camera handling)
9. **Do the RoboMaster targets move (continuous patrol) or randomly teleport?** (Still open)
10. **Is there a "spawn area" for the Hulas, or do they take off from anywhere?** (Still open)
11. 🆕 **Do RoboMaster ground robots carry UWB tags?** If yes, swarm can fly Hulas to their reported (x, y) and use ArUco only for ID confirmation; if no, swarm needs a visual search pattern.
12. 🆕 **What tag_ids do the 3 Hulas (and possibly RoboMasters) have?** Org should publish a mapping; likely labelled on hardware at venue.
13. 🆕 **What's the UWB origin?** Where is (0, 0) in the arena? Likely calibrated against a known landmark at venue.
14. 🆕 **Should we pre-prep code, or build only Day 1?** Org didn't answer — STINKIES asked 5/6 10:35pm, re-asked 6/6 14:13 ("what codes should we come prepared with on 10 June?"), still no response by 6/7 AM. Default: bring everything pre-built (we are).
15. 🆕 **Exact ArUco dictionary to be announced Day-1** (org 2026-06-06 21:32: *"The exact dictionary will be announced on the day"*). Could be any of: `DICT_4X4_{50,100,250,1000}`, `DICT_5X5_{50,100,250,1000}`, `DICT_6X6_{50,100,250,1000}`, `DICT_7X7_{50,100,250,1000}`, or AprilTag variants `DICT_APRILTAG_{16h5,25h9,36h10,36h11}`. Our `mapping.py:ArucoDetector` and `controller.py --aruco-dict` flag currently default to `DICT_6X6_250` and accept a subset of short-form names; widen this lookup before venue so any announced dict is accepted (today's `_ARUCO_DICTS` covers ~9 of the 20 possible options — see audit notes).
16. ✅ **Do Challenges 1 and 2 run in parallel or sequentially?** — **Resolved by finals brief slide 12**: C1 runs Day 1 (Wed) 1430–1800, C2 runs Day 2 (Thu) 1330–1600. Sequential across separate days; no parallel-within-slot.
17. 🆕 **Can camera pitch be commanded?** Calibruh_KangKiatYang asked 2026-06-08 1:59 pm — *"Can the camera pitch change with commands or is it physically fixed downwards forever?"* — still unanswered. Affects whether we lock to -90 or can sweep.
18. 🆕 **D430/D450 RGB stream availability** — org confirmed 2026-06-08 12:18 the mapping drone uses D430 + D450 (depth-only stereo IR, no RGB sensor in either module). Need confirmation whether the venue integration bolts on a separate RGB camera, or whether we must run ArUco on IR (emitter-toggle path, `--use-ir-for-aruco`).
19. 🆕 **Top-down depth map format** — FlyingExplorers asked 2026-06-07 6:03 pm whether the deliverable needs to be a stereo output map like the slide, or whether a matplotlib graph (a la `top_down.py`) is acceptable. Re-asked 2026-06-08 3:19 pm. Still unanswered.

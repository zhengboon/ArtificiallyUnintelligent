# BrainHack 2026 — Finals Plan

**Finals dates:** Wed 10 June + Thu 11 June 2026
**Scored windows (slide 12):** Day 1 1430-1800 = Challenge 1 (3.5h, Uni only). Day 2 1330-1600 = Challenge 2 (2.5h). Single scored window per challenge — NOT a free-form 9-hour iteration day.
**Venue:** Marina Bay Sands Expo and Convention Centre, Level 4
**Registration:** counter opens 10 June 7:30am — bring **Photo ID + confirmation email**
**Dress code:** Smart Casual. **Strictly no slippers or uncovered footwear.**
**Bring:** personal laptop, mouse, charger; note-taking tools; thumbdrive (or HDD + USB cables) for code transfer

**Today:** 2026-06-09 Tue (T-1 day)
**Plan version:** v3.0 (major reset based on official Finals brief pptx — superseded earlier Discord slides)

**MAJOR UPDATES vs v1.x:**
- Two challenges revealed in slides — Challenge 1 (Reconnaissance, University-only — **CONFIRMED we are University, so this IS ours**) + Challenge 2 (Deployment & Ambush, everyone)
- **Task 1 / Task 2 / Task 3** is org's internal name for the 3 sub-tasks (= our Challenge 1 + 2A + 2B)
- **C2 Terminal** ("dedicated laptop" per team, org-provided Windows + Ubuntu 22.04 VM) — Task 2 + Task 3 run from HERE, not on personal laptop
- **Drones are SHARED across teams** — testing time slots assigned per team. Slot announcement coming.
- **3 Hula drones** in the swarm (confirmed)
- **5 RoboMaster ground robots** as targets for Challenge 2B (NOT barrels!)
- **YOLOv11 confirmed** as base model (NOT v8) — org said use `yolo11n.pt` as base when custom-training
- **`_2.py` variants** of conversion scripts (`convertyolotoonnx_2.py` + `convertrknn2.py`) are canonical
- **Mapping drone has Ubuntu 22.04 + ROS2 + OpenCV pre-installed** + RKNN-NPU at ~50 FPS
- **NoMachine** = access pattern from C2 Terminal → mapping drone
- **RKNN conversion tooling lives on the org VM**
- All org reference scripts pulled and analysed (`learning_material_4_realsense/`, `learning_material_5_yolo_rknn/`, `learning_material_3_uwb/kolomee.py`)
- See [`CHALLENGE_BREAKDOWN.md`](CHALLENGE_BREAKDOWN.md) for the authoritative rules from slides

**🆕 v2.1 changes (2026-06-06 morning):**
- **Hula detects ground robots via ArUco markers, NOT YOLO** (org confirmed 5:00 am). A's RoboMaster YOLO is now insurance only — primary detection uses `cv2.aruco` on Hula camera feed (already in our Challenge 1 stack).
- **Map layout NOT provided** (org confirmed 11:40). We discover arena dimensions + obstacles only via Challenge 1 mapping.
- **All 3 team members attend BOTH days** (org confirmed 10:22 pm yesterday). No single-day-only attendance.
- **New UWB API for Hula swarm released**: `UWBParserThread.py` via USB-serial @ 921600 baud — see [`uwb_api_hula_swarm/`](uwb_api_hula_swarm/README.md). Different protocol from mapping-drone UWB. K's swarm controller must integrate this on C2 Terminal Windows side.

**🆕 v2.2 changes (team decisions 2026-06-06 evening → 2026-06-07 AM):**
- **A is OFF YOLO.** A confirmed "not using yolo" 2026-06-06 22:13. The YOLO insurance track is officially killed; A is not training a custom YOLOv11 RoboMaster model. A may poke at TensorFlow / ImageAI / OpenCV alternatives but flagged those as exploratory only — do not plan around them.
- **A reallocated** to: (1) ArUco helper on the Hula camera feed (same `cv2.aruco` pattern Z built for Challenge 1), (2) arena-scouting role Day-1 morning since the map isn't provided, (3) judge-talker / floor role, (4) USB packaging for A's own backup of work product (see laptop risk below).
- **A's laptop is unreliable** — A reported 2026-06-07 00:13 that it's "been repeating quite often". Treat as a Day-1 reliability risk; primary code lives on Z + K laptops too, and A USBs work nightly.
- **K starts Hula swarm search algorithm tonight** (per 2026-06-06 21:36) — this is the Challenge 2B lawnmower / coverage logic on top of the existing swarm controller draft.
- **Z secured a backup Intel depth camera** from a friend (close-to-D435, not exact model match). Reliability redundancy for the mapping drone Realsense path.
- **Open org question (Z, 2026-06-07):** "are we doing 2 challenges at once or 1 then 2?" — needs a fresh ticket (old ticket etiquette: close stale, open fresh).

**🆕 v2.2 changes (org drops 2026-06-06 PM, captured 2026-06-07 AM):**
- **ArUco beside Hula landing pads too** (org 2026-06-06 PM); markers are **20cm x 20cm**; **exact dictionary will be announced Day-1** — controller `--aruco-dict` flag must accept any standard dict. Same ArUco-aided landing aid pattern now applies to BOTH Challenge 1 (mapping drone landing-pad classification) AND Challenge 2A (Hula landings); Hula side uses `cv2.aruco` directly rather than the pyhulax landing-marker auto-land helper. Marker physical size (20cm) sets the detection-range budget — mapping drone altitude should be tuned so markers stay in reliable detection range. Audit of `mapping.py:ArucoDetector` confirms `--aruco-dict` currently accepts: `4X4_50`, `4X4_100`, `4X4_250`, `5X5_250`, `6X6_50`, `6X6_100`, `6X6_250`, `6X6_1000`, `7X7_250` (uppercase short-form only, exact match). **Gap:** missing `4X4_1000`, `5X5_{50,100,1000}`, `7X7_{50,100,1000}`, all 4 APRILTAG variants, no case-insensitive matching, no `DICT_` long-form. Code edit required before Day-1 to cover any dict the org might announce. **(RESOLVED — `mapping.py:ArucoDetector` now accepts all 20 standard dicts, case-insensitive, `DICT_` prefix optional; default `--aruco-dict 7X7_1000,6X6_250` scans both every frame. See section 3 / risk table.)**
- **Org ticket etiquette:** close stale support tickets and open fresh ones for new questions so the queue stays prioritised. STINKIES' 2026-06-06 14:13 "what codes should we come prepared with on 10 June?" is still unanswered.

**🆕 v3.0 changes (2026-06-09 T-1, from the official Finals brief pptx received Telegram 22:06 SGT — supersedes all earlier Discord-derived schedule/scoring assumptions):**

- **Authoritative source:** `semifinal/finals_brief_extracted.md` (extracted from the org pptx). Read for any field-by-field detail; everything below is the distilled call-to-action.
- **Locked schedule (slide 12):**
  - Day 1 (Wed 10 Jun) Uni: 0930-1030 briefing → 1030-1200 testing → 1200-1300 lunch → 1300-1330 testing → 1330-1430 prep for C1 **(NO MAPPING DRONE FLYING)** → 1430-1800 **Challenge 1 (SCORED, Uni only)** → ~1800 end.
  - Day 2 (Thu 11 Jun): 0900-1230 testing → 1230-1330 lunch → 1330-1600 **Challenge 2 (SCORED)** → ~1600 end.
  - The "9-hr workshop-style day" framing from v2.x is **wrong**. C1 has a single 3.5-hour scored window; C2 has a single 2.5-hour scored window. We don't get unlimited iteration.
- **Order of assessment (slides 13-14):**
  - **Challenge 1:** ARTIFICIALLYUNINTELLIGENT = **slot #3** (after 4FINGERS at #1, AAA at #2). Expect call ~10-15 min after slot 1 starts at 14:30 → ~14:40-14:45.
  - **Challenge 2:** ARTIFICIALLYUNINTELLIGENT = **slot #3, convoy opponent STD**. Same expected delay from 13:30 → ~13:40-13:45.
  - **Challenge 2 slot #24: we drive 2 convoy RoboMasters against THE WIENERS.** This is a cross-team duty — K + A take an org-supplied RoboMaster controller each; Z stays on artifacts.
- **Drone sharing (slide 22):** We get **Hula 3,4 + Mapping 3,4**, shared with **BOYD BUDDIES (slot #4)**. Back-to-back handoff. Coordinate with BOYD BUDDIES Day-1 morning — agree on hot-battery swap pattern + who returns drones to cage marshal.
- **Speed caps (slides 5,6):**
  - Mapping drone: **0.3 m/s max**. The primary entry point is now `python3 -m mapping_drone` → `moveit_mission` (MAVSDK on `serial:///dev/ttyS6:921600`); `controller.py` is RETIRED (legacy, no longer an entry point), and `px4_mission` is the PX4-ROS2/XRCE fallback only. Clamp `moveit_mission`'s cruise/velocity caps to 0.3 m/s before Day-1.
  - Hula: **0.5 m/s max, recommended height 1.1 m, STRICTLY NO FLYING OVER OBSTACLES.** Different altitude regime from the 3.5 m mapping-drone floor — two altitude profiles needed.
- **Time budgets:** Each scored attempt is **max 8 min** (slide 5 mapping + slide 6 hula). Our `--max-flight-time-s` defaults to 420 s (7 min) — already sized 60 s under the 480 s org cap, no further extension needed.
- **Scoring rubric (slide 9) for University (total 100%):**
  - S/N 1 (15%): C1 — # landing pads detected (image recognition) + # landing points verified (ArUco) + timing.
  - S/N 2 (15%): C1 — accuracy of distance from reference point using depth map. **Depth accuracy explicitly scored — P1 priority for Z.**
  - S/N 3 (30%): C2 — # landings within hoop + timing.
  - S/N 4 (30%): C2 cont'd — # ArUco detections + timing.
  - S/N 5 (4%): bonus — Counter UAS tech showcase completion.
  - S/N 6 (7%): bonus — overall concept explanation.
  - (Pre-Uni split is 44% C2A + 44% C2B + 4% + 8%, no C1.)
- **Validity rule (slide 5):** "Before the assessment starts, the valid and invalid ArUco Marker IDs will be announced." Org publishes at venue — our `lookup` validity rule path is correct.
- **Challenge 2A landing coords (slide 6):** Org provides 5 valid coords via Discord; we pick 3. **Our C1 output does NOT feed C2A** (judges don't require it). `HANDOFF_C1_TO_C2.md` is internal awareness only.
- **Artifact outputs:**
  - C1: top-down depth map + ArUco marker images (with annotation).
  - C2B: "print the outputs from the ArUco marker on the ground robot" — likely means produce annotated snapshots, not literal paper. Verify Day-1.
- **Crash policy (slide 18):** **No re-assessment if drone crashes.** SAFE-FIRST is mandatory. This kills Config B (aggressive) as a first-attempt option; Config A only until C1 is banked.
- **Testing regulations (slides 16-18):**
  - FCFS Discord queue, no prior booking. 5 min/session in either cage.
  - Hula: 2 teams in cage at once, 20-min cooldown after each test.
  - Mapping drone: per-day per-team **total** allowance (carries over within day, NOT per-session).
  - **1 hour no-testing penalty** for any rule violation.
- **Logistics per team (slides 20-22):** 1 mapping drone + 1 Hula drone (both shared with BOYD BUDDIES), 1 sample landing pad, 1 sample ArUco pad, 1 laptop + charger + mouse. No personal-laptop dependency for the scored mission.
- **Layout warning (slide 5):** "The landing pads for the assessment will have a different configuration compared to the test set-up." Test runs do not transfer 1-1.
- **CUAS booth bonus (slide 10):** Photo of drone at Counter UAS booth + screenshot of zone-explored page. Booth = Above & Beyond: Skies & Space zone, MBS L4. **4% — easy points, collect Day 1.**
- **Code touches required before Day-1:**
  1. `moveit_mission` (the live mapping-drone entry point; `controller.py` is retired): clamp cruise/velocity caps to 0.3 m/s.
  2. `swarm_controller.py`: add 0.5 m/s velocity cap + 1.1 m altitude default + obstacle-avoidance assertion (it's still a stub).
  3. Both controllers: surface the per-attempt 8-min limit; current default is already 420 s (sized 60 s under the 480 s org cap).

**🆕 v2.3 changes (2026-06-09 T-1 from 2026-06-07/08 org drops):**
- **Minimum flight height = 3.5 m** (org 2026-06-08 12:18). All pre-staged arena templates (1.5 m / 2.5 m) sit below the floor. Bump every waypoint template to **4.0 m** for margin against the 3.5 m floor and re-verify on a mock dry-run before any scored slot.
- **Mapping drone cameras = Intel Realsense D430 + D450 mixed across runs** (org 2026-06-08 12:18). D435 has RGB; D450 is depth-only stereo IR + projector (no RGB). **Handled in code:** `RealsenseNode` AUTO-falls-back color→IR when all colour profiles fail, so it works on both D435 (RGB) and D450 (no-RGB) with no flag; `--use-ir-for-aruco` forces IR (emitter off for the ArUco frame). Camera is headless (no `cv2.imshow`) and tolerates dropped frames.
- **Camera facing down** (org 2026-06-08 12:19) confirms `--gimbal-pitch -90` default. No change.
- **Resolution configurable** (org 2026-06-08 12:19) confirms `RealsenseNode.PROFILE_CANDIDATES` fallback chain is correct. No change.
- **Launch direction is free; takeoff point is fixed** (org 2026-06-08 12:17). Pre-yaw the drone to the optimal first-scan direction before arming. Captured in `runbook.md` Day-1 morning + `DAY1_RUNBOOK.md` pre-flight.
- **6 still-open questions from other teams** logged in `learning_materials_and_others.md` under *Still-open in other teams' tickets* — candidates for our Day-1 morning ticket batch (camera-pitch commandable, convoy motion model, fly-over-boxes allowance, top-down depth map format, camera resolution/FOV/tag-pixel-count, depth-map format re-ask).

> We got pushed straight from qualifier → finals, skipping the semi-final tier. Reason unknown, doesn't change scope. Same two-drone architecture: Hula swarm + mapping drone.
>
> **Important:** unlike qualifier we use our OWN laptops, not org-provided VMs. All our Python / pyhulax / pyrealsense2 installs must work on our hardware.
>
> ~~**9-hour days suggest multiple runs / iteration time during the event** — closer to a workshop format than a fixed-slot competition.~~ **Superseded by v3.0 (finals brief slide 12):** scored windows are fixed — C1 = 1430-1800 Day 1 (3.5h, ~14 teams sharing the slot), C2 = 1330-1600 Day 2 (2.5h, ~24 teams). Per-attempt cap 8 min. Treat testing windows (Day 1 1030-1330, Day 2 0900-1230) as the only iteration time; the scored windows are slot-call execution, not free-form runs.

**Contact:** brainhackreg@dsta.gov.sg or brainhack@pico.com

---

## 0. Plan principles

- **Software-first.** Build every drone-touching line of code BEFORE finals. Hardware time is for tuning, not authoring.
- **Use org's reference patterns.** Don't reinvent — `getDepthAndDetect.py` + `generateTopDown.py` + `kolomee.py` are the canonical templates. Copy them and add our own logic on top.
- **Three parallel tracks.** Challenge 1 (mapping + ArUco landing-pad classification), Challenge 2A (3-Hula coordinated landing), Challenge 2B (Hula search + snapshot RoboMasters).
- **Match org's expected env where possible.** Hula swarm runs on the C2 Terminal Windows side; mapping drone code runs onboard via NoMachine. We don't fight the architecture.
- **Fail safe.** Every script: `try / finally land + disarm`. Battery failsafe enabled. Watchdog on every loop. UWB-loss handling.
- **Document as we go.** Update `semifinal/README.md` + `learning_materials_and_others.md` whenever org posts.
- **Day-of runbook = [`OP_DOC.md`](OP_DOC.md).** All mapping-drone operating procedures (Step 0 fingerprint → 1 sensors → 2 check → 3 frame → 4 nofly → 5 fly → 6 artifacts, with lettered fallbacks) live there. This plan is the strategy/schedule/roles; OP_DOC is the procedure. The mapping drone runs as `python3 -m mapping_drone` with three modes: `--check` (connect + pose, no arm), `--nofly` (camera + detect + map, no arm), `--fly` (autonomous).

---

## 1. Workload split (overall)

| Person | Primary focus | Approx load |
|---|---|---|
| **A** | Hula camera ArUco helper + judge-talker + arena scout + USB packaging for own backup (YOLO track killed by A 2026-06-06 22:13) | **~30% (was 70% → 40%)** — YOLO de-scoped 2026-06-06 PM after A confirmed not using YOLO |
| **K** | Hula swarm controller (3 drones, pyhulax, runs on C2 Windows) + **`UWBParserThread` integration** + ArUco detection on Hula camera + Challenge 2A landings + Challenge 2B search/snapshot | ~100% |
| **Z** | Mapping drone controller (Challenge 1: top-down map + ArUco landing pad classifier) + cross-platform glue + docs + runbook | ~100% |

**Reallocation note (2026-06-07, supersedes 2026-06-06):** A confirmed "Nope not using yolo" (team chat 6/6 22:13) — YOLO + annotation_tool dead. A's bandwidth shifts to: (1) helping K wire `cv2.aruco` detection on Hula camera (same pattern Z built for Challenge 1), (2) arena-scouting role Day 1 morning (since map isn't provided), (3) judge-talker / runtime ops role, (4) USB packaging of any backup-detection exploratory work (TensorFlow / ImageAI / OpenCV) onto a shared drive given A's laptop is intermittently failing (7/6 00:13). K + Z still carry the heaviest loads.

---

## 2. Daily breakdown (T-5 → finals)

> Assumption: laptop + D435 + access to a Hula drone (for K) is available by T-5 or T-4. If drones don't arrive in time, K shifts to software prep alongside Z.

### T-5 — Fri 5 June

> **Recap:** this was when slides + L4 + L5 dropped and Plan v2.0 kicked off. Catch-up + replan day.

| Person | Tasks | Deliverables |
|---|---|---|
| **A** | (1) Read [`CHALLENGE_BREAKDOWN.md`](CHALLENGE_BREAKDOWN.md). (2) **Switch to YOLOv11n base** (`yolo11n.pt`) — org confirmed YOLOv11 is the required base, not YOLOv8. (3) **Pivot training target to RoboMaster ground robots** (not barrels) — search Discord / web for RoboMaster S1 / EP imagery, start a dataset. (4) Read [`learning_material_5_yolo_rknn/README.md`](learning_material_5_yolo_rknn/README.md) — use `_2.py` variants of org conversion scripts (those are the canonical ones). | RoboMaster YOLOv11 training started |
| **K** | (1) Read [`CHALLENGE_BREAKDOWN.md`](CHALLENGE_BREAKDOWN.md). (2) **Install pyhulax + opencv-contrib-python + numpy + pyrealsense2** on personal laptop for dev (still useful). (3) Run all 3 prototype scripts ([`semifinal/prototypes/`](prototypes/)) against D435. (4) Print 4-6 DICT_6X6_250 ArUco markers. (5) Start drafting Hula swarm controller using `huladola.py` pattern; 3 drones, Challenge 2 focus. | Prototypes verified; ArUco markers printed; swarm controller draft started |
| **Z** | (1) Read [`CHALLENGE_BREAKDOWN.md`](CHALLENGE_BREAKDOWN.md). (2) Start `semifinal/mapping_drone/controller.py` adapting `kolomee.py` + `generateTopDown.py` + `getDepthAndDetect.py` — fuse top-down occupancy grid across frames using UWB pose. (3) Add ArUco-marker landing-pad classifier (using L4 patterns). | Mapping drone controller skeleton runs locally with mock UWB + real D435 |

**Evening sync.** University category confirmed (2026-06-05). Challenge 1 mapping IS our deliverable; Z proceeds on mapping drone code without pivoting.

### T-4 — Sat 6 June (today)

| Person | Tasks | Deliverables |
|---|---|---|
| **A** | (1) **YOLO track killed 2026-06-06 22:13** — no dataset / no training. (2) **Diagnose + stabilise laptop** (intermittent failures reported 7/6 00:13) OR resign self to running off Z/K laptops Day-1. (3) Pack any exploratory detection scripts (TensorFlow / ImageAI / OpenCV) onto a shared drive + USB before bed. (4) Review Hula camera ArUco helper plan with K. | Laptop diagnosis logged; exploratory work backed up to shared drive |
| **K** | (1) Hula swarm controller: 3-drone discovery via `Dola` + per-drone state machine + simultaneous takeoff + simultaneous landing. (2) Challenge 2A logic: take 3 target (X,Y,Z) waypoints → assign 1 per drone → fly + land. (3) Challenge 2B sketch: search pattern (e.g., lawnmower split between 3 drones) + per-drone ArUco detection + snapshot-on-detection. (4) Integrate `UWBParserThread` (see [`uwb_api_hula_swarm/README.md`](uwb_api_hula_swarm/README.md)) into the swarm controller (NOT YET BUILT — placeholder for `swarm_controller.py`) — instantiate the pyserial @ 921600 baud parser thread on the C2 Terminal Windows side and wire `get_tag_position(tag_id)` into the per-drone state machine for closed-loop position feedback (separate transport from the mapping drone's ROS2 `uwb_tag` topic). | Swarm controller runs against mock drones for both Challenge 2A and 2B flows; controller consumes `UWBParserThread` tag positions for 3 drones |
| **Z** | (1) Mapping drone controller integrated: UWB sub + Realsense + occupancy grid accumulation across frames (camera-frame → world-frame via UWB) + ArUco landing-pad detection → write `landing_pads.json` with `(world_xyz, aruco_id, marker_image_path)`. (2) Write helper `decide_landing_validity()` (stub until we know the encoding). (3) Run summary + STATUS.txt writer. | Mapping drone controller runs end-to-end against mock MAVSDK + mock UWB + real D435. Outputs `top_down.png`, `landing_pads.json`, marker images. |

(University confirmed — no pivot needed. Z stays on mapping drone, K stays on swarm, both critical.)

### T-3 — Sun 7 June (buffer)

> If T-5 → T-4 fell behind, catch up here. Otherwise: polish + dry runs.

| Person | Tasks |
|---|---|
| **A** | If model is rough: add more training data, augmentation, more epochs. If good: prep the conversion (export ONNX with `convertyolotoonnx_2.py` settings). Confirm RKNN conversion params per `convertyolotoonnx_2.py` + `convertrknn2.py` (YOLOv11 base already locked per v2.1). |
| **K** | Dry run #1 of swarm controller end-to-end (mocked). Walk through emergency-land-all on Ctrl-C. Stress-test 3-drone coordination logic. |
| **Z** | Dry run #1 of mapping drone controller (mocked). Walk through full Challenge 1 mission: takeoff → survey → landing pad detection → ArUco read → output JSON + map. Then **start writing the runbook** ([`semifinal/runbook.md`](runbook.md)). |

### T-2 — Mon 8 June

| Person | Tasks |
|---|---|
| **A** | Final model training run on best dataset. Export `.onnx` using `convertyolotoonnx_2.py` exact settings. Pack training data + script + ONNX model on USB in case we need to retrain at venue. |
| **K** | Dry run #2 — full sim of Challenge 2 (2A landing + 2B search/snapshot) end-to-end against mocks. Aim for smooth muscle memory. Also help Z dry-run Challenge 1 (we're University, both challenges are ours). |
| **Z** | (1) Finalise `semifinal/runbook.md` — roles, T+timeline, fallbacks for Challenge 1 + Challenge 2. Print on paper. (2) USB packaging: code + `best.pt` + `best.onnx` + docs + offline `pyhulax` mirror + `semifinal_scrape.md` + `CHALLENGE_BREAKDOWN.md` onto two USB sticks. |


### T-1 — Tue 9 June

> Light day before finals. Don't introduce new bugs.

| Person | Tasks |
|---|---|
| **A** | (1) Verify all model files load cleanly on the laptop one more time. (2) Pack training laptop (in case last-minute retrain needed at venue). (3) Confirm smart-casual outfit ready + covered shoes. |
| **K** | (1) Battery charge: ALL drone batteries to 100%, charger packed. (2) USB-C cables, spare cables, power adapter, mouse. (3) Run smoke test ONE more time and stop. (4) Read the runbook out loud. (5) Confirm smart-casual outfit + covered shoes. |
| **Z** | (1) Final repo push, double-check both `zb` and `main` are in sync. (2) Verify USB has everything (code, models, runbook printed, learning materials offline copy, pyhulax docs offline mirror). (3) Pack: **personal laptop + mouse + charger + USB×2 + Photo ID + printed confirmation email + paper runbook**. (4) Confirm smart-casual outfit + covered shoes. (5) Sleep 8 hours. |

**Last sync (Tue 9 Jun evening):** team call at 21:00 SGT. Confirm roles for the day. Confirm meeting time + place. Confirm logistics (transport, IDs, snacks).

### Finals Day 1 — Wed 10 June (9:00am – 6:00pm)

> **Runbook:** for the actual step-by-step mapping-drone procedures (sensors → check → frame → nofly → fly → artifacts, with lettered fallbacks), follow [`OP_DOC.md`](OP_DOC.md) — it is THE single day-of decision tree. The schedule below is the time-boxing; OP_DOC is the how.

| Time | Action |
|---|---|
| **6:00am** | Wake. Light breakfast. **Smart casual** dress code — covered footwear (NO slippers / sandals). |
| **6:30** | Final bag check: **personal laptop + mouse + charger** (mandatory), Photo ID, confirmation email (print + on phone), USB×2 with code + models, phones, paper runbook, pen, notebook, water, snack. Spare cables (USB-A, USB-C, HDMI), power strip if you have one. |
| **6:45** | Leave for MBS. Train + walk = ~30-45 min from most parts of SG. |
| **7:30** | **Registration counter opens** — Marina Bay Sands Expo and Convention Centre, **Level 4**. Collect lanyard + swag. Show photo ID + confirmation email. |
| **7:45–9:00** | On-site setup window. Find a spot, plug in, boot laptops, verify WiFi, sanity-check that `pyhulax` + `pyrealsense2` import. K runs the 3 prototype scripts as a smoke. Z reviews the runbook one more time. Find BOYD BUDDIES (slot #4) and agree on Hula/Mapping 3,4 handoff cadence. |
| **0930 – 1030** | **Org briefing.** Capture validity rule + ArUco dict + valid/invalid ID split announced here. Pass the dict to `--aruco-dict` and edit `configs/valid_ids_finals.json` with the marshal's real valid/invalid split before any scored slot (see [`OP_DOC.md`](OP_DOC.md)). |
| **1030 – 1200** | **Testing window** — Uni teams choose mapping cage or hula cage. FCFS via Discord. Mapping = per-day total allowance (carries over); Hula = 5 min/session + 20 min cooldown, 2 teams in cage max. Walk the mapping drone through [`OP_DOC.md`](OP_DOC.md): fingerprint → `--check` → frame → `--nofly` → `--fly`. |
| **1200 – 1300** | Lunch (no testing). Standup: apply briefing findings to configs. |
| **1300 – 1330** | Last testing window before C1 prep. Pick weakest path. |
| **1330 – 1430** | **Prep for Challenge 1 — NO MAPPING DRONE FLYING.** Mock dry-run only, USB sanity, configs locked. |
| **1430 – 1800** | **Challenge 1 (Uni only) — SCORED.** We are **slot #3** — expect call ~14:40-14:45. Max 8 min/attempt. Crash = no re-assessment. Use Configuration A (safe). |
| **~1800** | Day 1 ends. Final artifact copy to USB. Confirm with judges, thank them, leave. **CUAS booth bonus** — collect today if not already (4% easy points, Above & Beyond zone). |
| **Evening** | Dinner debrief. Update `progress.md` with what worked / failed. Decide overnight code changes (small + safe only). |

**Roles (lock at Mon evening sync):**
- **Keyboard (K):** drives terminal, swaps SD cards, plugs/unplugs batteries
- **Screen-watcher (Z):** watches log_broadcaster + STATUS.txt, calls out detections, holds runbook
- **Judge-talker / floor (A):** answers judge questions, manages physical drones / markers / Realsense placement, takes photos for our records

### Finals Day 2 — Thu 11 June (9:00am – 6:00pm)

| Time | Action |
|---|---|
| **6:00am** | Wake. Same routine. Re-check overnight changes loaded onto USB + laptop. |
| **8:00** | Arrive at venue. No new registration needed (lanyards from Day 1). |
| **8:30 – 9:00** | Setup. Verify everything still works after laptop sleep/restart. |
| **0900 – 1230** | **Testing window.** Mapping drone allowance resets daily; Hula 5 min + 20 min cooldown still applies. Coordinate Hula 3,4 + Mapping 3,4 cage handoff with BOYD BUDDIES. Focus on C2A landing accuracy + C2B ArUco-on-RoboMaster detection range. |
| **1230 – 1330** | Lunch (no testing). Pick 3 of 5 landing coords from the org's Discord drop. Final config check. |
| **1330 – 1600** | **Challenge 2 — SCORED.** We are **slot #3** with **STD as convoy opponent**. Expect call ~13:40-13:45. C2A: 3-Hula landings (0.5 m/s, 1.1 m, no fly-over). C2B: RoboMaster hunt via ArUco. Each attempt max 8 min. Crash = no re-assessment. **At slot #24 we drive 2 convoy RoboMasters against THE WIENERS** — K + A take a controller each, Z stays on artifacts. |
| **~1600** | Day 2 ends. Final results announced. Write the retro in `progress.md` before leaving. **CUAS booth bonus** — must be collected by now if not done Day 1. |

---

## 3. Dependencies + handoffs (so nobody blocks anyone)

**PRIMARY DETECTION PATH:** ArUco via `cv2.aruco` — runs on (a) mapping drone for Challenge 1 landing-pad IDs (wired in `mapping.py`, driven by the `moveit_mission` entry point; `controller.py` is retired), (b) Hula camera for ground-robot detection in Challenge 2B (K + A to wire, no model handoff needed, `opencv-contrib-python` ships it). Default `--aruco-dict` is **`7X7_1000,6X6_250`** and BOTH dicts are scanned every frame (we only guessed 7X7 from Discord; org markers are assumed DICT_7X7_1000, IDs 11/45/51/67/101 — CONFIRM with marshal). `--aruco-dict` accepts any of the 20 standard dicts (case-insensitive, `DICT_` prefix optional) — swap on the venue command line once org announces the actual dict.

```
INSURANCE PATH (YOLO backup):

A: train RoboMaster YOLO (best.pt)
     │
     ▼ ONNX export (T-2 latest, T-3 ideal)
A: best.onnx ───────────────────────────────► hand off to K + Z (insurance, non-blocking)
     │
     ▼ RKNN conversion at venue on org VM (Day 1 morning)
     │
A: best.rknn ──────► mapping drone code uses .rknn (if insurance is needed)
```

**RKNN conversion is AT VENUE on org VM** (not on our laptops). If the insurance model is needed, conversion takes ~5 min on the org VM (assuming their toolchain works as documented).

```
K: Hula swarm controller (mocked) [T-5 → T-4]
     │
     ▼ dry runs T-3, T-2
K: ready for Challenge 2 at venue [T-1]
```

```
Z: Mapping drone controller [T-5 → T-4]
     │
     ▼ Realsense + ArUco landing-pad classifier [T-4]
     │
     ▼ run-summary + emergency-land [T-4]
     │
     ▼ dry run T-3, runbook T-2
Z: ready for Challenge 1 at venue [T-1]
```

**Handoff windows:**
- A → K + Z: `best.pt` + `best.onnx` by **Mon 8 June 20:00 SGT** (T-2 evening). Earlier if possible. (insurance, non-blocking)
- K + Z: cross-review each other's controllers by **T-2 evening**.
- All: USB packed + runbook printed by **T-1 morning**.

---

## 4. Stack of risks + mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| ~~RoboMaster training data is hard to find~~ | **OBSOLETED 2026-06-06** | Detection is ArUco-based, not YOLO. YOLO model is insurance only. |
| ArUco markers on RoboMasters are too small / occluded for Hula camera | Medium | Train YOLO backup (A's track) + tune Hula camera focal length / fly altitude. Verify Day 1 morning during arena scouting. |
| Map layout unknown until venue | High (org confirmed not provided) | Challenge 1 mapping IS the recon — we discover dimensions + obstacles via the mapping drone before Challenge 2 starts. Make sure controller writes machine-readable obstacle/landing-pad data so Challenge 2 planner can consume it. |
| RoboMasters not UWB-tagged → swarm has to search visually | Medium | Lawnmower pattern split across 3 Hulas, ~1.1m AGL (org recommended Hula altitude, slide 6), ArUco detection on each. Add Day 1 morning question to org. |
| `UWBParserThread` COM port not auto-detected on org C2 Terminal | Low | Auto-detect string is "USB" in port description; fallback = pass `serial_port="COM3"` explicitly. Test Day 1 morning. |
| New `UWBParserThread` Hula-swarm API just released (2026-06-06) — K hasn't integrated into swarm controller yet (NOT YET BUILT — placeholder for `swarm_controller.py`) | High | Wire `UWBParserThread` into the swarm controller by **T-3 (Sun 7 June) end-of-day**. Use the canonical usage block from [`uwb_api_hula_swarm/README.md`](uwb_api_hula_swarm/README.md). Mock-test on Windows before venue. |
| RKNN conversion fails on the org VM | Medium | We have all 4 conversion scripts now — known params (rk3588, fp16, mean/std). Worst case: fall back to ONNX runtime inference on the drone CPU (slower but works). |
| YOLOv11 conversion fails or training is slow | Low | YOLOv11 is insurance only (ArUco is primary detection per 2026-06-06). A trains on `yolo11n.pt` with `_2.py` conversion scripts if time permits; otherwise ship ArUco-only and skip the RKNN export for YOLO. |
| Mapping drone NoMachine session laggy | Medium | Edit code in our local editor → scp to drone over network → run via SSH/NoMachine. Don't try to IDE-edit on the remote session. |
| Hula WiFi flaky at venue (many teams) | Medium | `set_wifi_band(5GHz)`, low video resolution, per-drone reconnect logic. C2 Terminal Windows side is the orchestrator. |
| UWB signal patchy in arena | Medium | Failsafe: hold position on UWB loss >1s, land if sustained. Logged for post-flight review. |
| One of us is sick on finals day | Low | Each task should have a "deputy" — if K is out, Z runs the swarm. Practice cross-coverage in dry runs. |
| Coordinate frame bug (camera-frame vs world-frame, ENU vs NED) | High | **Ground test** every direction command before flying. `generateTopDown.py` is explicit about the convention — match it exactly. |
| ArUco landing-pad validity rule undisclosed | Medium | Code reads + reports all marker IDs regardless. Default rule is now `lookup` → `configs/valid_ids_finals.json` (NOT `even`; an `even` default marked every odd org ID invalid). When the marshal announces the valid/invalid split (Day 1), just edit that JSON — no code change. Env override: `MAPPING_DRONE_VALIDITY` / `MAPPING_DRONE_VALIDITY_LOOKUP`. |
| A's laptop intermittently failing — Day-1 reliability risk | High (A reported 2026-06-07 00:13, "been repeating quite often") | A USBs work nightly; primary code lives on Z + K laptops too. A's role (judge-talker + arena scout + ArUco helper) does not require A's laptop to be the canonical dev box. If A's laptop dies at venue, A operates off Z's or K's machine. |
| Day-1 ArUco dict mismatch — org announces a dict our controller doesn't accept | **MITIGATED** | Controller now accepts all 20 standard dicts (16 ArUco + 4 AprilTag) via case-insensitive `--aruco-dict` per `mapping.py` fix 2026-06-07. Long-form `DICT_` prefix + whitespace also normalised. Smoke-tested: bad name raises ValueError listing all 20 supported names. |
| D450 exposes no RGB stream (D435 does) | **MITIGATED** | `RealsenseNode` AUTO-falls-back color→IR when all colour profiles fail, so it runs on D435 (RGB) and D450 (no-RGB) with NO flag. `--use-ir-for-aruco` forces IR (emitter off for the ArUco frame). Headless, tolerates dropped frames. |
| All arena waypoint templates sit below the 3.5 m minimum altitude floor | **High** (org 2026-06-08 12:18 set the 3.5 m floor; existing templates are 1.5 m / 2.5 m) | Bump every waypoint template to 4.0 m (3.5 m floor + 0.5 m margin). Re-verify with a mock dry-run before any scored slot. Owner: Z. |
| Code crashes mid-run | Medium | `try/finally land + disarm` everywhere. Watchdog 60s. Battery failsafe enabled. |
| Org's drones differ from what we trained for | Low | We've reviewed all org reference code; adaptation should be small. |
| ~~Pre-University~~ | N/A | We are University (confirmed 2026-06-05). |
| **University category** (confirmed) | DONE | Challenge 1 IS ours. Mapping drone + ArUco landing-pad classifier is the biggest single deliverable. K + Z carry full load. |

---

## 5. Repo organisation for finals

By T-2, the repo should look like:

```
hackerverse/
├── semifinal/
│   ├── FINALS_PLAN.md                    ← this file
│   ├── runbook.md                        ← day-of step-by-step (Z writes T-2)
│   ├── README.md                         ← overall prep report
│   ├── swarm_controller.py               ← Hula swarm orchestrator (K + Z) (NOT YET BUILT — placeholder)
│   ├── mapping_drone/                    ← run as `python3 -m mapping_drone` (Z)
│   │   ├── moveit_mission.py             ← PRIMARY entry point (MAVSDK on serial:///dev/ttyS6:921600)
│   │   ├── px4_mission.py                ← PX4-ROS2/XRCE FALLBACK only
│   │   └── controller.py                 ← LEGACY, RETIRED (no longer an entry point)
│   ├── OP_DOC.md                         ← THE day-of runbook (decision tree, Step 0→6 + fallbacks)
│   ├── uwb_api_hula_swarm/               ← UWBParserThread.py + PDF (org released 2026-06-06, Hula swarm UWB via pyserial @ 921600)
│   ├── run_finals.py                     ← unified launcher (Z, T-3) (NOT YET BUILT — placeholder)
│   ├── hula_smoke.py                     ← single-drone smoke (K, T-5) (NOT YET BUILT — placeholder)
│   ├── prototypes/                       ← drone-free validation (done)
│   ├── docs/                             ← analyses + offline mirrors (done)
│   ├── learning_material_3_uwb/          ← done
│   ├── learning_material_4_realsense/    ← done
│   ├── learning_material_5_yolo_rknn/    ← done
│   └── thumbdrive/                       ← USB contents (Z, T-2) (NOT YET BUILT — placeholder)
├── models/
│   ├── best.pt                           ← A's YOLOv11 insurance model (ArUco is primary detection)
│   ├── best.onnx                         ← A's export
│   └── best.rknn                         ← A's RKNN conversion
└── tools/log_broadcaster/                ← done
```

---

## 6. Communication

**Slack/Discord channel:** existing team channel
**Daily sync:** evening, ~15 min, brief — what's done, what's blocked, what's tomorrow
**Sync hours:** 21:00 SGT each day (T-6 → T-1)
**Finals day comms:** WhatsApp group + phone calls. Discord open on phone for org announcements.

---

## 7. What we WILL ship (success criteria)

| Item | Owner | Done means |
|---|---|---|
| Hula swarm controller | K + Z | Drives N drones, detects targets, lands all on Ctrl-C, writes run summary |
| Mapping drone controller | Z | `moveit_mission` (MAVSDK) + Realsense + ArUco landing-pad classifier (default `--aruco-dict 7X7_1000,6X6_250`, both scanned every frame; accepts any of the 20 standard dicts), writes top_down.png + landing_pads.json + marker images + run_summary.json. `controller.py` retired. YOLO insurance track de-scoped (A confirmed not using YOLO 2026-06-06). |
| Trained model in 3 formats | A | `.pt`, `.onnx`, `.rknn` all load without error, smoke-tested |
| Runbook | Z | Printed paper copy in venue bag |
| USB pack | Z | All code + models + docs on USB, tested by extracting on fresh laptop |
| Backup laptop | K | At venue, can swap in if primary dies |
| Practiced roles | All | Each member knows their job for finals day without reading the runbook |

---

## 8. What we WILL NOT ship (de-scope explicitly)

To avoid scope creep:
- No fancy mission planner — waypoints are hardcoded per slot, adjusted per arena
- No machine-learning-based path optimisation — straight lines + the SDK's barrier mode is enough
- No occupancy-grid SLAM — produce a top-down PNG from Realsense pointcloud accumulation; that's enough mapping for the judge
- No PostgreSQL flight logger — SQLite or JSONL is fine
- No web dashboard — `STATUS.txt` + log broadcaster is enough for assistant-watched runs
- No multi-arena layout adaptation — handle the actual arena when we see it on the 10th

---

## 9. Packing checklist (per person)

### Everyone brings
- [ ] **Photo ID** (IC / EZ-Link / Passport — at least one)
- [ ] **Confirmation email** — printed AND on phone (in case phone dies)
- [ ] Phone, fully charged + charger
- [ ] Lanyard from Day 1 (Day 2 only)
- [ ] **Smart casual outfit + COVERED footwear** (no slippers, no sandals — strict)
- [ ] Water bottle, snacks
- [ ] Notebook + pen for jotting observations

### Z (primary keyboard, also packs the kit)
- [ ] **Personal laptop + charger + mouse**
- [ ] **USB stick × 2** (identical contents — code, models, docs)
- [ ] Spare USB-A and USB-C cables
- [ ] HDMI cable (in case external display available)
- [ ] **Paper runbook** (printed copy of `semifinal/runbook.md`)
- [ ] Power strip / multi-adapter

### K (drones + hardware)
- [ ] Hula drone(s) if BYO — fully charged
- [ ] **All drone batteries to 100%**, spares included
- [ ] Drone chargers
- [ ] **Realsense D435 + USB-C cable** (high-quality, USB 3.0+ rated)
- [ ] Personal laptop + charger + mouse (backup if Z's dies)
- [ ] Small toolkit (screwdriver set, if BYO drone needs adjustment)

### A (ML + backup)
- [ ] Training laptop + charger + mouse (in case last-minute retrain)
- [ ] USB with training dataset
- [ ] Phone for taking photos of detection output / arena

### Optional but smart
- [ ] Portable WiFi router (if venue WiFi is shared/congested)
- [ ] 4G/5G hotspot dongle (backup network)
- [ ] Cash + EZ-Link card for transport home if it runs late

---

## 10. After-action

After Day 1 (Wed 10 June):
- Debrief over dinner
- Update `progress.md` with what worked / failed
- Cherry-pick fixes for Day 2

After Day 2 (Thu 11 June):
- Win or lose, **write the retro** in `progress.md`
- Push final repo state to both branches
- Save run artifacts off the USB to durable storage (Drive backup, etc)

---

*Plan v1 — created 2026-06-03 evening. Iterate as L4/L5 unlock and org clarifications arrive.*
*Owner of this file: Z. Edits welcome via PR or direct push.*

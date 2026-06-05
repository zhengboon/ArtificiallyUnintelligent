# BrainHack 2026 — Finals Plan

**Finals dates:** Wed 10 June + Thu 11 June 2026
**Hours each day:** 9:00am – 6:00pm (full 9-hour day, NOT a 40-min slot like qualifier)
**Venue:** Marina Bay Sands Expo and Convention Centre, Level 4
**Registration:** counter opens 10 June 7:30am — bring **Photo ID + confirmation email**
**Dress code:** Smart Casual. **Strictly no slippers or uncovered footwear.**
**Bring:** personal laptop, mouse, charger; note-taking tools; thumbdrive (or HDD + USB cables) for code transfer

**Today:** 2026-06-05 Fri (T-5 / T-6 days)
**Plan version:** v2.0 (major rewrite after org released L4 + L5 + Final Challenge slides on 2026-06-05)

**MAJOR UPDATES vs v1.x:**
- Two challenges revealed in slides — Challenge 1 (Reconnaissance, University-only — **CONFIRMED we are University, so this IS ours**) + Challenge 2 (Deployment & Ambush, everyone)
- **Task 1 / Task 2 / Task 3** is org's internal name for the 3 sub-tasks (= our Challenge 1 + 2A + 2B)
- **C2 Terminal** ("dedicated laptop" per team, org-provided Windows + Ubuntu 22.04 VM) — Task 2 + Task 3 run from HERE, not on personal laptop
- **Drones are SHARED across teams** — testing time slots assigned per team. Slot announcement coming.
- **3 Hula drones** in the swarm (confirmed)
- **5 RoboMaster ground robots** as targets for Challenge 2B (NOT barrels!) — A's model trains on RoboMasters
- **YOLOv11 confirmed** as base model (NOT v8) — org said use `yolo11n.pt` as base when custom-training
- **`_2.py` variants** of conversion scripts (`convertyolotoonnx_2.py` + `convertrknn2.py`) are canonical — older versions exist but use `_2`
- **Mapping drone has Ubuntu 22.04 + ROS2 + OpenCV pre-installed** + RKNN-NPU at ~50 FPS
- **NoMachine** = access pattern from C2 Terminal → mapping drone
- **RKNN conversion tooling lives on the org VM** — we don't need to install it ourselves (but should be familiar)
- All org reference scripts pulled and analysed (`learning_material_4_realsense/`, `learning_material_5_yolo_rknn/`, `learning_material_3_uwb/kolomee.py`)
- See [`CHALLENGE_BREAKDOWN.md`](CHALLENGE_BREAKDOWN.md) for the authoritative rules from slides

> We got pushed straight from qualifier → finals, skipping the semi-final tier. Reason unknown, doesn't change scope. Same two-drone architecture: Hula swarm + mapping drone.
>
> **Important:** unlike qualifier we use our OWN laptops, not org-provided VMs. All our Python / pyhulax / pyrealsense2 installs must work on our hardware.
>
> **9-hour days suggest multiple runs / iteration time during the event** — closer to a workshop format than a fixed-slot competition. Strategy adapts: warm up, take a measured first run, iterate based on observed scoring, peak in afternoon runs.

**Contact:** brainhackreg@dsta.gov.sg or brainhack@pico.com

---

## 0. Plan principles

- **Software-first.** Build every drone-touching line of code BEFORE finals. Hardware time is for tuning, not authoring.
- **Use org's reference patterns.** Don't reinvent — `getDepthAndDetect.py` + `generateTopDown.py` + `kolomee.py` are the canonical templates. Copy them and add our own logic on top.
- **Three parallel tracks.** Challenge 1 (mapping + ArUco landing-pad classification), Challenge 2A (3-Hula coordinated landing), Challenge 2B (Hula search + snapshot RoboMasters).
- **Match org's expected env where possible.** Hula swarm runs on the C2 Terminal Windows side; mapping drone code runs onboard via NoMachine. We don't fight the architecture.
- **Fail safe.** Every script: `try / finally land + disarm`. Battery failsafe enabled. Watchdog on every loop. UWB-loss handling.
- **Document as we go.** Update `semifinal/README.md` + `learning_materials_and_others.md` whenever org posts.

---

## 1. Workload split (overall)

| Person | Primary focus | Approx load |
|---|---|---|
| **A** | ML pipeline: train RoboMaster YOLO, ONNX export, RKNN (org's tooling), validate | ~70% |
| **K** | Hula swarm controller (3 drones, pyhulax, runs on C2 Windows) + Challenge 2A landings + Challenge 2B search/snapshot | ~100% |
| **Z** | Mapping drone controller (Challenge 1: top-down map + ArUco landing pad classifier) + cross-platform glue + docs + runbook | ~100% |

A's lighter load is intentional — model training is the longest-iteration task and can stall. K + Z carry equal heavier loads. **Confirmed University category — Challenge 1 IS ours**, so Z's mapping work is core, not optional.

---

## 2. Daily breakdown (T-6 → finals)

> Assumption: laptop + D435 + access to a Hula drone (for K) is available by T-5 or T-4. If drones don't arrive in time, K shifts to software prep alongside Z.

### T-5 — Fri 5 June (today)

> **Critical:** today is when slides + L4 + L5 dropped. Plan v2.0 starts here. Catch up + replan day.

| Person | Tasks | Deliverables |
|---|---|---|
| **A** | (1) Read [`CHALLENGE_BREAKDOWN.md`](CHALLENGE_BREAKDOWN.md). (2) **Switch to YOLOv11n base** (`yolo11n.pt`) — org confirmed YOLOv11 is the required base, not YOLOv8. (3) **Pivot training target to RoboMaster ground robots** (not barrels) — search Discord / web for RoboMaster S1 / EP imagery, start a dataset. (4) Read [`learning_material_5_yolo_rknn/README.md`](learning_material_5_yolo_rknn/README.md) — use `_2.py` variants of org conversion scripts (those are the canonical ones). | RoboMaster YOLOv11 training started |
| **K** | (1) Read [`CHALLENGE_BREAKDOWN.md`](CHALLENGE_BREAKDOWN.md). (2) **Install pyhulax + opencv-contrib-python + numpy + pyrealsense2** on personal laptop for dev (still useful). (3) Run all 3 prototype scripts ([`semifinal/prototypes/`](prototypes/)) against D435. (4) Print 4-6 DICT_6X6_250 ArUco markers. (5) Start drafting Hula swarm controller using `huladola.py` pattern; 3 drones, Challenge 2 focus. | Prototypes verified; ArUco markers printed; swarm controller draft started |
| **Z** | (1) Read [`CHALLENGE_BREAKDOWN.md`](CHALLENGE_BREAKDOWN.md). (2) Start `semifinal/mapping_drone/controller.py` adapting `kolomee.py` + `generateTopDown.py` + `getDepthAndDetect.py` — fuse top-down occupancy grid across frames using UWB pose. (3) Add ArUco-marker landing-pad classifier (using L4 patterns). | Mapping drone controller skeleton runs locally with mock UWB + real D435 |

**Evening sync.** University category confirmed (2026-06-05). Challenge 1 mapping IS our deliverable; Z proceeds on mapping drone code without pivoting.

### T-4 — Sat 6 June

| Person | Tasks | Deliverables |
|---|---|---|
| **A** | (1) Continue RoboMaster dataset (target: 200-500 labelled frames). (2) Initial training run (YOLOv8n or YOLOv11n — small model since NPU prefers it). (3) **Optional:** install `rknn-toolkit2` on WSL2/Linux to test conversion locally with a dummy model (validates the pipeline before A's real model is ready). | First model checkpoint (low quality is fine — proves pipeline) |
| **K** | (1) Hula swarm controller: 3-drone discovery via `Dola` + per-drone state machine + simultaneous takeoff + simultaneous landing. (2) Challenge 2A logic: take 3 target (X,Y,Z) waypoints → assign 1 per drone → fly + land. (3) Challenge 2B sketch: search pattern (e.g., lawnmower split between 3 drones) + per-drone YOLO inference + snapshot-on-detection. | Swarm controller runs against mock drones for both Challenge 2A and 2B flows |
| **Z** | (1) Mapping drone controller integrated: UWB sub + Realsense + occupancy grid accumulation across frames (camera-frame → world-frame via UWB) + ArUco landing-pad detection → write `landing_pads.json` with `(world_xyz, aruco_id, marker_image_path)`. (2) Write helper `decide_landing_validity()` (stub until we know the encoding). (3) Run summary + STATUS.txt writer. | Mapping drone controller runs end-to-end against mock MAVSDK + mock UWB + real D435. Outputs `top_down.png`, `landing_pads.json`, marker images. |

(University confirmed — no pivot needed. Z stays on mapping drone, K stays on swarm, both critical.)

### T-3 — Sun 7 June (buffer)

> If T-5 → T-4 fell behind, catch up here. Otherwise: polish + dry runs.

| Person | Tasks |
|---|---|
| **A** | If model is rough: add more training data, augmentation, more epochs. If good: prep the conversion (export ONNX with `convertyolotoonnx_2.py` settings). Lock in YOLOv8 vs YOLOv11 decision based on what's easier to RKNN-convert. |
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

| Time | Action |
|---|---|
| **6:00am** | Wake. Light breakfast. **Smart casual** dress code — covered footwear (NO slippers / sandals). |
| **6:30** | Final bag check: **personal laptop + mouse + charger** (mandatory), Photo ID, confirmation email (print + on phone), USB×2 with code + models, phones, paper runbook, pen, notebook, water, snack. Spare cables (USB-A, USB-C, HDMI), power strip if you have one. |
| **6:45** | Leave for MBS. Train + walk = ~30-45 min from most parts of SG. |
| **7:30** | **Registration counter opens** — Marina Bay Sands Expo and Convention Centre, **Level 4**. Collect lanyard + swag. Show photo ID + confirmation email. |
| **7:45–8:45** | On-site setup window. Find a spot, plug in, boot laptops, verify WiFi, sanity-check that `pyhulax` + `pyrealsense2` import. K runs the 3 prototype scripts as a smoke. Z reviews the runbook one more time. |
| **9:00** | **Event starts.** Watch for org's specific instructions on slot structure (multiple runs in a 9hr day vs one long mission TBD). |
| **9:00 – 12:00** | Morning block: first scored run, learn from it, iterate. Banking the safe run first is the priority. |
| **12:00 – 13:00** | Lunch / debrief. Have one of us write what we observed (target visibility, arena scale, what other teams' approaches look like). |
| **13:00 – 17:30** | Afternoon block: better-tuned runs. Push for higher score. |
| **17:30 – 18:00** | Final artifact copy to USB. Confirm with judges, thank them, leave. |
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
| **9:00 – 18:00** | Same shape as Day 1. Apply Day 1 lessons. If Day 1 was clean, push harder on bonus / extra targets. If Day 1 had issues, fix and re-run the safe configuration first. |
| **End of Day 2** | Final results announced (usually). Whatever happens, write the retro in `progress.md` before leaving. |

---

## 3. Dependencies + handoffs (so nobody blocks anyone)

```
A: train RoboMaster YOLO (best.pt)
     │
     ▼ ONNX export (T-2 latest, T-3 ideal)
A: best.onnx ───────────────────────────────► hand off to K + Z
     │
     ▼ RKNN conversion at venue on org VM (Day 1 morning)
     │
A: best.rknn ──────► mapping drone code uses .rknn
```

**RKNN conversion is now AT VENUE on org VM** (not on our laptops). So the critical path is: model trained + ONNX exported by T-2. Conversion takes ~5 min on the org VM (assuming their toolchain works as documented).

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
- A → K + Z: `best.pt` + `best.onnx` by **Mon 8 June 20:00 SGT** (T-2 evening). Earlier if possible.
- K + Z: cross-review each other's controllers by **T-2 evening**.
- All: USB packed + runbook printed by **T-1 morning**.

---

## 4. Stack of risks + mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| RoboMaster training data is hard to find | High | Use Robomaster S1/EP imagery from web + YouTube frames + Roboflow public datasets. If desperate, capture frames at venue Day 1 morning + retrain that evening. |
| RKNN conversion fails on the org VM | Medium | We have all 4 conversion scripts now — known params (rk3588, fp16, mean/std). Worst case: fall back to ONNX runtime inference on the drone CPU (slower but works). |
| YOLOv11 conversion fails or training is slow | Medium | Org confirmed YOLOv11 is the base. Use `_2.py` conversion scripts. K's old YOLOv8 model is moot — must retrain. |
| Mapping drone NoMachine session laggy | Medium | Edit code in our local editor → scp to drone over network → run via SSH/NoMachine. Don't try to IDE-edit on the remote session. |
| Hula WiFi flaky at venue (many teams) | Medium | `set_wifi_band(5GHz)`, low video resolution, per-drone reconnect logic. C2 Terminal Windows side is the orchestrator. |
| UWB signal patchy in arena | Medium | Failsafe: hold position on UWB loss >1s, land if sustained. Logged for post-flight review. |
| One of us is sick on finals day | Low | Each task should have a "deputy" — if K is out, Z runs the swarm. Practice cross-coverage in dry runs. |
| Coordinate frame bug (camera-frame vs world-frame, ENU vs NED) | High | **Ground test** every direction command before flying. `generateTopDown.py` is explicit about the convention — match it exactly. |
| ArUco landing-pad validity rule undisclosed | Medium | Code reads + reports all marker IDs regardless. When org reveals the rule (Day 1), add the classifier in <30 min. |
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
│   ├── swarm_controller.py               ← Hula swarm orchestrator (K + Z)
│   ├── mapping_drone/
│   │   └── controller.py                 ← mapping drone orchestrator (Z)
│   ├── run_finals.py                     ← unified launcher (Z, T-3)
│   ├── hula_smoke.py                     ← single-drone smoke (K, T-5)
│   ├── prototypes/                       ← drone-free validation (done)
│   ├── docs/                             ← analyses + offline mirrors (done)
│   ├── learning_material_3_uwb/          ← done
│   ├── learning_material_4_realsense/    ← unlock pending
│   ├── learning_material_5_yolo_rknn/    ← unlock pending
│   └── thumbdrive/                       ← USB contents (Z, T-2)
├── models/
│   ├── best.pt                           ← K's qualifier baseline → A retrains
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
| Mapping drone controller | Z | Adapted kolomee.py + Realsense + RKNN, writes map artifact + photos + summary |
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

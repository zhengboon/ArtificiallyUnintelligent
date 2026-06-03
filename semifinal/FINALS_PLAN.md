# BrainHack 2026 — Finals Plan

**Finals dates:** Tue 10 June + Wed 11 June 2026
**Hours each day:** 9:00am – 6:00pm (full 9-hour day, NOT a 40-min slot like qualifier)
**Venue:** Marina Bay Sands Expo and Convention Centre, Level 4
**Registration:** counter opens 10 June 7:30am — bring **Photo ID + confirmation email**
**Dress code:** Smart Casual. **Strictly no slippers or uncovered footwear.**
**Bring:** personal laptop, mouse, charger; note-taking tools; thumbdrive (or HDD + USB cables) for code transfer

**Today:** 2026-06-03 (T-6 / T-7 days)
**Plan version:** v1.1 (added venue + logistics 2026-06-03 evening)

> We got pushed straight from qualifier → finals, skipping the semi-final tier. Reason unknown, doesn't change scope. Same two-drone architecture: Hula swarm + mapping drone.
>
> **Important:** unlike qualifier we use our OWN laptops, not org-provided VMs. All our Python / pyhulax / pyrealsense2 installs must work on our hardware.
>
> **9-hour days suggest multiple runs / iteration time during the event** — closer to a workshop format than a fixed-slot competition. Strategy adapts: warm up, take a measured first run, iterate based on observed scoring, peak in afternoon runs.

**Contact:** brainhackreg@dsta.gov.sg or brainhack@pico.com

---

## 0. Plan principles

- **Software-first.** Build every drone-touching line of code BEFORE drones are in hand. Hardware time is for tuning, not authoring.
- **Carry over qualifier wins.** ~70% of the mapping drone code is qualifier `controller.py` with an SDK swap. The Hula swarm gets ~50% of its work for free from the pyhulax built-ins.
- **Two parallel tracks.** Hula swarm (K + Z) and mapping drone (Z + A handoff). Each platform deployable independently in case the other has issues at venue.
- **Fail safe.** Every script: `try / finally land + disarm`. Battery failsafe enabled. Watchdog on every loop.
- **Document as we go.** Update `semifinal/README.md` and `semifinal/semifinal_scrape.md` whenever org posts.

---

## 1. Workload split (overall)

| Person | Primary focus | Approx load |
|---|---|---|
| **A** | ML pipeline: training, ONNX, RKNN, calibration | ~70% (lighter to leave room for model iteration) |
| **K** | Hula swarm orchestrator + hardware smoke + flight ops | ~100% |
| **Z** | Mapping drone orchestrator + Realsense + cross-platform glue + docs | ~100% |

A's lighter load is intentional — model training can stall and need re-runs, so leave headroom. K + Z carry equal heavier loads on the orchestrators.

---

## 2. Daily breakdown (T-6 → finals)

> Assumption: laptop + D435 + access to a Hula drone (for K) is available by T-5 or T-4. If drones don't arrive in time, K shifts to software prep alongside Z.

### T-6 — Wed 4 June

| Person | Tasks | Deliverables |
|---|---|---|
| **A** | (1) Continue YOLO training on whatever images we have. (2) **Export current best.pt → best.onnx** via `ultralytics`. (3) Start reading [`learning_material_5_yolo_rknn/README.md`](learning_material_5_yolo_rknn/README.md) for what conversion pipeline looks like. | `models/best.onnx` checked into repo |
| **K** | (1) **Install pyhulax + opencv-contrib-python + numpy + pyrealsense2** on laptop. Run `python3 -c "from pyhulax import DroneAPI; from pyhulax.video import YOLODetector; print('OK')"`. (2) Run all 3 prototype scripts ([`semifinal/prototypes/`](prototypes/)): `realsense_verify.py`, `aruco_webcam.py`, `aruco_realsense.py`. Confirm D435 + ArUco work. (3) Print 4-6 DICT_6X6_250 markers on A4. | Screenshots + brief notes in PR. Markers ready. |
| **Z** | (1) **Stand up `semifinal/swarm_controller.py` skeleton** from [`semifinal/README.md §10`](README.md#10-skeleton-code-starting-point). Mock drones (`class MockDrone` with `takeoff/land/move`) so logic testable without hardware. (2) Wire log_broadcaster (`tools/log_broadcaster/`) into the skeleton so every state transition + detection is broadcast. | `semifinal/swarm_controller.py` runs against mock drones, logs reach desktop sink. |

**Evening sync (15 min):** What blocked who, what each person needs from the others tomorrow.

### T-5 — Thu 5 June

| Person | Tasks | Deliverables |
|---|---|---|
| **A** | (1) **Install `rknn-toolkit2`** on a Linux x86 box (or WSL2). This is the conversion-from-host tool. Notoriously version-pinned — Python 3.8–3.11 only. (2) Sample ~100 calibration images from training set (`semifinal/rknn_calibration/`). (3) When org unlocks L5, run their conversion script: `best.onnx → best.rknn` for `rk3588` target. If L5 still locked, try the generic conversion from the [L5 README](learning_material_5_yolo_rknn/README.md) draft. | `models/best.rknn` (or report exact failure mode so we can fix) |
| **K** | (1) **Continue Hula smoke** — if a drone is in hand, run `connect → takeoff(50) → hover(5) → land`. If no drone yet, prep the smoke script (`semifinal/hula_smoke.py`) so it's ready when one arrives. (2) Drive single-drone state machine: takeoff → set_barrier_mode → set_camera_angle(DOWN_ABSOLUTE, 45) → move(FORWARD, 100) → rotate(90) → land. Validate each method. (3) Start integrating K's `best.pt` into `pyhulax.video.YOLODetector` via the swarm controller skeleton. | Hula confirmed working end-to-end with one drone OR drone-free smoke script ready. |
| **Z** | (1) **Draft `semifinal/mapping_drone/controller.py`** by adapting [`kolomee.py`](learning_material_3_uwb/kolomee.py): keep UWB ROS2 subscriber + asyncio MAVSDK + offboard pre-warm + velocity P-controller. (2) Add Realsense capture pipeline (from [`prototypes/aruco_realsense.py`](prototypes/aruco_realsense.py)). (3) Add ArUco detection callback into the loop. (4) Stub the RKNN detection call (A's `.rknn` model goes here when ready). | `semifinal/mapping_drone/controller.py` runs end-to-end against MOCK UWB + MOCK MAVSDK + real Realsense (D435 plugged in). Outputs detection records to disk. |

**Evening sync.**

### T-4 — Fri 6 June

| Person | Tasks | Deliverables |
|---|---|---|
| **A** | (1) Final model iteration — train on the most representative target images. (2) If L5 unlocked, re-run RKNN conversion with org's exact code (their conversion may differ in subtle ways). (3) Build a small test harness: feed 20-30 sample images through `best.rknn` and verify detection rate + class names. Save outputs as `models/rknn_test_results.md`. (4) Hand off `best.pt` (Hulas), `best.onnx` (backup), `best.rknn` (mapping drone) to K + Z. | All 3 model formats committed, test report written. |
| **K** | (1) **Multi-drone Hula smoke** (if ≥2 drones available). Dola discovery → connect both → takeoff both → land both. Validate no command collision. (2) Tune `set_barrier_mode` aggression — observe behaviour at obstacle distances 0.5m / 1m / 2m. Document in `semifinal/swarm_controller_notes.md`. (3) Wire A's `.pt` into `swarm_controller.py` via `YOLODetector`. Live preview should show bboxes on a printed ArUco/barrel. | Multi-Hula smoke OK, detection on live stream OK. |
| **Z** | (1) Integrate A's `best.rknn` into `mapping_drone/controller.py`. (2) Add the body-frame-camera → world-frame transform (depends on Realsense mount orientation — placeholder constant until physical mount known). (3) Wire run-summary + STATUS.txt writer (carry over from qualifier `controller.py`). (4) Wire emergency-land-on-Ctrl-C + battery watchdog. | Mapping drone controller runs end-to-end against MOCK MAVSDK + real Realsense + real `.rknn`. Outputs `run_<ts>/STATUS.txt`, `run_summary.json`, detection JPGs. |

**Evening sync.**

### T-3 — Sat 7 June

> Buffer day. If T-6 → T-4 went off the rails, this is where we catch up. Otherwise: polish + dry runs.

| Person | Tasks |
|---|---|
| **A** | If RKNN broke: try alternate conversion paths (different ONNX opset, fp16 instead of int8 quant, different YOLO export args). If RKNN works: produce 2-3 backup models trained with slightly different hyperparams in case the primary fails at venue. |
| **K** | Dry run #1 of full Hula swarm controller against a printed-marker arena setup at home / wherever. Use the log broadcaster. Walk through Ctrl-C emergency-land. Document timing: from launch to "swarm in air" (target <30s), from Ctrl-C to "all landed" (target <15s). |
| **Z** | Dry run #1 of mapping drone controller (mock MAVSDK + real Realsense). Validate it can run for 5 min straight without leaks or crashes. Watch CPU/memory. Then **start writing the unified launcher** (`semifinal/run_finals.py`) — one command that brings up both orchestrators with proper ordering. |

### T-2 — Sun 8 June

| Person | Tasks |
|---|---|
| **A** | Ready to retrain on the fly if the venue lighting / target colours differ from training set. Have the training script + dataset on a USB stick. |
| **K** | Dry run #2 — full sim of finals procedure: power on drones, run discovery, fly mission, observe + record. Reset, repeat. Goal: smooth muscle memory. |
| **Z** | (1) **Build the finals runbook** (`semifinal/runbook.md`) modelled after the qualifier one — roles (keyboard / screen-watcher / judge-talker), step-by-step T+ minute timeline, fallbacks. (2) Print runbook on paper as backup. (3) USB packaging: copy all code + models + docs + log_broadcaster to a USB stick (the `thumbdrive/` pattern from qualifier). |

### T-1 — Mon 9 June

> Light day before finals. Don't introduce new bugs.

| Person | Tasks |
|---|---|
| **A** | (1) Verify all model files load cleanly on the laptop one more time. (2) Pack training laptop (in case last-minute retrain needed at venue). (3) Confirm smart-casual outfit ready + covered shoes. |
| **K** | (1) Battery charge: ALL drone batteries to 100%, charger packed. (2) USB-C cables, spare cables, power adapter, mouse. (3) Run smoke test ONE more time and stop. (4) Read the runbook out loud. (5) Confirm smart-casual outfit + covered shoes. |
| **Z** | (1) Final repo push, double-check both `zb` and `main` are in sync. (2) Verify USB has everything (code, models, runbook printed, learning materials offline copy, pyhulax docs offline mirror). (3) Pack: **personal laptop + mouse + charger + USB×2 + Photo ID + printed confirmation email + paper runbook**. (4) Confirm smart-casual outfit + covered shoes. (5) Sleep 8 hours. |

**Last sync:** team call at 21:00 SGT. Confirm roles for the day. Confirm meeting time + place. Confirm logistics (transport, IDs, snacks).

### Finals Day 1 — Tue 10 June (9:00am – 6:00pm)

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

### Finals Day 2 — Wed 11 June (9:00am – 6:00pm)

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
A: train best.pt
     │
     ▼ ONNX export (T-6)
A: best.onnx ──────────────────────────┐
     │                                  │
     ▼ RKNN conversion (T-5/T-4)        ▼
A: best.rknn ──────► Z: mapping drone   K: swarm controller
                          uses .rknn         uses .pt directly via YOLODetector
```

Critical path = A's RKNN conversion. If it fails by T-4 evening, Plan B = host-side YOLO on `.pt` via the laptop (slower but works).

```
K: Hula smoke (single drone, T-5)
     │
     ▼ confirmed
K: swarm controller integration (T-5 → T-4)
     │
     ▼ multi-drone test (T-4)
K: ready for finals
```

```
Z: mapping drone controller skeleton (T-5)
     │
     ▼ Realsense added (T-5)
     │
     ▼ RKNN added when A delivers (T-4)
     │
     ▼ run-summary + watchdog + emergency-land (T-4)
     │
     ▼ dry run (T-3)
Z: ready for finals
```

**Handoff windows:**
- A → K + Z: model files by **Fri 6 June 18:00 SGT** (T-4 evening). Earlier if possible.
- K → Z: any Hula-side quirks discovered, into shared notes file by **same deadline**.
- Z → A + K: orchestrator entry points + how to invoke, by **same deadline**.

---

## 4. Stack of risks + mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| L4 + L5 stays locked → no org reference code for Realsense + RKNN | Medium | Our prototypes + L3 + general OpenCV/RKNN docs are enough to reconstruct. Already drafted RKNN steps in `learning_material_5_yolo_rknn/README.md`. |
| Drones not delivered before T-3 | Medium | K runs everything as mock drones. Hardware integration becomes a venue-day task — risky but survivable. |
| RKNN conversion fails | Medium | Plan B: host-side YOLO inference. Slower but works. Both orchestrators support a `--detector pt|rknn` flag. |
| Hula WiFi flaky at venue | Medium | `set_wifi_band(5GHz)`, low video resolution, per-drone reconnect logic. |
| UWB signal patchy in arena | Medium | Failsafe: hold position on UWB loss >1s, land if sustained. Logged for post-flight review. |
| One of us is sick on finals day | Low | Each task should have a "deputy" — if K is out, Z runs the swarm. Practice cross-coverage in dry runs. |
| Last-minute target list change from org | Medium | A keeps the training pipeline hot. Should be ~30 min to retrain on different classes. |
| Code crashes mid-run | Medium | `try/finally land + disarm` everywhere. Watchdog 60s. Battery failsafe. |
| Org's drones differ from what we trained for | Low | We've ordered both Hula docs + kolomee.py reference, so adaptation is small. |
| Coordinate frame bug (ENU vs NED) silently sends drone wrong way | High | **Ground test** every direction command before flying it. Don't trust until verified. |

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

After Day 1 (Tue 10 June):
- Debrief over dinner
- Update `progress.md` with what worked / failed
- Cherry-pick fixes for Day 2

After Day 2 (Wed 11 June):
- Win or lose, **write the retro** in `progress.md`
- Push final repo state to both branches
- Save run artifacts off the USB to durable storage (Drive backup, etc)

---

*Plan v1 — created 2026-06-03 evening. Iterate as L4/L5 unlock and org clarifications arrive.*
*Owner of this file: Z. Edits welcome via PR or direct push.*

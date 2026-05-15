# Team task list — RoboVerse Qualifier (T-9 days)

Three of us. Roles roughly carved by domain so we don't merge-conflict:

| Person | Track | Primary deliverable | Owns code in |
|---|---|---|---|
| **K** | **Detection** (vision/AI) | `barrel.pt` weights + labeled dataset + eval report | `detection/` |
| **A** | **Strategy + testing + logistics** | Search-pattern logic + dry-run results + qualifier-day plan | `searchctl/planner/` (Z will scaffold), `testing/`, `qualifier/` |
| **Z** | **Controller + infra + integration** | `searchctl/controller.py` (flight, glue, deployment), runs everything in the VM | `searchctl/controller.py`, `searchctl/flight/`, infrastructure |

> Reassign as needed — these are best-fit defaults, not contracts.

## Critical dates

- **2026-05-20 (Wed) 14:00** — **OUR personal cancel/reschedule cutoff** = 48 h before our 22 May 14:00 slot (booking-page T&Cs). After this, our slot is fixed.
- **2026-05-21 (Thu) 10:00 SGT** — org-wide deadline for *unbooked* teams (per `65drones1` 13/5/2026 4:51 PM in `#general`). Unbooked teams get random slots assigned after this. Not directly relevant to us — we're already booked — but worth knowing.
- **~2026-05-21 (Thu)** — OP releases the actual qualifier map. We get ~24 h to tune to it.
- **2026-05-22 (Fri) 14:00** — **OUR QUALIFIER SLOT.** Orchard Grand Court, Lloyd I/II.

## Status snapshot (2026-05-13, end of day)

- ✅ VM imported, configured, disk expanded, ultralytics installed (Z)
- ✅ `searchctl/controller.py` Phase 1 (flight) — flies 2 m square, exit 0, all WPs sub-0.5 m (Z)
- ✅ Phase 2 detection pipeline **scaffolded** in controller — **not yet flight-tested with detector ON** (Z)
- ⏳ Everything else below

---

## 👁 Person K — Detection Pipeline

**End goal:** a `barrel.pt` YOLO weights file with 3 classes (yellow / red / toxic) that achieves > 0.8 precision and > 0.7 recall per class on a held-out test set. Plus the dataset + training notebook to reproduce it.

### K.1 — Image capture from the sim ⏰ ~4 hrs
- [ ] Boot the v3 VM, start sim with `~/start_px4.sh` → x500_vision → roboverse → QGC
- [ ] Set the three PX4 console commands (battery + EKF origin) — see `guides/vm_from_zero_to_flight.md` §10.2
- [ ] Use `~/Desktop/codes/keyboardcontrol.py` to fly the drone manually around the warehouse
- [ ] Use `~/Desktop/codes/save_photo.py` to capture frames as you fly. **Target counts:**
  - ≥ 200 frames containing a yellow barrel
  - ≥ 200 frames containing a red barrel
  - ≥ 200 frames containing a toxic-sign barrel (the OP's RED-drum-with-diamond-sign)
  - Bonus: frames containing **multiple barrel types in the same shot** — important adversarial cases
- [ ] Vary perspective: low altitude (~1 m), high altitude (~3.5 m), close (~2 m away), far (~8 m away), partially occluded
- [ ] Save into `detection/dataset/raw/` with timestamped filenames
- [ ] Push to GitHub on a branch `detection/k-capture-001` (don't merge to main yet — dataset will be gitignored later but the raw images can sit on the branch for K's review)

**Output:** ~600–800 raw frames in `detection/dataset/raw/`.

### K.2 — Labeling ⏰ ~3–4 hrs (the grindy part)
- [ ] Pick a tool: **Roboflow** (cloud, free <10k images, has YOLO export + auto-augmentation) is the fast path. **labelImg** is the slow-but-local fallback.
- [ ] Create a Roboflow project, **3 classes**: `yellow_barrel`, `red_barrel`, `toxic_barrel`
- [ ] Upload all frames. Label every barrel in every frame. **Don't skip occluded barrels** — those are training signal for the qualifier where the drone won't always have clean views.
- [ ] Auto-split 70/15/15 train/val/test
- [ ] Apply Roboflow's auto-augmentation: rotation ±15°, brightness ±25%, blur, slight crop. Doubles the dataset for free.
- [ ] Export YOLOv8 format → save `detection/dataset/processed/` (or use Roboflow's hosted dataset URL directly in Colab)

**Output:** a labeled dataset, exported in YOLOv8 format.

### K.3 — Training on Colab ⏰ ~2 hrs (mostly waiting)
- [ ] Open the workshop's `~/Desktop/codes/Train_YOLO_Models.ipynb` in Colab (upload it there)
- [ ] Set runtime → GPU (free T4 is fine)
- [ ] Point at the Roboflow dataset URL or upload the processed zip
- [ ] Start with default hyperparams: yolov8n base, 100 epochs, batch 16, imgsz 640
- [ ] First training run is the baseline — don't tune yet
- [ ] Download `best.pt` → rename `barrel_v1.pt` → save to `detection/weights/barrel_v1.pt`

**Output:** `detection/weights/barrel_v1.pt`

### K.4 — Evaluation ⏰ ~1 hr
- [ ] Run Ultralytics' `model.val()` on the test set
- [ ] Record per-class precision + recall + mAP50 + mAP50-95 in `detection/eval/barrel_v1.md`
- [ ] **Sanity-check toxic-barrel detection** specifically. If precision < 0.9 on toxic, you'll false-positive on real reds at the qualifier → loss of points. Iterate before integration.
- [ ] If yellow recall < 0.7, you'll miss easy points. Capture more yellow images.

**Output:** an eval report. If the numbers look good, push to Z for integration. If not, iterate.

### K.5 — Iteration (likely needed)
- [ ] More images of weak classes
- [ ] Tune confidence threshold during training
- [ ] Try larger model (yolov8s instead of yolov8n) if inference is fast enough on the VM
- [ ] Train `barrel_v2.pt`, `barrel_v3.pt`... eval each, hand off best

### K.6 — Integration hand-off to Z ⏰ ~5 min
- [ ] Drop final `barrel.pt` into the controller path. Tell Z the filename + classes + eval numbers.
- [ ] Z changes one line in `searchctl/controller.py` (`YOLO_WEIGHTS_DEFAULT`) and tests.

### K.7 — Standing tasks throughout the week
- [ ] **Watch Discord** for the OP's "barrel-tuned" model drop. If they release one, benchmark theirs vs ours; ship whichever is better.
- [ ] **Don't touch** `searchctl/controller.py`, `searchctl/README.md`, `guides/`, or `progress.md` — those are Z's lane. Coordinate through chat.

---

## 🧭 Person A — Strategy, Testing, Logistics

**End goal:** the drone has a search pattern that actually finds barrels in a 10-min run, has been validated against varied maze layouts, and we know exactly what to do on demo day if things go wrong.

### A.1 — Read the materials cold (do this FIRST) ⏰ ~2 hrs
- [ ] Read `challenge/Qualifier.pdf` end to end. Understand the scoring math:
  - Yellow barrel = 50 pts (ground only)
  - Red barrel = 100 pts (elevated only)
  - **University category needs ≥ 1 yellow AND ≥ 1 red to be ranked at all**
  - Speed bonus: 20 pts per 30 s under 5 min if all of one color found
  - Toxic-sign barrels: **do NOT detect them**, no points either way
- [ ] Skim `learning/LearningMaterial3.pdf` for search strategy ideas (lawnmower vs frontier)
- [ ] Skim `pastproject/docs/software.md` and `pastproject/remote_laptop_src/nodes/global_controller.py` — frontier-exploration logic that we may port
- [ ] Skim `searchctl/README.md` and the existing controller code so you know what hooks Z has built
- [ ] Read `guides/vm_from_zero_to_flight.md` — verification log especially. Tells you what works and what's known to break.

### A.2 — Search strategy design ⏰ ~3 hrs
- [ ] Decide between **lawnmower** (simple, predictable, good for Qualifier eligibility) or **frontier** (smarter for irregular maps, ported from pastproject).
  - Recommendation: lawnmower first as Phase 3 MVP. Frontier as a Phase 3.5 stretch goal.
- [ ] Sketch the actual waypoint sequence for a 40×40 m arena at **two altitudes**:
  - Pass 1: low (~1 m) for yellow barrels (ground only)
  - Pass 2: high (~3.5 m) for red barrels (elevated only)
- [ ] Account for the arena's IRREGULAR walls — the qualifier map is L-shaped, not a rectangle. Plan how to handle blocked cells.
- [ ] Write the strategy as a markdown spec in `testing/strategy_v1.md` BEFORE coding it. Z will implement the actual planner code based on this spec.

**Output:** `testing/strategy_v1.md` with waypoints + decision tree for "what to do when blocked."

### A.3 — Dry-run scoring framework ⏰ ~2 hrs
- [ ] Write `testing/score.py` — takes the controller's run log + the maze ground-truth JSON (from `maze_gen/output/*.json`) → computes the qualifier score:
  - Count distinct barrel detections (by class + NED position within 1.5 m of a ground-truth barrel)
  - Apply scoring math (50/100 per class, speed bonuses)
  - Penalty for toxic false-positives if any
- [ ] Test on a stub run log
- [ ] When Z's controller is producing real run logs (after Phase 2 integration), feed those through and report a score

**Output:** scoring script. Tells us if we're qualifying-tier or not.

### A.4 — Generate maze variants for testing ⏰ ~1 hr
- [ ] Use `maze_gen/generate_maze.py` to produce 5–10 varied mazes with different seeds
- [ ] Save SDF + JSON metadata in `testing/maze_set/`
- [ ] These become the "regression test suite" — every controller version gets run against all of them

### A.5 — Run the dry-runs ⏰ continuous (~1 hr per run, many runs)
- [ ] After Z's controller + K's weights are integrated, run the full controller against each maze in `testing/maze_set/`
- [ ] Record score per run via `testing/score.py`
- [ ] Log any failure modes (controller crashes, weird flight behavior, missed barrels) into `testing/dry_run_log.md`
- [ ] Goal: at least one **full 10-minute run** that scores in the eligible range (≥ 1 yellow + ≥ 1 red detected, no DQ)

### A.6 — Qualifier-day logistics ⏰ ~2 hrs spread over the week
- [ ] **Confirm booking** — verify Z has the confirmation email screenshot
- [ ] Plan the route to Orchard Grand Court Lloyd I/II (6 min walk from Somerset MRT). Test the route once if you can.
- [ ] Bring: student pass / IC, phone with Discord, the team's USB stick with code + backup USB
- [ ] **15-min setup window** — write a "what to do" checklist for the actual setup at the venue:
  1. Plug in USB
  2. Copy `searchctl/` and `barrel.pt` to the org laptop
  3. Set the three PX4 params + EKF origin (or run a setup script)
  4. Run `python3 controller.py` once to confirm it works on their machine
  5. Hit "ready" when judge prompts
- [ ] **Backup plan if smart controller misbehaves:** keep a `--no-detect` Phase-1-only version on the USB. Even a hover + return scores 0 but avoids DQ.

**Output:** `qualifier/day_of_runbook.md` — the playbook you read out loud on demo day.

### A.7 — Standing tasks
- [ ] **Watch Discord support-ticket channel** for new OP clarifications about the qualifier rules. Post anything important into our chat.
- [ ] **Don't touch** `searchctl/controller.py` (Z's lane) or `detection/` (K's lane) — write specs and tests, not direct edits to those.

---

## 🛠 Person Z — Controller, Infrastructure, Integration

**End goal:** a controller that on demo day arms the drone, flies the search pattern, runs detection, saves bbox `.jpg`s, lands cleanly. Plus all the deployment + recovery glue.

### Z.1 — Phase 2 integration test ⏰ ~30 min (Thursday half-day)
- [ ] Deploy controller v0.2 to VM via vmrun
- [ ] Sim startup + PX4 console commands
- [ ] Run `python3 controller.py` (detect ON)
- [ ] Verify: flight clean + detection log lines + `logs/run_<ts>/detections/*.jpg` files present
- [ ] Run `python3 controller.py --no-detect` — confirm Phase 1 still passes
- [ ] Update `progress.md` + `guides/vm_from_zero_to_flight.md` verification log

### Z.2 — Phase 3: lawnmower planner ⏰ ~4 hrs (Fri 5/15 + weekend)
- [ ] Implement based on A's strategy spec (`testing/strategy_v1.md`)
- [ ] Refactor `searchctl/controller.py` to extract the planner into `searchctl/planner/lawnmower.py`
- [ ] Two-altitude pass: low for yellow, high for red
- [ ] Handle blocked cells (depth-camera obstacle response triggers a re-route)
- [ ] Test against `testing/maze_set/` mazes from A

### Z.3 — Phase 4: detection deduplication ⏰ ~2 hrs
- [ ] In SharedState.detections: cluster by NED position (within 1.5 m → same barrel)
- [ ] Emit one "confirmed" record per unique barrel, not per frame
- [ ] Surface `unique_yellow_count`, `unique_red_count` to the planner so it can decide when to stop

### Z.4 — Phase 5: robustness ⏰ ~3 hrs
- [ ] Persist found-barrel records to disk on every confirmation (so a crash-restart resumes scoring)
- [ ] Watchdog tuning: too-tight tolerance has hurt us; loosen if false-positives in dry-runs
- [ ] Quick-restart script: one command launches `start_px4.sh`, applies params, runs controller (chain-on-fail with re-set EKF origin)

### Z.5 — Phase 6: pymavlink fake-GCS heartbeat ⏰ ~2 hrs — **CODE DONE 2026-05-15; flight test outstanding**
- [x] Sends MAVLink HEARTBEAT on UDP 14550 identifying as a GCS — satisfies PX4's "no GCS" preflight without needing QGC running
- [x] Important because on demo day QGC might fail to start (like it did on 2026-05-13)
- [x] Integrates as a background daemon thread in the controller (not asyncio — pymavlink is sync; thread is safer)
- [x] Auto-skips if QGC is already running (port 14550 conflict → log + skip cleanly)
- [x] CLI `--no-fake-gcs` opt-out
- [ ] **`pip install --user pymavlink` in the VM** (~5 MB, fast)
- [ ] **Flight test**: kill QGC, run controller, confirm `commander check` shows `Preflight check: OK` purely from our heartbeat

### Z.6 — Integration with K's weights ⏰ ~5 min (when K ships)
- [ ] Swap `YOLO_WEIGHTS_DEFAULT` in `controller.py` to K's `barrel.pt`
- [ ] Run one dry-run, confirm detections now show `class=yellow_barrel` etc. (not `class=bottle`)

### Z.7 — Dry-run support for A ⏰ continuous
- [ ] When A needs a clean controller run for testing, run it via vmrun and ship the log
- [ ] Diagnose any flight-side failures A surfaces

### Z.8 — Documentation upkeep ⏰ continuous
- [ ] Keep `progress.md`, `guides/vm_from_zero_to_flight.md`, `searchctl/README.md` current after every milestone
- [ ] Commit + push after every shippable change

### Z.9 — Demo-day execution ⏰ ~30 min on Fri 5/22
- [ ] Bring the laptop with the VM pre-booted (just in case the org laptop has issues)
- [ ] Bring backup USB with `searchctl/` + `barrel.pt` + setup script
- [ ] Run A's `qualifier/day_of_runbook.md` checklist
- [ ] If something breaks during the run, you're the on-the-fly debugger

---

## 🌐 Things any of us can do (low-priority grab-bag)

- [ ] Set up the Discord watcher (`discord_watcher/`) — first-run login + Task Scheduler entry. Auto-collects new Discord messages into `info_<date>/`.
- [ ] Read `learning/Supplementary_LearningMaterial*.pdf` (mostly Final-tier but might hint at strategy).
- [ ] Get the 3 v2 files from Discord that we couldn't auto-download (`get_position_with_task_v2.py`, `GlobalMapperV2.py`, `mapper.py` — see `info_2026-05-08/msg_005.md`).
- [ ] Take a VMware snapshot of the VM after Phase 2 verified working. Lets us roll back in 30 sec if anything breaks later.
- [ ] Train a backup YOLO with different hyperparams in parallel (K's stretch goal, or A as backup).

---

## 🔗 Hand-off points (where tracks intersect)

| From → To | What | When |
|---|---|---|
| A → Z | `testing/strategy_v1.md` (waypoint plan + decision tree) | before Z starts Phase 3 (Fri 5/15) |
| K → Z | `barrel.pt` weights file + classes + eval report | as soon as K.4 numbers look good (target Sun 5/17 or earlier) |
| Z → A | Controller producing real run logs | after Z.1 (Thu 5/14) |
| A → Z | Dry-run scores + failure modes | continuous Sun 5/17 onwards |
| Z → all | Daily push to GitHub + chat update | end of each day |

## 📞 Coordination contract

- **Branches:** each person owns one
  - `ks` — Person K (detection)
  - `ab` — Person A (strategy + testing + logistics)
  - `zb` — Person Z (controller + infra + integration)
  - `main` — protected; only merge via PR after review (or fast-forward if trivial / urgent)
- Work on your own branch. Pull from `main` daily to stay current. Merge to `main` via PR when something's shippable.
- **Commits:** descriptive subject. Prefix with track when helpful: `[detect]`, `[strategy]`, `[ctrl]`.
- **Daily check-in:** end-of-day chat message — what shipped, what's blocked, what's next.
- **Help requests:** if any task is taking 2× the estimate, flag immediately. We have 9 days, not 20.
- **Don't touch each other's files** without saying so. Spec the change, ship a PR, get a 👍.

---

## 🚨 Risks + mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| **Disk-space on org's stock v3 VM** — torch/ultralytics won't install on a 49 GB disk at 95% used | **HIGH** | See "Disk-space contingency" section below. DS-1 support ticket v2 drafted in `team/discord_drafts.md` (2026-05-15) — **needs to be sent**. ONNX fallback (DS-3) being built into searchctl. |
| K's `barrel.pt` not ready by qualifier | Medium | Stock `yolov10n.pt` as fallback — won't detect "barrel" but will fire on barrel-like objects. Partial points possible. |
| Z's controller has new bug from Phase 3/4 changes | Medium | `--no-detect` flag → known-good Phase 1. Tagged commits at each phase complete. |
| Org laptop fails or has weird setup | Low | Z brings backup laptop with own VM. A's runbook has fallback steps. |
| All three of us at qualifier and code doesn't work on org machine | Low | Backup USB with last-known-good. Worst case: hover + return (Phase 1) — scores 0 but no DQ. |
| EKF origin not set on org machine | Medium | Setup script that runs the 3 PX4 console commands on launch (Z's script in Z.4). |
| QGC crashes on org machine (it did on ours) | Medium | Pymavlink fake-GCS heartbeat (Z.5) — eliminates QGC dependency. |
| One of us sick on demo day | Low | The other two can run with the runbook in `qualifier/day_of_runbook.md` (A's deliverable). |

## ⚠️ Disk-space contingency (org VM is 49 GB, ~95% used)

**Update 2026-05-15:** the OP officially answered the *general* disk-pressure question — see `info_2026-05-15/general.md` (13/5/2026 6:00 PM) and `info_2026-05-15/tech-discussion.md`. The OP attributes disk-fill to **accumulated PX4 SITL logs** in `~/PX4-Autopilot/build/px4_sitl_default/rootfs/log/` and gives the cleanup command:

```bash
rm -rf ~/PX4-Autopilot/build/px4_sitl_default/rootfs/log/*
```

This **does not** answer our *install-time* problem (`ultralytics` + `torch` ≈ 3 GB) — that's a different failure mode the OP hasn't addressed. The DS-1 ticket below remains valid but is now sharpened to the install-time question.

**Four-pronged response (all in parallel):**

### DS-1 — Z: send the support ticket (drafted 2026-05-15, ready to copy-paste) 📌
Ask the OP:
1. Is `ultralytics` + `torch` pre-installed on the demo-day machine?
2. May we bring our own laptop with a pre-configured VM and demo from that instead?
3. If we must use the org machine, may we resize the partition during the 15-min setup window (`growpart` is non-destructive, ~30 sec to apply)?

Answer to any of these unblocks us. **Until this is filed, every other DS-* task is a hedge.**

### DS-2 — K: also export model to ONNX after every training run ⏰ ~5 min per run
At the end of `Train_YOLO_Models.ipynb`, add:
```python
model.export(format="onnx", imgsz=640, simplify=True)
```
Ship both `barrel.pt` AND `barrel.onnx` to Z. Future Z swaps backends with a CLI flag.

### DS-3 — Z: write an `onnxruntime`-based Detector backend ⏰ ~2 hr (fold into Phase 5)
`onnxruntime` install is ~50 MB vs torch's ~2 GB. Fits comfortably in 2.5 GB headroom.
- Add `searchctl/detector_onnx.py` — minimal class with same interface as workshop's `Detector` (submit_image, callback).
- CLI flag `--detector-backend ultralytics|onnx|opencv-dnn` (default ultralytics on our VM, onnx for org machine).
- Test both produce identical detections on the same input frame.

### DS-4 — Z: bring own laptop as day-of fallback ⏰ ~30 min the night before
Charge fully + bring HDMI cable + USB with last-known-good. If the org machine fights us, we run on Z's hardware. Workshop docs allow this ("you can use our machine" — `can`, not `must`).

**Decision tree for demo day:**
```
On arrival:
  1. Check org machine has ultralytics → run as normal
  2. Else, check our laptop can plug in → run from there
  3. Else, try onnxruntime backend (DS-3) on org machine
  4. Else, last resort: stock yolov10n.pt + --no-detect-style scoring
       (we still fly + photograph; submit images for manual review)
```

---

## Living-doc rule

When a task ships, **check the box**. When a date slips, **edit the estimate**. When the qualifier rules change, **fix the math**. This file is the team's source of truth — keep it accurate or it stops being useful.

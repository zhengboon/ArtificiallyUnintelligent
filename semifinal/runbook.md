<!--OPDOC-BANNER-->
> ⚠️ **SUPERSEDED — to run the mapping drone use [OP_DOC.md](OP_DOC.md).** This file is kept for historical detail only; the live decision-tree runbook is OP_DOC.md.

# Finals Runbook — ArtificiallyUnintelligent

**Finals: Wed 10 + Thu 11 June 2026, 9:00am – 6:00pm**
**Venue: Marina Bay Sands Expo and Convention Centre, Level 4**
**Category: University**
**Tasks: Challenge 1 (Reconnaissance) + Challenge 2A (3-Hula landings) + Challenge 2B (RoboMaster hunt via ArUco markers on robots — dict TBD Day-1, default DICT_6X6_250)**

**Attendance: All 3 members (K, Z, A) attend BOTH Day 1 and Day 2 — org confirmed 2026-06-05 22:22 SGT.**

> Read this aloud as you go. Tick every box. Do not skip. Print on paper as backup.

---

## The night before (Tue 9 June, 21:00 SGT call)

- [ ] **Write `semifinal/swarm_controller.py`** by porting `huladola.py` to the controller pattern (--mock, --task 2a/2b flags, pads_file/search-pattern args). Verify `python semifinal/swarm_controller.py --mock` prints clean import + lifecycle BEFORE 21:00 call. If we run out of time, fall back to invoking `huladola.py` directly and treat lines that reference `semifinal/swarm_controller.py` as pointing at `huladola.py`. **(NOT YET BUILT — placeholder)**
- [ ] **Pre-staged arena waypoint templates already exist at 4.0 m** in `semifinal/configs/` — `arena_3x3.json` / `arena_4x4.json` / `arena_6x6.json` / `arena_8x8.json` plus `waypoints_2x2_default.json`. All are at z=4.0 m (above the 3.5 m org floor confirmed 2026-06-08). Controller's `DEFAULT_WAYPOINTS` is `[(0,0,4.0),(2,0,4.0),(2,2,4.0),(0,2,4.0)]`. No new files needed; pick the closest pre-staged arena_NxN.json on Day-1 once A scouts the arena dimensions. Verify each `alt_m >= 4.0` before scored runs.
- [ ] Confirm USB×2 contents (run `ls semifinal/thumbdrive/` and verify all listed below):
  - `controllers/` (semifinal/mapping_drone/ + semifinal/swarm_controller.py **(TODO: file does not exist yet — see Night-Before task above)** + tests)
  - `models/best.pt` (K's qualifier model, in case of fallback)
  - `models/best.onnx` (A's old qualifier export — kept on USB as dead-weight backup only; YOLO track was killed 2026-06-06 22:13, A no longer training. ArUco is the primary detector; exact dict is TBD Day-1, default DICT_6X6_250.)
  - `docs/` (CHALLENGE_BREAKDOWN.md + FINALS_PLAN.md + learning_materials_and_others.md + offline pyhulax mirror + uwb_api_hula_swarm/UWB_API_Hula_swarm.pdf)
  - `prototypes/` (the 3 prototype scripts as fallback verification)
  - `uwb_api_hula_swarm/` (UWBParserThread.py + UWB_API_Hula_swarm.pdf — REQUIRED for Hula swarm UWB on C2 Terminal Windows side, pyserial @ 921600 baud; per org 2026-06-06 11:28)
  - `setup.sh` (one-command laptop bootstrap)
  - `runbook.md` (this file, printed too)
- [ ] **TWO USB sticks**, identical contents
- [ ] **A: USB the latest `annotation_tool/` + any backup-detection-path work (OpenCV / TensorFlow / ImageAI exploratory scripts) to a shared drive AND both USB sticks** — A's laptop has been repeating / hanging often (noted 2026-06-07 00:13), so we cannot assume A can run anything off it on the day. K and Z must be able to pick up A's work from the USB if A's laptop dies.
- [ ] All 3 personal laptops (one per team member) charged to 100%. Org provides the C2 Terminal — personal laptops are dev / backup / artifact viewing. **A's laptop is unreliable — treat it as a stretch resource, not a dependency.**
- [ ] **Packing: backup depth camera** — Z brings the Intel depth camera borrowed from a friend (close-to-D435, not exact). If the org-issued / onboard Realsense fails, this is our fallback.
- [ ] 3 phones charged
- [ ] **Photo IDs** (IC / EZ-Link / Passport) — all 3 of us
- [ ] **Confirmation email** printed AND on phone
- [ ] Print this runbook on paper (in case laptop dies)
- [ ] Confirm slot booking screenshot pinned in team chat
- [ ] Confirm transport plan (Somerset MRT → MBS, ~30-45 min)
- [ ] Lock roles for the day (see Roles below)
- [ ] Sleep 8 hours

---

## Day-1 / Day-2 timeline (from org Finals brief, slide 12)

**We are slot #3 in Challenge 1** (after 4FINGERS at #1, AAA at #2). Expect to be called ~10-15 min after slot 1 starts at 14:30.
**We are slot #3 in Challenge 2; our convoy opponent is STD.**
**At Challenge 2 slot #24 we operate 2 convoy RoboMasters against THE WIENERS.**
**Drones (Hula 3,4 + Mapping 3,4) are shared with BOYD BUDDIES (slot #4) — handoff between back-to-back slots.**

### Day 1 — Wed 10 June

| Time | Block | Notes |
|---|---|---|
| **0730** | Registration counter opens | Lanyard + swag, show photo ID + confirmation email |
| **0930 – 1030** | Org briefing | Validity rule + ArUco dict announced here. Capture both immediately. |
| **1030 – 1200** | Testing (mapping OR hula — Uni teams choose) | Mapping = per-day per-team total allowance (carries over); Hula = 5 min per session, 20 min cooldown, max 2 teams in cage |
| **1200 – 1300** | Lunch (no testing) | Standup + apply briefing findings to configs/code |
| **1300 – 1330** | Testing | Last testing window before C1 prep |
| **1330 – 1430** | Prep for Challenge 1 (Uni) — **NO MAPPING DRONE FLYING** | Configs locked, mock dry-run only, USB sanity check |
| **1430 – 1800** | **Challenge 1 (Uni only) — SCORED** | We are slot #3 — expect call ~14:40–14:45 |
| **~1800+** | Day 1 ends | Artifact copy to USB, vacate, debrief over dinner |

### Day 2 — Thu 11 June

| Time | Block | Notes |
|---|---|---|
| **0900 – 1230** | Testing | Apply Day-1 learnings; mapping drone allowance resets daily |
| **1230 – 1330** | Lunch (no testing) | Final config sanity check before C2 |
| **1330 – 1600** | **Challenge 2 — SCORED** | We are slot #3 with STD as convoy opponent; we operate 2 convoy RoboMasters at slot #24 against THE WIENERS |
| **~1600+** | Day 2 ends | Final artifacts to USB, write retro in `progress.md` before leaving |

---

## Wednesday morning (10 June, Day 1)

- [ ] **06:00** wake by alarm. Light breakfast. Limit caffeine.
- [ ] **06:30** final bag check (see Packing checklist in `FINALS_PLAN.md` §9)
- [ ] **06:45** leave for MBS. Bag: laptop + mouse + charger + USB×2 + ID + printed email + paper runbook + smart casual + covered shoes.
- [ ] **07:00** meet at Somerset MRT (Exit B) or whoever's coming via different route, locked at Tue night call.
- [ ] **07:25** arrive Marina Bay Sands. Walk to Level 4.
- [ ] **07:30** registration counter opens. Collect lanyard + swag. Show photo ID + confirmation email.
- [ ] **07:45** find our team's table / spot. Plug in laptops + chargers.
- [ ] **08:00** boot org-provided C2 Terminal (Windows host). Launch the Ubuntu 22.04 VM. Verify both are accessible.
- [ ] **08:00** pre-event smoke test (no drones yet):
  - On the C2 Terminal Windows side: import test for pyhulax + opencv + pyserial (`python -c "import serial, serial.tools.list_ports"`) + the new Hula-swarm UWB module (`python -c "import sys; sys.path.insert(0, 'semifinal/uwb_api_hula_swarm'); from UWBParserThread import UWBParserThread"`)
  - On the C2 Terminal Ubuntu VM: import test for rknn-toolkit2 + pyrealsense2 + rclpy + mavsdk
  - If any fail → tell judge / coordinator immediately

---

## 0930 — Event starts (Day 1)

### Step 1 (0830 – 0930): Code load (before org briefing)
- [ ] Plug in USB to C2 Terminal. Copy `controllers/` to a working dir.
- [ ] On Windows side: if `swarm_controller.py` was finished overnight, run it to confirm clean import + lifecycle. **(NOT YET BUILT — placeholder.)** Otherwise: `huladola.py` is a reference example only — has no CLI mock mode. Fallback: smoke-test by importing the module to confirm Python env works, e.g. `python3 -c "import importlib.util, sys; sys.path.insert(0, 'semifinal'); import huladola"`.
- [ ] On Ubuntu VM: `python3 -m mapping_drone.controller --mock` should run a fake mission end-to-end (≈45 s) and write `runs/run_*/STATUS.txt` + `top_down.png`.
- [ ] If both pass, code is loaded. If either fails, see "If X breaks" cheatsheet at the bottom.

### Step 2 (0930 – 1030): Org briefing
- [ ] Listen for org's full briefing on slot structure, scoring, and arena tour.
- [ ] Confirm we are slot #3 in Challenge 1 (after AAA) and slot #3 in Challenge 2 vs STD. Confirm we also drive 2 convoy RoboMasters at slot #24 vs THE WIENERS.
- [ ] Confirm Hula 3,4 + Mapping 3,4 shared with BOYD BUDDIES (slot #4) — exchange numbers, agree on handoff cadence.
- [ ] Capture the FCFS Discord queue links for mapping drone cage + hula drone cage as soon as org posts them.
- [ ] **Ask org-on-site (A walks to the org desk in person):**
  - (a) Exact ArUco / AprilTag dictionary in use today (it is one of 20 possibilities: ArUco 4X4/5X5/6X6/7X7 × {50,100,250,1000}, or AprilTag 16h5/25h9/36h10/36h11). STINKIES already asked 2026-06-06 14:13 and got no answer — we re-ask Day-1 morning.
  - (Resolved separately by slide 12: C1 runs Day 1 1430-1800; C2 runs Day 2 1330-1600 — sequential across days, not parallel within a slot. No need to ask.)
  - As soon as (a) lands → pass it via `--aruco-dict <name>`. The code now accepts all 20 dicts (see mapping.py `_build_aruco_dict_table`), so no code change should be required even for an unexpected dict — but A/K double-checks the smoke test still passes with the announced name before the first scored slot.
- [ ] Note the validity rule for ArUco markers (org said they'll publish it).
  - As soon as we know: **update `semifinal/mapping_drone/validity.py`** — single line in `decide_landing_validity()`. Test by re-running mock mission.
- [ ] **Map layout is NOT provided** (org clarified 2026-06-06 11:40). During the org's arena tour, A walks the perimeter, sketches obstacle positions, paces out approximate dimensions (L × W), and photographs the floor/markings.
- [ ] A reports estimated arena bounds + obstacle list to K before Step 3; K picks the closest pre-staged `semifinal/configs/arena_<N>x<N>.json` (3x3 / 4x4 / 6x6 / 8x8) so waypoints fit the real arena. Re-run a mock mission to confirm waypoints parse.

### Step 3 (1030 – 1200 + 1300 – 1330): Testing windows
- [ ] **1030–1200:** Uni teams choose between mapping cage or hula cage. Mapping = per-day total allowance (carries over within day), so we burn it strategically across morning + early afternoon. Hula = 5 min per session, 20 min cooldown after each, max 2 teams in cage.
- [ ] Join FCFS Discord queue link (no prior booking; head to waiting area when 3rd in line). DO NOT violate testing regulations — penalty is **1 hour no-testing**.
- [ ] Coordinate sharing with BOYD BUDDIES on Hula 3,4 + Mapping 3,4 — they get same drones; sequence which team grabs the cage first.
- [ ] **1200–1300 lunch — NO testing.** Standup: lessons learned, apply briefing's validity rule + announced ArUco dict to configs.
- [ ] **1300–1330:** Final testing window. Pick whichever cage we're weakest in (likely mapping if RGB/IR pivot is still shaky).

### Step 4 (1330 – 1430): Prep for Challenge 1 — NO MAPPING DRONE FLYING
- [ ] **Confirm RGB stream availability on the drone** — `python -c "import pyrealsense2 as rs; ctx=rs.context(); d=ctx.query_devices()[0]; print([s.get_info(rs.camera_info.name) for s in d.query_sensors()])"`. Org confirmed 2026-06-08 12:18 the mapping drone uses Realsense **D430 + D450 mixed across runs**, neither of which has an RGB sensor in the bare module. If RGB present (a bolt-on was added), proceed as normal. If only IR + depth, add `--use-ir-for-aruco` to the controller command — this routes ArUco detection through one IR camera with the IR emitter toggled off for the ArUco frame.
- [ ] **Pre-yaw the drone facing your chosen scan direction before arming.** Org confirmed 2026-06-08 12:17 that launch direction is free (takeoff point fixed). Pick the heading that minimises first-leg flight time to the densest pad cluster A scouted, then yaw the airframe to that heading before arm.
- [ ] Pre-flight smoke test, again, with the validity rule applied.
- [ ] **Confirm the exact ArUco / AprilTag dictionary name announced by org today** (org confirmed 2026-06-06 21:32 that the exact dict is announced on the day; markers are 20cm x 20cm). Pass it to both controllers via `--aruco-dict <dict_name>` for the first scored slot. Default in code is `6X6_250`. `mapping_drone/mapping.py` now builds the dict table via `_build_aruco_dict_table()` and accepts all 20 possibilities (ArUco `{4X4,5X5,6X6,7X7}_{50,100,250,1000}` + AprilTag `{16h5,25h9,36h10,36h11}`). Normalization handles `DICT_` prefix, case, and whitespace, so the announced name (e.g. `DICT_6X6_250`, `6x6_250`, ` APRILTAG_36H11 `) should all resolve. If startup still raises `ValueError`, the error message lists every accepted name — copy that and tell K immediately.
- [ ] **Battery check**: confirm each drone's battery >70% on the Hula app (Windows side) / mapping-drone GCS (Ubuntu VM side) before takeoff. Below 50% → swap before launch.
- [ ] Lock down which run config to use for the first attempt (see Run configurations below).
- [ ] Print or screenshot the planned mission waypoints (in case the laptop slows / crashes mid-run).

### Step 5 (1430 – 1800): Challenge 1 — SCORED (we are slot #3, expect call ~14:40–14:45)
- [ ] From the C2 Terminal (Windows side), open a NoMachine/SSH session into the **mapping drone** (separate onboard Ubuntu 22.04 + ROS2 + RKNN NPU device — NOT the C2 Terminal's local VM).
- [ ] `scp` (or USB-copy) the `mapping_drone/` controllers from the C2 Terminal onto the drone.
- [ ] Connect to the mapping drone and run the controller **on the drone** over that session (`python3 -m mapping_drone.controller --waypoints-from-json semifinal/configs/arena_4x4.json`).
- [ ] Watch `STATUS.txt` live (in another shell: `watch -n 1 cat runs/run_*/STATUS.txt | tail -25`).
- [ ] K (Keyboard) reads out mapping-drone battery % at takeoff and every 60 s; Z (Screen-watcher) calls "ABORT — RTL" if any drone drops <20% mid-mission.
- [ ] Screen-watcher (Z) calls out every new sighting + validity classification.
- [ ] Once mapping drone returns + lands: copy `top_down.png` + `landing_pads.json` + bbox JPGs to USB.
- [ ] **Show judge** the outputs: top-down map (arena scale), per-pad classification table, marker images.
- [ ] Note any judge feedback for the afternoon run.

### Step 6 (1430 – 1800): Iterate within Challenge 1 window (post-slot-3)
- [ ] If our slot-3 attempt finished cleanly, slot 4+ teams run while we observe — note their patterns + timing.
- [ ] Mapping drone testing allowance may have remaining budget — confirm with marshal whether re-queue is allowed for refinement runs (allowance is per-day per-team).
- [ ] DO NOT push code changes that affect Day 2 (C2) state during this window. C1 is fully scored at 1800.
- [ ] **CUAS booth — 4% bonus:** if any team member has bandwidth between assessment slots, walk to the Above & Beyond: Skies & Space zone, photograph the drone at the Counter UAS booth, screenshot the zone-explored page. Easy 4 points.

### Step 7 (~1800): Day 1 wrap — artifacts
- [ ] Copy latest run dir to USB: `latest=$(ls -td mapping_drone/runs/run_* | head -1); cp -r "$latest" /media/$USER/USB-LABEL/saved_runs_day1/`
- [ ] Confirm artifact integrity: `python3 -c "import json,glob,os; d=sorted(glob.glob('mapping_drone/runs/run_*'))[-1]; j=json.load(open(os.path.join(d,'landing_pads.json'))); print('pads:', j.get('count', len(j.get('pads', []))))"`
- [ ] After Day-1 Challenge 1, record the `run_<TS>` directory name in `STATUS.txt` and write it on the paper runbook hardcopy (needed for `--pads_file` in later steps; no `run_latest` symlink exists).
- [ ] Save a backup of the C2 Terminal Ubuntu VM state if allowed (judge tells us).
- [ ] Thank the judge.
- [ ] Vacate by 18:00.

### Day 1 evening (after 19:00)
- [ ] Dinner debrief.
- [ ] Update `progress.md` with day 1 results.
- [ ] **DO NOT** introduce big code changes overnight. Small + safe only:
  - Validity rule (if org clarifies)
  - Mission waypoints (if arena layout demands re-plan)
  - Detection confidence threshold (if false positives are killing us)
- [ ] Pack laptop again. Sleep 8 hrs.

---

## Day 2 — Thu 11 June

Apply Day 1 lessons. Same wake-up routine. No new registration (lanyard from Day 1 still valid). Arrive 08:00.

> All 3 members attend Day 2 too (org confirmed 2026-06-05: best that all team members are there on both days).
> Still bring photo ID + confirmation email in case of re-screening at the door.
> No big code changes overnight — only the Day-1 evening short list (validity rule, waypoint tweaks, confidence threshold). If you broke something at 02:00, revert before 08:00.

- [ ] All 3 members present (org: "best that all members of team can be there on both days").
- [ ] **08:00** at venue. Pre-flight smoke (Step 3 mechanics, no scored slot yet).
- [ ] **0900 – 1230 testing window.** Mapping drone allowance resets daily; Hula 5 min/session + 20 min cooldown still applies. Coordinate cage handoff with BOYD BUDDIES (Hula 3,4 shared). Focus testing on Challenge 2A landing accuracy + Challenge 2B ArUco-on-RoboMaster detection range.
- [ ] **1230 – 1330 lunch — NO testing.** Final config check. Pick 3 of 5 landing coords from the Discord drop (org-provided per slide 6).
- [ ] **1330 – 1600 Challenge 2 — SCORED.**
  - We are **slot #3** with **STD as convoy opponent**. Expect call ~10-15 min after slot 1 starts (i.e. ~13:40-13:45).
  - **Challenge 2A — 3-Hula landings**: pick 3 valid pads from org-published Discord coords, edit `swarm_controller.py` config or feed via CLI. Run `swarm_controller.py --task 2a --pads pad1,pad2,pad3`. Hula speed cap **0.5 m/s**, height **1.1 m**, **strictly no flying over obstacles** (slide 6). Max 8 min per attempt.
  - **Challenge 2B — RoboMaster hunt**: org launches 5 RoboMasters (2 driven by other-team participants, 3 autonomous). Run `swarm_controller.py --task 2b --search-pattern lawnmower-3way`. ArUco is sole detection path (YOLO killed 2026-06-06). Snapshot images + bbox overlays saved under `runs/run_*/snapshots/`. Max 8 min per attempt.
  - Show judge: landed-on-pad evidence + snapshot images with bbox overlays + unique-robot count.
- [ ] **At slot #24 (later in the 1330-1600 window): we drive 2 convoy RoboMasters against THE WIENERS.** This is the convoy-opponent duty (slide 14 cross-table). A + Z take a RoboMaster each on org-supplied controllers (per CONVOY_OPPONENT_ROLE.md — Z is freer in the Day 2 afternoon since C1 finished Day 1, A is judge-talker/utility); K stays on artifact-watching. Brief each other on driving pattern before slot 24 starts.
- [ ] **CUAS booth — 4% bonus:** if not already collected Day 1, finish before 1600. Photo of drone at Counter UAS booth (Above & Beyond: Skies & Space zone, MBS L4) + screenshot of zone-explored page.
- [ ] **~1600 end:** results announced. Whatever happens, write the retro in `progress.md` before leaving.

---

## Roles (lock at Tue 9 Jun 21:00 SGT call)

| Role | Person | Responsibilities |
|---|---|---|
| **Keyboard** | K | drives terminal + NoMachine session, executes commands, swaps SD cards, monitors process health |
| **Screen-watcher** | Z | watches `STATUS.txt` + log_broadcaster (Tailscale), calls out detections + classifications, holds runbook |
| **Judge-talker / arena scout / hand-on-camera-feed** | A | answers judge questions, communicates with org coordinators, takes photos of arena/drones for our records, **sketches obstacles + estimates bounds for waypoint config (map not provided by org)**, sits on the live camera feed during runs and calls out misses. **No YOLO retrain duty** — A killed the YOLO track 2026-06-06; the freed slot is now arena scouting + judge-facing + camera-watch. |

Cross-coverage: each role has a deputy. If K is sick, Z takes keyboard; if Z is sick, A takes screen-watching; if A is sick, K talks to judge (with Z holding runbook).

---

## Run configurations (pick ONE per slot)

> **NOTE:** `semifinal/swarm_controller.py` is **NOT YET BUILT** as of T-1 — see Night-Before tasks. `semifinal/configs/` IS pre-staged with arena_3x3.json / arena_4x4.json / arena_6x6.json / arena_8x8.json + waypoints_2x2_default.json (all at z=4.0 m, above the 3.5 m floor).
> - `--waypoints-from-json` can be **omitted**; controller falls back to built-in `DEFAULT_WAYPOINTS = [(0,0,4.0),(2,0,4.0),(2,2,4.0),(0,2,4.0)]` (above the 3.5 m floor).
> - For Hula swarm commands, substitute `semifinal/huladola.py` (the existing prototype) for `semifinal/swarm_controller.py`.
> - Replace `run_<TS>` with the actual timestamped run dir from Challenge 1 startup log.

### Configuration A — Safe (default first attempt)
```bash
# Challenge 1 — controller's --max-flight-time-s defaults to 420 s (60 s under the 480 s org cap)
python3 -m mapping_drone.controller --waypoints-from-json semifinal/configs/arena_4x4.json --gimbal-pitch -90

# Challenge 2A
python3 semifinal/swarm_controller.py --task 2a --pads_file mapping_drone/runs/run_<TS>/landing_pads.json --select_strategy first_three_valid  # fill <TS> from controller startup log

# Challenge 2B
python3 semifinal/swarm_controller.py --task 2b --search-pattern lawnmower-3way --confidence 0.5
```

### Configuration B — Aggressive (if Config A worked and we have time)
```bash
# Wider waypoint spacing → faster mapping but lower resolution. Still uses the 420 s controller default.
python3 -m mapping_drone.controller --waypoints-from-json semifinal/configs/arena_8x8.json --gimbal-pitch -75

# More aggressive landing zone selection (closer pads). Replace ... with mapping_drone/runs/run_<TS>/landing_pads.json from Challenge 1.
python3 semifinal/swarm_controller.py --task 2a --pads_file ... --select_strategy nearest_three

# Lower confidence threshold → more candidate detections
python3 semifinal/swarm_controller.py --task 2b --search-pattern lawnmower-3way --confidence 0.35
```

### Configuration C — Recovery (something broke, just get a baseline)
```bash
# Mock everything (no drone, no UWB, no Realsense) — safest baseline; just produces artifacts the judge can score on.
python3 -m mapping_drone.controller --mock --waypoints-from-json semifinal/configs/arena_4x4.json

# Single-drone fallback (only 1 of 3 Hulas working). Replace ... with mapping_drone/runs/run_<TS>/landing_pads.json from Challenge 1.
python3 semifinal/swarm_controller.py --task 2a --single-drone --pads_file ...
```

---

## Cheatsheet — what to do if X breaks

| Problem | Fix |
|---|---|
| USB #1 won't mount | Try USB #2 (identical contents) |
| Both USBs broken | Ask coordinator if there's wifi; if yes, `gh repo clone zhengboon/ArtificiallyUnintelligent`. Repo is private — Z must have done `gh auth login` on the C2 Terminal once it's available. |
| `pyhulax` import fails on C2 Windows | Tell judge — they should have it installed. If not, run `pip install --user pyhulax` from our USB. |
| `pyrealsense2` import fails on Ubuntu VM | Same as above. From USB: `pip install --user pyrealsense2` |
| `rclpy` import fails (mapping drone Ubuntu) | ROS2 distro might not be activated. Try `source /opt/ros/humble/setup.bash` (or jazzy depending on org install). |
| Mapping drone won't connect via MAVSDK | Check serial port (`ls /dev/ttyS*`). Possibly drone needs reboot — tell coordinator. |
| Hula drones not discovered by Dola | Check WiFi network — drones + C2 must be on same network. Try `set_wifi_band(band_5ghz=True)` per Hula. |
| `STATUS.txt` not updating | Check our controller wrote to the right `run_dir`. The path is logged at startup. |
| Top-down map blank | Realsense intrinsics might be wrong. Check `controller.py --log-level DEBUG` for intrinsics print. |
| ArUco detection returns nothing | Re-confirm the announced dict with org-on-site (see Step 2 / Step 3). All 20 possibilities are accepted by the controller — ArUco `{4X4,5X5,6X6,7X7}_{50,100,250,1000}` + AprilTag `{16h5,25h9,36h10,36h11}` — and the `DICT_` prefix / case / whitespace are normalized. If startup raised `ValueError`, the error lists every accepted name; copy-paste the announced name and retry. Confirm marker is in FOV — lower altitude and verify `--gimbal-pitch -90`. |
| ArUco marker physical size / detection range | Markers are **20cm x 20cm** (org confirmed 2026-06-06 21:32). On D435 RGB 640x480 (~70deg HFOV) the marker subtends ~hundreds of px at 1m and drops below ~30 px around 5-6m where detection becomes unreliable. A: pace this out during the arena scout so the mapping-drone cruise altitude in `arena_waypoints_safe.json` keeps markers in reliable detection range. Same marker also appears near Challenge 2 landing pads (org 2026-06-06 21:34) — Hula side uses `cv2.aruco`, not the pyhulax auto-land helper. |
| Wrong landing-pad validity classification | Edit `mapping_drone/validity.py` `decide_landing_validity()` — should be a one-liner. |
| Hula collides mid-air during Challenge 2A | Stagger takeoffs by 5 s, assign different altitudes per drone (0.9 / 1.0 / 1.1 m — canonical Hula recommended altitude is 1.1 m and the org rule "strictly no flying over obstacles" means clearance, not altitude, drives invalidation). |
| RoboMaster not detected | ArUco is the sole detection path (YOLO killed 2026-06-06). Confirm the announced dict matches what was passed via `--aruco-dict <name>` (default `DICT_6X6_250`); check gimbal pitch (-90 default); lower altitude for marker FOV (markers are 20cm × 20cm — detection drops below ~30 px around 5-6m on the D435). If still nothing, A reports robot positions verbally from the camera-feed watch + we ask judge whether a re-fly slot is possible. |
| Battery dies mid-flight | Built-in failsafe should auto-land. Ask coordinator for spare battery. **(Procedural prevention: see Step 3 / Step 4 battery checks added below.)** |
| C2 Terminal Windows crashes | Reboot. Re-load our code from USB. State is in `runs/` which is persisted to disk. |
| Mapping drone NoMachine session laggy | Edit code in our local editor → `scp` to drone → re-run via SSH (faster than IDE-in-NoMachine). |
| Time running out | Show judge whatever artifacts exist. Even partial top-down + 1 valid pad classification counts. |

---

## Emergency contacts

| Person | Phone | Notes |
|---|---|---|
| Z | ______ | runbook holder |
| K | ______ | drone hardware lead |
| A | ______ | judge-talker / arena scout / hand-on-camera-feed |
| Discord | keep open on phone | for org last-minute announcements |
| brainhackreg@dsta.gov.sg | (registration questions only) |
| brainhack@pico.com | (registration questions only) |

---

## Score math (for verifying judges + estimating)

| Item | Source | Points (TBC) |
|---|---|---|
| Challenge 1 — concept understanding | Org judges qualitatively | TBC |
| Challenge 1 — mapping speed | Org judges quantitatively | TBC |
| Challenge 1 — landing-pad classification accuracy | Per pad correctly classified | TBC |
| Challenge 2A — successful landing on designated pad | Per Hula | TBC |
| Challenge 2A — accuracy (centre offset) | Distance from pad centre | TBC |
| Challenge 2A — time | Faster = more | TBC |
| Challenge 2B — successful + accurate snapshots | Per RoboMaster | TBC |
| Challenge 2B — time | Faster = more | TBC |

Specific point values not in slides. Update this table when org publishes scoring.

---

## What we DON'T need to worry about

- **Internet at venue** — repo is on USB; pyhulax docs mirrored offline; Discord on phone
- **Bringing our own laptop hardware** — org provides C2 Terminal; personal laptops are dev/backup only

## Hard constraints (DO worry about these)

- **Wall collisions** — finals are PHYSICAL drones at MBS, so a wall hit = crashed Hula / mapping drone and likely run termination. The qualifier no-penalty rule was sim-only (Roboverse) and does NOT carry over. Treat walls as hard constraints: enforce ≥0.5 m clearance in waypoint files, cap Hula lateral velocity near walls, and verify Realsense-based obstacle distance before any commanded translation. Map layout will NOT be provided (org confirmed 2026-06-06), so clearance must be derived live from the Challenge 1 map.

---

*Runbook v3 (2026-06-09) — authoritative source: finals_brief_extracted.md (org pptx, T-1 evening).*

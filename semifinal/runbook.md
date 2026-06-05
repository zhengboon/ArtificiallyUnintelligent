# Finals Runbook — ArtificiallyUnintelligent

**Finals: Wed 10 + Thu 11 June 2026, 9:00am – 6:00pm**
**Venue: Marina Bay Sands Expo and Convention Centre, Level 4**
**Category: University**
**Tasks: Challenge 1 (Reconnaissance) + Challenge 2A (3-Hula landings) + Challenge 2B (RoboMaster hunt)**

> Read this aloud as you go. Tick every box. Do not skip. Print on paper as backup.

---

## The night before (Tue 9 June, 21:00 SGT call)

- [ ] Confirm USB×2 contents (run `ls semifinal/thumbdrive/` and verify all listed below):
  - `controllers/` (semifinal/mapping_drone/ + semifinal/swarm_controller.py + tests)
  - `models/best.pt` (K's qualifier model, in case of fallback)
  - `models/best.onnx` (A's RoboMaster YOLOv11 export)
  - `docs/` (CHALLENGE_BREAKDOWN.md + FINALS_PLAN.md + learning_materials_and_others.md + offline pyhulax mirror)
  - `prototypes/` (the 3 prototype scripts as fallback verification)
  - `setup.sh` (one-command laptop bootstrap)
  - `runbook.md` (this file, printed too)
- [ ] **TWO USB sticks**, identical contents
- [ ] All 3 laptops charged to 100% (personal laptop is dev/backup; org provides the C2 Terminal)
- [ ] 3 phones charged
- [ ] **Photo IDs** (IC / EZ-Link / Passport) — all 3 of us
- [ ] **Confirmation email** printed AND on phone
- [ ] Print this runbook on paper (in case laptop dies)
- [ ] Confirm slot booking screenshot pinned in team chat
- [ ] Confirm transport plan (Somerset MRT → MBS, ~30-45 min)
- [ ] Lock roles for the day (see Roles below)
- [ ] Sleep 8 hours

---

## Friday morning (10 June, Day 1)

- [ ] **06:00** wake by alarm. Light breakfast. Limit caffeine.
- [ ] **06:30** final bag check (see Packing checklist in `FINALS_PLAN.md` §9)
- [ ] **06:45** leave for MBS. Bag: laptop + mouse + charger + USB×2 + ID + printed email + paper runbook + smart casual + covered shoes.
- [ ] **07:00** meet at Somerset MRT (Exit B) or whoever's coming via different route, locked at Tue night call.
- [ ] **07:25** arrive Marina Bay Sands. Walk to Level 4.
- [ ] **07:30** registration counter opens. Collect lanyard + swag. Show photo ID + confirmation email.
- [ ] **07:45** find our team's table / spot. Plug in laptops + chargers.
- [ ] **08:00** boot org-provided C2 Terminal. Verify dual-boot (Windows + Ubuntu 22.04 VM accessible).
- [ ] **08:00** pre-event smoke test (no drones yet):
  - On the C2 Terminal Windows side: import test for pyhulax + opencv
  - On the C2 Terminal Ubuntu VM: import test for rknn-toolkit2 + pyrealsense2 + rclpy + mavsdk
  - If any fail → tell judge / coordinator immediately

---

## 09:00 — Event starts (Day 1)

### Step 1 (T+0 – 30 min): Code load
- [ ] Plug in USB to C2 Terminal. Copy `controllers/` to a working dir.
- [ ] On Windows side: `python3 semifinal/swarm_controller.py --mock-all` should print clean import + lifecycle.
- [ ] On Ubuntu VM: `python3 -m mapping_drone.controller --mock-all` should run a fake mission end-to-end (≈45 s) and write `runs/run_*/STATUS.txt` + `top_down.png`.
- [ ] If both pass, code is loaded. If either fails, see "If X breaks" cheatsheet at the bottom.

### Step 2 (T+30 min – 60 min): Org briefing + drone slot allocation
- [ ] Listen for org's full briefing on slot structure, scoring, and arena tour.
- [ ] Note our drone testing slots (they will be announced).
- [ ] Note the validity rule for ArUco markers (org said they'll publish it).
  - As soon as we know: **update `semifinal/mapping_drone/validity.py`** — single line in `decide_landing_validity()`. Test by re-running mock mission.

### Step 3 (T+60 min – first slot): Pre-slot prep
- [ ] Pre-flight smoke test, again, with the validity rule applied.
- [ ] Lock down which run config to use for the first attempt (see Run configurations below).
- [ ] Print or screenshot the planned mission waypoints (in case the laptop slows / crashes mid-run).

### Step 4: First scored slot — Challenge 1 (Reconnaissance)
- [ ] Load mapping drone code into the C2 Terminal Ubuntu VM via NoMachine session.
- [ ] Connect to the mapping drone (`mapping_drone.controller --real --waypoints arena_waypoints.json`).
- [ ] Watch `STATUS.txt` live (in another shell: `watch -n 1 cat runs/run_*/STATUS.txt | tail -25`).
- [ ] Screen-watcher (Z) calls out every new sighting + validity classification.
- [ ] Once mapping drone returns + lands: copy `top_down.png` + `landing_pads.json` + bbox JPGs to USB.
- [ ] **Show judge** the outputs: top-down map (arena scale), per-pad classification table, marker images.
- [ ] Note any judge feedback for the afternoon run.

### Step 5: First scored slot — Challenge 2A (3-Hula landings)
- [ ] Pick 3 valid landing pads from Challenge 1 output (`landing_pads.json`).
- [ ] Manually edit `semifinal/swarm_controller.py` config OR feed pad coordinates via CLI flag.
- [ ] Run `swarm_controller.py --task 2a --pads pad1,pad2,pad3`.
- [ ] Watch all 3 Hulas take off, navigate, land. Pads marked green / red post-land.
- [ ] Show judge: landed-on-correct-pad evidence.

### Step 6: First scored slot — Challenge 2B (RoboMaster hunt)
- [ ] Org launches the 5 RoboMaster ground robots.
- [ ] Run `swarm_controller.py --task 2b --search-pattern lawnmower-3way`.
- [ ] Watch Hulas split arena, fly, detect, snapshot.
- [ ] Each Hula returns + lands. Snapshots saved under `runs/run_*/snapshots/`.
- [ ] Show judge: snapshot images with bbox overlays + count of unique robots detected.

### Step 7: Lunch (12:00 – 13:00) — debrief
- [ ] Quick standup. What worked? What sucked? What to change for afternoon?
- [ ] **If mapping was bad:** retrain altitude / gimbal pitch. Tweak in `controller.py` constants.
- [ ] **If detection rate was low:** A retrains model on snapshots taken during the morning run.
- [ ] **If timing was slow:** review waypoint plan, raise altitude for faster scan.
- [ ] Sync code changes to USB. Push to repo if connected.

### Step 8 (13:00 – 17:30): Afternoon scored slots
- [ ] Apply morning lessons. Repeat Steps 4 / 5 / 6.
- [ ] Aim for higher score / faster mission.
- [ ] If first attempt produced acceptable score: choose to either rerun (risky) or bank.
- [ ] Save EVERY run's outputs to USB. Don't overwrite.

### Step 9 (17:30 – 18:00): Pack up + artifacts
- [ ] Copy every run dir to USB: `cp -r runs/ /media/$USER/USB-LABEL/saved_runs_day1/`
- [ ] Run `python3 -c "import json; print(len(json.load(open('runs/run_latest/landing_pads.json'))))"` to confirm artifact integrity.
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

- [ ] **08:00** at venue. Pre-flight smoke (Step 3).
- [ ] **09:00** event starts. Apply overnight changes.
- [ ] Same Steps 4 / 5 / 6 / 7 / 8 / 9 as Day 1.
- [ ] If Day 1 was clean → push for bonus. If Day 1 had issues → fix and re-run the safe configuration first.
- [ ] **End of Day 2:** results announced. Whatever happens, write the retro in `progress.md` before leaving.

---

## Roles (lock at Tue 9 Jun 21:00 SGT call)

| Role | Person | Responsibilities |
|---|---|---|
| **Keyboard** | K | drives terminal + NoMachine session, executes commands, swaps SD cards, monitors process health |
| **Screen-watcher** | Z | watches `STATUS.txt` + log_broadcaster (Tailscale), calls out detections + classifications, holds runbook |
| **Judge-talker / floor** | A | answers judge questions, communicates with org coordinators, takes photos of arena/drones for our records |

Cross-coverage: each role has a deputy. If K is sick, Z takes keyboard; if Z is sick, A takes screen-watching; if A is sick, K talks to judge (with Z holding runbook).

---

## Run configurations (pick ONE per slot)

### Configuration A — Safe (default first attempt)
```bash
# Challenge 1
python3 -m mapping_drone.controller --real --waypoints semifinal/configs/arena_waypoints_safe.json --gimbal-pitch -90 --max-flight-time-s 240

# Challenge 2A
python3 semifinal/swarm_controller.py --task 2a --pads_file semifinal/runs/run_latest/landing_pads.json --select_strategy first_three_valid

# Challenge 2B
python3 semifinal/swarm_controller.py --task 2b --search-pattern lawnmower-3way --confidence 0.5
```

### Configuration B — Aggressive (if Config A worked and we have time)
```bash
# Higher cruise altitude + wider waypoint spacing → faster mapping but lower resolution
python3 -m mapping_drone.controller --real --waypoints semifinal/configs/arena_waypoints_aggressive.json --gimbal-pitch -75 --max-flight-time-s 180

# More aggressive landing zone selection (closer pads)
python3 semifinal/swarm_controller.py --task 2a --pads_file ... --select_strategy nearest_three

# Lower confidence threshold → more candidate detections
python3 semifinal/swarm_controller.py --task 2b --search-pattern lawnmower-3way --confidence 0.35
```

### Configuration C — Recovery (something broke, just get a baseline)
```bash
# Mock mapping (no drone), just to produce artifacts the judge can score on
python3 -m mapping_drone.controller --mock-mavsdk --mock-uwb --waypoints semifinal/configs/arena_waypoints_safe.json

# Single-drone fallback (only 1 of 3 Hulas working)
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
| Hula drones not discovered by Dola | Check WiFi network — drones + C2 must be on same network. Try `set_wifi_band(5GHz)` per Hula. |
| `STATUS.txt` not updating | Check our controller wrote to the right `run_dir`. The path is logged at startup. |
| Top-down map blank | Realsense intrinsics might be wrong. Check `controller.py --log-level DEBUG` for intrinsics print. |
| ArUco detection returns nothing | Marker dict wrong (try DICT_5X5_100 or APRILTAG_36h11 fallback). Or marker out of FOV — adjust gimbal. |
| Wrong landing-pad validity classification | Edit `mapping_drone/validity.py` `decide_landing_validity()` — should be a one-liner. |
| Hula collides mid-air during Challenge 2A | Stagger takeoffs by 5 s, assign different altitudes per drone (1.2 / 1.5 / 1.8 m) |
| RoboMaster YOLO model not firing | Lower confidence (0.5 → 0.35 → 0.25). Confirm K's `best.rknn` is loaded (logged at startup). |
| Battery dies mid-flight | Built-in failsafe should auto-land. Ask coordinator for spare battery. |
| C2 Terminal Windows crashes | Reboot. Re-load our code from USB. State is in `runs/` which is persisted to disk. |
| Mapping drone NoMachine session laggy | Edit code in our local editor → `scp` to drone → re-run via SSH (faster than IDE-in-NoMachine). |
| Time running out | Show judge whatever artifacts exist. Even partial top-down + 1 valid pad classification counts. |

---

## Emergency contacts

| Person | Phone | Notes |
|---|---|---|
| Z | ______ | runbook holder |
| K | ______ | drone hardware lead |
| A | ______ | judge-talker / ML retrain on the fly |
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

- **Wall collisions** — per qualifier policy, no penalty (confirm if same for finals)
- **Internet at venue** — repo is on USB; pyhulax docs mirrored offline; Discord on phone
- **Bringing our own laptop hardware** — org provides C2 Terminal; personal laptop is dev/backup only

---

*Runbook v1 — based on org slides (5 Jun 2026) + L1-L5 Discord material. Iterate as we learn more at venue.*

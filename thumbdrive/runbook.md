# Qualifier Day Runbook — ArtificiallyUnintelligent
**Friday 22 May 2026, 14:00 SGT**
**Orchard Grand Court, Lloyd I / II**

> Read this aloud as you go. Tick every box. Do not skip.
> Verified end-to-end in sim 21/5 night with K's `best.pt` model.

---

## The night before (Thu 21 May, 23:30+ team call)

- [ ] Confirm USB stick has all of these (run `ls`):
  - `QUICKSTART.txt`
  - `setup.sh`
  - `ArtificiallyUnintelligent.tar.gz` (~64 MB)
  - `best.pt` (K's model, ~6 MB)
  - `verylousymodel.pt` (org reference, ~6 MB)
  - `wheels/` folder (~41 MB, has pymavlink + onnxruntime + deps)
  - `README.md`, `runbook.md` (this file)
- [ ] **TWO USB sticks**, both with identical contents
- [ ] All 3 laptops charged to 100% (can't run on them at venue, but useful for debug + travel)
- [ ] 3 phones charged
- [ ] Student IDs / ICs (all 3 of us)
- [ ] Print this runbook on paper (in case laptop dies)
- [ ] Confirm slot booking screenshot pinned in team chat

---

## Friday morning (22 May)

- [ ] Wake by 10:00 AM. Light breakfast. Limit caffeine.
- [ ] **12:30** — final bag check (USB×2, phones, IDs, paper runbook, pen+pad, water+snack)
- [ ] **13:15** — meet at Somerset MRT (Exit B). If you're late, call others.
- [ ] **13:21** — walk to Orchard Grand Court (6 min)
- [ ] **13:30** — find Lloyd I or II, identify coordinator
- [ ] **13:50** — stand at the door, ready

---

## 14:00 — Clock starts (40 min total)

### Roles (lock at the Thu 11:30pm call)
- **Keyboard**: ______ (drives terminal)
- **Screen-watcher**: ______ (calls out detections, watches map.png, holds the runbook)
- **Judge-talker**: ______ (smiles, asks for VM reset, answers questions, shows artifacts at end)

### Step 1 (T+0–2 min): Reset request
- [ ] Judge-talker: "Hi, please reset the VM to default state."
- [ ] Wait for coordinator to confirm reset. They click a button.
- [ ] Keyboard: plug in USB stick #1.

### Step 2 (T+2–4 min): Disk hygiene
- [ ] Keyboard: open a VM terminal.
- [ ] Run: `df -h /`
- [ ] If disk > 80% used:
  ```bash
  rm -rf ~/PX4-Autopilot/build/px4_sitl_default/rootfs/log/*
  pip cache purge
  df -h /
  ```
- [ ] If still > 80%: ask coordinator to do another reset.

### Step 3 (T+4–8 min): Install our code
- [ ] Keyboard:
  ```bash
  mkdir -p ~/thumbdrive
  cp -r /media/$USER/*/* ~/thumbdrive/      # may differ — tab-complete the USB path
  cd ~/thumbdrive
  bash setup.sh
  ```
- [ ] Script auto-tars repo to `~/ArtificiallyUnintelligent`, copies `best.pt`, installs offline pip wheels.
- [ ] Watch for "SETUP COMPLETE" message.
- [ ] If `setup.sh` complains about a wheel — note which one, install with `pip install --user --no-index --find-links=wheels/ <name>` and try again.

### Step 4 (T+8–12 min): Start sim + EKF origin
- [ ] Keyboard (Terminal 1):
  ```bash
  ~/start_px4.sh
  ```
  - At "Select vehicle model": type `1` (x500_vision), Enter
  - At "Select world": type `1` (roboverse), Enter
  - At "Start QGroundControl": type `2` (No — fake-GCS handles it), Enter
- [ ] Wait ~30 sec for "pxh>" prompt. Sim window should appear with the drone in the arena.
- [ ] At `pxh>` prompt, type:
  ```
  commander set_ekf_origin 47.397742 8.545594 488.0
  ```
- [ ] Watch for "New NED origin (LLA)" + "Ready for takeoff!" in the PX4 log.

### Step 5 (T+12–14 min): Smoke test (Phase 1 only)
- [ ] Keyboard (Terminal 2, leave Terminal 1 with sim running):
  ```bash
  cd ~/ArtificiallyUnintelligent/searchctl
  python3 controller.py --no-detect --no-map
  ```
- [ ] Drone should arm, fly 2m square, land cleanly in ~33 seconds.
- [ ] Watch for "run finished cleanly" in terminal.
- [ ] **If this works, controller + sim are healthy. Move to Step 6.**
- [ ] **If it crashes** — go to "Step 5 failed" in cheatsheet below.

### Step 6 (T+14–24 min): First REAL run
- [ ] Keyboard (Terminal 2) — **recommended: wall-follow mode for coverage**:
  ```bash
  python3 controller.py --pattern wall
  ```
- [ ] OR if wall-follow misbehaves, fall back to scan (yaw 360° at spawn):
  ```bash
  python3 controller.py --pattern scan
  ```
- [ ] All features ON: detection + map + fake-GCS + planner.
- [ ] Runtime: `wall` = up to 8 min then auto-lands. `scan` = ~120 sec.
- [ ] Screen-watcher: call out every `[ctl] detection: class=yellow_barrel ...` or `red_barrel ...` line. Note the count.
- [ ] Open `~/ArtificiallyUnintelligent/searchctl/run_*/map.png` in an image viewer with auto-refresh. Map updates every ~1 sec.
- [ ] For wall: log lines `wall: state=follow_wall front=2.34 right=1.18 ...` print every 5 sec so judge sees the FSM in action.

### Step 7 (T+24–34 min): Re-run if needed
- [ ] If first run found both `yellow_barrel` AND `red_barrel`: STOP, save artifacts. Go to Step 8.
- [ ] If only one or zero: re-run with different starting yaw:
  ```bash
  python3 controller.py --pattern square
  ```
  or try the actual wall-follow if it's working:
  ```bash
  python3 controller.py --pattern wall    # if integrated by Thu
  ```
- [ ] Per org: drone restarts at takeoff after each run. State doesn't persist.

### Step 8 (T+34–38 min): Show the judge
- [ ] Judge-talker opens `~/ArtificiallyUnintelligent/searchctl/run_<latest>/`
- [ ] Show:
  - `detections/*.jpg` — bbox images with `yellow_barrel` / `red_barrel` labels
  - `map.png` — the top-down obstacle map (proves "mapping is being done")
  - `run_summary.json` — flight time + detection count + per-detection poses
- [ ] Say: "We detected N barrels (X yellow, Y red), built a map of the arena, total flight time was Z seconds across N runs."

### Step 9 (T+38–40 min): Pack up
- [ ] Keyboard: copy outputs to USB:
  ```bash
  cp -r ~/ArtificiallyUnintelligent/searchctl/run_* /media/$USER/<USB_LABEL>/saved_runs_$(date +%H%M)/
  ```
- [ ] Judge-talker: thank the judge.
- [ ] Vacate room.

---

## Cheatsheet — what to do if X breaks

| Problem | Fix |
|---|---|
| USB #1 won't mount | Try USB #2. Both have identical contents. |
| Both USBs broken | Ask coordinator if there's wifi. If yes: `git clone https://github.com/zhengboon/ArtificiallyUnintelligent` (Note: repo is private — Z must have already done `gh repo clone` setup OR uploaded a zip somewhere). |
| `setup.sh` fails on extraction | `tar -xzf ArtificiallyUnintelligent.tar.gz -C ~/AU --strip-components=1` manually. |
| `pip install` fails | Add `--no-deps` for the failing package. Most of our deps are already on the org VM. |
| Sim won't start (`start_px4.sh` errors) | Check Gazebo: `gz topic -l`. If empty, sim isn't running. Try `pkill -9 -f px4; pkill -9 -f gz; ~/start_px4.sh` again. |
| Drone won't arm — "is_armable False" | EKF origin not set. Re-type `commander set_ekf_origin 47.397742 8.545594 488.0` at `pxh>` prompt. |
| Drone arms but won't take off | Possible `is_global_position_ok` check. Should not happen with our controller (we skip GPS check). If it does, run `--no-detect --no-map` to isolate. |
| Detection never fires | YOLO worker may not have loaded. Check terminal for `Detector` import errors. Try `--no-detect` to at least get the map + flight credit. |
| Map crashes (matplotlib error) | Run with `--no-map`. We still get flight + detection. |
| QGC needed but not running | Our fake-GCS heartbeat (Phase 6) handles this. If it doesn't, install QGC: `cd ~/Desktop && ./QGroundControl-x86_64.AppImage &` |
| Run hangs after "on ground; disarming" | Wait 15 sec for teardown. If still stuck after 30 sec: `Ctrl-C` once. Artifacts are still saved. |
| "No space left on device" mid-run | `rm -rf ~/PX4-Autopilot/build/px4_sitl_default/rootfs/log/* ~/ArtificiallyUnintelligent/searchctl/run_*` |
| Time running out | Just show the judge whatever artifacts exist. Even 1 detection + map counts. |

---

## Step 5 failed (smoke test)

If `python3 controller.py --no-detect --no-map` fails:

1. **Did sim start?** In sim terminal, you should see `pxh>` prompt + drone visible in Gazebo. If not, restart sim.
2. **Did you set EKF origin?** Re-type the `commander set_ekf_origin ...` line.
3. **Is `mavsdk_server` running?** `ps -ef | grep mavsdk` — if not, kill controller and re-run.
4. **As a last resort**: run an even simpler test:
   ```bash
   cd ~/ArtificiallyUnintelligent/codes/Codes
   python3 takeoff_and_land.py
   ```
   This is the workshop's known-good takeoff script.

If even that fails: ask coordinator for VM reset.

---

## Score math (in case you need to verify the judge)

| Event | Points |
|---|---|
| Yellow barrel detected (unique, ≥50% in bbox) | +50 |
| Red barrel detected (unique, ≥50% in bbox) | +100 |
| Toxic barrel detected | **0** (no penalty, no points — per org) |
| Workshop oil-drum detected | **0** (no penalty, no points — incorrect detection per 16/5 rule change) |
| Manual control of ANY kind during run | **DISQUALIFICATION** |
| University category: only yellow OR only red (no both) | **Unranked** |
| Speed bonus: all yellows found, finished 30s under 5 min | +20 (per 30s) |

---

## What we DON'T need to worry about

- **Wall collisions** — no penalty per org 18/5
- **Multiple photos of same barrel** — no deduction per org today (`there is no points deduct...for incorrect detection`)
- **Internet at venue** — we don't need it. Everything is on the USB.
- **Bringing our own laptop** — we can bring them for travel/debug but won't use at venue (not allowed)

---

## Emergency phone numbers

- Z phone: ______ (call if separated)
- K phone: ______
- A phone: ______
- Discord: keep open on phone for last-minute OP announcements

---

*Runbook v3 — based on 21/5/2026 ~21:00 SGT end-to-end VM test (Phase 1+2+6+7 all confirmed working, K's best.pt firing on barrels with underscore-format labels).*

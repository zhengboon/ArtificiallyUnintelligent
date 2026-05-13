# Progress log — BrainHack 2026 RoboVerse

Running diary of what's been done, day by day. Newest at the top.

Format per entry: what got built / decided / blocked, with concrete paths
and commit hashes where they exist. Skim-able when looking back later.

---

## 2026-05-13 (Wednesday) — Sim verified, YOLO ready, world inspected

Detailed report at `reports/2026-05-13_sim_verification.md`. Troubleshooting cheatsheet at `reports/troubleshooting.md`.

### Sim verified end-to-end
- User booted VM, ran `~/start_px4.sh` (x500_vision + roboverse + QGC), set EKF origin
- Patched `~/Desktop/codes/takeoff_and_land.py` via sed: removed `is_global_position_ok` check, kept `is_home_position_ok`. Original backed up at `.orig`.
- Ran the patched script → **drone armed, took off, hovered 5 s, landed** ✅
- Confirms: PX4 SITL + Gazebo + MAVSDK + EKF origin all wired correctly

### YOLO installed in VM (was missing from v3 image)
- v3 VM didn't have `ultralytics`. First install attempt failed on disk pressure (root was at 95% used) AND uninstalled numpy mid-failure.
- Cleaned `pip cache purge` + `sudo apt clean` → freed ~5 GB
- Restored `numpy<2`, then installed `ultralytics --no-deps` plus selective heavy deps (torch 2.11, torchvision 0.26, opencv-python-headless, etc.)
- Final state: YOLO loads `yolov10n.pt` with 80 COCO classes ✅. Disk now 91% (4.4 GB free).
- **Flag:** disk pressure will keep biting. Either expand the VM disk in VMware, train YOLO on Colab, or use a shared folder for big artifacts.

### Real roboverse world inspected
- Subscribed to `/world/roboverse/.../IMX214/image` from PowerShell-driven Python in the VM
- Grabbed one 1920×1080 frame, copied to host as `D:\hackerverse\spawn_view.jpg`
- Required `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` env var — `vmrun` doesn't source `.bashrc` for non-interactive shells
- Findings:
  - World is a single 38 MB baked GLB at `/home/drone/worlds/groundmodel/meshes/base6.glb`. No discrete barrel/wall models in SDF.
  - Spawn view: 2 **toxic distractors** (RED barrels with yellow diamond hazard signs) flanking 1 **legitimate yellow barrel**. All on ground. Clearly designed to fool naive colour-only detectors.
  - **Toxic barrels are RED, not orange** — my maze_gen had the wrong colour. Fixed.
  - Environment: dark gray hex panels, neon blue accents, white floor grid lines (the 4 m cells).
- `gz model --list` confirms only 3 models loaded: `ground_plane`, `base`, `x500_vision_0`. Everything in the world is in `base`.

### Maze generator updated
- `COLOR_TOXIC` orange → dark red (matches real world)
- README updated with the "what the real world looks like" section
- Generator placement strategy unchanged for now (toxics still random) — noted as TODO to cluster toxics with yellows for realistic adversarial testing

### Documentation
- New `reports/2026-05-13_sim_verification.md` — full run-by-run breakdown
- New `reports/troubleshooting.md` — 30+ symptoms → fixes
- Updated `maze_gen/README.md` and `maze_gen/generate_maze.py`

### Outstanding for next session
- The patched `takeoff_and_land.py` set the pattern — other workshop scripts (`avoid.py`, `basic_offboard.py`) likely need the same `is_global_position_ok` removal
- Run `avoid.py` to see depth-camera-based obstacle avoidance in action
- Run `UseDetectorExample.py` with the patched protobuf env var to see YOLO bbox detection on the live camera (will detect COCO classes, not barrels yet)
- Get the OP's barrel-tuned YOLO weights from Discord (or train via Colab)
- Decide search-controller architecture (port frontier exploration from `pastproject/`)

---

## 2026-05-12 (Tuesday) — VMware up, GitHub repo live, sim install verified

### Environment switch: Linux → Windows
- Switched workstation from the Ubuntu jugaad box to the Windows laptop on `D:\`
- Confirmed: workshop wants Ubuntu 22.04. User's Windows host = VMware Workstation Pro path (not WSL2, not dual-boot, not VM on Linux).

### Workspace consolidation
- Moved `D:\calude files\hackerverse\` → `D:\hackerverse\`
- Updated all hardcoded paths in `discord_watcher/watcher.py`, `discord_watcher/notif_listener.py`, `discord_watcher/README.md`. Verified no stale `calude files` references remain.

### Discord watcher infrastructure (option 2: notifications + 6h poll)
- Installed Python 3.12.10, Playwright 1.59, Chromium for Playwright, `winsdk` (Windows notification API)
- Built `discord_watcher/watcher.py` — Playwright-based poller with persistent profile, auto-discovers channels from sidebar, dedup by message-ID monotonicity
- Built `discord_watcher/notif_listener.py` — UserNotificationListener API, filters to Discord toasts, saves to `info_<date>/notif_<ts>_<id>.md`
- Wrapper batch files: `run_login.bat`, `run_poll.bat`, `run_listener.bat`
- Decision: 6 h poll cadence (not 10 min) for lower detection risk; notifications fill the gap as real-time placeholder
- **Not yet:** scheduled tasks not registered, user hasn't done first-run login

### Discord dump
- Created `info_2026-05-08/` with `msg_001.md` through `msg_008.md` containing manually-pasted Discord channel content (general, support-ticket, qualifier challenge, learning materials, coding-discussion, tech-discussion, files-for-option-b)
- Audited links: 2 new useful files appeared (`gzphotodetectorsaver.py`, `OakD-Lite_model.sdf`) — downloaded both via PowerShell + Drive confirm-token trick into the right local folders
- Flagged 3 v2 files (`get_position_with_task_v2.py`, `GlobalMapperV2.py`, `mapper.py`) as Discord attachments-only, not on Drive — still need manual fetch from Discord

### VMware Workstation Pro install
- Installed via Broadcom (free for personal use). Picked **17.6.4** branch over 25H2 — older, more battle-tested for our 3D-Gazebo-heavy workload, less chance of surprise regressions in a 10-day window.
- v3 VM image (`Drone-Ubuntu-22.04_v3.zip`, 18.4 GB) downloaded
- Moved zip C: → D:, extracted via `tar -xf` (48.4 GB extracted)
- VMX: `D:\hackerverse\vm\Drone-Ubuntu-22.04\Drone-Ubuntu-22.04.vmx`

### Cross-host control via vmrun
- Discovered `vmrun.exe` lets the Windows host run commands inside the VM without SSH
- Wrote an `Invoke-VMGuest` PowerShell helper that runs guest scripts and captures stdout/stderr via temp file roundtrip
- Verified install: Gazebo Harmonic 8.11.0, Python 3.10.12, MAVSDK Python imports OK, 41 files in `~/Desktop/codes`
- Found `base6.glb` missing from VM's worlds dir → copied 37 MB file in from Windows side
- Verified `x500_vision/model.sdf` references OakD-Lite (depth camera comes via that include — not the literal `depth_camera` string I first grepped for)
- VM is ready for tomorrow's sim test

### GitHub
- Installed GitHub CLI 2.92.0 via winget
- `gh auth login` → logged in as `zhengboon` (web flow, scopes: `gist`, `read:org`, `repo`, `workflow`)
- Git identity: `zhengboon` / `e1399019@u.nus.edu`
- Pushed to `https://github.com/zhengboon/ArtificiallyUnintelligent` (private, default branch `main`)
- Initial commit: 66 files (commit `467f89c`, force-pushed over the auto-generated README)
- Follow-up: added `pastproject/` (removed from .gitignore, stripped its inner .git, 195 total files now, commit `f862532`)
- Warning logged: `pastproject/CAD/turtlebot with launcher.zip` is 65 MB — over GitHub's 50 MB soft limit, under 100 MB hard limit, pushed anyway
- .gitignore excludes: `vm/`, `learning/*.mp4`, `discord_watcher/profile/`, `discord_watcher/config.json`, `discord_watcher/logs/`, `info_*/`, `maze_gen/output/*.{sdf,json,png}`, `__pycache__/`, editor cruft

### Documentation
- Created `progress.md` (this file)
- All setup docs updated to new path (`D:\hackerverse\`)
- `context.md` reflects two-machine plan: primary = Windows + VMware (v3 VM, this work), secondary = bare-metal old box (when user revives it later)

### Outstanding for next session
- v3 VM credentials confirmed: `drone` / `password`
- VMware shared folders not set up — currently bridging via `vmrun copyFile*`
- SSH inside VM not enabled — vmrun is sufficient for now
- Discord watcher needs first-run (`run_login.bat`) + scheduled task registration

---

## 2026-05-08 (Friday) — Workshop research, downloads, maze generator built

This was on the Ubuntu jugaad box (`/home/jugaad/zbstuff/hackerverse/`). Files later migrated to `D:\hackerverse\` on 2026-05-12.

### Workshop materials downloaded
- All 5 PDFs (Lecture 1–3 + Supplementary 1–2): 14 MB total
- All 5 MP4 lecture videos: 1.7 GB total (later gitignored from repo to keep size down)
- Qualifier brief, Workshop Laptop Requirements docx, Option B docx
- Full Codes folder mirror (39 reference scripts incl. `yolov10n.pt` weights and `*_new.py` updated versions)
- Option B setup files: `start_px4.sh`, `roboverse.sdf`, `base6.glb`, modified `x500_vision/model.sdf`
- Not downloaded: VM image (per user instruction; downloaded fresh on 2026-05-12), VMware Fusion Pro (Mac-only), `vionode` (Drive perm error, optional for Qualifier)

### Materials review (deep read of L1–L3 + Qualifier brief)
- L1: PX4 / MAVSDK / Gazebo sim basics; takeoff_and_land + basic_offboard demos
- L2: localization via VO; depth camera via gz-transport; reactive obstacle avoidance pipeline (depth → histogram → cost map → NED waypoint); EKF origin trick on slide 14
- L3: goal vector + avoidance vector hybrid; exploration strategies (lawnmower + BFS/DFS); YOLO via Ultralytics; occupancy grid (Final-tier, not strictly needed for Qualifier)
- Wrote an opinionated review with priority order: search strategy is the differentiator (avoidance + flight are solved), detection dedup is critical, vertical search for elevated reds is the most-missed thing by beginners

### Past project clone + review
- Cloned `https://github.com/hong-yiii/CDE2310_System_Design` into `pastproject/`
- 1608-line `global_controller.py` is the gold: frontier exploration (`detect_closest_frontier_outside`), occupancy filtering (`occ_callback`), heat→world fusion (`calculate_heat_world`), KMeans clustering (`find_centers`), state machine. Direct analog for RoboVerse barrel hunt.
- No "random maze generator" in the repo (user misremembered) — but the frontier exploration logic is far more valuable than a generator would be
- Key lesson from `improvements.md`: their "fully scan then cluster" strategy was time-inefficient; reactive submit-on-detect would have been better. Applies directly to RoboVerse's 10-min hard cap.

### Random maze generator (`maze_gen/`)
- Built `generate_maze.py` — single-file Python, stdlib + optional matplotlib for PNG previews
- Polyomino wall placement (1×1, 2×1, 3×1, 4×1, L, T, 2×2 shapes with random rotation), BFS connectivity-checked after each placement
- Central 2×2 keepout so drone spawn at (0, 0, 0) is always OPEN
- Yellow barrels on ground (cylinders, z=BARREL_HEIGHT/2), red on shelves (cylinders, z=SHELF_HEIGHT + BARREL_HEIGHT/2), toxic distractors mixed
- Outputs: `.sdf` world file (drop-in for PX4-Autopilot worlds dir, default `<world name='roboverse'>`), `.json` ground-truth metadata, optional PNG preview
- Seedable via `--seed N`
- Tested with seeds 1, 2, 42, 99 — clean valid layouts each time, central spawn always open, no isolated regions

### Documentation
- `context.md` — full project context (qualifier constraints, tech stack, gotchas, code map, past-project notes)
- `README.md` — workspace manifest
- `setup_guide.md` — VMware-on-Windows install guide (Path A: provided v3 VM, Path B: fresh Ubuntu)
- `setup_guide_part2.md` — bare-metal native Ubuntu install for the second computer (when revived)
- Each doc references the others, no duplication

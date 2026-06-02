# BrainHack 2026 RoboVerse — `ArtificiallyUnintelligent` team workspace

Repo: <https://github.com/zhengboon/ArtificiallyUnintelligent>
Qualifier: **2026-05-22 (Fri) 14:00 SGT** at Orchard Grand Court, Lloyd I/II. ✅ **PASSED** — all targets detected, top 26 of ~70 teams advancing.

## Semi-final — start here

We're now prepping for the semi-final (date TBA). The scope is a big shift:

- Sim → **real Hula drones** (multiple, swarm-controlled from one laptop)
- MAVSDK → **pyhulax** SDK (MAVSDK does NOT work with Hula)
- New depth source: **Realsense D430/D450** via `pyrealsense2`
- New target types likely: **ArUco / QR / AprilTag** fiducial markers in addition to barrels

**Read [`semifinal/README.md`](semifinal/README.md) for the exhaustive prep report** — what changes, what we get for free from the SDK, what we need to build, open questions for the org, code skeleton, per-member tracks, learning materials index.

## Where things are

| Path | What |
|---|---|
| `semifinal/` | **Semi-final prep** — Hula SDK references, prep report, working files (post-qualifier) |
| `searchctl/` | Qualifier controller (Phases 1–6) — DONE, kept for reference |
| `maze_gen/` | Random maze generator for testing the controller against varied layouts |
| `discord_watcher/` | Local Playwright + Flask tools for watching/auditing the workshop Discord |
| `team/tasks.md` | **Exhaustive task list for K, A, Z** — read first if joining the project |
| `team/discord_drafts.md` | Outbound Discord messages we've drafted but not yet sent |
| `progress.md` | Day-by-day diary; newest at top |
| `guides/vm_from_zero_to_flight.md` | **Canonical setup guide** — every fix we discovered from stock v3 to flying |
| `reports/` | Session reports + troubleshooting cheat sheet |
| `challenge/` | Workshop's qualifier brief + setup docs (Drive mirrors) |
| `learning/` | Workshop's L1–3 + Supp 1–2 lecture PDFs + MP4s |
| `optionB/` | Workshop's BYO setup files (`start_px4.sh`, `roboverse.sdf`, `base6.glb`, modified `x500_vision/model.sdf`, OAK-D Lite model.sdf) |
| `codes/Codes/` | Workshop's reference Python scripts (mirror of their Drive folder) |
| `pastproject/` | Frontier-exploration TurtleBot3 project we reference for search-strategy ideas |
| `tools/` | One-off debugging scripts (`patch_drone_control.py`, `diag_arm.py`) |
| `info_*/` (gitignored) | Discord channel snapshots — local only, not shared |
| `vm/` (gitignored) | v3 VM image + extraction — too big for git |

## Key reminders

- **Drone model: `x500_vision` only.** Qualifier forbids GNSS. Workshop's `x500_depth` uses GPS — would DQ us.
- **EKF origin trick (every fresh sim start):** `commander set_ekf_origin 47.397742 8.545594 488.0` in the `pxh>` console. Without this, drone can't arm. Our controller can't do this for you — `commander` is a PX4-shell command, not a MAVLink message.
- **Battery + supply checks:** `param set CBRK_SUPPLY_CHK 894281` and `param set SIM_BAT_MIN_PCT 100`. Our `searchctl/controller.py` applies these automatically via MAVSDK; you only need them manually if running workshop scripts directly.
- **Detect target:** plain yellow + plain red barrels. **NOT the ones with toxic-sign warning labels.**
- **Submission:** bounding-box `.jpg` files (`detectN.jpg`) or live bbox window during the 10-min demo. ≥50% of barrel inside box.

## Workshop reference scripts (`codes/Codes/`)

The OP says "files ended with `_new.py` are updated codes" — generally true, **with one exception**:

> ⚠️ **`drone_control_new.py` is INCOMPLETE.** It's missing `rotate_to_yaw` (and probably other methods) the original `drone_control.py` had. If you naively `cp drone_control_new.py drone_control.py`, `avoid.py` will crash with `AttributeError: 'Drone' object has no attribute 'rotate_to_yaw'`. We hit this on 2026-05-13 — see `guides/vm_from_zero_to_flight.md` §8.1 for the surgical-patch alternative.

Other `_new` files (`GlobalMapper_new.py`, `PointCloudPlanner_new.py`, `RRTExample_new.py`) appear complete and are fine to use as drop-in replacements.

## How to start

- **New teammate?** Read `team/tasks.md` for your assigned track, then your track's docs (`searchctl/README.md` for Z, the dataset section of `team/tasks.md` for K, etc.).
- **First time setting up the sim?** Follow `guides/vm_from_zero_to_flight.md` end-to-end — it's the canonical guide. (The older `setup_guide.md` and `setup_guide_part2.md` at the root are kept for historical reference but should be considered superseded.)
- **Running into something weird?** Check `reports/troubleshooting.md` first — most known gotchas have one-line fixes.

## Not in this repo

- VM v3 image — too big, gitignored. Download from Discord and put in `vm/`.
- `vionode` (OpenVINS helper) — Drive download fails for us; not needed for Qualifier per OP.
- VMware Fusion Pro installer — Mac-only.
- Discord scrape outputs (`info_*/`) — gitignored; team-only.

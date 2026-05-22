# 06 — DEEP REVIEW + HANDOFF — Fri 22 May 2026, T-5h to qualifier

> Compiled after the K-merge + zb-layering pass. Latest commit on `zb`
> at write time: `b517374` (thumbdrive cleanup). Branch ready for venue.

## Current branch state

- `origin/main` @ `750b1ff` (Z's pre-merge baseline, unchanged since)
- `origin/ks`   @ `62feaba` (K's "Update with my working code", 22 May 04:20)
- `origin/zb`   @ `b517374` (working branch, ALL improvements live here)

## What's in `zb` that isn't in `main` or `ks`

### Architecture
- Took K's `controller.py` (983 lines) as the base, layered our features
  back on top. K's `wall_following.py` untouched (his speed/corner tuning
  preserved — we tried bumping them and EKF blew up, reverted).

### Detection pipeline fix (CRITICAL)
- K's `image_callback` only bumped `state.detection_count`; never appended
  `DetectionRecord` to `state.detections`. So dedup + STATUS.txt + early-
  exit on dual-colour-found all saw 0 forever even with 29+ raw detections.
- Now: each surviving box (toxic class filtered out) becomes a
  `DetectionRecord(seq, ts, class_name, confidence, bbox_xyxy,
  pose_at_detect, saved_path)` appended to `state.detections`.
- Class-name remap added: K's `best.pt` exports "yellow barrel" /
  "red barrel" (with spaces); org example uses underscores. Remap fires
  on both `model.model.names` and `model.names`.

### Bonus mode (`--bonus`)
- Hard-land at `BONUS_HARD_LAND_S = 260s` (~4:20) to stay inside the
  qualifier's 5-min bonus window.
- Early-exit when both colours detected + `BONUS_DUAL_COLOUR_HOLD_S = 25s`
  hold to let YOLO find more.
- Plateau early-exit: no new unique cluster for 30s (bonus) / 60s (default)
  while both colours present.

### A. Stuck-escape (always on)
- If drone drifts <1m in 20s, escape maneuver: back 1.5s + yaw in place
  3s + forward 2s, all at 0.5 m/s / 60°/s.
- Resets K's WallFollower FSM to `find_wall`.
- Cooldown 25s between escapes.

### B. Periodic 360° scan station (always on)
- Every 75s of wall-follow time, pause and yaw 360° at 50°/s for 8s.
- Pure rotation, vision-EKF safe.
- Designed to catch barrels K's algo flies past without seeing.

### C. Detect-and-approach nudge (always on)
- When YOLO fires with bbox center in outer 25% of frame,
  `image_callback` writes a one-shot yaw delta (±20°) into
  `state.pending_yaw_nudge_deg`.
- Main loop applies on next tick and zeros the channel.
- Cooldown 8s.

### `--backup` — SCAN-AND-WALK EXPLORER (alternative nav algo)
- Independent of K's wall-follow entirely.
- Loop: hover + yaw 360° in place → read depth → walk forward 10s at
  0.5 m/s along the direction with most clearance → repeat.
- Pure body-frame velocity (EKF-safe).
- Covers ARENA INTERIOR (where K's wall-follow never goes — yellow
  barrels on floor are likely in interior).

### Detection dedup tuning
- `DETECTION_CLUSTER_RADIUS_M` 1.5 → 3.0 m. The 1.5m radius reported
  4 unique reds for 1 physical barrel (drone moves past it over 37s).

### Live `STATUS.txt`
- Written every 5s during flight by `incremental_status_writer` task.
- Shows: status (RUNNING/LANDED/ABORTED), elapsed, bonus-window
  countdown, ELIGIBLE flag, base score estimate, unique counts,
  next-action hint, last 3 detections.

### `slot_summary.py` (post-slot helper)
- Scans every `run_*/run_summary.json`, scores by qualifier rubric
  (50/100 base + bonus), reports best. Run at end of slot:
  `python3 slot_summary.py` → writes `slot_summary.txt`.

### CLI flags
| Flag | Purpose |
|---|---|
| `--bonus` | 4:20 hard-land + dual-colour hold |
| `--backup` | SCAN-AND-WALK explorer (different nav algo) |
| `--altitude FLOAT` | Cruise altitude (default 3.0 — K's tuning) |
| `--conf FLOAT` | YOLO conf threshold (default 0.70 — K's tuning) |
| `--no-detect` / `--no-map` / `--no-fake-gcs` | Disable subsystems |

## Verified in sim

| Test | Result |
|---|---|
| Wait-until-armable for x500_vision (no GPS) | ✅ Fixed (accept home_ok+local_ok) |
| Takeoff completion (EKF-stale case) | ✅ Fixed (accept in_air + 1m + 15s) |
| First clean bonus run: 277s flight | ✅ 32 raw dets, 4 unique red (1 real barrel × 4 cluster centroids — fixed via radius 3.0m) |
| Bonus mode hard-land at T+260s | ✅ Exact, clean exit |
| Detection JPGs saved | ✅ 32 files in `detections/` |
| `STATUS.txt` updated every 5s | ✅ |
| K's model on Roboverse | ✅ red_barrel confidence 0.85–0.97 |
| K's model on yellow | ❌ **0 yellow detections so far** |

## NOT YET TESTED IN SIM

- A/B/C backup behaviours (just deployed `c87f7ab`)
- `--backup` scan-and-walk explorer
- Yellow detection at altitude 2.0 + conf 0.5

## Known unresolved problems

1. **No yellow barrel detection.** K's model may not fire on the new
   yellow target (floor-level object), or our camera angle misses it.
   Mitigations available:
   - `--altitude 2.0` (closer to floor)
   - `--conf 0.5` (more aggressive threshold)
   - `--backup` (covers arena interior where yellow may live)
2. **EKF drift between runs.** Each run leaves PX4 in a drifted state.
   Sim restart needed between attempts (Ctrl-C PX4 + relaunch).
   This is documented in runbook + QUICKSTART.
3. **Gazebo ogre renderer crash** intermittent on heavy VM use.
   Reset VM if it appears. Should be a non-issue on the fresh org VM
   at venue.

## Recommended qualifier strategy

| T+min | Command | Goal |
|---|---|---|
| 0-12 | setup.sh + sim boot + EKF origin | Get to ready state |
| 12-13 | `python3 controller.py --no-detect --no-map` smoke | Verify takeoff |
| 14-19 | `python3 controller.py --bonus` (FIRST scored run) | Bank bonus if lucky |
| 22-32 | `python3 controller.py --backup --bonus` (SECOND scored) | Cover interior, find yellow |
| 34-40 | `python3 controller.py --bonus --altitude 2.0 --conf 0.5` (THIRD if time) | Yellow chase |
| End | `python3 slot_summary.py` | Pick best attempt for judge |

Best-attempt-counts per qualifier PDF. Score = 50·N_yellow + 100·N_red +
bonus (20 pts per 30s under 5min for finding ALL of a colour).
Eligibility requires ≥1 yellow AND ≥1 red.

## Files inventory (zb)

| Path | Lines | State |
|---|---|---|
| `searchctl/controller.py` | 1648 | Heavily modified |
| `searchctl/wall_following.py` | 172 | K's, untouched |
| `searchctl/slot_summary.py` | 125 | New (Z) |
| `codes/Codes/Detector.py` | K's 0.70 default | Untouched |
| `codes/Codes/depthcloud.py` | (workshop, was in initial commit) | Untouched |
| `codes/Codes/drone_control.py` | (Z's safety-check tweaks pre-merge) | Untouched |
| `thumbdrive/_vm_run_wall.sh` | Default wall-follow launcher | Updated |
| `thumbdrive/_vm_run_bonus.sh` | `--bonus` launcher | Updated |
| `thumbdrive/_vm_run_backup.sh` | `--backup --bonus` launcher | NEW |
| `thumbdrive/_smoke.sh` | Pre-flight smoke test | Updated |
| `thumbdrive/runbook.md` | Qualifier-day procedure | Updated |
| `thumbdrive/QUICKSTART.txt` | One-page summary | Updated |

## Things NOT in zb that aren't worth porting

- The grid pattern + scan pattern from my old zb code (replaced by
  the always-on periodic scan B + the --backup nav algo, both better)
- Map detection markers overlay (was in my old zb; not in K's render)
- Speed boosts on clear straights (broke EKF, reverted)

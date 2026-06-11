# 07 — VENUE READY — Fri 22 May 2026, T-2.5h to qualifier (14:00 SGT)

> Final state after multiple test cycles. Latest commit on `zb`: `5cff151`.
> Branch is ready for the venue. K's algorithm preserved; minimal safe
> additions on top.

## Current `zb` state vs `origin/ks`

`zb` ≠ `ks` in **one** file only: `searchctl/controller.py`.

`wall_following.py` and `codes/Codes/Detector.py` match `origin/ks 62feaba`
byte-for-byte. K's wall-follow algorithm is **untouched**.

## What's on top of K's controller (zb additions)

### Safe data layer (no flight behaviour change)
- **Protobuf env var** at top — without it the `depthcloud` / `depth_receiver`
  imports fail with "Descriptors cannot be created" on the VM's protobuf
  version. Required for the module to even load.
- **Class-name remap** at YOLO load: `"yellow barrel"` → `"yellow_barrel"`,
  `"red barrel"` → `"red_barrel"`, `"toxic barrel"` → `"toxic_barrel"`.
  Makes JPG bbox labels + log lines match the org example format.
- **DetectionRecord append** in the YOLO callback — K's original only
  bumped `detection_count` but left `state.detections` empty. With this
  fix, the dedup + STATUS.txt + run_summary all see real per-frame data.
- **Class names in detection log line**:
  `detection: frame=N boxes=K [red_barrel(0.92),yellow_barrel(0.87)] total=M`
  — no need to open JPGs to know which colours fired.
- **`compute_unique_detections()`** clusters detections within 3.0m by
  drone pose at detect time. Output written to `run_summary.json` as
  `unique_detections: {yellow_barrel, red_barrel, toxic_barrel, total}`.
- **`incremental_status_writer`** async task writes `run_summary.json` +
  `STATUS.txt` every 5 s during flight. STATUS.txt shows ELIGIBLE flag,
  base score estimate, bonus-window countdown, next-action hint, and the
  last 3 detections.

### Bonus mode (`--bonus`) — only DECIDES, never overrides velocity
- Hard-land at `BONUS_HARD_LAND_S = 260s` (~4:20) to stay inside the
  qualifier's 5-min bonus window per the rubric in the PDF.
- Early-exit `BONUS_DUAL_COLOUR_HOLD_S = 25s` after both colours first
  detected — gives YOLO a chance to spot additional barrels.
- Plateau early-exit: no new unique cluster for 30s (bonus) / 60s (default)
  while both colours present.

### Periodic 360° scan station (with velocity gate)
- Every `SCAN_EVERY_S = 60.0s`, IF `vel_mag < 0.1 m/s` AND timer up,
  pause and yaw 360° in place at `SCAN_YAW_RATE_DEG = 60.0 deg/s` for
  `SCAN_DURATION_S = 6.0s` = exactly 360°.
- Velocity gate added 22/5 after drone-crash report: scan only fires
  when K's wall-follow naturally has the drone in a hover state
  (`avoid_front` or `outer_corner` phase 2). If K keeps drone moving
  continuously, scans are skipped (better to miss a scan than crash).
- Pure yaw, no altitude change, no translation.

### CLI flags
| Flag | Default | Purpose |
|---|---|---|
| `--bonus` | off | 4:20 hard-land + dual-colour early-exit |
| `--altitude FLOAT` | 3.0 | Takeoff altitude — drop to 2.0 for floor-level yellow |
| `--conf FLOAT` | 0.70 | YOLO threshold — drop to 0.5/0.35 for more aggressive detection |
| `--no-detect` / `--no-fake-gcs` / `--no-map` | off | Subsystem opt-outs |

## Tested configurations + results today

| Time (host) | Config | Outcome | Score est |
|---|---|---|---|
| 11:18 | `--bonus --altitude 2.0 --conf 0.5` + periodic scan (120°/s × 3.5s) | **1Y / 3R, ELIGIBLE** | **350 pts** + bonus |
| ~11:30 | Same + spawn-scan + altitude wiggle + peek + turnaround | Drone crashing into walls — reverted |
| 11:35 | `--bonus --altitude 2.0 --conf 0.5` + NO scans (clean K) | 0Y / 2R, NOT eligible | 0 pts |
| 11:44 | Same + slow scan (60°/s × 6s) | (testing now) | TBD |
| 11:46 | Same + slow scan + velocity gate | (next test) | TBD |

## Recommended qualifier strategy at venue

40-min slot, best-attempt-counts, sim-restart between attempts.

| T+min | Command | Goal |
|---|---|---|
| 0-12 | setup.sh + sim boot + ekf_origin | Get to ready state |
| 12-13 | `python3 controller.py --no-detect --no-map` | Verify takeoff (~1 min smoke) |
| 14-19 | `python3 controller.py --bonus --altitude 2.0 --conf 0.5` | PRIMARY scored attempt (proven 350 pts last sim) |
| 22-32 | `python3 controller.py --bonus --altitude 2.5 --conf 0.5` | Try higher altitude (see top of lockers) |
| 34-40 | `python3 controller.py --bonus --altitude 1.5 --conf 0.35` | Hail-Mary: very low + very aggressive |
| End | `python3 slot_summary.py` | Pick best attempt for judge |

## Known problems carried into venue

1. **No yellow detection without scans.** Periodic scan was actually
   catching the yellow in the 350-pt run. Currently testing whether
   the slow + velocity-gated scan is safe enough.
2. **EKF drift between runs** — sim restart between attempts is
   essential. Documented in runbook + QUICKSTART.
3. **Drone never returns to spawn** even in K's 19-min run. Not a
   problem for scoring but artifact recovery requires walking to
   wherever drone landed.
4. **Gazebo ogre renderer crashes** occasionally — only an issue on
   our dev VM, fresh org VM should be clean.

## Files inventory (zb @ 5cff151)

| Path | Lines | State |
|---|---|---|
| `searchctl/controller.py` | ~1090 | K base + zb safe layer + bonus + slow gated scan |
| `searchctl/wall_following.py` | 172 | K's exact, untouched |
| `searchctl/slot_summary.py` | 125 | zb post-slot scoring helper |
| `codes/Codes/Detector.py` | (K's) | Untouched |
| `codes/Codes/depthcloud.py` | (workshop original) | Untouched |
| `codes/Codes/drone_control.py` | (Z's safety check pre-merge) | Untouched |
| `thumbdrive/_vm_run_wall.sh` | (no flags, default wall-follow) | Updated 22/5 |
| `thumbdrive/_vm_run_bonus.sh` | `--bonus` | Updated 22/5 |
| `thumbdrive/_smoke.sh` | `--no-detect --no-map`, Ctrl-Cs after takeoff | Updated 22/5 |
| `thumbdrive/runbook.md` | Qualifier-day playbook | Updated 22/5 |
| `thumbdrive/QUICKSTART.txt` | One-page summary | Updated 22/5 |

## Things explicitly NOT in zb (don't re-add without testing)

These were tried and caused wall crashes per user observation:
- Stuck-escape maneuver (back+yaw+fwd)
- Detect-and-approach yaw nudge
- Initial spawn 360 scan at takeoff
- Front-of-takeoff peek (translation + end-scan)
- Altitude wiggle during periodic scan (descend → scan → climb)
- Hard 180° turnaround at T+3:30
- Speed boosts on clear straights (blew EKF to D=+877m)
- `--backup` scan-and-walk explorer nav

## Commit lineage on zb today (22 May)

```
5cff151  scan gate — only trigger periodic 360 when drone velocity ~zero
ad17b68  add back periodic 360 scan but SLOW (60 deg/s for 6s vs 120/3.5)
a1956a3  REVERT all 360 scans + altitude wiggle + turnaround (drone crashing)
4066293  add 4 low-risk soft-hardcoded enhancements (A+B+C+D)  ← CAUSED CRASHES
19a45e3  re-add SAFE features on top of K's controller (no velocity overrides)
9f5428a  add periodic fast 360 scan to K's wall-follow (every 60s)
127cdbd  REVERT controller.py to K's untouched version (+ protobuf env var only)
b517374  thumbdrive scripts + runbook + QUICKSTART updated for current CLI
c87f7ab  backup behaviours (A+B+C) + --backup nav algo (scan-and-walk)
5c8fb16  dumpcontext/06 deep-review handoff + progress.md entry for T-5h state
93ce5ef  Pull every linked Drive doc/slide we hadn't fetched
cdd0cd8  Add captured Qualifier Challenge PDF
8ec035e  zb: retries + detection dedup + live status writer + smoke test
afd6c74  zb: fix grid pattern divergence
596acc8  zb: --pattern grid BACKUP STRATEGY
c7ffa6f  zb: scoring-visible artifacts + at-venue tuning levers + slot summary
130eaa0  zb: --bonus mode for the qualifier 5-min bonus window
1675dcc  zb: wait_until_armable accepts vision-drone armable state
9912748  zb: set PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION before depth imports
7d45f67  zb: arm_and_takeoff robustness
159d4f1  zb: tighten in_air takeoff fallback
403e32e  zb: detection callback now appends DetectionRecord
0817819  zb: speed-up pass based on first successful sim run analysis  ← BROKE EKF
cb620f5  zb: REVERT aggressive speed boost
1819838  zb: merge K's working code (origin/ks) + relayer high-value zb features
```

## TL;DR for someone walking in now

```bash
# Setup
git clone <repo> + checkout zb        # or USB unpack
bash setup.sh                          # in VM, after unpacking thumbdrive
~/start_px4.sh                         # then 1, 1, 2
commander set_ekf_origin 47.397742 8.545594 488.0    # in pxh>

# Run (current best known config)
cd ~/ArtificiallyUnintelligent/searchctl
python3 controller.py --bonus --altitude 2.0 --conf 0.5

# After all runs in slot
python3 slot_summary.py                # picks best for judge
```

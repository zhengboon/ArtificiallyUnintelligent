# KEY FACTS — load these into the next session

## Qualifier rules (most recent)

- **Map**: workshop Roboverse map (no change). Only barrels change.
- **Targets**: red gas cylinder in locker (~1.5m elevated) + small yellow gas cylinder on floor.
- **OLD oil-drums**: NOT targets anymore (per 16/5 announcement, crossed out by org).
- **Detection format**: bbox image OR live display, ≥50% of barrel in box, label format `yellow_barrel` / `red_barrel` (underscores, per org's example image).
- **No deduction** for incorrect detections (org confirmed 21/5).
- **Wall collisions**: no penalty.
- **Manual control**: any form = DQ. No joystick/keyboard/mouse/gamepad/remote.
- **Time**: 40 min total at venue. Multiple 10-min runs allowed. Drone resets to takeoff position each restart.
- **Compute**: org laptop + org VM ONLY. We bring USB. No internet guaranteed. No setup help from judges.
- **VM**: 4-8 cores, 8GB RAM, 50GB disk, reset between teams.

## Models in `D:\hackerverse\models\`

| File | Classes | Trained | Notes |
|---|---|---|---|
| `best.pt` (K's) | yellow barrel / red barrel / toxic barrel (SPACES) | 16/5/2026, 40 epochs, yolov8n | Has the obsolete toxic class. Detector.py filters classes=[0,1] to drop toxic. Mixed targets in training data (some workshop drums, some new cylinders). |
| `verylousymodel.pt` (org) | red_barrel / yellow_barrel (UNDERSCORES) | 18/5/2026, 100 epochs | Disclaimer "very lousy". Fires on workshop drums in tests. Org reference. |

**Current symlink in VM**: `/home/drone/AU/models/best.pt` → real K's file (not symlink anymore).

**Label remap in controller.py setup_detection()** monkey-patches K's model.names → `{0: yellow_barrel, 1: red_barrel, 2: toxic_barrel}` so output matches org's underscore format.

## Architecture decisions made

1. **Setpoint pumper at 10 Hz** independent task (so PX4 heartbeat never times out)
2. **Lazy imports** for detection/mapping/fake-GCS deps (so flight isn't blocked by missing libs)
3. **Headless matplotlib** (Agg) for Phase 7 mapping (no display server needed)
4. **fake-GCS UDP 14550** (Phase 6, pymavlink MAV_TYPE_GCS heartbeat) — removes QGC dependency
5. **Map cap at 200k points** — prevents unbounded growth, oldest dropped past cap
6. **--pattern flag**: `square` (smoke test, no yaw), `scan` (hover + 360° yaw at spawn), `wall` (K's wall-following, in progress)
7. **Detection confidence threshold lowered to 0.35** (was 0.5) — uncommitted change
8. **Shutdown flag in detection + mapping callbacks** so teardown doesn't hang on draining queues

## Team status

- **Z (user)**: doing all integration + USB prep tonight
- **K**: still tuning wall_following standalone (was at 3:55pm "needs more tuning, gets stuck in corners"). Last known: he's somewhere on a bus, said "I'll only be back home at 11pm"
- **A**: light involvement. Will be at the team call. Saturday occupied so can't qualify backup day.

## Files modified, not yet committed (as of context dump)

- `searchctl/controller.py`:
  - SharedState velocity-mode fields added
  - VelocityBodyYawspeed imported
  - DETECT_CONFIDENCE_DEFAULT 0.5 → 0.35
  - Label-name monkey-patch (yellow_barrel underscore format)
  - (Wall-following planner NOT YET added)

## Sim test artifacts in `D:\hackerverse\info_2026-05-21\`

- `vm_test_2026-05-21_run1/` — Wed night first end-to-end (square, verylousymodel, hung teardown)
  - `map.png` shows arena obstacles from the 2m square
- `vm_test_2026-05-21_run2_FULL/` — Thu night with teardown fix (square, verylousymodel)
  - 2 yellow_barrel detections, run_summary.json clean, "run finished cleanly"
  - `detection1.jpg` shows yellow oil drum (WORKSHOP, not new target) with `yellow_barrel 0.52` bbox

## Open questions still pending org answer

1. Pre-planned waypoints with prior map knowledge allowed? (ROBO06 asked 17/5, no answer)
2. Max altitude? (ROBO06 asked yesterday, no answer)
3. Which photo wins for repeat detections of same barrel? (kaushik asked, no answer)

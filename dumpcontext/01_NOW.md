# NOW — current state (Thu 21 May 2026 ~22:18 SGT)

**T-15 hours 42 min to qualifier.** Friday 22 May 14:00 SGT at Orchard Grand Court.
**Team call at ~23:30 tonight** (~1 hr 12 min from now).

## What I'm in the middle of

**Integrating K's `searchctl/wall_following.py` into `searchctl/controller.py` as `--pattern wall`.**

K's code is **velocity-based** (body-frame), our controller was **position-based**. Adding velocity-mode support.

**Progress so far:**
- ✅ `SharedState` gained `velocity_mode`, `vel_fwd`, `vel_right`, `vel_down`, `yaw_rate_deg` fields
- ✅ Imported `VelocityBodyYawspeed` from `mavsdk.offboard`
- ⏸️ **NOT YET DONE**: setpoint_pumper branch on `state.velocity_mode`
- ⏸️ **NOT YET DONE**: `_depth_to_points_3d()` helper for K's `get_wall_distances(points)` (Nx3 expected)
- ⏸️ **NOT YET DONE**: `planner_wall(state, map_handle)` async function
- ⏸️ **NOT YET DONE**: `--pattern wall` in CLI choices
- ⏸️ **NOT YET DONE**: dispatch in `main()`/`run()` to invoke planner_wall when pattern=wall

## What's verified working (end-to-end VM tests tonight 21:01 and earlier)

✅ **Phase 1 flight** — 5-WP square, sub-0.4m err per WP, 79-90s total
✅ **Phase 2 detection** — verylousymodel fired 2× `yellow_barrel 0.52` during landing
✅ **Phase 6 fake-GCS** — 131 heartbeats sent, PX4 said "Ready for takeoff" without QGC
✅ **Phase 7 mapping** — 200k points accumulated, map.png + map_points.npy + run_summary.json all saved
✅ **Teardown fix** — clean exit, "run finished cleanly" printed
✅ **Label format** — verylousymodel outputs `yellow_barrel` (underscore, matches org example)

## Issues discovered tonight

⚠️ **K's `best.pt` fired 0 detections** on square pattern. Possible causes:
- Square pattern doesn't yaw (camera looks same direction throughout)
- K's model trained on different angles than verylousymodel had
- Confidence threshold 0.5 may be high — lowered to 0.35 (uncommitted)

⚠️ **Disarm sometimes fails** with COMMAND_DENIED if drone doesn't quite land before timeout. Recoverable but cosmetically ugly.

⚠️ **All test detections** so far have been on workshop oil-drums (the OLD targets, now distractors). We haven't flown close to the new red gas cylinder + yellow gas cylinder targets yet.

## Live VM state

- VM running: `D:\hackerverse\vm\Drone-Ubuntu-22.04\Drone-Ubuntu-22.04.vmx`
- VMware Tools: alive (was dead earlier, recovered)
- User: `drone`
- Disk: 98 GB, 51 GB free (47% used) — comfortable
- tmux session: `au` with windows `sim` + `ctl`
- Sim probably mid-flight or recently completed. Last test was `--pattern square` with K's best.pt at 21:11 (got 0 detections).

## Local repo state

**On main, ~3 file changes uncommitted:**
- `searchctl/controller.py` — label remap + velocity_mode state fields + VelocityBodyYawspeed import (partial wall-following integration)
- Latest pulled to VM at `/home/drone/ArtificiallyUnintelligent/searchctl/controller.py`

**Recently committed (pushed to main):**
- `c5fa970` Controller teardown fix, --pattern scan mode, thumbdrive scaffold (Wed night work)
- `6c4ac81` Merge PR #9 K's wall_following.py
- `d7c4278` Phase 7 mapping
- All branches except `main` deleted (per user request earlier this session)

## Thumbdrive status (`D:\hackerverse\thumbdrive\`)

**116 MB total, ready to copy to USB.** Contents:
- `QUICKSTART.txt` — first thing user reads
- `runbook.md` — comprehensive Thu/Fri runbook (just written)
- `README.md` — fuller docs
- `setup.sh` — install script for org VM
- `make_thumbdrive.sh` — regenerate this folder
- `ArtificiallyUnintelligent.tar.gz` (64 MB) — repo tarball (NEEDS REBUILD after wall integration)
- `best.pt` (6 MB) — K's model
- `verylousymodel.pt` (6 MB) — org's reference
- `wheels/` (41 MB) — pymavlink, onnxruntime, deps
- `_*.sh` helper scripts (clean, capture, run_sim, etc)

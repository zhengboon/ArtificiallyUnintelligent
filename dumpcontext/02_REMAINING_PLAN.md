# REMAINING PLAN — what to do (in order)

**Deadline**: team call ~23:30 SGT tonight, qualifier 14:00 Fri.

## Block A — Finish wall-following integration (~20-30 min)

In `searchctl/controller.py`:

1. **Edit `setpoint_pumper`** (around line 244-280) to branch on `state.velocity_mode`:
   ```python
   if state.velocity_mode:
       await drone.drone.offboard.set_velocity_body(
           VelocityBodyYawspeed(
               state.vel_fwd, state.vel_right, state.vel_down, state.yaw_rate_deg
           )
       )
   else:
       await drone.drone.offboard.set_position_ned(
           PositionNedYaw(state.target_north, state.target_east,
                          state.target_down, state.target_yaw)
       )
   ```
   Note: MAVSDK may need a `begin_offboard` prime with the matching setpoint type. Currently it's primed with PositionNedYaw. For wall mode, may need to prime with VelocityBodyYawspeed BEFORE starting offboard, then switching is fine.

2. **Add `_depth_to_points_3d(depth, K)` helper** (after `_local_to_ned_global`):
   ```python
   def _depth_to_points_3d(depth, K, stride=2, np_mod=None):
       """Convert HxW depth image → Nx3 point cloud in camera frame.
        x=right, y=down, z=forward."""
       if np_mod is None:
           import numpy as np_mod
       d = depth[::stride, ::stride]
       h, w = d.shape
       fx, fy = K[0,0], K[1,1]
       cx, cy = K[0,2]/stride, K[1,2]/stride
       i, j = np_mod.meshgrid(np_mod.arange(w), np_mod.arange(h))
       z = d.astype(np_mod.float32)
       x = (i - cx) * z / fx
       y = (j - cy) * z / fy
       mask = z > 0.05  # filter invalid
       return np_mod.stack((x[mask], y[mask], z[mask]), axis=-1)
   ```

3. **Add `async planner_wall(state, map_handle)`** (after existing `planner()`):
   ```python
   async def planner_wall(state, map_handle):
       """K's wall-following: read depth → wall distances → velocity cmd."""
       from wall_following import WallFollower, get_wall_distances, VelocitySmoother
       if map_handle is None:
           log.error("planner_wall needs the mapping pipeline (--no-map disables it)")
           return
       follower = WallFollower()
       smoother = VelocitySmoother()
       np = map_handle["np"]
       K = map_handle["K"]
       state.velocity_mode = True
       log.info("planner_wall: starting wall-follow loop (~10 Hz)")
       run_until = time.monotonic() + 480.0  # cap at 8 min so we always land
       while time.monotonic() < run_until and not state.abort_requested:
           with map_handle["latest_lock"]:
               depth = map_handle["latest"]["depth"]
           if depth is None:
               await asyncio.sleep(0.1)
               continue
           pts = _depth_to_points_3d(depth, K, np_mod=np)
           regions = get_wall_distances(pts)
           vx, vy, vz, yaw_rate = follower.compute(regions)
           # smooth
           smoothed = smoother.smooth((vx, vy, vz, yaw_rate))
           state.vel_fwd = float(smoothed[0])
           state.vel_right = float(smoothed[1])
           state.vel_down = float(smoothed[2])
           state.yaw_rate_deg = float(smoothed[3]) * 180.0 / math.pi
           state.last_planner_progress = time.monotonic()
           await asyncio.sleep(0.1)
       # zero out before exit
       state.vel_fwd = state.vel_right = state.vel_down = state.yaw_rate_deg = 0.0
       state.velocity_mode = False
       log.info("planner_wall: exiting")
   ```

4. **Add `"wall"` to `--pattern` choices** in argparse.

5. **In `run()`**, dispatch on pattern:
   ```python
   if args.pattern == "wall":
       await planner_wall(state, map_handle)
   else:
       await planner(state)  # existing
   ```
   But — args isn't accessible inside run(). Need to pass pattern through. Simplest: add `pattern_name: str = "square"` parameter to `run()`, set in `main()`.

6. **Prime offboard appropriately** — if pattern is wall, prime with VelocityBodyYawspeed(0,0,0,0) instead of PositionNedYaw. Modify `begin_offboard` or add a branch in run() before calling it.

## Block B — Deploy + test (~15 min)

1. Push `controller.py` to VM:
   `vmrun copyFileFromHostToGuest controller.py /home/drone/ArtificiallyUnintelligent/searchctl/`
2. Also push `wall_following.py` (it's K's PR, already on main)
3. Kill any running controller, restart sim if needed
4. Run: `python3 controller.py --pattern wall`
5. Watch tmux ctl for wall-follow logs + detection logs
6. If it works: great. If it stalls/crashes: fall back to `--pattern scan`, document failure.

## Block C — Commit + push (~5 min)

```bash
cd /d/hackerverse
git add searchctl/controller.py
git commit -m "Wall-following integration as --pattern wall (K's algorithm)"
git push origin main
```

## Block D — Rebuild thumbdrive (~3 min)

```bash
cd /d/hackerverse
tar --exclude=... -czf thumbdrive/ArtificiallyUnintelligent.tar.gz .
cp models/best.pt thumbdrive/best.pt
```

## Block E — Final verification + checklist (~5 min)

- `ls -lh thumbdrive/` confirm everything present
- Reread runbook.md, sanity check
- Update progress.md with tonight's results (optional)

## Block F — Skip if running short on time

- Dead code cleanup in `codes/Codes/`
- Doc date refresh in `tasks.md` / `progress.md`
- info_*/ folder cleanup

# D430 / D450 no-RGB risk — mapping drone

> **SUPERSEDED 2026-06-10:** cameras CONFIRMED as **D435 + D450** (mixed, shared fleet). **There is no
> D430.** The **D435 has RGB** so the colour path works UNMODIFIED; only the **D450** (no RGB) needs the IR
> fallback in this doc. Filename kept as `D430_RGB_RISK.md` so existing links don't break — the content is
> the D435/D450 fleet.

## Summary

Org confirmed on 2026-06-08 12:18 (BH2026ROBOVERSE Discord, reply to
ROBO05_KyrosChenJunyu / Mili 2026-06-07 8:53pm) that the mapping drone
carries an Intel RealSense **D435** (has RGB) or **D450** (no RGB) module — a mixed/shared
fleet (user-confirmed 2026-06-10; the earlier 2026-06-08 "D430 or D450, both depth-only"
reply is superseded — there is no D430). The **D450** is the depth-only stereo-IR + projector
module with **no RGB sensor**; the **D435 has RGB** and runs the colour path unmodified.

Our current pipeline at `mapping_drone/mapping.py::ArucoDetector` reads
from `frame.color_bgr` and runs `cv2.cvtColor(..., COLOR_BGR2GRAY)` on it.
`mapping_drone/realsense.py::RealsenseNode` enables both `rs.stream.depth`
and `rs.stream.color`. On a D435 (which has RGB) this works. On a D430 /
D450 the colour stream simply will not exist — `pipeline.start()` will
raise on every profile in `PROFILE_CANDIDATES` because each one calls
`cfg.enable_stream(rs.stream.color, ...)`.

If org's drone integration did not bolt a separate RGB camera onto the
D430 / D450 module, we have **zero ArUco detection** on the real drone
unless we patch this before takeoff.

## Severity

P0 for Challenge 1. ArUco detection is the entire deliverable — no
markers means no `landing_pads.json`, which is the main judge-readable
output.

The no-RGB case is now a CONFIRMED-real branch, not a hypothetical: if your assigned
drone carries the **D450**, the colour pipeline raises and you get zero ArUco until the IR
patch below is applied. (A **D435** needs no patch.) Drones are shared, so re-check the
camera model after every handoff.

## Decision: TODO, not implemented

Implementing `--use-ir-for-aruco` blind, with no hardware to test on,
risks shipping a path that looks right but doesn't actually negotiate
the IR profile or toggle the emitter the way librealsense expects.
We're flagging it as a documented TODO with a patch sketch instead, so
the Day-1 morning fix is mechanical (no design left to do under
pressure).

Estimated patch time on the bench with a real D430/D450 in hand:
**1-2 hours** including a 5-minute confirmation that ArUco detection
actually works on the IR-as-grayscale stream.

## Patch sketch

### Step 1 — `mapping_drone/realsense.py`

Add an opt-in IR mode to `RealsenseNode`.

```python
class RealsenseNode:
    def __init__(self, use_ir_for_aruco: bool = False) -> None:
        ...
        self._use_ir = bool(use_ir_for_aruco)
        self._depth_sensor = None  # set in start() so we can toggle emitter

    def _build_config(self, width, height, fps):
        cfg = rs.config()
        cfg.enable_stream(rs.stream.depth, width, height, rs.format.z16, fps)
        if self._use_ir:
            # IR_LEFT (index 1). Y8 = 8-bit grayscale, native to the stereo cam.
            # No RGB stream — the D430/D450 doesn't have one.
            cfg.enable_stream(rs.stream.infrared, 1, width, height, rs.format.y8, fps)
        else:
            cfg.enable_stream(rs.stream.color, width, height, rs.format.bgr8, fps)
        return cfg

    def start(self) -> None:
        ...
        # After successful pipeline.start():
        if self._use_ir:
            # Align IR to depth instead of color (color stream doesn't exist).
            self._align = rs.align(rs.stream.infrared)
            ir_stream = self._profile.get_stream(rs.stream.infrared, 1)
            self._intrinsics = ir_stream.as_video_stream_profile().get_intrinsics()
            # Grab the depth sensor so we can toggle the IR projector emitter.
            # With emitter ON: depth is clean, but the projector dot pattern is
            # all over the IR image -> ArUco detection degrades sharply.
            # With emitter OFF: IR image is a clean greyscale -> ArUco works,
            # but depth quality drops on textureless surfaces.
            self._depth_sensor = self._profile.get_device().first_depth_sensor()
        else:
            self._align = rs.align(rs.stream.color)
            ...

    def grab(self) -> RealsenseFrame | None:
        ...
        if self._use_ir:
            # Strategy A (simplest): emitter OFF for every grab. Depth quality
            #   suffers on plain floors but ArUco is clean. Acceptable if the
            #   arena has texture (carpet, tape lines).
            # Strategy B (alternating): toggle emitter off, grab, toggle back on
            #   next iteration. Halves both depth-FPS and ArUco-FPS. Use only if
            #   Strategy A's depth is unusable.
            # Recommend Strategy A for the patch — re-evaluate on bench if depth
            # holes appear.
            try:
                self._depth_sensor.set_option(rs.option.emitter_enabled, 0.0)
            except Exception as exc:
                log.warning("emitter off failed: %s", exc)
            frames = self._pipeline.wait_for_frames(timeout_ms=2000)
            aligned = self._align.process(frames)
            ir_frame = aligned.get_infrared_frame(1)
            depth_frame = aligned.get_depth_frame()
            if not ir_frame or not depth_frame:
                return None
            ir = np.asanyarray(ir_frame.get_data())  # (H, W) uint8
            # Promote IR grayscale to a 3-channel BGR so downstream ArucoDetector
            # (which does cv2.cvtColor(color_bgr, COLOR_BGR2GRAY)) still works
            # WITHOUT any change to mapping.py. The cvtColor on a triplicated
            # grayscale image is a no-op that returns the same single-channel
            # data — slightly wasteful but keeps the fix surgical.
            color_bgr_synth = cv2.cvtColor(ir, cv2.COLOR_GRAY2BGR)
            depth = np.asanyarray(depth_frame.get_data())
            return RealsenseFrame(
                color_bgr=color_bgr_synth,
                depth_mm=depth.astype(np.uint16, copy=False),
                intrinsics=self._intrinsics,
                timestamp=time.monotonic(),
                width=self.WIDTH,
                height=self.HEIGHT,
            )
        # else: original color path, unchanged.
        ...
```

### Step 2 — `mapping_drone/controller.py`

Add the CLI flag and thread it through.

```python
# In _parse_args():
p.add_argument(
    "--use-ir-for-aruco",
    action="store_true",
    help="D430/D450 fallback: stream IR instead of color (no RGB sensor on "
         "those modules). Synthesises a grey BGR image from IR_LEFT so "
         "ArucoDetector still works. Disables the IR projector emitter for "
         "every frame so the dot pattern doesn't degrade marker detection; "
         "depth quality may drop on textureless surfaces. Mock path ignores "
         "this flag.",
)

# In _build_realsense():
def _build_realsense(args: argparse.Namespace) -> RealsenseAdapter:
    if args.mock_realsense or args.mock_all:
        return MockRealsenseNode()
    return RealsenseNode(use_ir_for_aruco=getattr(args, "use_ir_for_aruco", False))
```

### Step 3 — no change needed to `mapping_drone/mapping.py`

`ArucoDetector.detect_in_frame` consumes `frame.color_bgr` and does its
own `cv2.cvtColor(..., COLOR_BGR2GRAY)`. By having the IR path synthesise
a 3-channel BGR from IR_LEFT, the detector keeps working without any
edit. Same goes for `OccupancyGrid.integrate` which only touches
`frame.depth_mm` and `frame.intrinsics`.

The intrinsics field gets the IR_LEFT intrinsics instead of color
intrinsics — those are the right ones for deprojecting IR-pixel
coordinates anyway.

## Day-1 morning checklist (if drone confirmed no-RGB)

1. SSH to drone, `cd ~/semifinal`.
2. Apply the three-block patch above.
3. `python -m mapping_drone.controller --real --use-ir-for-aruco --dry-run`
   to confirm pipeline.start() succeeds with the IR profile.
4. Print one ArUco marker, point camera at it, run a quick grab + detect
   smoke test (one-off Python script — don't waste time on a full mission).
5. If detection works: commit, ready for arena.
6. If detection fails because the emitter projector pattern leaks
   through despite `set_option(rs.option.emitter_enabled, 0.0)`, switch
   to Strategy B (alternating-frame emitter toggle) — the depth sensor
   handle is already grabbed.

## Open question for org (already drafted in `ORG_TICKETS_DRAFT.md`)

If we can confirm with org that they bolted a separate RGB camera onto
the D430 / D450 module, this entire risk evaporates and we delete this
file. As of 2026-06-09 no such confirmation exists.

ROBO05_Daniel's still-open question (2026-06-07 8:04pm) about camera
"resolution and FOV" is related but doesn't disambiguate — answer would
likely give us colour-stream resolution if one exists, or IR-stereo
resolution if not. Worth chasing today.

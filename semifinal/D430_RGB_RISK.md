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

Our pipeline at `mapping_drone/mapping.py::ArucoDetector` reads from
`frame.color_bgr` and runs `cv2.cvtColor(..., COLOR_BGR2GRAY)` on it. On a
D435 (which has RGB) the colour path in `RealsenseNode` works unmodified.
On a D450 the colour stream does not exist, so `pipeline.start()` raises on
every colour profile in `PROFILE_CANDIDATES` (each calls
`cfg.enable_stream(rs.stream.color, ...)`).

That no-RGB case is now HANDLED: `RealsenseNode` automatically retries the
profile list in IR mode when every colour profile fails, and synthesises a
BGR image from the left IR stream so ArUco and the depth/mapping path keep
working with no change to `mapping.py`. See "Decision: IMPLEMENTED" and
"How it works (as built)" below.

## Severity

P0 for Challenge 1. ArUco detection is the entire deliverable — no
markers means no `landing_pads.json`, which is the main judge-readable
output.

The no-RGB case is now a CONFIRMED-real branch, not a hypothetical: if your assigned
drone carries the **D450**, the colour pipeline raises — but `RealsenseNode` now AUTO-falls
back to IR (no flag needed), so ArUco still works. (A **D435** also works unchanged.) Drones
are shared, so re-check the camera model after every handoff and watch the start() log line
to confirm which path negotiated.

## Decision: IMPLEMENTED

The IR fallback is shipped in `mapping_drone/realsense.py::RealsenseNode`.
It runs in two ways:

* **Automatic (default, no flag).** `start()` first tries the colour
  profiles; if EVERY colour profile fails (the D450 no-RGB case), it logs
  `all COLOR profiles failed — AUTO-falling back to IR (no-RGB camera?)`
  and retries the same profile list in IR mode. So the same command works
  on a D435 (RGB) and a D450 (no RGB) with no operator action.
* **Manual.** `--use-ir-for-aruco` forces IR mode directly (skips the
  colour attempt), wired via `RealsenseNode(use_ir_for_aruco=...)`.

The mock path ignores the flag. No bench-time patching is required.

## How it works (as built)

### `mapping_drone/realsense.py`

`RealsenseNode.__init__(use_ir_for_aruco: bool = False)` stores `_use_ir`
and pre-builds the alignment target. `_build_config()` enables
`rs.stream.depth` plus either `rs.stream.color` (BGR8) or, in IR mode,
`rs.stream.infrared` index 1 (Y8 — left IR, native grayscale; the D450
has no RGB stream).

`start()` iterates modes `[False, True]` (or just `[True]` when IR was
requested) and, within each, the `PROFILE_CANDIDATES` list. On the first
profile that negotiates it captures the right intrinsics (IR_LEFT
intrinsics in IR mode), and **in IR mode disables the projector emitter**
(`set_option(rs.option.emitter_enabled, 0.0)`, guarded by a `supports()`
check) so the dot pattern doesn't corrupt ArUco. This is the
emitter-off-for-every-grab strategy (clean ArUco; depth may suffer on
textureless surfaces — acceptable if the arena has texture).

`grab()` pulls `infrared_frame(1)` + depth in IR mode and synthesises a
3-channel BGR via `cv2.cvtColor(ir, cv2.COLOR_GRAY2BGR)`, so
`RealsenseFrame.color_bgr` is populated the same way as the colour path.

### `mapping_drone/moveit_mission.py` (the entry point)

The CLI flag lives in the real entry point — `python3 -m mapping_drone`
runs `moveit_mission`; `controller.py` is RETIRED (legacy, not an entry
point). `moveit_mission.py` adds `--use-ir-for-aruco` (argparse) and
constructs `RealsenseNode(use_ir_for_aruco=args.use_ir_for_aruco)`.

### `mapping_drone/mapping.py` — no change needed

`ArucoDetector.detect_in_frame` consumes `frame.color_bgr` and does its
own `cv2.cvtColor(..., COLOR_BGR2GRAY)`. Because the IR path synthesises a
3-channel BGR from IR_LEFT, the detector keeps working without any edit.
Same goes for the depth/mapping integration, which only touches
`frame.depth_mm` and `frame.intrinsics`. The intrinsics field gets the
IR_LEFT intrinsics in IR mode — the right ones for deprojecting IR-pixel
coordinates anyway.

## Day-1 morning checklist (any camera — no patch to apply)

No code change is required; the fallback is shipped. Follow the runbook in
**OP_DOC.md** (Step 1 sensors -> Step 2 check -> Step 4 nofly). The
camera-specific confirmations are:

1. Run a `--nofly` pass and watch the `Realsense started: ... (color|IR/no-RGB)`
   log line to confirm which path negotiated. On a D450 it should report
   `IR/no-RGB` (auto-fallback); on a D435, `color`. Force IR with
   `--use-ir-for-aruco` if you want to test the IR path on a D435.
2. Point the camera at a real DICT_7X7_1000 marker and confirm a detection
   logs (`detect_in_frame` reports id/center/bbox and the matched dict).
3. If IR detection is poor because the projector pattern leaks through
   despite the emitter being disabled, the alternating-frame emitter toggle
   is the documented next option (the depth sensor handle is already grabbed
   in `start()` — would need a small `grab()` change).

## Open question for org (already drafted in `ORG_TICKETS_DRAFT.md`)

The IR fallback already de-risks the no-RGB case regardless of org's
answer. Confirming whether org bolted a separate RGB camera onto the D450
would just let us prefer the colour path on those units — nice-to-know, no
longer blocking. As of 2026-06-09 no such confirmation exists.

ROBO05_Daniel's still-open question (2026-06-07 8:04pm) about camera
"resolution and FOV" is related but doesn't disambiguate — answer would
likely give us colour-stream resolution if one exists, or IR-stereo
resolution if not. Worth chasing today.

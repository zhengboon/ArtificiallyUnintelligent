"""Smoke test: stationary Realsense depth-quality sanity check.

Opens the REAL pyrealsense2-backed RealsenseNode (D435/D430/D450). For each of
4 target ranges (0.5, 1.0, 2.0, 3.0 m) the operator points the camera at a
flat surface at that distance; the script grabs 30 frames and reports the
fraction of pixels whose depth value is 0 (i.e. invalid / no return).

This is a STANDALONE test — pure operator interaction, no controller, no
flight. The user runs it once when a D435 is plugged in to confirm the camera
profile actually returns plausible depth at the working ranges.

Run via:
    python -m mapping_drone.tests.smoke_realsense_stationary

If pyrealsense2 is not installed OR a device cannot be opened, the script
prints a WARN and exits 0 (skipped — not a failure of the rest of the
pipeline). Otherwise:

PASS criteria printed per range:
    [INFO] range=0.5m depth_zero_rate=NN.NN%
    ...
    [PASS] all four ranges sampled

There is no hard threshold — the operator is expected to read the numbers and
decide whether the camera is healthy for the day's flight.

Exit code: 0 (skip or pass), 1 only if a frame grab failed unexpectedly.
"""

from __future__ import annotations

import logging
import sys
import time

import numpy as np


_TARGET_RANGES_M = (0.5, 1.0, 2.0, 3.0)
_FRAMES_PER_RANGE = 30


def _prompt(message: str) -> None:
    """Block on stdin so the operator can position the camera.

    Falls back to a polite warn if stdin is not a TTY (e.g. piped invocation)
    — in that case the user still gets the numbers but can't pause between
    ranges.
    """
    print(message)
    try:
        if sys.stdin.isatty():
            input("    press ENTER when ready ... ")
        else:
            print("    (stdin not a TTY — auto-continuing after 3s)")
            time.sleep(3.0)
    except Exception:
        time.sleep(3.0)


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    # Import lazily so the test still loads on a laptop without librealsense.
    try:
        from mapping_drone.realsense import RealsenseNode
    except Exception as exc:
        print(f"[WARN] cannot import RealsenseNode: {exc!r} — skipping")
        return 0

    try:
        node = RealsenseNode()
    except RuntimeError as exc:
        print(f"[WARN] {exc} — skipping (no librealsense)")
        return 0
    except Exception as exc:
        print(f"[WARN] RealsenseNode construction failed: {exc!r} — skipping")
        return 0

    try:
        node.start()
    except Exception as exc:
        print(f"[WARN] RealsenseNode.start() failed: {exc!r} — is a D435 connected? — skipping")
        return 0

    print()
    print("=" * 60)
    print(" REALSENSE STATIONARY DEPTH SANITY CHECK")
    print("=" * 60)
    print(" Point the camera at a flat, textured surface (wall, floor)")
    print(" at each requested distance. Hold steady while frames are sampled.")
    print()

    any_failed_grabs = False
    results: list[tuple[float, float, int, int]] = []  # (range, zero_rate, total_px, total_frames)

    try:
        for r in _TARGET_RANGES_M:
            _prompt(f"[STEP] Aim camera at a surface roughly {r:.1f} m away.")
            zero_px = 0
            total_px = 0
            ok_frames = 0
            for _ in range(_FRAMES_PER_RANGE):
                frame = node.grab()
                if frame is None:
                    any_failed_grabs = True
                    time.sleep(0.05)
                    continue
                depth = np.asarray(frame.depth_mm)
                zero_px += int(np.count_nonzero(depth == 0))
                total_px += int(depth.size)
                ok_frames += 1
            if total_px == 0:
                print(f"[WARN] range={r:.1f}m: 0 frames captured (all grabs failed)")
                results.append((r, float("nan"), 0, 0))
                continue
            rate = 100.0 * zero_px / total_px
            results.append((r, rate, total_px, ok_frames))
            print(
                f"[INFO] range={r:.1f}m depth_zero_rate={rate:6.2f}% "
                f"({zero_px:>9d} / {total_px:>9d} px over {ok_frames}/{_FRAMES_PER_RANGE} frames)"
            )
    finally:
        try:
            node.stop()
        except Exception:
            pass

    print()
    print("-- SUMMARY --")
    for r, rate, total_px, frames in results:
        if total_px == 0:
            print(f"  range={r:.1f}m  -- no frames captured --")
        else:
            print(f"  range={r:.1f}m  depth_zero_rate={rate:6.2f}%  frames_ok={frames}/{_FRAMES_PER_RANGE}")
    print()

    if any_failed_grabs:
        print("[WARN] some frame grabs returned None — check USB cable / camera health")
    if all(r[3] > 0 for r in results):
        print("[PASS] all four ranges sampled")
        return 0
    print("[FAIL] at least one range yielded zero frames")
    return 1


if __name__ == "__main__":
    sys.exit(main())

"""Smoke test: stationary Realsense depth-quality sanity check.

Opens the REAL pyrealsense2-backed RealsenseNode (D435/D430/D450). Two modes:

INTERACTIVE (default):
    For each of 4 target ranges (0.5, 1.0, 2.0, 3.0 m) the operator points the
    camera at a flat surface at that distance; the script grabs 30 frames per
    range and reports the fraction of pixels whose depth value is 0
    (i.e. invalid / no return).

AUTO (--auto):
    Skip the interactive prompts. Grab N frames (default 30, see --frames) at
    whatever the camera is currently looking at and report depth quality:
        - total frames captured
        - depth=0 fraction at centre (10% box around image centre)
        - depth=0 fraction across full frame
        - median depth (mm) of valid pixels
        - depth range (min / max, mm) of valid pixels
    Useful in setup scripts / CI-style pre-flight where there's no operator
    to press ENTER.

This is a STANDALONE test — pure depth sanity, no controller, no flight.

Run via:
    python -m mapping_drone.tests.smoke_realsense_stationary
    python -m mapping_drone.tests.smoke_realsense_stationary --auto
    python -m mapping_drone.tests.smoke_realsense_stationary --auto --frames 10

If pyrealsense2 is not installed OR a device cannot be opened, the script
prints a WARN and exits 0 in interactive mode (skipped — not a failure of
the rest of the pipeline). In --auto mode the exit code is 1 when zero
frames are captured, because the caller is asking a yes/no question.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

import numpy as np


_TARGET_RANGES_M = (0.5, 1.0, 2.0, 3.0)
_FRAMES_PER_RANGE = 30
_AUTO_DEFAULT_FRAMES = 30


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


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="smoke_realsense_stationary",
        description="Realsense stationary depth-quality sanity check.",
    )
    p.add_argument(
        "--auto",
        action="store_true",
        help="Skip interactive prompts; capture N frames at current camera "
             "position and report depth stats.",
    )
    p.add_argument(
        "--frames",
        type=int,
        default=_AUTO_DEFAULT_FRAMES,
        help=f"Frames to capture in --auto mode (default: {_AUTO_DEFAULT_FRAMES}).",
    )
    return p.parse_args(argv)


def _open_node(skip_exit_code: int):
    """Try to import + construct + start a RealsenseNode.

    Returns the started node on success, or an int exit code to return when
    the device/library isn't usable. skip_exit_code lets the caller pick
    0 (interactive — skip is fine) or 1 (auto — caller wants a hard answer).
    """
    try:
        from mapping_drone.realsense import RealsenseNode
    except Exception as exc:
        print(f"[WARN] cannot import RealsenseNode: {exc!r} — skipping")
        return skip_exit_code

    try:
        node = RealsenseNode()
    except RuntimeError as exc:
        print(f"[WARN] {exc} — skipping (no librealsense)")
        return skip_exit_code
    except Exception as exc:
        print(f"[WARN] RealsenseNode construction failed: {exc!r} — skipping")
        return skip_exit_code

    try:
        node.start()
    except Exception as exc:
        print(f"[WARN] RealsenseNode.start() failed: {exc!r} — is a D435 connected? — skipping")
        return skip_exit_code

    return node


def _run_auto(node, frames_target: int) -> int:
    """Capture frames_target frames at the current camera pose and report stats."""
    print()
    print("=" * 60)
    print(" REALSENSE AUTO DEPTH SANITY CHECK")
    print("=" * 60)
    print(f" Capturing {frames_target} frames at current camera position ...")
    print()

    zero_full = 0
    total_full = 0
    zero_center = 0
    total_center = 0
    ok_frames = 0
    failed_grabs = 0
    valid_depths: list[np.ndarray] = []

    try:
        for _ in range(frames_target):
            frame = node.grab()
            if frame is None:
                failed_grabs += 1
                time.sleep(0.05)
                continue
            depth = np.asarray(frame.depth_mm)
            h, w = depth.shape[:2]
            # 10% box at image centre — same fraction in u and v
            cw = max(1, w // 10)
            ch = max(1, h // 10)
            x0 = (w - cw) // 2
            y0 = (h - ch) // 2
            center = depth[y0:y0 + ch, x0:x0 + cw]

            zero_full += int(np.count_nonzero(depth == 0))
            total_full += int(depth.size)
            zero_center += int(np.count_nonzero(center == 0))
            total_center += int(center.size)

            valid = depth[depth > 0]
            if valid.size > 0:
                valid_depths.append(valid)
            ok_frames += 1
    finally:
        try:
            node.stop()
        except Exception:
            pass

    print("-- SUMMARY --")
    print(f"  frames_captured = {ok_frames}/{frames_target}  (failed grabs: {failed_grabs})")

    if ok_frames == 0 or total_full == 0:
        print("  depth_zero_full   = n/a")
        print("  depth_zero_center = n/a")
        print("  depth_median_mm   = n/a")
        print("  depth_range_mm    = n/a")
        print("[FAIL] zero frames captured — check USB cable / camera health")
        return 1

    full_rate = 100.0 * zero_full / total_full
    center_rate = 100.0 * zero_center / total_center if total_center > 0 else float("nan")
    print(f"  depth_zero_full   = {full_rate:6.2f}%  ({zero_full} / {total_full} px)")
    print(f"  depth_zero_center = {center_rate:6.2f}%  ({zero_center} / {total_center} px)")

    if valid_depths:
        flat = np.concatenate(valid_depths)
        median_mm = float(np.median(flat))
        min_mm = int(flat.min())
        max_mm = int(flat.max())
        print(f"  depth_median_mm   = {median_mm:.0f}")
        print(f"  depth_range_mm    = [{min_mm}, {max_mm}]")
    else:
        print("  depth_median_mm   = n/a (no valid depth pixels)")
        print("  depth_range_mm    = n/a")

    print("[PASS] frames captured")
    return 0


def _run_interactive(node) -> int:
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


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    args = _parse_args(argv)

    if args.auto and args.frames <= 0:
        print(f"[FAIL] --frames must be > 0, got {args.frames}")
        return 1

    # In --auto mode treat "no camera" as a hard failure (caller wants a
    # yes/no answer). In interactive mode it's a skip.
    skip_code = 1 if args.auto else 0
    node_or_code = _open_node(skip_code)
    if isinstance(node_or_code, int):
        return node_or_code
    node = node_or_code

    if args.auto:
        return _run_auto(node, args.frames)
    return _run_interactive(node)


if __name__ == "__main__":
    sys.exit(main())

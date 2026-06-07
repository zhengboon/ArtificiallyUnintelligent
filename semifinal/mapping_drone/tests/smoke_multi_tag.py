"""Smoke test: multi-tag run with mixed even/odd ArUco IDs.

Subclasses MockRealsenseNode so it emits a different ArUco marker at each
waypoint, deterministically cycling through IDs 100, 101, 102, 103 (a mix of
even and odd so the default 'even' validity rule produces both VALID and
INVALID pads). With --mock-all the controller will fly the default 4-waypoint
sweep and scan once at each WP.

Run via:
    python -m mapping_drone.tests.smoke_multi_tag

PASS criteria:
    [PASS] landing_pads.json has 4 entries (ids 100..103)
    [PASS] STATUS.txt contains a VALID LANDING PADS section with at least one id
    [PASS] STATUS.txt contains an INVALID LANDING PADS section with at least one id

Exit code: 0 on PASS, 1 on FAIL.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import tempfile
from argparse import Namespace
from pathlib import Path

import cv2
import numpy as np

from mapping_drone import controller as controller_mod
from mapping_drone.realsense import MockRealsenseNode, RealsenseFrame


# IDs chosen specifically to span the default 'even' validity rule:
#   100, 102 -> even -> VALID
#   101, 103 -> odd  -> INVALID
_MULTI_TAG_IDS = [100, 101, 102, 103]


class MultiTagMockRealsense(MockRealsenseNode):
    """MockRealsense that cycles through _MULTI_TAG_IDS one ID per grab() burst.

    The controller calls grab() FRAMES_PER_WAYPOINT (=8) times per waypoint;
    rather than rely on that, we count frames and advance the emitted ID every
    FRAMES_PER_WAYPOINT calls. Each waypoint therefore sees one ID, and across
    4 waypoints we cover all 4 IDs.
    """

    FRAMES_PER_BURST = 8  # matches FRAMES_PER_WAYPOINT in controller.py

    def __init__(self, seed: int | None = 0) -> None:
        super().__init__(seed=seed)
        self._frame_idx = 0

    def grab(self) -> RealsenseFrame | None:
        frame = super().grab()
        if frame is None:
            return None
        burst = (self._frame_idx // self.FRAMES_PER_BURST) % len(_MULTI_TAG_IDS)
        marker_id = _MULTI_TAG_IDS[burst]
        self._frame_idx += 1

        # Repaint the colour image with a marker whose ID we control.
        marker_img = self._generate_marker(marker_id, self.MARKER_PX)
        canvas = np.full(
            (self.HEIGHT, self.WIDTH, 3), 80, dtype=np.uint8
        )
        x0 = (self.WIDTH - self.MARKER_PX) // 2
        y0 = (self.HEIGHT - self.MARKER_PX) // 2
        canvas[y0:y0 + self.MARKER_PX, x0:x0 + self.MARKER_PX] = cv2.cvtColor(
            marker_img, cv2.COLOR_GRAY2BGR
        )
        frame.color_bgr = canvas
        return frame


def _patch_build_realsense():
    def _build(args):
        return MultiTagMockRealsense(seed=0)
    controller_mod._build_realsense = _build  # type: ignore[assignment]


def _make_args(runs_dir: Path) -> Namespace:
    return Namespace(
        real=False,
        mock_all=True,
        mock_uwb=False,
        mock_mavsdk=False,
        mock_realsense=False,
        mavsdk_address="udp://:14540",
        waypoints=None,
        gimbal_pitch=-90.0,
        aruco_dict="6X6_250",
        max_flight_time_s=120,
        runs_dir=str(runs_dir),
        log_level="WARNING",
    )


def _find_run_dir(runs_dir: Path) -> Path | None:
    candidates = sorted(p for p in runs_dir.glob("run_*") if p.is_dir())
    return candidates[-1] if candidates else None


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    failures: list[str] = []
    passes: list[str] = []

    _patch_build_realsense()

    with tempfile.TemporaryDirectory(prefix="smoke_multi_tag_") as tmp:
        runs_dir = Path(tmp)
        args = _make_args(runs_dir)

        try:
            asyncio.run(controller_mod.run(args))
        except Exception as exc:
            print(f"[INFO] controller.run() raised at top level: {exc!r}")

        run_dir = _find_run_dir(runs_dir)
        if run_dir is None:
            print("[FAIL] no run_<ts> directory was created")
            return 1
        print(f"[INFO] run dir: {run_dir}")

        # 1) landing_pads.json: expect 4 entries, ids {100,101,102,103}
        pads_path = run_dir / "landing_pads.json"
        if not pads_path.exists():
            failures.append("landing_pads.json missing")
        else:
            try:
                payload = json.loads(pads_path.read_text(encoding="utf-8"))
            except Exception as exc:
                failures.append(f"landing_pads.json invalid JSON: {exc!r}")
            else:
                pads = payload.get("pads", []) or []
                ids = sorted({int(p.get("aruco_id")) for p in pads if p.get("aruco_id") is not None})
                if len(pads) == 4 and ids == sorted(_MULTI_TAG_IDS):
                    passes.append(f"landing_pads.json has 4 entries (ids={ids})")
                else:
                    failures.append(
                        f"landing_pads.json count={len(pads)} ids={ids} "
                        f"(expected 4 entries {_MULTI_TAG_IDS})"
                    )

        # 2) STATUS.txt has VALID + INVALID sections with content
        status_path = run_dir / "STATUS.txt"
        if not status_path.exists():
            failures.append("STATUS.txt missing")
        else:
            text = status_path.read_text(encoding="utf-8")
            valid_marker = "-- VALID LANDING PADS --"
            invalid_marker = "-- INVALID LANDING PADS --"
            if valid_marker not in text:
                failures.append("STATUS.txt missing VALID LANDING PADS section header")
            if invalid_marker not in text:
                failures.append("STATUS.txt missing INVALID LANDING PADS section header")
            if valid_marker in text and invalid_marker in text:
                v_start = text.index(valid_marker) + len(valid_marker)
                i_start = text.index(invalid_marker)
                valid_block = text[v_start:i_start]
                invalid_block = text[i_start + len(invalid_marker):]
                if "id=" in valid_block:
                    passes.append("STATUS.txt VALID section contains at least one id")
                else:
                    failures.append("STATUS.txt VALID section has no id entries")
                if "id=" in invalid_block:
                    passes.append("STATUS.txt INVALID section contains at least one id")
                else:
                    failures.append("STATUS.txt INVALID section has no id entries")

    print()
    for p in passes:
        print(f"[PASS] {p}")
    for f in failures:
        print(f"[FAIL] {f}")
    print()
    if failures:
        print("RESULT: FAIL")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Smoke test: mid-mission abort path.

Subclasses MockMavsdk so its offboard.set_velocity_ned() raises a RuntimeError
once the drone has flown past WP1 and is operating around WP2. The controller
should treat this as an unhandled mission failure, fall through to its
emergency_land() path, and still leave behind a coherent run_<ts>/ directory:

  - run_summary.json with aborted=true
  - landing_pads.json present and parseable as JSON (may be partial — any
    sightings from WP1 should still be there)

Run via:
    python -m mapping_drone.tests.smoke_abort

PASS criteria printed at end:
    [PASS] aborted=true in run_summary.json
    [PASS] landing_pads.json parses cleanly
    [PASS] no orphan .tmp files in run dir

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

from mapping_drone.controller import (
    DEFAULT_WAYPOINTS,
    MockMavsdk,
    _MockOffboard,
    _MockVelocityNedYaw,
    run,
)
from mapping_drone import controller as controller_mod


class _AbortAtWp2Offboard(_MockOffboard):
    """Offboard impl that raises once the drone is approaching/in WP2.

    WP2 is (2.0, 0.0, 1.5) in the default waypoint list. As soon as the mock
    east_m position exceeds 1.5 m we raise — this fires mid-flight on the leg
    from WP1 to WP2, ensuring at least the WP1 scan has already populated a
    landing_pads.json entry.
    """

    async def set_velocity_ned(self, vel) -> None:  # type: ignore[override]
        await super().set_velocity_ned(vel)
        if self._d._pos.east_m > 1.5:
            raise RuntimeError("smoke_abort: synthetic failure at WP2")


class AbortingMockMavsdk(MockMavsdk):
    """MockMavsdk variant that swaps in the failing offboard."""

    def __init__(self) -> None:
        super().__init__()
        self.offboard = _AbortAtWp2Offboard(self)


def _patch_build_drone():
    """Replace _build_drone so the controller uses AbortingMockMavsdk."""
    async def _build_aborting(args):
        drone = AbortingMockMavsdk()
        await drone.connect(args.mavsdk_address)
        return drone, _MockVelocityNedYaw

    controller_mod._build_drone = _build_aborting  # type: ignore[assignment]


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
        max_flight_time_s=60,
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

    _patch_build_drone()

    with tempfile.TemporaryDirectory(prefix="smoke_abort_") as tmp:
        runs_dir = Path(tmp)
        args = _make_args(runs_dir)

        # Use the default waypoint list (4 WPs); we abort during the 2nd leg.
        # No --waypoints override needed — DEFAULT_WAYPOINTS is fine.
        _ = DEFAULT_WAYPOINTS

        try:
            asyncio.run(run(args))
        except Exception as exc:
            print(f"[INFO] controller.run() raised at top level: {exc!r}")

        run_dir = _find_run_dir(runs_dir)
        if run_dir is None:
            print("[FAIL] no run_<ts> directory was created")
            return 1
        print(f"[INFO] run dir: {run_dir}")

        # 1) run_summary.json with aborted=true
        summary_path = run_dir / "run_summary.json"
        if not summary_path.exists():
            failures.append("run_summary.json missing")
        else:
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
            except Exception as exc:
                failures.append(f"run_summary.json invalid JSON: {exc!r}")
            else:
                if summary.get("aborted") is True:
                    passes.append("aborted=true in run_summary.json")
                else:
                    failures.append(
                        f"run_summary.json aborted={summary.get('aborted')!r} (expected True)"
                    )

        # 2) landing_pads.json present and parseable
        pads_path = run_dir / "landing_pads.json"
        if not pads_path.exists():
            failures.append("landing_pads.json missing")
        else:
            try:
                pads = json.loads(pads_path.read_text(encoding="utf-8"))
            except Exception as exc:
                failures.append(f"landing_pads.json invalid JSON: {exc!r}")
            else:
                passes.append(
                    f"landing_pads.json parses cleanly (pads count={pads.get('count')})"
                )

        # 3) no orphan .tmp files
        orphans = list(run_dir.rglob("*.tmp"))
        if orphans:
            failures.append(f"orphan tmp files found: {[str(p) for p in orphans]}")
        else:
            passes.append("no orphan .tmp files in run dir")

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

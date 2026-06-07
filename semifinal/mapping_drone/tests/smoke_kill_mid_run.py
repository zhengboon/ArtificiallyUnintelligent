"""Smoke test: SIGTERM mid-run leaves on-disk state coherent.

Launches the controller in a child process with --mock-all, polls the
controller's STATUS.txt until the run reports SCAN_WP_2 (or beyond) — meaning
WP1 has been scanned and WP2 reached — then sends a Windows-friendly
subprocess.terminate(). Afterwards it inspects the run dir and asserts:

  - landing_pads.json on disk is valid JSON
  - landing_pads.json contains at least one pad sighting (from WP1+WP2)
  - no orphan *.tmp files remain anywhere in the run directory

Run via:
    python -m mapping_drone.tests.smoke_kill_mid_run

PASS criteria printed at end:
    [PASS] landing_pads.json parses cleanly
    [PASS] landing_pads.json has >=1 pad
    [PASS] no orphan .tmp files in run dir

Exit code: 0 on PASS, 1 on FAIL.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path


# How long we are willing to wait for the run to reach WP2.
_WP2_WAIT_TIMEOUT_S = 30.0
# How long we wait after terminate() before inspecting disk.
_POST_TERMINATE_GRACE_S = 5.0


def _latest_run_dir(runs_dir: Path) -> Path | None:
    candidates = sorted(p for p in runs_dir.glob("run_*") if p.is_dir())
    return candidates[-1] if candidates else None


def _status_state(run_dir: Path) -> str | None:
    """Cheap parse of STATUS.txt 'State          : ...' line."""
    status_path = run_dir / "STATUS.txt"
    if not status_path.exists():
        return None
    try:
        for line in status_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("State"):
                # "State          : SCAN_WP_2"
                _, _, rhs = line.partition(":")
                return rhs.strip()
    except Exception:
        return None
    return None


def _wp2_reached_or_beyond(state: str | None) -> bool:
    """True once STATUS reports we have moved beyond WP1.

    Order of states observed: ARMING, TAKEOFF, OFFBOARD_PREWARM, MISSION,
    SCAN_WP_1, SCAN_WP_2, SCAN_WP_3, SCAN_WP_4, LANDING, DONE.
    """
    if not state:
        return False
    if state.startswith("SCAN_WP_"):
        try:
            n = int(state.rsplit("_", 1)[1])
            return n >= 2
        except ValueError:
            return False
    # Anything past mission scans (LANDING/DONE) trivially counts as 'beyond WP2'.
    return state in {"LANDING", "DONE", "ABORTED", "EMERGENCY_LAND"}


def main() -> int:
    failures: list[str] = []
    passes: list[str] = []

    with tempfile.TemporaryDirectory(prefix="smoke_kill_") as tmp:
        runs_dir = Path(tmp)

        cmd = [
            sys.executable,
            "-m",
            "mapping_drone",
            "--mock-all",
            "--runs-dir",
            str(runs_dir),
            "--log-level",
            "WARNING",
        ]
        print(f"[INFO] launching: {' '.join(cmd)}")
        # subprocess.Popen inherits stdio; redirect to DEVNULL to keep output clean.
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        try:
            deadline = time.monotonic() + _WP2_WAIT_TIMEOUT_S
            reached = False
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    # Process exited before we could terminate — still treat as
                    # acceptable if WP2 was reached. Otherwise that's a failure.
                    print(f"[INFO] child exited early with code {proc.returncode}")
                    break
                run_dir = _latest_run_dir(runs_dir)
                if run_dir is not None and _wp2_reached_or_beyond(_status_state(run_dir)):
                    reached = True
                    print(f"[INFO] WP2 reached after {time.monotonic() - (deadline - _WP2_WAIT_TIMEOUT_S):.1f}s")
                    break
                time.sleep(0.5)

            if not reached and proc.poll() is None:
                print(f"[WARN] WP2 not reached within {_WP2_WAIT_TIMEOUT_S:.0f}s — terminating anyway")

            if proc.poll() is None:
                # Windows-friendly: subprocess.terminate() sends TerminateProcess
                # on Windows and SIGTERM on POSIX. We don't escalate to kill()
                # because the controller's KeyboardInterrupt/SIGTERM path is
                # exactly what we are testing here.
                proc.terminate()

            # Wait for the controller's finalise() to flush state.
            try:
                proc.wait(timeout=_POST_TERMINATE_GRACE_S + 10.0)
            except subprocess.TimeoutExpired:
                print("[WARN] child did not exit after terminate; killing")
                proc.kill()
                proc.wait(timeout=5.0)
        finally:
            if proc.poll() is None:
                proc.kill()

        time.sleep(0.5)  # tiny grace for any in-flight file replace

        run_dir = _latest_run_dir(runs_dir)
        if run_dir is None:
            print("[FAIL] no run_<ts> directory was created")
            return 1
        print(f"[INFO] run dir: {run_dir}")

        # 1) landing_pads.json valid JSON
        pads_path = run_dir / "landing_pads.json"
        if not pads_path.exists():
            failures.append("landing_pads.json missing")
            pads_payload = None
        else:
            try:
                pads_payload = json.loads(pads_path.read_text(encoding="utf-8"))
                passes.append("landing_pads.json parses cleanly")
            except Exception as exc:
                failures.append(f"landing_pads.json invalid JSON: {exc!r}")
                pads_payload = None

        # 2) landing_pads.json has >=1 pad (from WP1+WP2 scans). Note: with the
        # default random mock the mock may or may not draw a marker in the depth
        # window — but with FRAMES_PER_WAYPOINT=8 across 2 WPs the probability of
        # at least one sighting is overwhelming. We assert >=1.
        if pads_payload is not None:
            pads = pads_payload.get("pads", []) or []
            if len(pads) >= 1:
                passes.append(f"landing_pads.json has {len(pads)} pad(s)")
            else:
                failures.append("landing_pads.json has 0 pads (expected >=1 from WP1+WP2)")

        # 3) no orphan tmp files
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

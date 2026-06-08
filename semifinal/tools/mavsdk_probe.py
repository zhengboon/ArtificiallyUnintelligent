"""Day-1 diagnostic — runs before mission to confirm at least one MAVSDK
address negotiates. Faster than launching the full controller.

Walks DAY1_MAVSDK_TRY_ORDER (or an operator-supplied list) and reports one
line per address: 'OK connected' or 'FAILED: <err>'. Exits 0 if any address
succeeded, 1 if every probe failed. Safe to run on a bench laptop with no
drone attached — all probes will fail and the script exits 1, which is the
expected dev-laptop signature.

Usage:
    python tools/mavsdk_probe.py
    python tools/mavsdk_probe.py --timeout 2
    python tools/mavsdk_probe.py --addresses udp://:14540,udp://:14550
    python -m tools.mavsdk_probe --timeout 3
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Allow 'python tools/mavsdk_probe.py' from semifinal/ — make the repo root
# importable so the 'mapping_drone' package resolves without needing to
# install or set PYTHONPATH.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from mapping_drone.controller import DAY1_MAVSDK_TRY_ORDER
except Exception:
    # Fallback if the controller import chain (rclpy/realsense/etc.) is not
    # importable on this host — keep the probe usable on a stripped dev box.
    # Must stay in lock-step with the canonical list in controller.py.
    DAY1_MAVSDK_TRY_ORDER = [
        "serial:///dev/ttyS6:921600",
        "serial:///dev/ttyACM0:115200",
        "serial:///dev/ttyUSB0:57600",
        "udp://:14540",
        "udp://:14550",
    ]


async def _probe_one(addr: str, timeout_s: float) -> tuple[bool, str]:
    """Attempt a single MAVSDK connect against ``addr``.

    Returns (ok, detail). ok=True means connect() returned AND the system
    reported is_connected within the timeout. Any failure mode — missing
    mavsdk install, connect raise, is_connected timeout — collapses to
    (False, <err>) so the caller can render a uniform FAILED line.
    """
    try:
        from mavsdk import System  # local import — keeps --help fast
    except Exception as exc:
        return False, f"mavsdk import failed: {exc!r}"

    drone = System()
    try:
        await asyncio.wait_for(drone.connect(system_address=addr), timeout=timeout_s)
    except asyncio.TimeoutError:
        return False, f"connect timed out after {timeout_s:.1f}s"
    except Exception as exc:
        return False, f"connect raised: {exc!r}"

    async def _await_connected() -> None:
        async for cs in drone.core.connection_state():
            if cs.is_connected:
                return

    try:
        await asyncio.wait_for(_await_connected(), timeout=timeout_s)
    except asyncio.TimeoutError:
        return False, f"is_connected timed out after {timeout_s:.1f}s"
    except Exception as exc:
        return False, f"connection_state raised: {exc!r}"

    return True, "connected"


async def _run(addresses: list[str], timeout_s: float) -> int:
    any_ok = False
    for addr in addresses:
        print(f"PROBE addr={addr} ...", flush=True)
        ok, detail = await _probe_one(addr, timeout_s)
        if ok:
            print("  OK connected", flush=True)
            any_ok = True
        else:
            print(f"  FAILED: {detail}", flush=True)
    return 0 if any_ok else 1


def _parse_addresses(raw: str | None) -> list[str]:
    if raw is None:
        return list(DAY1_MAVSDK_TRY_ORDER)
    parts = [a.strip() for a in raw.split(",")]
    parts = [a for a in parts if a]
    if not parts:
        raise argparse.ArgumentTypeError("--addresses must contain at least one entry")
    return parts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Probe every MAVSDK address in DAY1_MAVSDK_TRY_ORDER and "
                    "report which connects. Exit 0 if any succeed, 1 if all fail.",
    )
    ap.add_argument(
        "--addresses",
        default=None,
        help="Comma-separated MAVSDK system addresses to probe in order. "
             "Defaults to DAY1_MAVSDK_TRY_ORDER from mapping_drone.controller.",
    )
    ap.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Per-address connect timeout in seconds (default: 5).",
    )
    args = ap.parse_args(argv)

    addresses = _parse_addresses(args.addresses)
    return asyncio.run(_run(addresses, args.timeout))


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Survey the flyable box BEFORE flying — NO FLIGHT, read-only.

>>> CONSTRAINT: this corner-walk mode requires CARRYING the drone to each
>>> corner. If you can only launch from the floor and may NOT touch the drone,
>>> this mode is UNUSABLE. Instead follow OP_DOC.md Step 3:
>>>   - if /uwb_tag streams cleanly: it IS the arena frame after the start_uwb
>>>     bottom-right calibration (br_n=raw_y, br_e=raw_x) — use --pose uwb and
>>>     arena-coordinate waypoints directly; OR
>>>   - run a conservative autonomous frame-probe to learn the NED<->arena
>>>     transform. (Corner-walk below is kept for the case where carrying IS
>>>     allowed.)


Why: we do NOT know how arena coords (corners (0,0),(0,11),(5.5,11),(5.5,0))
map to the drone's NED frame (which axis is North? where is the origin? is
there a yaw offset?). Guessing waypoints could fly the drone into a wall.
So we MEASURE it: carry the drone (props OFF) to each arena corner, and this
tool records the flight controller's reported NED position there. From the 4
corner correspondences it fits the arena->NED transform, prints the box (with
a sanity check that edges are ~5.5 and ~11 m), and writes a lawnmower waypoint
file IN THE NED FRAME the mission actually commands.

Pose source = MAVSDK (serial:///dev/ttyS6:921600) — the same NED frame the
mission's set_position_velocity_ned uses, and immune to ROS2/DDS cross-team
interference. The FC must have a valid local position (UWB feeding the EKF):
run start_micro + start_uwb first, props OFF.

    cd ~/AD/semifinal            # wherever the repo is
    python3 tools/survey_box.py --margin 0.7 --lanes 3 --alt 4.0 \
        --out configs/waypoints_surveyed.json

It never arms. It only reads telemetry while you physically move the drone.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from pathlib import Path

import numpy as np

try:
    from mavsdk import System
except Exception as exc:  # noqa: BLE001
    print(f"[FATAL] mavsdk not importable: {exc}")
    sys.exit(1)

# Arena corners (arena coords, metres). Order: walk them in this sequence.
ARENA_W = 5.5   # width  (the "5.5" axis)
ARENA_L = 11.0  # length (the "11" axis)
CORNERS = [
    ("A  arena (0, 0)",       (0.0,     0.0)),
    ("B  arena (0, 11)",      (0.0,     ARENA_L)),
    ("C  arena (5.5, 11)",    (ARENA_W, ARENA_L)),
    ("D  arena (5.5, 0)",     (ARENA_W, 0.0)),
]


def fit_rigid(arena_pts, ned_pts):
    """Least-squares rigid (rotation+translation) fit mapping arena->NED.
    Returns (R 2x2, t 2, residuals per point, yaw_deg)."""
    A = np.asarray(arena_pts, dtype=float)
    B = np.asarray(ned_pts, dtype=float)
    ca, cb = A.mean(0), B.mean(0)
    A0, B0 = A - ca, B - cb
    H = A0.T @ B0
    U, S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1.0, d]) @ U.T          # ned0 ≈ A0 @ R.T  (R @ a_col)
    t = cb - R @ ca
    pred = A @ R.T + t
    res = np.linalg.norm(pred - B, axis=1)
    yaw_deg = math.degrees(math.atan2(R[1, 0], R[0, 0]))
    return R, t, res, yaw_deg


def to_ned(R, t, x, y):
    p = R @ np.array([x, y], dtype=float) + t
    return float(p[0]), float(p[1])


def lawnmower_arena(margin, lanes, lane_step):
    """Serpentine lanes along the LENGTH (y, 0..11), stepped across the WIDTH
    (x, 0..5.5). Scan points spaced lane_step along each lane."""
    x0, x1 = margin, ARENA_W - margin
    y0, y1 = margin, ARENA_L - margin
    xs = np.linspace(x0, x1, max(1, lanes))
    pts = []
    for i, x in enumerate(xs):
        span = abs(y1 - y0)
        n = max(2, int(math.ceil(span / max(0.1, lane_step))) + 1)
        ys = list(np.linspace(y0, y1, n))
        if i % 2 == 1:
            ys = ys[::-1]
        for y in ys:
            pts.append((float(x), float(y)))
    return pts


async def main() -> int:
    ap = argparse.ArgumentParser(description="Survey the flyable box (no flight).")
    ap.add_argument("--mavsdk-address", default="serial:///dev/ttyS6:921600")
    ap.add_argument("--margin", type=float, default=0.7, help="wall margin (m)")
    ap.add_argument("--lanes", type=int, default=3, help="lanes across the 5.5 m width")
    ap.add_argument("--lane-step", type=float, default=1.5, help="scan-point spacing along a lane (m)")
    ap.add_argument("--alt", type=float, default=4.0, help="flight altitude written to waypoints (m, +up)")
    ap.add_argument("--out", default="configs/waypoints_surveyed.json")
    args = ap.parse_args()

    drone = System()
    print(f"[survey] connecting MAVSDK on {args.mavsdk_address} (no arm) ...")
    await drone.connect(system_address=args.mavsdk_address)
    async for st in drone.core.connection_state():
        if st.is_connected:
            print("[survey] MAVSDK connected")
            break

    latest = {"n": None, "e": None, "d": None}

    async def telem():
        async for p in drone.telemetry.position_velocity_ned():
            latest["n"] = p.position.north_m
            latest["e"] = p.position.east_m
            latest["d"] = p.position.down_m

    telem_task = asyncio.ensure_future(telem())

    print("[survey] waiting for FC position (need UWB feeding the EKF; start_micro+start_uwb up)...")
    for _ in range(150):
        if latest["n"] is not None:
            break
        await asyncio.sleep(0.2)
    if latest["n"] is None:
        print("[FATAL] no FC position in 30s. Is start_micro + start_uwb running? Is local position OK?")
        telem_task.cancel()
        return 2

    loop = asyncio.get_running_loop()
    captured = []
    print("\n*** PROPS OFF. Carry the drone to each corner; press Enter to capture. ***")
    for label, arena_xy in CORNERS:
        print(f"\n=== Place drone at corner {label}.  Live NED below — press Enter to capture (or type s+Enter to skip). ===")
        stop = {"v": False}

        async def show():
            while not stop["v"]:
                print(f"\r    NED  n={latest['n']:+.2f}  e={latest['e']:+.2f}  d={latest['d']:+.2f}    ",
                      end="", flush=True)
                await asyncio.sleep(0.2)

        show_task = asyncio.ensure_future(show())
        line = (await loop.run_in_executor(None, sys.stdin.readline)).strip().lower()
        stop["v"] = True
        await asyncio.sleep(0.05)
        if line == "s":
            print(f"\n    skipped {label}")
            continue
        n, e = latest["n"], latest["e"]
        captured.append((arena_xy, (n, e)))
        print(f"\n    captured {label}:  NED n={n:+.3f} e={e:+.3f}")

    telem_task.cancel()

    if len(captured) < 2:
        print("\n[FATAL] need at least 2 corners (ideally 4). Got", len(captured))
        return 2

    arena_pts = [c[0] for c in captured]
    ned_pts = [c[1] for c in captured]
    R, t, res, yaw_deg = fit_rigid(arena_pts, ned_pts)

    print("\n==================== SURVEY RESULT ====================")
    print(f"corners captured: {len(captured)}")
    print(f"arena->NED yaw offset: {yaw_deg:+.1f} deg   |  fit residual: "
          f"max {res.max():.3f} m, mean {res.mean():.3f} m")
    # Edge-length sanity check from the recovered transform
    cA = to_ned(R, t, 0.0, 0.0)
    cB = to_ned(R, t, 0.0, ARENA_L)
    cD = to_ned(R, t, ARENA_W, 0.0)
    len_long = math.dist(cA, cB)
    len_wide = math.dist(cA, cD)
    print(f"recovered edges: length={len_long:.2f} m (expect {ARENA_L}), width={len_wide:.2f} m (expect {ARENA_W})")
    if res.max() > 0.30:
        print("  !! WARNING: residual > 0.30 m — corners may be mismeasured. Re-survey before trusting.")
    if abs(len_long - ARENA_L) > 0.15 * ARENA_L or abs(len_wide - ARENA_W) > 0.15 * ARENA_W:
        print("  !! WARNING: recovered edges differ >15% from 5.5x11 — check corner order / positions.")
    print("box NED corners:")
    for name, (x, y) in [("(0,0)", (0, 0)), ("(0,11)", (0, ARENA_L)),
                         ("(5.5,11)", (ARENA_W, ARENA_L)), ("(5.5,0)", (ARENA_W, 0))]:
        nn, ee = to_ned(R, t, x, y)
        print(f"   arena {name:9s} -> NED n={nn:+.2f} e={ee:+.2f}")

    # Generate lawnmower (arena coords) -> NED waypoints [n, e, alt]
    arena_wps = lawnmower_arena(args.margin, args.lanes, args.lane_step)
    wps = []
    for x, y in arena_wps:
        nn, ee = to_ned(R, t, x, y)
        wps.append([round(nn, 3), round(ee, 3), float(args.alt)])

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(wps, indent=2))
    print(f"\nlawnmower: {args.lanes} lanes, {len(wps)} waypoints, margin {args.margin} m, alt {args.alt} m")
    print(f"written -> {out}")
    print("Run it (after a clean --check) with:  --waypoints-from-json", args.out)
    print("=======================================================")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n[survey] aborted")

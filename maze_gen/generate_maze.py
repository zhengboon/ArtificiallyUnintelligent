#!/usr/bin/env python3
"""
Random maze generator for the BrainHack 2026 RoboVerse Qualifier.

Outputs a Gazebo Harmonic .sdf world file (drop-in for
~/PX4-Autopilot/Tools/simulation/gz/worlds/) plus a JSON ground-truth
file and an ASCII top-down preview. Optional PNG preview if matplotlib
is importable.

Spec (from challenge brief):
- 40 m x 40 m floor, 8 m ceiling
- 4 m grid cells (10x10 grid)
- yellow barrels: ground level only
- red barrels: never on ground (placed on shelf platforms)
- toxic-sign barrels: visual distractors (must NOT be detected)
- all OPEN+SHELF cells must be connected for the drone

Drone start pose: world origin (0, 0, 0). The center of the arena is
guaranteed to land in an OPEN cell because the generator never places
walls or shelves on the central 2x2.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import deque
from pathlib import Path

# ---------------------------------------------------------------------------
# Spec constants
# ---------------------------------------------------------------------------
ARENA_SIZE = 40.0           # meters per side
GRID_N = 10                 # cells per side -> 4 m cells
CELL_SIZE = ARENA_SIZE / GRID_N
ARENA_HEIGHT = 8.0
WALL_HEIGHT = 6.0           # tall enough that the drone must navigate around
SHELF_HEIGHT = 2.0
SHELF_FOOTPRINT = 1.5       # smaller than cell so drone can fly past
PERIMETER_THICKNESS = 0.5
BARREL_RADIUS = 0.4
BARREL_HEIGHT = 0.8

# Cell states
OPEN, WALL, SHELF = 0, 1, 2

# Polyomino wall shapes. Each is a list of (dx, dy) offsets; rotate_shape
# normalizes them to non-negative coords after rotation.
WALL_SHAPES = [
    [(0, 0)],                                  # 1x1 pillar
    [(0, 0), (1, 0)],                          # 2x1 horizontal
    [(0, 0), (1, 0), (2, 0)],                  # 3x1 horizontal
    [(0, 0), (1, 0), (2, 0), (3, 0)],          # 4x1 horizontal
    [(0, 0), (1, 0), (1, 1)],                  # L (3 cells)
    [(0, 0), (1, 0), (2, 0), (2, 1)],          # L (4 cells)
    [(0, 0), (1, 0), (2, 0), (1, 1)],          # T
    [(0, 0), (1, 0), (0, 1), (1, 1)],          # 2x2 block
]


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def cell_to_world(i: int, j: int) -> tuple[float, float]:
    """Cell (i, j) center in world coords. Origin at arena center."""
    half = ARENA_SIZE / 2
    return (-half + CELL_SIZE * (i + 0.5), -half + CELL_SIZE * (j + 0.5))


def rotate_shape(shape: list[tuple[int, int]], rot: int) -> list[tuple[int, int]]:
    """Rotate a polyomino by rot * 90 degrees and normalize to non-negative."""
    out = []
    for (x, y) in shape:
        rx, ry = x, y
        for _ in range(rot % 4):
            rx, ry = ry, -rx
        out.append((rx, ry))
    min_x = min(c[0] for c in out)
    min_y = min(c[1] for c in out)
    return [(x - min_x, y - min_y) for (x, y) in out]


# ---------------------------------------------------------------------------
# Maze generation
# ---------------------------------------------------------------------------
def in_central_keepout(i: int, j: int) -> bool:
    """Keep the central 2x2 (cells 4,4..5,5) clear so spawn is OPEN."""
    return 4 <= i <= 5 and 4 <= j <= 5


def can_place(grid, shape, ox, oy) -> bool:
    for (dx, dy) in shape:
        x, y = ox + dx, oy + dy
        if not (0 <= x < GRID_N and 0 <= y < GRID_N):
            return False
        if grid[x][y] != OPEN:
            return False
        if in_central_keepout(x, y):
            return False
    return True


def place(grid, shape, ox, oy, val):
    for (dx, dy) in shape:
        grid[ox + dx][oy + dy] = val


def is_connected(grid, shelves_block: bool) -> bool:
    """BFS — every non-blocked cell must be reachable from any non-blocked cell."""
    blocked = {WALL}
    if shelves_block:
        blocked.add(SHELF)
    start = None
    for i in range(GRID_N):
        for j in range(GRID_N):
            if grid[i][j] not in blocked:
                start = (i, j)
                break
        if start is not None:
            break
    if start is None:
        return False
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < GRID_N and 0 <= ny < GRID_N and (nx, ny) not in seen:
                if grid[nx][ny] not in blocked:
                    seen.add((nx, ny))
                    q.append((nx, ny))
    target = sum(
        1 for i in range(GRID_N) for j in range(GRID_N)
        if grid[i][j] not in blocked
    )
    return len(seen) == target


def generate_layout(
    seed: int,
    num_walls: int,
    num_shelves: int,
    num_yellow: int,
    num_red: int,
    num_toxic: int,
):
    rng = random.Random(seed)
    grid = [[OPEN] * GRID_N for _ in range(GRID_N)]

    # 1. Place wall structures one at a time, accept only if drone-level
    #    connectivity is preserved.
    placed = 0
    attempts = 0
    while placed < num_walls and attempts < 500:
        attempts += 1
        shape = rotate_shape(rng.choice(WALL_SHAPES), rng.randint(0, 3))
        ox = rng.randint(0, GRID_N - 1)
        oy = rng.randint(0, GRID_N - 1)
        if not can_place(grid, shape, ox, oy):
            continue
        place(grid, shape, ox, oy, WALL)
        # Drone flies above shelves, so only walls block at this stage.
        if is_connected(grid, shelves_block=False):
            placed += 1
        else:
            place(grid, shape, ox, oy, OPEN)

    # 2. Place shelves in OPEN cells, preserving ground-level connectivity
    #    (so yellow barrels can be reached on the floor).
    shelf_count = 0
    candidate_cells = [
        (i, j) for i in range(GRID_N) for j in range(GRID_N)
        if grid[i][j] == OPEN and not in_central_keepout(i, j)
    ]
    rng.shuffle(candidate_cells)
    for (i, j) in candidate_cells:
        if shelf_count >= num_shelves:
            break
        grid[i][j] = SHELF
        if is_connected(grid, shelves_block=True):
            shelf_count += 1
        else:
            grid[i][j] = OPEN

    if shelf_count < num_shelves:
        print(
            f"warning: requested {num_shelves} shelves, placed {shelf_count} "
            "(connectivity constraint hit)",
            file=sys.stderr,
        )

    # 3. Pick barrel locations.
    open_cells = [
        (i, j) for i in range(GRID_N) for j in range(GRID_N)
        if grid[i][j] == OPEN and not in_central_keepout(i, j)
    ]
    shelf_cells = [
        (i, j) for i in range(GRID_N) for j in range(GRID_N) if grid[i][j] == SHELF
    ]
    rng.shuffle(open_cells)
    rng.shuffle(shelf_cells)

    yellow = open_cells[:num_yellow]
    red = shelf_cells[:num_red]

    # Toxic distractors: pick from leftovers, mix of ground and elevated.
    leftover_open = open_cells[num_yellow:]
    leftover_shelf = shelf_cells[num_red:]
    toxic_pool = [("ground", c) for c in leftover_open] + \
                 [("elevated", c) for c in leftover_shelf]
    rng.shuffle(toxic_pool)
    toxic = toxic_pool[:num_toxic]

    return grid, yellow, red, toxic


# ---------------------------------------------------------------------------
# SDF emission
# ---------------------------------------------------------------------------
SDF_HEADER = """<?xml version="1.0" encoding="UTF-8"?>
<sdf version="1.9">
  <world name='{world_name}'>
    <physics type="ode">
      <max_step_size>0.001</max_step_size>
      <real_time_factor>1</real_time_factor>
      <real_time_update_rate>1000</real_time_update_rate>
    </physics>
    <plugin name='gz::sim::systems::Physics' filename='gz-sim-physics-system'/>
    <plugin name='gz::sim::systems::UserCommands' filename='gz-sim-user-commands-system'/>
    <plugin name='gz::sim::systems::SceneBroadcaster' filename='gz-sim-scene-broadcaster-system'/>
    <plugin name='gz::sim::systems::Contact' filename='gz-sim-contact-system'/>
    <plugin filename="gz-sim-imu-system" name="gz::sim::systems::Imu"/>
    <plugin filename="gz-sim-air-pressure-system" name="gz::sim::systems::AirPressure"/>
    <plugin filename="gz-sim-magnetometer-system" name="gz::sim::systems::Magnetometer"/>
    <plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors"/>
    <plugin filename="gz-sim-navsat-system" name="gz::sim::systems::NavSat"/>
    <gravity>0 0 -9.8</gravity>
    <magnetic_field>5.5645e-06 2.28758e-05 -4.23884e-05</magnetic_field>
    <atmosphere type='adiabatic'/>
    <scene>
      <ambient>0.4 0.4 0.4 1</ambient>
      <background>0.7 0.7 0.7 1</background>
      <shadows>true</shadows>
    </scene>
    <model name='ground_plane'>
      <static>true</static>
      <link name='link'>
        <collision name='collision'>
          <geometry><plane><normal>0 0 1</normal><size>100 100</size></plane></geometry>
        </collision>
        <visual name='visual'>
          <geometry><plane><normal>0 0 1</normal><size>100 100</size></plane></geometry>
          <material>
            <ambient>0.85 0.85 0.85 1</ambient>
            <diffuse>0.85 0.85 0.85 1</diffuse>
          </material>
        </visual>
      </link>
    </model>
"""

SDF_FOOTER = """    <light name='sun' type='directional'>
      <pose>0 0 10 0 0 0</pose>
      <cast_shadows>true</cast_shadows>
      <intensity>3</intensity>
      <direction>1.5 5.1 -3.9</direction>
      <diffuse>0.95 0.95 0.95 1</diffuse>
      <specular>0.32 0.32 0.32 1</specular>
      <attenuation>
        <range>1023</range>
        <linear>0.098148</linear>
        <constant>0.9</constant>
        <quadratic>0</quadratic>
      </attenuation>
    </light>
    <spherical_coordinates>
      <surface_model>EARTH_WGS84</surface_model>
      <world_frame_orientation>ENU</world_frame_orientation>
      <latitude_deg>47.397971057728974</latitude_deg>
      <longitude_deg>8.546163739800146</longitude_deg>
      <elevation>0</elevation>
    </spherical_coordinates>
  </world>
</sdf>
"""


def static_box_model(name: str, x: float, y: float, z: float,
                     sx: float, sy: float, sz: float, rgb: tuple[float, float, float]) -> str:
    r, g, b = rgb
    return f"""    <model name='{name}'>
      <static>true</static>
      <pose>{x:.3f} {y:.3f} {z:.3f} 0 0 0</pose>
      <link name='link'>
        <visual name='visual'>
          <geometry><box><size>{sx:.3f} {sy:.3f} {sz:.3f}</size></box></geometry>
          <material>
            <ambient>{r:.3f} {g:.3f} {b:.3f} 1</ambient>
            <diffuse>{r:.3f} {g:.3f} {b:.3f} 1</diffuse>
          </material>
        </visual>
        <collision name='collision'>
          <geometry><box><size>{sx:.3f} {sy:.3f} {sz:.3f}</size></box></geometry>
        </collision>
      </link>
    </model>
"""


def static_cylinder_model(name: str, x: float, y: float, z: float,
                          radius: float, length: float,
                          rgb: tuple[float, float, float]) -> str:
    r, g, b = rgb
    return f"""    <model name='{name}'>
      <static>true</static>
      <pose>{x:.3f} {y:.3f} {z:.3f} 0 0 0</pose>
      <link name='link'>
        <visual name='visual'>
          <geometry><cylinder><radius>{radius:.3f}</radius><length>{length:.3f}</length></cylinder></geometry>
          <material>
            <ambient>{r:.3f} {g:.3f} {b:.3f} 1</ambient>
            <diffuse>{r:.3f} {g:.3f} {b:.3f} 1</diffuse>
          </material>
        </visual>
        <collision name='collision'>
          <geometry><cylinder><radius>{radius:.3f}</radius><length>{length:.3f}</length></cylinder></geometry>
        </collision>
      </link>
    </model>
"""


# Color palette
COLOR_WALL = (0.45, 0.45, 0.5)
COLOR_SHELF = (0.55, 0.5, 0.45)
COLOR_PERIMETER = (0.35, 0.35, 0.4)
COLOR_YELLOW = (0.95, 0.85, 0.1)
COLOR_RED = (0.85, 0.1, 0.1)
COLOR_TOXIC = (0.95, 0.55, 0.1)  # orange — visually similar to yellow, distractor


def emit_sdf(grid, yellow, red, toxic, world_name: str) -> str:
    out = [SDF_HEADER.format(world_name=world_name)]

    # Perimeter walls (4 long boxes around the 40x40 arena).
    half = ARENA_SIZE / 2
    pt = PERIMETER_THICKNESS
    perim_z = WALL_HEIGHT / 2
    out.append(static_box_model(
        "perimeter_north", 0, half + pt / 2, perim_z,
        ARENA_SIZE + 2 * pt, pt, WALL_HEIGHT, COLOR_PERIMETER,
    ))
    out.append(static_box_model(
        "perimeter_south", 0, -half - pt / 2, perim_z,
        ARENA_SIZE + 2 * pt, pt, WALL_HEIGHT, COLOR_PERIMETER,
    ))
    out.append(static_box_model(
        "perimeter_east", half + pt / 2, 0, perim_z,
        pt, ARENA_SIZE, WALL_HEIGHT, COLOR_PERIMETER,
    ))
    out.append(static_box_model(
        "perimeter_west", -half - pt / 2, 0, perim_z,
        pt, ARENA_SIZE, WALL_HEIGHT, COLOR_PERIMETER,
    ))

    # Wall cells
    for i in range(GRID_N):
        for j in range(GRID_N):
            if grid[i][j] != WALL:
                continue
            x, y = cell_to_world(i, j)
            out.append(static_box_model(
                f"wall_{i}_{j}", x, y, WALL_HEIGHT / 2,
                CELL_SIZE, CELL_SIZE, WALL_HEIGHT, COLOR_WALL,
            ))

    # Shelf cells (the platform that elevates a red barrel)
    for i in range(GRID_N):
        for j in range(GRID_N):
            if grid[i][j] != SHELF:
                continue
            x, y = cell_to_world(i, j)
            out.append(static_box_model(
                f"shelf_{i}_{j}", x, y, SHELF_HEIGHT / 2,
                SHELF_FOOTPRINT, SHELF_FOOTPRINT, SHELF_HEIGHT, COLOR_SHELF,
            ))

    # Yellow barrels — ground level, sitting on the floor
    for k, (i, j) in enumerate(yellow):
        x, y = cell_to_world(i, j)
        out.append(static_cylinder_model(
            f"yellow_barrel_{k}", x, y, BARREL_HEIGHT / 2,
            BARREL_RADIUS, BARREL_HEIGHT, COLOR_YELLOW,
        ))

    # Red barrels — sitting on top of shelves
    for k, (i, j) in enumerate(red):
        x, y = cell_to_world(i, j)
        z = SHELF_HEIGHT + BARREL_HEIGHT / 2
        out.append(static_cylinder_model(
            f"red_barrel_{k}", x, y, z,
            BARREL_RADIUS, BARREL_HEIGHT, COLOR_RED,
        ))

    # Toxic distractors
    for k, (kind, (i, j)) in enumerate(toxic):
        x, y = cell_to_world(i, j)
        z = (SHELF_HEIGHT + BARREL_HEIGHT / 2) if kind == "elevated" else BARREL_HEIGHT / 2
        out.append(static_cylinder_model(
            f"toxic_barrel_{k}", x, y, z,
            BARREL_RADIUS, BARREL_HEIGHT, COLOR_TOXIC,
        ))

    out.append(SDF_FOOTER)
    return "".join(out)


# ---------------------------------------------------------------------------
# Metadata + previews
# ---------------------------------------------------------------------------
def build_metadata(seed, grid, yellow, red, toxic, world_name) -> dict:
    def cell_meta(i, j, label):
        x, y = cell_to_world(i, j)
        return {"cell": [i, j], "world_xy": [round(x, 3), round(y, 3)], "kind": label}

    return {
        "seed": seed,
        "world_name": world_name,
        "arena_size_m": ARENA_SIZE,
        "cell_size_m": CELL_SIZE,
        "grid_n": GRID_N,
        "wall_height_m": WALL_HEIGHT,
        "shelf_height_m": SHELF_HEIGHT,
        "barrel_radius_m": BARREL_RADIUS,
        "barrel_height_m": BARREL_HEIGHT,
        "yellow_barrels": [
            {**cell_meta(i, j, "yellow"), "z_center": BARREL_HEIGHT / 2}
            for (i, j) in yellow
        ],
        "red_barrels": [
            {**cell_meta(i, j, "red"), "z_center": SHELF_HEIGHT + BARREL_HEIGHT / 2}
            for (i, j) in red
        ],
        "toxic_barrels": [
            {**cell_meta(i, j, f"toxic_{kind}"),
             "z_center": (SHELF_HEIGHT + BARREL_HEIGHT / 2) if kind == "elevated" else BARREL_HEIGHT / 2}
            for (kind, (i, j)) in toxic
        ],
        "wall_cells": [[i, j] for i in range(GRID_N) for j in range(GRID_N) if grid[i][j] == WALL],
        "shelf_cells": [[i, j] for i in range(GRID_N) for j in range(GRID_N) if grid[i][j] == SHELF],
    }


def ascii_preview(grid, yellow, red, toxic) -> str:
    """ASCII top-down map. North is up; cell (i, j) -> column i, row j."""
    barrel_glyph = {}
    for (i, j) in yellow:
        barrel_glyph[(i, j)] = "Y"
    for (i, j) in red:
        barrel_glyph[(i, j)] = "R"
    for (_, (i, j)) in toxic:
        barrel_glyph[(i, j)] = "T"

    lines = []
    lines.append("    " + " ".join(f"{i:2d}" for i in range(GRID_N)))
    for j in reversed(range(GRID_N)):  # north-up
        row = []
        for i in range(GRID_N):
            if grid[i][j] == WALL:
                glyph = "##"
            elif grid[i][j] == SHELF:
                glyph = "[]"
            elif (i, j) in barrel_glyph:
                glyph = " " + barrel_glyph[(i, j)]
            else:
                glyph = " ."
            row.append(glyph)
        lines.append(f"{j:2d}  " + " ".join(row))
    legend = (
        "\nlegend: ## wall    [] shelf (red barrel on top)    "
        "Y yellow barrel    R red barrel    T toxic distractor    . open"
    )
    return "\n".join(lines) + legend


def png_preview(grid, yellow, red, toxic, path: Path) -> bool:
    """Optional matplotlib preview. Returns True if written."""
    try:
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle, Circle
    except ImportError:
        return False

    fig, ax = plt.subplots(figsize=(8, 8))
    half = ARENA_SIZE / 2
    ax.set_xlim(-half - 1, half + 1)
    ax.set_ylim(-half - 1, half + 1)
    ax.set_aspect("equal")
    ax.set_facecolor("#f4f4f4")

    # Arena boundary
    ax.add_patch(Rectangle(
        (-half, -half), ARENA_SIZE, ARENA_SIZE,
        fill=False, edgecolor="black", linewidth=2,
    ))

    # Walls
    for i in range(GRID_N):
        for j in range(GRID_N):
            if grid[i][j] == WALL:
                x, y = cell_to_world(i, j)
                ax.add_patch(Rectangle(
                    (x - CELL_SIZE / 2, y - CELL_SIZE / 2),
                    CELL_SIZE, CELL_SIZE,
                    facecolor="#5a5a64", edgecolor="black",
                ))
            elif grid[i][j] == SHELF:
                x, y = cell_to_world(i, j)
                ax.add_patch(Rectangle(
                    (x - SHELF_FOOTPRINT / 2, y - SHELF_FOOTPRINT / 2),
                    SHELF_FOOTPRINT, SHELF_FOOTPRINT,
                    facecolor="#a78c6f", edgecolor="black",
                ))

    # Barrels
    for (i, j) in yellow:
        x, y = cell_to_world(i, j)
        ax.add_patch(Circle((x, y), BARREL_RADIUS, color="#f1d927", ec="black"))
    for (i, j) in red:
        x, y = cell_to_world(i, j)
        ax.add_patch(Circle((x, y), BARREL_RADIUS, color="#d11919", ec="black"))
    for (_, (i, j)) in toxic:
        x, y = cell_to_world(i, j)
        ax.add_patch(Circle((x, y), BARREL_RADIUS, color="#f08a1a",
                            ec="black", linestyle="--"))

    # Drone start marker
    ax.plot(0, 0, marker="x", color="blue", markersize=12, markeredgewidth=3)
    ax.annotate("drone start", (0, 0), xytext=(1, 1), fontsize=8)

    # Grid lines
    for k in range(GRID_N + 1):
        v = -half + k * CELL_SIZE
        ax.axvline(v, color="gray", linewidth=0.3, alpha=0.5)
        ax.axhline(v, color="gray", linewidth=0.3, alpha=0.5)

    ax.set_xlabel("east (m)")
    ax.set_ylabel("north (m)")
    ax.set_title(path.stem)
    plt.tight_layout()
    plt.savefig(path, dpi=120)
    plt.close(fig)
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--seed", type=int, default=None,
                    help="RNG seed (defaults to a random seed).")
    ap.add_argument("--out-dir", type=Path,
                    default=Path(__file__).parent / "output",
                    help="Output directory for .sdf, .json, .png.")
    ap.add_argument("--name", type=str, default=None,
                    help="Base filename (default: maze_<seed>).")
    ap.add_argument("--world-name", type=str, default="roboverse",
                    help="<world name=...> in the SDF. Default 'roboverse' "
                         "so start_px4.sh picks it up as a drop-in replacement.")
    ap.add_argument("--num-walls", type=int, default=6,
                    help="How many wall polyominoes to attempt placing.")
    ap.add_argument("--num-shelves", type=int, default=4,
                    help="How many shelf platforms (host elevated red barrels).")
    ap.add_argument("--num-yellow", type=int, default=3)
    ap.add_argument("--num-red", type=int, default=3)
    ap.add_argument("--num-toxic", type=int, default=2)
    ap.add_argument("--no-png", action="store_true",
                    help="Skip the matplotlib PNG preview.")
    args = ap.parse_args()

    if args.seed is None:
        args.seed = random.randint(0, 2**31 - 1)
    base = args.name or f"maze_{args.seed}"
    args.out_dir.mkdir(parents=True, exist_ok=True)

    grid, yellow, red, toxic = generate_layout(
        args.seed,
        num_walls=args.num_walls,
        num_shelves=args.num_shelves,
        num_yellow=args.num_yellow,
        num_red=args.num_red,
        num_toxic=args.num_toxic,
    )

    sdf_path = args.out_dir / f"{base}.sdf"
    json_path = args.out_dir / f"{base}.json"
    png_path = args.out_dir / f"{base}.png"

    sdf_path.write_text(emit_sdf(grid, yellow, red, toxic, args.world_name))
    json_path.write_text(json.dumps(
        build_metadata(args.seed, grid, yellow, red, toxic, args.world_name),
        indent=2,
    ))

    print(f"seed: {args.seed}")
    print(ascii_preview(grid, yellow, red, toxic))
    print()

    n_y = len(yellow)
    n_r = len(red)
    n_t = len(toxic)
    n_walls_actual = sum(1 for i in range(GRID_N) for j in range(GRID_N) if grid[i][j] == WALL)
    n_shelves_actual = sum(1 for i in range(GRID_N) for j in range(GRID_N) if grid[i][j] == SHELF)
    print(f"placed: {n_walls_actual} wall cells, {n_shelves_actual} shelves, "
          f"{n_y} yellow, {n_r} red, {n_t} toxic")
    print(f"sdf:  {sdf_path}")
    print(f"json: {json_path}")

    if not args.no_png:
        if png_preview(grid, yellow, red, toxic, png_path):
            print(f"png:  {png_path}")
        else:
            print("png:  skipped (matplotlib not available)")


if __name__ == "__main__":
    main()

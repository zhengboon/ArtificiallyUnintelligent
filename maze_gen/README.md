# maze_gen — Random RoboVerse maze generator

Generates Gazebo Harmonic `.sdf` worlds that satisfy the BrainHack 2026
RoboVerse Qualifier spec: 40 m × 40 m × 8 m arena, 4 m grid cells, yellow
barrels on the ground, red barrels elevated on shelves, toxic distractors
visually similar to yellow.

## Quickstart

```bash
# Use the conda python (has matplotlib for the PNG preview)
~/.miniforge3/bin/python generate_maze.py --seed 42

# Defaults: 6 wall structures, 4 shelves, 3 yellow, 3 red, 2 toxic.
# Outputs land in ./output/:
#   maze_42.sdf   — the world file
#   maze_42.json  — ground-truth metadata
#   maze_42.png   — top-down preview
```

Or with system python (skips PNG):

```bash
python3 generate_maze.py --seed 42 --no-png
```

## CLI flags

| Flag | Default | Notes |
|---|---|---|
| `--seed N` | random | reproducible runs |
| `--out-dir PATH` | `./output` | where files land |
| `--name STR` | `maze_<seed>` | filename stem |
| `--world-name STR` | `roboverse` | `<world name=...>` in the SDF; default is a drop-in replacement for `start_px4.sh` |
| `--num-walls N` | 6 | polyomino structures attempted (each may cover 1–4 cells) |
| `--num-shelves N` | 4 | platforms hosting elevated red barrels |
| `--num-yellow N` | 3 | ground barrels |
| `--num-red N` | 3 | elevated barrels |
| `--num-toxic N` | 2 | distractors (mix of ground and elevated) |
| `--no-png` | off | skip matplotlib preview |

## Using the generated world in PX4 SITL

1. Copy the `.sdf` into the PX4 worlds directory:
   ```bash
   cp output/maze_42.sdf ~/PX4-Autopilot/Tools/simulation/gz/worlds/
   ```
2. Run the provided launcher:
   ```bash
   ~/start_px4.sh
   ```
3. Pick `x500_vision`, then pick the world. With the default
   `--world-name roboverse`, the new file *replaces* the original
   `roboverse.sdf` if you overwrite — back up the original first.

   To keep both available, generate with a unique world name:
   ```bash
   python generate_maze.py --seed 42 --world-name maze42
   ```
   Then select `maze42` from the world menu.

## Spec compliance

| Constraint | How the generator enforces it |
|---|---|
| 40×40×8 m arena | `ARENA_SIZE = 40`, perimeter walls 6 m tall |
| 4 m grid cells | `GRID_N = 10`, walls snap to cell centers |
| Yellow barrels ground-only | placed in `OPEN` cells, `z = BARREL_HEIGHT/2` |
| Red barrels never on ground | placed only on `SHELF` cells, `z = SHELF_HEIGHT + BARREL_HEIGHT/2` |
| All reachable area connected | BFS connectivity check after every wall placement; rejected if it disconnects the map |
| Drone spawn (0,0,0) lands in OPEN cell | central 2×2 cells (i,j ∈ {4,5}) are kept clear |
| Toxic barrels visually similar to yellow | rendered as orange cylinders (close hue to yellow) |

The drone's `is_home_position_ok` check still requires the EKF origin
trick — see `../context.md` for the `commander set_ekf_origin ...`
incantation.

## JSON ground truth

`maze_<seed>.json` lists every barrel with its grid cell, world XY, and
`z_center`. Schema:

```json
{
  "seed": 42,
  "world_name": "roboverse",
  "yellow_barrels": [{"cell": [i, j], "world_xy": [x, y], "z_center": 0.4, "kind": "yellow"}, ...],
  "red_barrels":    [{"cell": [i, j], "world_xy": [x, y], "z_center": 2.4, "kind": "red"}, ...],
  "toxic_barrels":  [{"cell": [i, j], "world_xy": [x, y], "z_center": ..., "kind": "toxic_ground|toxic_elevated"}, ...],
  "wall_cells":  [[i, j], ...],
  "shelf_cells": [[i, j], ...]
}
```

Use this for offline scoring of search runs (compute precision/recall of
your detector + planner against the ground truth).

## Design notes

- **Wall topology is polyomino-based**, not perfect-maze (no Prim/Kruskal).
  The reference image in the brief shows large open chunks with peninsular
  obstacles, not a corridor maze, so we drop random L/T/2×2/strip shapes.
- **Walls are 6 m tall** (out of 8 m ceiling) so the drone *can* fly
  over in principle — useful if you want to test "give up and go above"
  recovery — but it must clear 6 m, not trivial. Set `WALL_HEIGHT = 8.0`
  in the script if you want hard barriers.
- **Shelves are 1.5 m × 1.5 m × 2 m** (smaller than the cell), so the
  drone can fly past them at altitude. Red barrel sits on top at z = 2.4.
- **Connectivity is checked twice**: once treating only walls as blocked
  (drone-level), and once treating shelves as blocked too (ground-level,
  to ensure yellow barrels can be approached on the floor).
- **Barrel materials are flat colors**, not textured GLB meshes. Good
  enough for testing your YOLO pipeline against varied layouts; the
  actual judge run uses the baked `base6.glb` which has higher visual
  fidelity. If you train a custom YOLO on this generator's output, also
  fine-tune on screenshots from the real `roboverse.sdf` world before
  the qualifier.

# Search Strategy v1 — RoboVerse Qualifier
**Author:** AB  
**Status:** Draft — for Z to implement as `searchctl/planner/lawnmower.py`  
**Last updated:** 2026-05-16

---

## 1. Goal

Cover the 40 m × 40 m arena in one 10-minute run, detecting as many fuel barrels as possible. Priority order:

1. **Achieve eligibility** — detect ≥ 1 yellow AND ≥ 1 red barrel (University category requirement).
2. **Maximise barrel count** — more yellow (50 pts each) and red (100 pts each) detections = higher score.
3. **Chase speed bonus** — if all barrels of one colour found under 5 min, earn +20 pts per 30 s saved.

---

## 2. Strategy choice: Lawnmower (Phase 3 MVP)

**Decision: lawnmower sweep at two altitudes.** Frontier exploration is more adaptive but requires a working occupancy grid (camera frame ↔ NED frame transforms, noisy depth fusion). Given the time constraint and that we need a reliable qualifying run, lawnmower is the safer choice. Frontier can be attempted as a Phase 3.5 stretch goal if time allows.

**Why lawnmower works here:**
- Yellow barrels are ground-only → a systematic low pass will find all of them.
- Red barrels are elevated → a systematic high pass will find all of them.
- The arena has a known approximate shape (L-shaped, ~40 × 40 m). We can pre-plan a valid waypoint list.
- Predictable timing: we can estimate coverage time and know in advance whether we can hit the speed bonus.

---

## 3. Arena and grid model

```
Arena:    40 m (N–S) × 40 m (E–W) × 8 m (height)
Grid cell: 4 m × 4 m  →  10 × 10 logical grid
Shape:    L-shaped (not all 100 cells are accessible — see §4)
Origin:   Drone spawn point = NED (0, 0, 0)
```

**Coordinate convention (NED — North-East-Down):**
- North (+N) = forward from spawn
- East (+E) = right from spawn
- Down (+D) = altitude is **negative** (drone at 1 m altitude = D = -1.0)

**Waypoint spacing:** 4 m between lawnmower rows (matches grid cell size). Camera FOV at 1 m altitude covers ~2–3 m forward; at 3.5 m it covers ~4–5 m forward. 4 m row spacing gives adequate overlap at both heights.

---

## 4. Pre-flight: arena boundary mask

> ⚠️ The actual qualifier map is released ~Thu 2026-05-21 (T-1 day). This spec uses the sample map shape. **Z should make the waypoint list a config parameter** (e.g. loaded from `testing/maze_set/qualifier_map.json`) so we can swap in the real coordinates in < 5 minutes after the map drops.

Based on the sample top-down image, the accessible area is approximately:

```
  Col:  0  1  2  3  4  5  6  7  8  9
Row 0: [.][.][X][X][X][X][X][X][X][X]
Row 1: [.][.][.][.][X][X][X][X][X][X]
Row 2: [.][.][.][.][.][.][.][X][X][X]
Row 3: [.][.][.][.][.][.][.][.][X][X]
Row 4: [.][.][.][.][.][.][.][.][.][X]
Row 5: [.][.][.][.][.][.][.][.][.][.]
Row 6: [.][.][.][.][.][.][.][.][.][.]
Row 7: [X][X][.][.][.][.][.][.][.][.]
Row 8: [X][X][X][.][.][.][.][.][.][.]
Row 9: [X][X][X][X][.][.][.][.][.][.]
  . = accessible   X = wall / out of bounds
```

> This is an approximation. Z should load the actual accessible cell list from the maze JSON. The waypoint generator (see §5) should skip any cell marked as wall/out-of-bounds.

---

## 5. Waypoint generation algorithm

```
INPUTS:
  accessible_cells: list of (row, col) tuples for valid grid cells
  cell_size: 4.0  (metres)
  origin_ned: (0.0, 0.0)  (NED north, east of spawn)

PASS 1 — Yellow sweep (low altitude):
  altitude: -1.0 m (NED Down = -1.0)
  pattern: snake (lawnmower)
    for row in range(0, 10):
      if row is even:  sweep cols left → right (col 0 → 9)
      if row is odd:   sweep cols right → left (col 9 → 0)
      for each col in sweep direction:
        if (row, col) in accessible_cells:
          emit waypoint: north = row * cell_size + 2.0
                          east  = col * cell_size + 2.0
                          down  = -1.0
          (the +2.0 centres the waypoint in the cell)
        else:
          skip cell (don't emit; planner moves to next valid cell)

PASS 2 — Red sweep (high altitude):
  altitude: -3.5 m (NED Down = -3.5)
  pattern: same snake, but reversed start corner to avoid
           backtracking all the way to (0,0):
    begin from where Pass 1 ended (last waypoint of Pass 1)
    snake in same grid order, now at -3.5 m

TERMINATION:
  If all unique_yellow_count == total_yellow_barrels in map:
    skip remaining Pass 1 waypoints, jump to Pass 2 immediately.
  If all unique_red_count == total_red_barrels in map:
    skip remaining Pass 2 waypoints, land early.
  (These counts come from SharedState exposed by Z.3)
```

**Centre-of-cell offset (+2.0 m):** ensures the drone's camera points into the cell interior rather than at a corner. Adjust if cell_size changes.

---

## 6. Obstacle response (when blocked mid-waypoint)

The controller already has obstacle avoidance (Goal Vector + Avoidance Vector from LearningMaterial3). The planner's job is to respond at the *waypoint level* when the drone cannot reach a planned cell:

```
BLOCKED CELL DECISION TREE:

When drone is trying to reach waypoint W and:
  - depth camera reports obstacle within 1.5 m for > 3 consecutive seconds, AND
  - drone has not moved > 0.3 m toward W in those 3 seconds:

  → Mark cell as BLOCKED in visited_grid
  → Skip W, move to next waypoint in sequence
  → Log: "Waypoint (row, col) skipped — blocked"

If 3 or more consecutive cells in the same row are blocked:
  → Treat entire row segment as inaccessible
  → Jump to next row (advance row index by 1, reset col direction)
  → Log: "Row segment blocked — skipping to row N"

If drone is stuck (no progress for 8 seconds total):
  → Execute BACKTRACK:
      1. Pop last 3 visited waypoints from visited_grid
      2. Navigate back to the most recent successfully reached waypoint
      3. Resume sequence from the waypoint AFTER the blocked one
  → If backtrack itself fails (stuck again within 5 s):
      → Ascend 1.0 m (hover higher to clear obstacle top)
      → Retry original waypoint once
      → If still blocked, skip and continue
```

---

## 7. Altitude transition (Pass 1 → Pass 2)

```
When Pass 1 complete (all accessible cells visited OR all yellows found):
  1. Pause at current (N, E) position
  2. Ascend from -1.0 m to -3.5 m at 0.5 m/s vertical
  3. Wait 1.0 s for altitude stabilisation
  4. Begin Pass 2 waypoint sequence
```

Do NOT change altitude mid-lawnmower-row. Altitude changes only at pass boundaries (or backtrack recovery).

---

## 8. Timing estimate

| Phase | Cells to visit (estimate) | Speed | Time |
|---|---|---|---|
| Takeoff + EKF settle | — | — | ~20 s |
| Pass 1 (low, yellow) | ~60 valid cells × ~5 s/cell | 1.5 m/s cruise | ~5 min |
| Altitude transition | — | 0.5 m/s | ~10 s |
| Pass 2 (high, red) | ~60 valid cells × ~4 s/cell | 1.5 m/s cruise | ~4 min |
| Land + margin | — | — | ~30 s |
| **Total** | | | **~9 min 50 s** |

> ⚠️ This is tight. If the sim shows > 10 min in dry-runs, reduce cell_size to 5 m (8×8 grid, fewer waypoints) or increase cruise speed to 2.0 m/s. AB to flag after first dry-run (A.5).

**Speed bonus target:** if Pass 1 finishes all yellow barrels in < 5 min, we earn +20 pts per 30 s saved. With the above timing, Pass 1 completes around 5 min — borderline. If we start from a corner where yellow barrels cluster (revealed by the real map), we may be able to earn 1–2 bonus ticks.

---

## 9. Interface contract for Z

The planner should expose the following to the controller:

```python
# searchctl/planner/lawnmower.py

class LawnmowerPlanner:
    def __init__(self, accessible_cells, cell_size=4.0, origin=(0.0, 0.0)):
        ...

    def get_waypoints(self) -> list[tuple[float, float, float]]:
        """Returns ordered list of (north, east, down) waypoints for full run."""
        ...

    def mark_blocked(self, waypoint_index: int):
        """Call when a waypoint is unreachable. Planner skips it."""
        ...

    def notify_yellow_complete(self):
        """Call when SharedState reports all yellows found. Planner jumps to Pass 2."""
        ...

    def notify_red_complete(self):
        """Call when SharedState reports all reds found. Planner signals done."""
        ...

    def current_phase(self) -> str:
        """Returns 'pass1_yellow', 'pass2_red', or 'complete'."""
        ...
```

Z should call `get_waypoints()` once at startup and iterate through the list, calling `mark_blocked()` if a waypoint times out. The controller's existing waypoint-following loop feeds these NED coordinates directly to `set_position()`.

---

## 10. Config file format (for easy map swap)

```json
{
  "cell_size_m": 4.0,
  "origin_ned": [0.0, 0.0],
  "accessible_cells": [
    [0, 0], [0, 1],
    [1, 0], [1, 1], [1, 2], [1, 3],
    ...
  ],
  "total_yellow_barrels": null,
  "total_red_barrels": null
}
```

`total_yellow_barrels` / `total_red_barrels` can be `null` (unknown) or set to an integer once the real map is released. If `null`, the termination condition based on barrel count is disabled and the planner always completes the full sweep.

---

## 11. Open questions for Z

1. **What is the drone's max reliable cruise speed?** (Phase 1 tested at what m/s?) — affects timing estimate in §8.
2. **Waypoint arrival tolerance** — currently sub-0.5 m from tasks.md. Is 0.5 m the threshold for "arrived", or does the drone hover until exactly at the point?
3. **Does the controller expose `set_position(north, east, down)`?** Or does it use a different coordinate signature? Strategy assumes NED.
4. **Is there a max altitude limit in the sim?** Arena height is 8 m; Pass 2 at 3.5 m should be fine, but confirm.

---

## 12. Stretch goal: frontier exploration (Phase 3.5)

If dry-runs show the lawnmower missing barrels due to irregular arena walls or large blocked sections, we can switch to a frontier-based approach adapted from `pastproject/remote_laptop_src/nodes/global_controller.py`. Key differences for our drone context:

- No Nav2 stack — we'd implement BFS frontier detection directly in NED grid coordinates.
- Obstacle padding: 1 cell (4 m) radius around known blocked cells (gentler than pastproject's 3-cell padding).
- Same two-altitude structure: frontier exploration at 1 m first, then 3.5 m second pass.

This is explicitly a stretch goal. Do not block Phase 3 on it.

---

*When Z implements this, please confirm the interface contract in §9 works with the controller's existing waypoint loop, or propose amendments.*

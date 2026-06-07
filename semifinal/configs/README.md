# semifinal/configs/

Runtime configuration files consumed by the mapping drone (Challenge 1) and,
later, by K's Hula swarm controller (Challenge 2). Everything in here is
plain JSON so it can be hand-edited at the venue without re-flashing or
re-deploying code.

## Files

### `waypoints_2x2_default.json`
The current hard-coded 2x2 survey pattern used by `mapping_drone.controller`
when no `--waypoints-from-json` flag is passed. This file MIRRORS the
constant `DEFAULT_WAYPOINTS` in `controller.py`; if you change one, change
the other (or pass this file explicitly via `--waypoints-from-json`).

Schema:
```
[
  [x, y, z],     # meters, NED-ish world frame, z is positive altitude
  [x, y, z],
  ...
]
```

### `waypoints_unknown.json`
Empty placeholder. At the venue we measure the actual arena and either:
- copy `waypoints_2x2_default.json` over this, or
- hand-edit a fresh 3x3 / 4x4 grid into the empty list.

Loaded via `--waypoints-from-json configs/waypoints_unknown.json`.

### `valid_ids_unknown.json`
Lookup file consumed by the `validity.py` rule #6 ("lookup"). Populate on
Day-1 once the organisers publish the official valid/invalid ArUco ID
set. Until then both lists are empty and the rule effectively no-ops.

Schema:
```
{
  "valid_ids":   [int, int, ...],
  "invalid_ids": [int, int, ...],
  "note":        "free-form human note"
}
```

## Day-1 swap procedure

1. Org publishes the rule (waypoint geometry / valid IDs).
2. Edit the relevant `*_unknown.json` in place (or copy the default over it).
3. Re-launch the controller with the matching `--waypoints-from-json` and
   `MAPPING_DRONE_VALIDITY_LOOKUP=/path/to/valid_ids_unknown.json`.
4. No code change, no rebuild.

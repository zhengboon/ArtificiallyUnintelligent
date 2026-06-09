# semifinal/configs/

Runtime configuration files consumed by the mapping drone (Challenge 1) and,
later, by K's Hula swarm controller (Challenge 2). Everything in here is
plain JSON so it can be hand-edited at the venue without re-flashing or
re-deploying code.

## Files

> **Altitude note (2026-06-08):** All templates now use 4.0m altitude after
> org confirmed 3.5m minimum flight height on 2026-06-08 12:18. 4.0m gives
> a 0.5m safety margin.

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

### `arena_3x3.json`, `arena_4x4.json`, `arena_6x6.json`, `arena_8x8.json`
Pre-staged 4-corner survey patterns for common arena sizes. Same schema as
`waypoints_2x2_default.json` (list-of-[x, y, z], metres). All four templates
fly at 4.0 m to clear the 3.5 m minimum flight height the org confirmed on
2026-06-08.

Day-1: once the org publishes arena dimensions, pass the closest match via
`--waypoints-from-json configs/arena_NxN.json`. If none match exactly,
copy the nearest one to `waypoints_unknown.json` and edit in place.

### `valid_ids_unknown.json`
Lookup file consumed by the `validity.py` rule #6 ("lookup"). Populate on
Day-1 once the organisers publish the official valid/invalid ArUco ID
set. Until then both lists are empty and the rule effectively no-ops.

### `valid_ids_even.json`, `valid_ids_odd.json`, `valid_ids_below50.json`, `valid_ids_whitelist_example.json`
Pre-staged lookup templates covering the three rule shapes we expect from
the org plus one whitelist example:

- `valid_ids_even.json`: even ArUco ID = VALID, odd = INVALID. IDs 0-50
  enumerated; extend manually if org uses higher IDs.
- `valid_ids_odd.json`: opposite of even.
- `valid_ids_below50.json`: ID < 50 = VALID, ID >= 50 = INVALID. Mirrors
  the existing `id_below_50` stub rule in `validity.py`.
- `valid_ids_whitelist_example.json`: small explicit set (3, 7, 12, 19,
  24) with empty `invalid_ids`. On Day-1 the operator REPLACES the list
  with the org's actual valid set. Empty `invalid_ids` means anything not
  listed is treated as unknown (not classified).

Loaded via `MAPPING_DRONE_VALIDITY_LOOKUP=/path/to/<file>.json`.

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

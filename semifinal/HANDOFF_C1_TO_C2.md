<!--OPDOC-BANNER-->
> ⚠️ **SUPERSEDED — to run the mapping drone use [OP_DOC.md](OP_DOC.md).** This file is kept for historical detail only; the live decision-tree runbook is OP_DOC.md.

# HANDOFF_C1_TO_C2

> **IMPORTANT — C2A landing coords come from Discord, NOT this artifact.**
> Per finals brief slide 6 ("Refer to Discord for the coordinates of valid
> landing points"), the authoritative C2A waypoint source is the org-published
> Discord coordinates. `landing_pads.json` is **internal cross-check only**:
> useful for confirming which ArUco IDs we saw at which world-XY, but the
> swarm controller must take the Discord coords as ground truth. The
> "Consumption pattern" section below describes the file shape and a planning
> path that predated the org clarification — keep it as a spec, but revise
> once K wires the Discord-coord ingest in.

Challenge 1 (mapping drone, owned by Z) hands a list of detected landing pads
to Challenge 2A (Hula swarm controller, owned by K) via the on-disk artifact
`landing_pads.json`. This file is Z's spec to K of the JSON shape that
`mapping_drone/run_writer.py` writes and that `swarm_controller.py` should
consume for 2A waypoint planning. (Note: `swarm_controller.py` is currently
a stub — see the file header; the consumption pattern below is a spec for the
future implementation, not a description of running code.)

The on-disk schema is the single source of truth — both sides agree on it
explicitly here so the two pipelines can be developed and exercised
independently right up to Day-1 integration.

## Path

```
D:/hackerverse/semifinal/mapping_drone/runs/run_<YYYYMMDD_HHMMSS>/landing_pads.json
```

`--runs-dir` defaults to `mapping_drone/runs` (relative to the cwd that
launched `python -m mapping_drone.controller`). The runbook launches from
`semifinal/`, so the canonical path above holds without overrides. K should
glob `runs/run_*/landing_pads.json` and pick the lexicographically last
directory (timestamps sort correctly).

## Top-level schema

```json
{
  "run_ts": "20260610_104215",
  "count": 1,
  "pads": [ ... ]
}
```

| Field      | Type   | Notes                                                      |
| ---------- | ------ | ---------------------------------------------------------- |
| `run_ts`   | string | `YYYYMMDD_HHMMSS` system local time (controller.py uses naive `datetime.now()`); matches the parent directory suffix. |
| `count`    | int    | `len(pads)`. Convenience; derive from `pads` if it diverges. |
| `pads`     | array  | Sorted ascending by `aruco_id`. May be empty.              |

## Per-pad schema

Each entry in `pads[]` is the on-disk projection of one `ArucoSighting`
record (defined in `mapping_drone/mapping.py`). All fields are written by
`RunWriter._pad_for_serialization`; absent or unparseable source fields are
serialised as `null` rather than fabricated.

| Field                     | Type                              | Example                                | Notes |
| ------------------------- | --------------------------------- | -------------------------------------- | ----- |
| `aruco_id`                | int                               | `150`                                  | Canonical key; unique per pad. Never null on a real pad (malformed sightings are dropped upstream). |
| `world_xyz_m`             | `[float, float, float]` or `null` | `[1.42, -0.37, 0.02]`                  | World ENU in metres: `[north, east, up]`. `null` if depth at the marker pixel was invalid that frame. |
| `pixel_center`            | `[int, int]`                      | `[321, 244]`                           | RGB pixel centroid `(u, v)` at the highest-confidence sighting. |
| `bbox`                    | `[int, int, int, int]`            | `[298, 220, 344, 268]`                 | `[x1, y1, x2, y2]` in RGB pixels. |
| `image_path`              | string or `null`                  | `"<run>/markers/marker_0150_0003.jpg"` | Absolute or run-relative path to a bbox-overlaid JPG snapshot. |
| `validity_classification` | bool or `null`                    | `true`                                 | `true` = land here, `false` = skip, `null` = rule did not classify (see consumption notes). |
| `first_seen_at`           | float (epoch seconds)             | `1717999335.412`                       | Earliest sighting timestamp; preserved across replacements. |
| `last_seen_at`            | float (epoch seconds)             | `1717999341.087`                       | Most recent sighting timestamp. |
| `confidence`              | float in `[0.0, 1.0]`             | `0.87`                                 | Detector confidence at the stored sighting. |
| `sighting_count`          | int                               | `4`                                    | Total observations of this ID across the run (cumulative, not reset on replacement). |

Worked example (single-pad smoke run, marker id 150 detected on the
Hula-side pad):

```json
{
  "run_ts": "20260610_104215",
  "count": 1,
  "pads": [
    {
      "aruco_id": 150,
      "world_xyz_m": [1.42, -0.37, 0.02],
      "pixel_center": [321, 244],
      "bbox": [298, 220, 344, 268],
      "image_path": "mapping_drone/runs/run_20260610_104215/markers/marker_0150_0003.jpg",
      "validity_classification": true,
      "first_seen_at": 1717999335.412,
      "last_seen_at": 1717999341.087,
      "confidence": 0.87,
      "sighting_count": 4
    }
  ]
}
```

## Consumption pattern for `swarm_controller.py` (internal cross-check use only)

Reminder: per the top-of-doc IMPORTANT block, the real C2A waypoint source is
the org-published Discord coordinates. The pattern below describes how the
swarm controller would consume `landing_pads.json` if used as a cross-check,
and is the spec for the still-stubbed `swarm_controller.py`.

1. Load:

    ```python
    import json
    from pathlib import Path

    run_dir = sorted(Path("mapping_drone/runs").glob("run_*"))[-1]
    with (run_dir / "landing_pads.json").open(encoding="utf-8") as f:
        payload = json.load(f)
    pads = payload["pads"]
    ```

2. Filter by `validity_classification`:

    - `True` -> land here (push onto the 2A target list).
    - `False` -> skip (do not target).
    - `None` -> unknown / unclassified. **Decision tree TBD** pending
      Rank 1 in `ORG_TICKETS_DRAFT.md` (the VALID/INVALID rule itself).
      Default behaviour for the Day-1 build: treat `None` the same as
      `False` (skip) so the swarm
      only commits to pads the rule definitively accepted. Revisit once
      org publishes the rule and `validity.py` can emit a non-`None`
      classification for every ID.

3. Drop pads with `world_xyz_m is None` regardless of validity — without a
   world position there is nothing to fly to.

4. Convert `world_xyz_m` (mapping drone's world ENU, metres) to Hula's
   coordinate system (`x = right`, `y = forward`, `z = up`, **centimetres**).
   The mapping drone's world frame is `[N, E, U]` in metres (see the
   coordinate-frame callout in `mapping_drone/README.md`); Hula's "forward"
   is the arena-local +y axis defined by the takeoff pad heading. Both the
   unit (m -> cm) and the axis convention (NEU -> right/forward/up)
   differ. The conversion is:

    ```python
    # ENU metres -> Hula right/forward/up centimetres.
    # Caveat: the in-arena Hula forward axis is set by takeoff heading. If
    # that heading is not arena-north on Day-1, the (N, E) -> (right, fwd)
    # swap below is wrong and K must rotate by the takeoff yaw first.
    n_m, e_m, u_m = pad["world_xyz_m"]
    hula_x_cm = e_m * 100.0       # east  -> right
    hula_y_cm = n_m * 100.0       # north -> forward (assumes takeoff faces north)
    hula_z_cm = u_m * 100.0       # up    -> up
    ```

   This convention matches the existing pyhulax helpers we use elsewhere
   in the repo. If the takeoff heading differs at the venue, apply the
   yaw rotation before the unit conversion, not after.

## Handoff contract

The operative contract is **(b) snapshot-read after C1 finalises** — and
this is the only operative mode because finals brief slide 12 schedules C1
on Day 1 (Wed 1430-1800, Uni only) and C2 on Day 2 (Thu 1330-1600). The two
challenges cannot share a slot, so the parallel-on-same-slot variant is moot.

- C1 runs to completion (or aborts via the emergency_land path); either
  way `RunWriter.finalise` flushes the final `landing_pads.json` plus
  `run_summary.json` to disk.
- K's `swarm_controller.py` is launched on Day 2, reads `landing_pads.json`
  once at start as a cross-check (Discord coords remain the authoritative
  C2A waypoint source — see top-of-doc IMPORTANT block). No live polling,
  no re-reading.

Recorded for completeness — these alternates are no longer in play given
slide 12, but the file shape supports them if the situation ever changes:

- **(a) Live read while C1 is still running.** `RunWriter._write_pads_locked`
  rewrites `landing_pads.json` atomically (tmp + replace) on every new
  sighting, so K *could* poll the file mid-flight without ever seeing a
  half-written JSON. Not applicable on a two-day sequential schedule.
- **(c) Judge-side artifact submission.** If org ever wants the pad list
  handed in as a deliverable rather than consumed inline, `landing_pads.json`
  is already the canonical artifact — K's controller does not need to change,
  we just hand the file to the judge. Re-read of an inbound judge-edited
  file would still be safe because the schema is stable.

All three modes consume the same bytes; the contract is purely about *when*
K reads them.

## Open questions

- **Validity rule** (Rank 1 in `ORG_TICKETS_DRAFT.md`). Until org publishes
  the ID -> valid/invalid mapping, `validity.py` is running on a placeholder
  (even = valid, odd = invalid) and the `None` branch above is speculative.
  The `MAPPING_DRONE_VALIDITY` env override lets us swap the rule in one
  shell variable on Day-1.
- ~~**Parallel vs sequential**~~ — resolved by finals brief slide 12: C1 on
  Day 1, C2 on Day 2. Sequential across days, not parallel within a slot.
  Snapshot-read (b) is the only operative contract.

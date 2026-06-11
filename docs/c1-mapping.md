---
layout: default
title: Challenge 1 — Mapping
---

# Challenge 1 — Mapping drone

> Autonomously map the arena from above and classify each landing pad as valid or invalid for landing. Mapping speed and accuracy of validity classification are the scored axes.

[← Back to home]({{ '/' | relative_url }})

---

## The mission

A mapping drone flies over a fenced arena (≈5.5 × 11 m, see-through net walls). The arena contains five drone landing pads, each with an ArUco marker placed *beside* (not on) the pad. The marshal announces the valid + invalid marker IDs before the assessment begins. We must produce:

1. A **top-down depth map** of the arena.
2. **An image of every ArUco marker** sighted.
3. **A classification** of each landing pad as valid or invalid.

All artifacts written to one timestamped run folder for the judges.

---

## Flight envelope (hard caps in the control loop)

- **Speed:** 0.3 m/s horizontal cap (org rule, slide 5). Velocity setpoints are clamped at construction time so a higher operator request is silently floored to 0.3 m/s with a log warning.
- **Altitude:** default 2.5 m, hard cap 3.2 m. The arena cage net sits at ≈3.5 m. Anything above 3.2 m risks net contact; the controller's altitude clamp is in the closed-loop velocity step, not an init check.
- **Time:** 7 min per attempt with a 1-minute buffer under the org's 8-minute hard cap (slide 5).
- **Crash policy:** the org awards no re-assessment if the drone crashes (slide 18). Safe-first is therefore not a preference — it is the only viable strategy.

---

## Coverage strategy — lawnmower, not SLAM

The cage's walls are a see-through net. Depth-based obstacle sensing reports random fragments through it, so any reactive avoidance system would steer the drone into the net or chase phantom obstacles outside it.

We therefore use a **deterministic boustrophedon (lawnmower) sweep**:

- Lanes are centred on the arena origin with a 1.0 m wall margin (widened from 0.7 m after a margin-sensitivity sweep).
- Geometry guarantees full coverage; nothing depends on wall sensing.
- Pre-computed waypoint lists for several arena sizes ship in `semifinal/configs/arena_*.json`.

The closed-loop velocity controller polls the current pose (10 Hz), computes error to the waypoint, and sends a trapezoidal velocity-profiled NED setpoint with the 0.3 m/s cap and a slow-down approach into each waypoint.

---

## Perception — multi-dictionary ArUco

The official ArUco dictionary was announced only on the day. We hedged at *every* scan by detecting two dictionaries per frame:

- `cv2.aruco.DICT_7X7_1000` — the announced dictionary
- `cv2.aruco.DICT_6X6_250` — the pyhulax sample-code default + a likely common choice

Cost is roughly 2× per-frame detection latency, which is cheap compared to the cost of guessing wrong. For each marker found:

1. Compute pixel centre and bounding box.
2. Look up depth at the centre pixel.
3. Deproject (`X = (u-cx)·Z/fx`, `Y = (v-cy)·Z/fy`, `Z = depth_m`) into the camera frame.
4. Apply the drone-to-world transform (gimbal pitch + drone pose) into the arena UWB frame.
5. De-duplicate by ID across waypoints.
6. Classify via the validity lookup table.

The depth-deprojection math is shared between marker localisation and the top-down occupancy grid, so a pixel-to-world bug is caught in either.

---

## Pose — redundant, automatic fallback

Indoor UWB-frame ambiguity is the single most common failure mode of indoor missions. Our defence is layered:

- **Primary:** Flight-Controller-fused NED, read from `telemetry.position_velocity_ned()` over MAVSDK. Robust to UWB anchor dropouts.
- **Secondary:** `/uwb_tag` PoseStamped on ROS2, with an ENU→NED axis swap (`n = pose.y`, `e = pose.x`, `alt = -pose.z`).
- **Tertiary:** position-hold if both go stale.

`--pose auto` (default) prefers FC NED, watches its staleness, and auto-falls-back to UWB when the FC stream degrades. `--pose fc` and `--pose uwb` are operator overrides.

The `survey_box.py` tool *measures* the arena→NED frame at venue setup so we never have to assume axis orientation. It produces the centred-origin waypoint JSON that the mission consumes.

---

## Camera — D435 (dev) vs D430 / D450 (venue)

We developed on a Realsense D435 (depth + RGB). The venue drones carry a D430 or D450 — the depth modules without RGB. Our `realsense.py` adapter detects this at startup:

- If RGB is present, use the standard color stream for ArUco.
- If not, synthesise BGR from the IR stream and toggle the IR emitter off during ArUco frames so the marker pattern isn't corrupted by dot projections.

Auto-fallback. No operator intervention. Logged at INFO so we know which path is live.

---

## Safety watchdogs (in the control loop, not on a checklist)

Five run-time watchdogs gate every iteration:

| Watchdog | Trigger | Action |
|---|---|---|
| Battery | < 15 % | Emergency land in place |
| Pose loss | UWB + FC both stale > 5 s | Emergency land |
| Position-stuck | drone moves < 0.3 m in 30 s (excluding scan dwell) | Emergency land |
| Setpoint failure | offboard `set_velocity_ned` raises 5× consecutively | Emergency land with `abort_reason` |
| Max flight time | 7 min (1-min buffer under org's 8-min cap) | Emergency land |

The stuck-watchdog skips during the per-waypoint scan phase (state name starts with `SCAN_WP_`) so deliberate hovers don't trip it.

---

## Output — the judge artifact

Every run produces:

```
runs/run_<TIMESTAMP>/
├── STATUS.txt           ← human-readable, atomically rewritten every 5 s
├── run_summary.json     ← machine-readable full record
├── landing_pads.json    ← per-pad: id, world XYZ, validity (judge-readable JSON)
├── top_down.png         ← occupancy grid render
├── top_down.npy         ← raw NumPy grid for downstream analysis
├── markers/             ← per-sighting JPEG with bounding box + ID
└── log.txt              ← controller log
```

`landing_pads.json` is also the contract C2A's swarm controller can consume directly — same coordinate frame, no re-survey.

---

## Decision tree on the day

The full venue runbook is a 6-step decision tree with lettered fallbacks at each step:

```
Step 0  → fingerprint        (which drone is this? which serial port? which camera?)
Step 1  → sensors            (UWB, FC, camera all alive?)
Step 2  → check              (connect + read pose, no arm)
Step 3  → frame              (measure arena↔NED via survey_box)
Step 4  → nofly              (full perception pass, no arm — proves detection works)
Step 5  → fly                (autonomous lawnmower sweep)
Step 6  → artifacts          (retrieve run dir → USB)
```

See `semifinal/OP_DOC.md` in the repo for every command verbatim.

[Challenge 2 →]({{ '/c2-swarm' | relative_url }})

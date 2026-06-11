---
layout: default
title: Design principles
---

# Design principles

> Five rules drove every architectural decision. Together they explain why the system looks the way it does — and why it survived contact with hardware.

[← Back to home]({{ '/' | relative_url }})

---

## 1. Intelligence drives the strike

Challenge 1 isn't a standalone deliverable. Its output — a per-pad validity classification with world coordinates — is the C2 swarm's *targeting list*. We designed `landing_pads.json` as a **contract**:

```json
{
  "pads": [
    {"aruco_id": 67, "world_xyz_m": [2.31, 4.88, 0.00], "validity_classification": "valid"},
    ...
  ]
}
```

C2A's swarm controller reads it directly. Same coordinate frame, same canonical schema. The two challenges share one operational world.

---

## 2. Coverage over cleverness

The arena cage has see-through netting. Depth sensors return random fragments through it, so any reactive obstacle-avoidance system would either chase phantoms outside the cage or steer the drone into the net.

We therefore picked **deterministic full-coverage search** everywhere:

- **C1 mapping:** a pre-planned boustrophedon (lawnmower) sweep at controlled altitude. Geometry guarantees full coverage.
- **C2B hunt:** wall-following perimeter + 360° spin-scan at each corner.

Both are predictable, debuggable, and *immune to the see-through netting that defeats depth-based obstacle sensing*. SLAM and reactive exploration look better in a paper. Deterministic sweeps survive the venue.

---

## 3. Degrade, don't fail

Every critical path has a fallback so a single sensor or link problem *downgrades* a run instead of ending it:

| Subsystem | Primary | Fallback | Switch mechanism |
|---|---|---|---|
| **Pose** | FC-fused NED via MAVSDK | UWB `/uwb_tag` via ROS2 | `--pose auto` switches when FC goes stale |
| **Camera** | RGB color stream | Synthesised BGR from IR (emitter toggled off for ArUco frames) | `realsense.py` auto-detects RGB availability |
| **Marker dictionary** | DICT_7×7_1000 (announced) | DICT_6×6_250 (sample-code default) | Both scanned every frame |
| **Transport** | MAVSDK (`serial:///dev/ttyS6:921600`) | PX4-ROS2 via micro-XRCE-DDS | Operator runs `px4_mission.py` instead of the default |
| **MAVSDK address** | `serial:///dev/ttyS6:921600` | 4 other addresses pre-baked | Controller tries each with 5 s timeout |

Each fallback is tested either by smoke tests (camera RGB↔IR, multi-dict) or by explicit operator action (alternate transport). None are speculative.

---

## 4. Safe-first

> *"Throughout the challenge, teams will not be given re-assessment attempts should the drone crash due to any reasons."* — slide 18

A crash equals zero points for the run, with no recovery. Safety is therefore *the* primary constraint, not a secondary one. It lives **inside the control loop**:

- **Hard altitude cap** (3.2 m) below the cage net (≈3.5 m). The clamp is applied at every velocity step, not on init.
- **Speed cap** 0.3 m/s for the mapping drone, applied at construction time.
- **Five run-time watchdogs** — battery, pose-loss, position-stuck, setpoint-failure, max-flight-time — every one of which auto-lands the drone.
- **Stuck-watchdog tuning:** widened to 30 s window after the 0.3 m/s cap landed (a slow drone is legitimately motionless during scan dwells; the original 20 s window caught false stalls).

No-arm modes (`--check`, `--nofly`) exist so an operator can validate every subsystem on the drone in less than a minute before committing to flight.

---

## 5. Frame discipline

Indoor UWB-frame ambiguity is the number-one failure mode of indoor missions. You can lose a competition to a silent ENU↔NED axis swap.

Our defence:

- **One coordinate world** for both challenges — arena UWB centred origin, axes locked to the cage corners.
- **`uwb.py` does the ENU→NED swap** in one well-tested place (`n = pose.y`, `e = pose.x`, `alt = -pose.z`). Nothing else in the codebase touches the swap.
- **`survey_box.py`** *measures* the arena-to-NED frame mapping at venue setup by hand-flying a known fly-path and watching the telemetry. We never assume which way north points.
- **Frame callout in code comments** — every module that touches world coordinates has an explicit ENU vs NED note in its docstring.

The cost is one operator step (~2 min) before the first scored run. The benefit is that we never had to debug "the drone flew the wrong way" mid-run.

---

## Why these specifically

These aren't generic principles — each one is a direct response to a specific failure mode we either saw in dev or anticipated for the venue:

| Principle | The failure it prevents |
|---|---|
| Intelligence drives the strike | Building C1 and C2 independently and re-surveying twice |
| Coverage over cleverness | Reactive sensing failures from see-through netting |
| Degrade, don't fail | Single-point hardware drops ending the run |
| Safe-first | Crash → zero points → no recovery |
| Frame discipline | Silent axis errors that look like "everything is wrong" |

[Engineering log →]({{ '/engineering' | relative_url }})

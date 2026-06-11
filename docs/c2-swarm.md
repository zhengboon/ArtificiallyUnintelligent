---
layout: default
title: Challenge 2 — Swarm
---

# Challenge 2 — Hula swarm

> Two halves. **2A — Deployment:** land three Hula drones on three valid pads. **2B — Ambush:** hunt five RoboMaster ground robots and tag each with a snapshot of its on-body ArUco marker.

[← Back to home]({{ '/' | relative_url }})

---

## What we knew vs. what was clarified late

Challenge 2 had several late-breaking surprises from the org's Discord:

- The 5 RoboMaster targets carry **ArUco markers**, not coloured silhouettes. Detection is `cv2.aruco`, not a custom YOLO. *(2026-06-06)*
- An ArUco marker is also placed *beside* every Hula landing pad (mirroring Challenge 1). The Hula can use it as a final visual landing aid. *(2026-06-06)*
- **The map layout is not provided.** Arena dimensions must be discovered live. *(2026-06-06)*
- All 5 RoboMasters' marker size is **20 cm × 20 cm**. Exact dictionary announced on the day. *(2026-06-06)*
- Of the 5 ground robots, **2 are driven by another team** as adversarial convoy operators; we drive 2 convoy bots for THE WIENERS in their slot. *(slide 14)*

Our swarm design accommodates all of these — ArUco-first detection, UWB-positioned landing with visual confirmation, no hard dependence on arena dimensions.

---

## Architecture overview

```
 dola.py (UDP discovery: plane_id → IP)
        │
        ▼
 swarm_controller.py  ── per-drone state machine ───────────────
   Phase A (DEPLOY): UWB → fly to landing zone → visual confirm → land
   Phase B (HUNT):   perimeter waypoints + 360° spin-scan
        │  position from ──► UWBParserThread.py (tag_id → x, y)
        │  motion via ─────► pyhula  send_manual_control
        ▼
   central video: all drones' streams aggregated → ArUco detection
```

Why a single central detector? Multi-stream from one machine simplifies dedup (one detection table, not three), and lets us add expensive visual sanity checks (multi-frame confirmation) cheaply.

---

## Phase A — Deployment (Challenge 2A)

### Inputs

- **From the org:** the Discord-published landing-pad coordinates (5 points). The validity split (which 3 of the 5 are valid) is announced on the day.
- **From C1:** `landing_pads.json` cross-checks the validity split against what our mapping drone saw. Same coordinate frame (arena UWB centred origin), so it's a lookup.

### Per-drone state machine

```
IDLE → TAKEOFF → CRUISE_TO_ZONE → APPROACH → ARUCO_VISUAL_LOCK → DESCEND → LANDED
                                       │                                 │
                                       └── timeout / no lock ──► HOLD ──┘
```

- **CRUISE_TO_ZONE:** UWB-driven `send_manual_control` velocity vectors toward the landing-pad coordinate at 0.5 m/s cap (org rule, slide 6). Recommended altitude 1.1 m (slide 6) — well below the cage net.
- **APPROACH:** slow profile into the final 1 m horizontally with altitude held.
- **ARUCO_VISUAL_LOCK:** confirm we see the pad's own ArUco marker in the down-facing camera before committing to descent.
- **DESCEND:** controlled descent with horizontal hold; pyhula handles the touchdown.

Strict rule from the org: **no flying over obstacles** (slide 6). Our waypoint planner therefore keeps every drone over open floor — the deployment path is a direct UWB-frame straight line from takeoff to each zone, never over a pad or the convoy.

### Coordination across 3 drones

Drones launch staggered to avoid mid-air conflict; each operates an independent state machine with no peer-to-peer talk. The shared resources are the central video pipeline and the swarm controller's main loop, which dispatches events back to each per-drone task.

---

## Phase B — Hunt (Challenge 2B)

### Inputs

- The 5 RoboMasters loiter in the cage. 3 follow an autonomous patrol; 2 are adversarial operators (another team driving with the same intent — evade us, harass us).
- Each RoboMaster carries an ArUco marker on its top surface.

### Strategy

Each Hula drone runs the same coverage routine:

1. **Perimeter waypoints** at 1.1 m altitude trace the cage interior just inside the obstacle ring.
2. **360° spin-scan** at each corner — a slow yaw rotation with the down-camera streaming continuously to the central detector.
3. The central detector runs `cv2.aruco` on the aggregated video and emits `(robomaster_id, detected_at_drone_n, world_xyz, frame_jpeg)` events.
4. Each robot is confirmed via **2–3 frames** to reject noise.

Detection coverage is *temporal* (the spin) and *spatial* (3 drones at 3 corners cover the cage from different angles, defeating one-side ArUco occlusion).

### Snapshots = judge artifact

Per slide 7 of the org's brief, *"teams will have to print the outputs from the Aruco marker on the ground robot to represent successful tagging."* For each confirmed RoboMaster we save:

- The full frame with the marker's bounding box and ID overlay.
- The world coordinate at detection time.
- A timestamp.

All saved to the run directory, copied to USB, presented to the judge.

---

## Convoy operator role (slot #24)

Our schedule includes a second responsibility on Day 2: at slot #24 we operate two convoy RoboMasters *against* THE WIENERS. The same role STD plays against us at our slot #3.

Our convoy strategy:

- Two of us split the cage half each.
- Keep moving — don't sit still long enough to be tagged.
- Stay near obstacles where Hulas can't approach from above (no flying over obstacles, slide 6).
- Track the opposing Hula's perimeter waypoints by ear (Hula motor pitch) and zig away from its sweep.

This is operationally the *fun* slot of the day.

---

## Speed + altitude caps (Hula)

- **Max speed:** 0.5 m/s (slide 6)
- **Recommended altitude:** 1.1 m (slide 6)
- **No flying over obstacles** (slide 6) — hard rule. Path planning respects obstacle footprints, not just altitude.
- **Per-attempt cap:** 8 minutes (slide 6)

[← Challenge 1]({{ '/c1-mapping' | relative_url }})
&nbsp; · &nbsp;
[Design principles →]({{ '/principles' | relative_url }})

# Scoring Playbook — what we know, what we guess, how we run

Companion to `runbook.md` and `DAY1_RUNBOOK.md`. Read once before Day-1, again before each scored run. Weights are guessed — update the moment org publishes the rubric (Ticket #4 in `ORG_TICKETS_DRAFT.md`).

---

## What the org has said about scoring

- **Challenge 1** (slides 2026-06-05): "Understanding of the concept + Mapping speed + Accuracy of identifying landing sites as valid or invalid."
- **Challenge 2A** (slides): "Successful landings + accurate placement on designated zones + minimum time."
- **Challenge 2B** (slides + 2026-06-06 ArUco-on-robots clarification): "Successful + accurate snapshots + minimum time."
- Exact point weights NOT published. Filed as **Ticket #4** in `ORG_TICKETS_DRAFT.md`. Re-read this file after the briefing and overwrite the hypothesis section with announced weights.

---

## Our scoring hypothesis (until org publishes)

Assume the rubric weights are roughly equal across the 3 dimensions per challenge. Optimise per-challenge as follows.

### Challenge 1 — Reconnaissance

- **Completeness > speed on run 1.** Find ALL pads. A missed pad is unrecoverable; a slow run is recoverable.
- **Accuracy is binary per pad.** Each pad is either correctly classified valid/invalid or it isn't — partial credit is unlikely. Verify `landing_pads.json` per-pad classification matches the announced validity rule before submitting.
- **Run 2 = minimise mission time** now that the layout is known. Trim waypoints to known pad neighbourhoods; raise altitude only if detection still works at the higher alt.

### Challenge 2A — 3-Hula landings

- **Land all 3 Hulas successfully** (binary per drone).
- **Accurate placement on designated zone**: assume +/-0.5 m = full points, +/-1.0 m = partial, miss = 0. Until org publishes, treat 0.5 m as the safe target radius.
- **Time below max** matters but is dominated by the landing-success term. Don't sacrifice a landing for 10 s of speed.

### Challenge 2B — RoboMaster hunt (ArUco on robots)

- **Find all 5 robots** — count of unique ArUco IDs detected.
- **Crisp snapshots**: ArUco marker visible AND bounded bbox in-frame. Blurry / clipped frames likely don't count. Take 2-3 frames per sighting if time allows.
- **Total time** is the tiebreaker.

---

## Run strategy: safe-then-aggressive

- **Run 1 = SAFE.** Bank a confirmed score. Conservative altitude — **4.0 m default** (above the 3.5 m floor org set on 2026-06-08 12:18; the older 1.5-2.0 m guidance is dead), conservative speed (0.3-0.5 m/s), short waypoint list. Pick the closest pre-staged template at venue: `configs/arena_3x3.json`, `arena_4x4.json`, `arena_6x6.json`, or `arena_8x8.json` (all bumped to 4.0 m for the 3.5 m floor). Fallback if none match: `waypoints_2x2_default.json` (also 4.0 m). Goal: have something to submit.
- **Run 2+ = AGGRESSIVE.** Tune based on run-1 deductions:
  - Higher altitude only if detection still works (verify with a mock dry-run on the captured top-down).
  - Faster speed only if UWB tracking stays clean (no spikes in sniffer log).
  - Trim waypoints to known pad neighbourhoods for C1; widen search box for C2B if any robot was missed.
- **Never skip the safe run.** If run 1 fails for an environmental reason (UWB drift, Realsense disconnect), do a second SAFE run before going aggressive.

---

## Hard caps for safety

- `--max-flight-time-s`: **240** default (4 WPs x ~10 s/wp + 200 s buffer). Lower for short scored slots; never raise above battery margin.
- **Consecutive velocity failures**: 5. The controller aborts after 5 back-to-back `_send_velocity` warnings — this is the safety abort committed for this slot.
- **Altitude floor**: **3.5 m minimum** (org 2026-06-08 12:18). All pre-staged templates default to **4.0 m** (3.5 m floor + 0.5 m margin). Do NOT use the older 1.5-2.0 m guidance — those altitudes are below the floor and the run will be rejected/unsafe.
- **Battery cutoff**: per-drone failsafe. Ground when <20%. Do not arm a drone below 30% for a scored run.
- **Geofence**: rely on Hula's own — we do not enforce in code. Confirm with org during setup that geofence is active for our slot.

---

## Failure mode triage

- **ArUco 0 sightings**: check `--aruco-dict` matches org announcement (Ticket #2). Increase frames-per-waypoint if time allows. If still 0, mount/lighting is the suspect — re-do the marker-on-floor camera mount check from `DAY1_RUNBOOK.md`.
- **UWB drift**: bring the sniffer back up (`python3 -m tools.uwb_sniffer`), confirm topic name + NED axes (Ticket #5). If pose jumps >1 m between adjacent frames, do not arm.
- **Realsense disconnect mid-flight**: swap cable on landing; `PROFILE_CANDIDATES` in `realsense.py` handles graceful degrade across 640x480@30 / 848x480@30 / 1280x720@30 / 640x480@15.
- **Hula offboard refuses**: battery <20% OR RC mode wrong. Cycle drone, verify RC mode, retry.
- **Velocity setpoints failing repeatedly**: the controller will hit the 5-consecutive-failure abort. Land, inspect `log.txt` for the underlying MAVSDK exception, do not retry blind.
- **RGB stream missing on drone** → use `--use-ir-for-aruco` (emitter toggle, may halve effective fps). Org confirmed 2026-06-08 12:18 the mapping drone uses D430 + D450, neither of which has an RGB sensor in the bare module. If the venue did not bolt on a separate RGB camera, the color-frame path in `ArucoDetector` returns empty — pivot to IR-with-emitter-toggle and accept the fps hit.

---

## Roles during a scored run

- **K (keyboard)**: types the command, holds Ctrl-C ready. Does NOT watch logs — eyes on the drone.
- **Z (screen)**: tails `STATUS.txt` + `log.txt` live. Calls out detections + anomalies. Owns the abort call if numbers go wrong.
- **A (judge-talker)**: captures the scored result on paper / phone, handles judge questions, runs USB copy after each run.

---

*Scoring Playbook v1. Weights are guessed; rubric arrives via Ticket #4. If something here contradicts `runbook.md`, `runbook.md` wins for event flow; this file wins for per-challenge scoring intent.*

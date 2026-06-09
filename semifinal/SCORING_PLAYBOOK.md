# Scoring Playbook — confirmed rubric, strategy, hard caps

Companion to `runbook.md` and `DAY1_RUNBOOK.md`. Read once before Day-1, again before each scored run. Rubric confirmed from org finals brief 2026-06-09 (slide 9). Authoritative source: `finals_brief_extracted.md`.

---

## Confirmed rubric (slide 9 of finals brief 2026-06-09)

University Total = 100% across 6 criteria. For S/N 1, 3 & 4 the priority order is the sequence shown (detected → verified → timing, etc).

- **S/N 1 (15%)** — Challenge 1: number of landing pads **detected** (image recognition) + number of landing points **verified** (ArUco marker) + **timing**. Priority order: detected, verified, timing.
- **S/N 2 (15%)** — Challenge 1: **accuracy of distance** of obstacles + landing pads from the **reference point** (using depth map).
- **S/N 3 (30%)** — Challenge 2A: number of **landings within hoop** + timing.
- **S/N 4 (30%)** — Challenge 2B: number of **ArUco detections** (on RoboMasters) + timing.
- **S/N 5 (4%)** — Bonus: completion of **Counter UAS tech showcase** (photo of drone at booth + screenshot of zone-explored page per slide 10).
- **S/N 6 (7%)** — Bonus: **overall concept explanation**. Format (verbal vs written) unclear — Day-1 briefing will clarify.

Pre-Uni split (for reference): 44% C2A + 44% C2B + 4% CUAS + 8% concept = 100% (no C1).

---

## Strategy implications

- **C1 dimension 1 (15%) — MAXIMIZE pad detection rate.** Priority order is detected → verified → timing, so a missed pad is worse than a slow run. Better to be slower + thorough than fast + incomplete. Cover the full arena; don't trim waypoints for time on the safe run.
- **C1 dimension 2 (15%) — DEPTH ACCURACY from the reference point.** This was not previously optimised. `OccupancyGrid` integrates the point cloud — verify accuracy at the venue against the **sample landing pad** the org provides (slide 20). Capture measured-vs-true distance for the sample pad before the scored run and trim systematic bias if any.
- **C2A (30%) — land within hoop.** Priority is landings, then timing. Conservative speed (0.3-0.4 m/s on Hula even though cap is 0.5), UWB pre-position, and ArUco visual aid for final descent (ArUco markers sit beside the Hula landing pads per 2026-06-06 clarification). Don't sacrifice a landing for seconds.
- **C2B (30%) — maximise ArUco detections.** Priority is detections, then timing. Finding all 5 RoboMasters beats finishing fast with 3. Take 2-3 frames per sighting; blurry/clipped frames likely don't count.
- **CUAS bonus (4%) — non-trivial.** Assign A to walk to the Counter UAS booth ("Above & Beyond: Skies & Space" zone, MBS L4) during a testing-window slot. Bring the drone for the photo, complete the BrainHack Frontier Exploration System task, screenshot the zone-explored page. 4% can be the gap between podium places.
- **Concept explanation (7%) — prepare a 3-min talk track.** Cover: team architecture (mapping → C1 artifacts → C2A coords from Discord → C2B hunt), what we built (controller, ArUco detector, occupancy grid, UWB sniffer fallback), what trade-offs we made (safe-first runs, IR fallback if no RGB on D430/D450, 4 m altitude above 3.5 m floor). Z owns the script, K and A rehearse.

---

## Hard caps from brief

- **Mapping drone max speed: 0.3 m/s** (slide 5). Currently `controller.py` `MAX_VEL_XY` may allow higher — clamp before scored run.
- **Hula max speed: 0.5 m/s** (slide 6). Recommended altitude **1.1 m**. **Strictly no flying over obstacles** — score invalidated if violated.
- **Per-attempt time: 8 min** for both C1 and C2 (slides 5, 6). Current `--max-flight-time-s` default is 240 s (4 min); we have budget to extend up to ~470 s if the run needs it.
- **Per-session testing: 5 min** (slide 17). Hula cage holds 2 teams at once.
- **Hula cage cooldown after each test: 20 min** — no re-queue allowed for 20 min after our session ends.
- **Mapping drone testing**: per-day per-team total allowance (not per-session); unused carries over within the day; non-transferable between teams.
- **1h no-testing penalty** for any rule violation or marshal-instruction ignore.
- **Crash = no re-assessment** (slide 18). Safe-first is mandatory, not a preference.

---

## Run strategy: safe-then-aggressive

A safe-first run that completes banks at minimum the dimension-1 partial credit on every scored S/N: 15% (some C1 detection) + 15% (some depth accuracy) + 30% (some C2A landings) + 30% (some C2B detections). Aggressive runs only happen after a safe score is already banked.

- **Run 1 = SAFE.** Bank a confirmed score. Conservative altitude — **4.0 m default** for the mapping drone (above the 3.5 m floor org set on 2026-06-08 12:18; the older 1.5-2.0 m guidance is dead). Mapping speed **0.3 m/s** (clamped to cap). Hula at **1.1 m** recommended altitude, **0.3-0.4 m/s** even though cap is 0.5. Short waypoint list, full arena coverage for C1. Pick the closest pre-staged template at venue: `configs/arena_3x3.json`, `arena_4x4.json`, `arena_6x6.json`, or `arena_8x8.json` (all bumped to 4.0 m). Fallback if none match: `waypoints_2x2_default.json`. Goal: bank S/N 1-4 partial points.
- **Run 2+ = AGGRESSIVE.** Tune based on run-1 deductions:
  - Mapping drone speed already at 0.3 m/s cap — gain time by trimming waypoints to **known pad neighbourhoods**, not by going faster.
  - Higher mapping altitude only if detection still works (verify with a mock dry-run on the captured top-down).
  - Hula speed only up to 0.5 m/s cap if UWB tracking stays clean (no spikes in sniffer log).
  - Widen search box for C2B if any robot was missed; tighten if all 5 found.
- **Never skip the safe run.** If run 1 fails for an environmental reason (UWB drift, Realsense disconnect), do a second SAFE run before going aggressive. **Crash = no re-assessment** — safe-first is mandatory.

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

*Scoring Playbook v2 (2026-06-09). Rubric confirmed from org finals brief slide 9; source: `finals_brief_extracted.md`. If something here contradicts `runbook.md`, `runbook.md` wins for event flow; this file wins for per-challenge scoring intent.*

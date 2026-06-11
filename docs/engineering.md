---
layout: default
title: Engineering log
---

# Engineering log

> Trade-offs we made on purpose, surprises we hit, and things we'd do differently next time.

[← Back to home]({{ '/' | relative_url }})

---

## Decisions and trade-offs

| Decision | Why we picked it | Trade-off accepted |
|---|---|---|
| **Lawnmower / wall-follow, not SLAM** | Predictable, immune to see-through netting that defeats depth sensing | No adaptive re-routing if a pad layout changes mid-run |
| **Pose redundancy (FC ↔ UWB, auto-fallback)** | DDS / UWB drop on a shared network; we needed independent paths | Extra telemetry plumbing in `uwb.py` + `px4_ros.py` |
| **Scan two ArUco dictionaries** | Announced dict was a late, single-source fact; getting it wrong = 0 detections | ~2× detect cost per frame (cheap) |
| **Camera RGB ↔ IR auto-fallback** | Mixed fleet — D435 has RGB, D430 / D450 don't | IR loses colour, fine for ArUco |
| **Hard altitude cap below the net** | Crash = no re-assessment | Small usable-height loss vs the 3.5 m cage ceiling |
| **Watchdogs in the control loop** | Autonomy must self-recover; a checklist won't intervene mid-flight | Conservative early-landing on flaky pose |
| **Measure the frame (survey tool)** | Indoor UWB frame is the #1 failure mode | An extra setup step before flying |
| **Closed-loop velocity, not position commands** | Org's recommended pattern (`kolomee.py`); more efficient than position | More tuning surface (max-vel, slow-down profile) |
| **Single repo, both challenges** | One coordinate world; the C1→C2 handoff is a JSON read, not a re-survey | Slightly larger surface for any cross-challenge change |

---

## Surprises during prep

### The mapping drones don't all have RGB

The org confirmed late (2026-06-08) that the mapping drone fleet includes Realsense **D430** and **D450** modules. Neither has an integrated RGB sensor. Our dev camera (D435) does.

This would have broken our color-frame ArUco pipeline silently — there would have been no error, just zero detections.

Fix: `realsense.py` auto-detects the available streams at startup and, if no RGB sensor is exposed, synthesises a BGR frame from the IR stream with the IR emitter toggled off (so the projector's dot pattern doesn't corrupt the marker). The ArUco pipeline downstream sees the same `RealsenseFrame` interface either way.

### The ArUco dictionary was announced *on the day*

We assumed `DICT_6X6_250` based on the org's sample code. They announced `DICT_7X7_1000` at the briefing.

Fix: we'd already broadened the runtime dict registry to all 20 standard variants with case-insensitive lookup, and the mapping pipeline scans **two** dictionaries every frame as a hedge. Configuration was a `--aruco-dict` flag change; no code edit at venue.

### The altitude floor and our defaults

Org confirmed a 3.5 m minimum altitude on 2026-06-08. Our defaults were 1.5 m / 2.5 m — well below.

Fix: bumped every pre-staged waypoint template to 4.0 m, and made the alt clamp a *runtime* value (not a constant) so we could revise it again on the day. (We later revised down to 2.5 m default with 3.2 m hard cap once we learned the cage net height.)

### A documented flag that didn't exist

During a deep doc audit on the night before, we caught that `--use-ir-for-aruco` was referenced in three different runbook files as if it were a real CLI flag — but it had never been wired into argparse. An operator following the docs would have hit "unrecognized argument" mid-prep.

Fix: replaced every reference with "escalate to org marshal" guidance, since the underlying IR fallback is the auto-detect path, not a flag.

### Tickets stopped being useful

We drafted 11 support-ticket questions for the org over the prep week. By T-1 evening it was clear that org responses were slow enough that filing more tickets had negative expected value — better to ask the on-site marshal verbally on the day. The drafted file is preserved in the repo for completeness but reframed as "verbal asks" in the day-of runbook.

---

## Things we'd do differently

### Build the C2 swarm earlier

C1 was solid by T-3 days. C2's `swarm_controller.py` was still a stub at T-3 evening because pyhula can't be exercised on a dev laptop. We patched around it by writing detailed adapter interfaces and a handoff contract from C1, but earlier hardware time would have caught the per-drone state machine pace issues that we didn't see until on-site.

### Run the thumbdrive flow earlier

`thumbdrive/build.sh` + `setup.sh` were never run end-to-end until T-1. They worked, but the first-discovered bug at venue would have been infuriating.

### Test on the actual drone hardware sooner

Our dev camera was a Realsense D435 plugged directly into a development laptop via USB. The venue setup is `C2 Terminal → NoMachine → drone's onboard Orange Pi → pyrealsense2`. We never exercised that path before the day, and the no-RGB camera fallback was a same-day "if this works, great; if not, escalate" risk.

### Adversarial reviews work

Multiple passes of multi-agent review (one author, multiple skeptical reviewers in parallel) caught silent killers — a validity rule that marked every real pad invalid because of an `Optional[bool] → bool` coercion, a broken no-RGB camera path, the wrong altitude default, the fake `--use-ir-for-aruco` flag. Every one of those would have surfaced live, in the assessment slot.

We'd run more of them next time.

---

## Stats

- **Total commits during prep (5 days):** ~140 on the working branch
- **Stand-up files:** README, CHALLENGE_BREAKDOWN, FINALS_PLAN, runbook, DAY1_RUNBOOK, DAY1_POCKET_CARD, DAY1_SETUP_SEQUENCE, SCORING_PLAYBOOK, HANDOFF_C1_TO_C2, CONVOY_OPPONENT_ROLE, D430_RGB_RISK, ORG_TICKETS_DRAFT, CONCEPT_PLAN, OP_DOC
- **Smoke tests on the C1 stack:** end-to-end multi-tag, mid-run abort, kill-mid-run, stationary depth-zero rate, multi-dict normalisation
- **Lines of code, C1 pipeline:** ~3,500 (excluding tests, mocks, docs)
- **Org Discord drops handled live (during prep):** 11 separate clarifications

[← Back to home]({{ '/' | relative_url }})

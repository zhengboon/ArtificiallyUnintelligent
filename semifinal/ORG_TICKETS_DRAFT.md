# Org Tickets — First-Batch Drafts (Copy-Paste Ready)

> **STATUS 2026-06-09 T-1: tickets path is dead** — ask the org marshal verbally at the venue Day-1 morning instead of filing into `#support-ticket`. This file is kept for the question text only (so we can read the prepared wording aloud or paraphrase it on the day). Do **not** treat the filing-batch plan below as live.

These are the **file-first tickets** surfaced by the deep audit, plus new tickets added from 2026-06-07/08 Discord activity. Each section below contains a single ticket — ready to copy verbatim into the `#support-ticket` Discord channel.

For each ticket:

- **To file in:** the Discord channel.
- **Why we're asking:** one-sentence internal rationale (do NOT paste this into Discord — it's a reminder for whoever is filing).
- **Body (quoted block):** copy the contents of the block verbatim as the Discord message.

See the **Filing Recommendation** at the bottom for the suggested firing order and pacing — do **NOT** fire everything at once.

---

## Updated 2026-06-09 — new tickets surfaced from 2026-06-07/08 Discord activity

The 5 originally-drafted file-first tickets (further down) remain valid and unfired. The 6 tickets below were added after the 2026-06-08 org clarifications (D430/D450 cameras confirmed, 3.5m minimum altitude, camera facing down, configurable resolution, fixed launch point + free direction) and after sweeping the still-unanswered questions other teams asked on 06-07 and 06-08.

---

### Ticket 6 (P0): Do the mapping drones expose an RGB color stream, or only depth + IR?

**To file in:** #support-ticket | **Why we're asking:** P0 — if the answer is no, we need a different code path on Day-1 (emitter-toggle IR ArUco instead of color ArUco).

> **Challenge:** Challenge 1 — Reconnaissance (University)
> **Team:** ArtificiallyUnintelligent
>
> Thanks for confirming on 2026-06-08 that the mapping drone uses Intel Realsense D430 and D450 modules. Both of those SKUs are depth-only by default (stereo IR + IR projector, no RGB sensor). Many drone integrators bolt on a separate RGB camera alongside the depth module — we wanted to confirm whether our team's mapping drone exposes a usable colour stream, since our current ArUco detector consumes a colour frame.
>
> ***Ask: does the mapping drone expose an RGB colour stream (e.g. via a bolted-on RGB sensor or a second camera), or only the D430/D450 depth + IR streams?***
>
> *Why we're asking:* if only IR + depth is exposed, we have an `--use-ir-for-aruco` fallback ready (toggle the IR emitter off on alternating frames so the dot pattern doesn't degrade marker detection) — but we want to know in advance so we don't burn setup-day flight time discovering this on-site.
>
> Thanks,
> — ArtificiallyUnintelligent (University)

---

### Ticket 7 (P1): Is camera pitch programmable from MAVSDK / pyhulax, or is it physically fixed downwards?

**To file in:** #support-ticket | **Why we're asking:** if the mount is fixed, our `set_camera_angle(pitch_deg)` call is a no-op and we should disable our gimbal commands to avoid confusion on the field.

> **Challenge:** Challenge 1 — Reconnaissance (University)
> **Team:** ArtificiallyUnintelligent
>
> Following the 2026-06-08 confirmation that the camera is mounted facing down: is the camera pitch programmable from MAVSDK (i.e. can we issue a runtime command to change the pitch angle), or is the mount physically fixed downwards for the entire run?
>
> Calibruh_KangKiatYang asked the same question on 2026-06-08 1:59pm — flagging that this answer is useful for multiple teams.
>
> ***Ask: is camera pitch software-controllable from MAVSDK, or physically fixed at the downward orientation?***
>
> *Why we're asking:* our mapping-drone controller currently issues `set_camera_angle(pitch_deg)` via MAVSDK — if the mount is fixed, that call is a no-op and we'll disable it to avoid confusion. If programmable, we'll leave the default at -90° (straight down) per the 06-08 confirmation.
>
> Thanks,
> — ArtificiallyUnintelligent (University)

---

### Ticket 8 (P1): Challenge 2B — what is the convoy movement model?

**To file in:** #support-ticket | **Why we're asking:** affects whether the Hula swarm should continuously patrol (intercept-style) or sweep waypoint hubs (intersection-style).

> **Challenge:** Challenge 2B — Convoy hunt (University)
> **Team:** ArtificiallyUnintelligent
>
> Could you clarify how the ground-robot convoys move during Challenge 2B? Specifically: do they pick a random direction on every step (continuous random walk), or do they only make a random decision when they reach an intersection (random-at-intersection)?
>
> yangweiindustries_LimYangWei raised this on 2026-06-08 3:29pm without a response yet.
>
> ***Ask: is convoy movement random-per-step or random-at-intersection?***
>
> *Why we're asking:* it changes our swarm search strategy. Continuous random walk favours a patrol-and-intercept approach; random-at-intersection lets us dedup detections by ArUco ID rather than by world-position clustering. We'd rather lock the right strategy in before finals day.
>
> Thanks,
> — ArtificiallyUnintelligent (University)

---

### Ticket 9 (P1): Challenge 2B — are Hula drones allowed to fly over the convoy boxes?

**To file in:** #support-ticket | **Why we're asking:** if disallowed, our path planner has to route around box footprints rather than running a lawnmower over the whole arena.

> **Challenge:** Challenge 2 — Hula swarm (University)
> **Team:** ArtificiallyUnintelligent
>
> For Challenge 2, are the Hula drones allowed to fly *over* the convoy boxes throughout the run, or must we keep the swarm's lateral footprint clear of the boxes at all altitudes?
>
> ROBO11_DarwinHoShengXian asked this on 2026-06-08 11:03pm without a response yet.
>
> ***Ask: are Hula drones permitted to overfly the boxes during Challenge 2?***
>
> *Why we're asking:* if overflight is allowed, a lawnmower pattern over the whole arena is the simplest search. If not, we need to plan paths that route around the box footprints — different code, different rehearsal.
>
> Thanks,
> — ArtificiallyUnintelligent (University)

---

### Ticket 10 (P2): Challenge 1 top-down depth map — matplotlib-style graph acceptable, or must it be a stereo output map?

**To file in:** #support-ticket | **Why we're asking:** affects which artifact we present to judges (our `top_down.png` is matplotlib-style from the occupancy grid).

> **Challenge:** Challenge 1 — Reconnaissance (University)
> **Team:** ArtificiallyUnintelligent
>
> For the Challenge 1 top-down depth map deliverable: does the judging panel expect a stereo-output map (i.e. a depth image rendered directly from the Realsense stereo pipeline, matching the briefing slide), or is a matplotlib-style top-down occupancy graph (e.g. `top_down.py`) also acceptable?
>
> FlyingExplorers raised this on 2026-06-07 6:03pm and again on 2026-06-08 3:19pm without a response yet.
>
> ***Ask: is a matplotlib top-down graph an acceptable Challenge 1 artifact, or must we present a stereo-output depth map?***
>
> *Why we're asking:* our current pipeline emits `top_down.png` from the occupancy grid (matplotlib-style). If judges want a stereo output specifically, we may need to switch the artifact we present — better to know now than discover on Day-1.
>
> Thanks,
> — ArtificiallyUnintelligent (University)

---

### Ticket 11 (P2): Camera resolution, FOV, and expected tag pixel count?

**To file in:** #support-ticket | **Why we're asking:** FOV lets us pre-compute the optimal flight altitude against the confirmed 20cm x 20cm markers and the 3.5m minimum-altitude floor.

> **Challenge:** Challenge 1 — Reconnaissance (University)
> **Team:** ArtificiallyUnintelligent
>
> Following the 06-08 confirmation that camera resolution is configurable: could you share the FOV (horizontal + vertical, degrees) of the D430 / D450 modules as mounted, and the rough tag pixel count we should expect for the 20cm x 20cm ArUco markers at the 3.5m minimum altitude?
>
> ROBO05_Daniel asked this on 2026-06-07 8:04pm (edited 8:26pm) without a response yet.
>
> ***Ask: FOV + expected tag pixel count at the 3.5m minimum altitude?***
>
> *Why we're asking:* FOV lets us pre-compute the optimal flight altitude for detection range, and the tag-pixel-count target lets us pick a resolution from the configurable set that keeps ArUco corners reliable.
>
> Thanks,
> — ArtificiallyUnintelligent (University)

---

## Rank 14: Are pre-built code submissions allowed on Day-1, or must all code be written on-site?

**To file in:** #support-ticket | **Why we're asking:** if pre-prep is disallowed, our entire strategy collapses and we need to replan immediately — this is the single biggest unknown blocking our plan.

> Hi organisers,
>
> Could we get clarification on whether teams are allowed to arrive at the finals with pre-built code, or whether all code must be written on-site during the event itself? Specifically, can we load our existing pipeline onto the C2 Terminal / mapping drone on Day-1, and if so, does the 7:45-8:45 onsite setup window count as the code-load slot (or is there a separate window)?
>
> We noticed STINKIES_TanFengYuan raised the same question on 5 June and again on 6 June without a response yet — flagging that this is time-sensitive for multiple teams.
>
> ***Ask: Are pre-built code submissions permitted on Day-1, and if yes, when does the load-onto-hardware window open?***
>
> Why we're asking: our team has prepared a complete pipeline on the assumption we can load it Day-1 morning. If pre-prep is disallowed and everything must be written in-room, we need to replan immediately.
>
> Thanks,
> ArtificiallyUnintelligent (University)

---

## Rank 1: Challenge 1 — What rule maps ArUco marker ID to VALID vs INVALID landing pad?

**To file in:** #support-ticket | **Why we're asking:** without this rule, our valid/invalid output is guessing — directly hits Challenge 1 accuracy score.

> **Challenge:** Challenge 1 — Reconnaissance (University)
> **Team:** ArtificiallyUnintelligent
>
> Hi org, quick question on the landing-pad scoring for Challenge 1.
>
> Our mapping drone detects ArUco markers reliably end-to-end — every marker ID is read correctly. What we don't yet know is the rule that maps a detected marker ID to **VALID vs INVALID** for the landing-pad classification score. A few possibilities we've considered:
>
> - A fixed ID allow-list (e.g. `{3, 7, 12, 19, 24}` are valid)
> - A bit-pattern / parity rule (e.g. even IDs valid)
> - A numeric threshold or range (e.g. `id < 50` valid)
> - A lookup table provided as a file at run-time
> - Something else we haven't thought of
>
> ***Ask: could the org publish the VALID/INVALID rule, or confirm when it will be revealed — at the Day-1 morning briefing, or only deeper into the run? If it will be distributed as a file (CSV/JSON/etc.), is there any chance it can be shared in advance so we can validate our loader?***
>
> *Why we're asking:* our classifier currently has a single patchable line for this rule, so we can swap it in immediately once known — but without it our valid/invalid output is effectively guessing, which directly hits the Challenge 1 accuracy score. Thanks!
>
> — ArtificiallyUnintelligent (University)

---

## Rank 7: Are Challenge 1 and Challenge 2 run in parallel or sequentially within a team's slot?

**To file in:** #support-ticket | **Why we're asking:** answer drives role allocation and whether we invest rehearsal time in a live C1 to C2 data pipeline.

> **Context:** University category, ArtificiallyUnintelligent. Challenge 1 (Reconnaissance mapping drone) and Challenge 2A/2B (Hula swarm landing + ground-robot hunt) both apply to our team.
>
> We want to confirm the slot structure so we can finalise role allocation and rehearsal plan for the finals:
>
> 1. Are Challenge 1 and Challenge 2 run **sequentially** within our slot (C1 finishes fully, then C2 begins), or **in parallel** (both platforms active simultaneously on the arena)?
> 2. If sequential: is there an official handoff of Challenge 1 outputs (e.g. landing pad IDs + world coordinates) into Challenge 2A as a judge-accepted artifact (JSON / form / verbal), or do we simply consume our own C1 artifacts internally with no formal handover?
>
> ***Ask: please confirm (a) parallel vs sequential, and (b) whether any C1 to C2 handoff is officially recognised by judges.***
>
> *Why we're asking:* we are preparing both modes, but the answer changes our team-member allocation and whether we invest practice time in a live C1 to C2 data pipeline vs treating them as independent runs. We'd like to focus rehearsal on the actual format.
>
> Thanks!
> — ArtificiallyUnintelligent (University)

---

## Rank 8: Scored-run policy — attempts per challenge, time budget, and retry / abort / crash treatment

**To file in:** #support-ticket | **Why we're asking:** this dictates aggression on run 1, whether to build a fast-abort path, and our crash-mitigation budget.

> Hi organisers,
>
> We're trying to firm up our run-day strategy for the finals and would appreciate clarification on the scored-run policy. The schedule mentions 9am-6pm on both days with testing slots TBA, but we don't yet have visibility on:
>
> - How many **scored attempts** each team gets per challenge
> - The **time allowance** per scored attempt
> - Whether attempts are **back-to-back** or **distributed** across the day
> - If a run is **aborted due to a software issue** (e.g. MAVSDK fails to connect, vision pipeline hangs before takeoff), can we restart fresh, or does the aborted run count as one of our attempts?
> - If we **crash a drone** mid-run, what is the penalty — do we lose remaining attempts, take a fixed deduction, or something else?
>
> ***Ask: could you outline the scored-run policy and how retries / aborts / crashes are treated?***
>
> Why we're asking: this materially changes whether we plan a safe-first-then-aggressive iteration approach or a one-shot-conservative one, and we'd rather lock in the right strategy before finals day than improvise on the field. Thanks very much.
>
> — ArtificiallyUnintelligent (University)

---

## Rank 5: UWB coordinate frame, anchor layout, and arena dimensions

**To file in:** #support-ticket | **Why we're asking:** without the UWB frame definition and anchor layout, we can't plan waypoints or safe-envelope checks against `UWBParserThread.get_tag_position(tag_id)`.

> **Challenge:** University Finals — Drone Autonomy
> **Context:** Planning waypoints / safe envelopes against the UWB position feed exposed by `UWBParserThread.get_tag_position(tag_id)` (org release 2026-06-06 11:28).
>
> We can read tag positions fine, but we have no information about the coordinate frame they're returned in. Specifically, we don't know: (1) how many anchors are deployed and where they sit in arena coordinates, (2) the arena's usable X-Y dimensions in metres, (3) where the UWB origin (0, 0) is located relative to the arena (corner? centre? takeoff pad?), (4) the axis convention of the published position (ENU, NED, or arena-local), and (5) whether there are known dead zones or degraded-accuracy regions we should design around.
>
> ***Ask:** could the org share the arena UWB anchor layout and dimensions ahead of time, or confirm that we are expected to discover this on-site? If it's the latter, would the org be willing to include a simple ASCII or PNG layout sketch in the briefing slides so teams can pre-plan waypoint extents without trial-and-error during setup?*
>
> Why we're asking: without the frame definition and arena bounds, any waypoint mission we write now is effectively a guess, and we'd rather not burn setup-day flight time calibrating coordinates that the org already knows.
>
> — ArtificiallyUnintelligent (University)

---

## Filing Recommendation

**Suggested firing order (combined, updated 2026-06-09):**

1. **Ticket 6 — D430/D450 RGB stream.** Fire first. Highest correctness blocker now: if no RGB is exposed, our Day-1 code path is different (emitter-toggle IR ArUco). The 06-08 confirmation that the modules are D430/D450 created this risk; we want the answer before we burn flight time on it.
2. **Rank 1 — VALID/INVALID rule.** Still the highest Challenge 1 *scoring* impact — the rule may already be drafted org-side and just needs releasing.
3. **Rank 14 — pre-prep policy.** Still open from 2026-06-05; if the answer is "no pre-built code", our whole strategy collapses. Adding our voice continues to raise the priority.
4. **Ticket 7 — pitch programmable vs fixed.** Code-path decision (do we keep the gimbal command or rip it out?). Another team already asked on 06-08 without response.
5. **Ticket 9 — overflying boxes.** Strategy decision — lawnmower vs route-around-footprint. Another team asked on 06-08 without response.
6. **Rank 7 — parallel vs sequential.** Drives role allocation and rehearsal plan.
7. **Rank 8 — scored-run policy.** Drives aggression, abort-path design, and crash budget.
8. **Ticket 8 — convoy movement model.** Refines Challenge 2B strategy (patrol-intercept vs intersection-dedup). Useful but not blocking.
9. **Rank 5 — UWB layout.** Needed for waypoint planning but only blocks late-stage tuning.
10. **Ticket 10 — matplotlib vs stereo depth map.** Artifact format question; affects presentation, not pipeline correctness.
11. **Ticket 11 — FOV + tag pixel count.** Nice-to-have for altitude tuning; the 3.5m floor + configurable resolution already pin most of our setup.

**Pacing — do NOT fire everything at once.**

- **Batch 1 (fire now):** Ticket 6 + Rank 1. The two highest-impact correctness questions; both look like the org can answer them quickly from existing internal docs.
- **Batch 2 (after Batch 1 sees any response, or after ~4 hours):** Rank 14 + Ticket 7 + Ticket 9. Three strategic decisions that all gate code-path or path-planning work.
- **Batch 3 (Day-1 morning ticket batch, if still unanswered):** Rank 7 + Rank 8 + Ticket 8. Run-day strategy questions — sensible to ask in the morning ticket window if they remain open by then.
- **Batch 4 (only if earlier batches are landing):** Rank 5 + Ticket 10 + Ticket 11. Lower-priority refinements; do not file these into a noisy unresponsive channel.

If Batch 1 goes unanswered for >24 hours, escalate via DM to the organiser who posted the 2026-06-06 21:47 ticket-etiquette note (they are clearly active), or raise in person at any onsite briefing.

**Etiquette reminder (per 2026-06-06 21:47 org post):** close stale tickets and open fresh ones rather than bumping. If any of our questions get partially answered, ack-and-close and re-open a tighter follow-up.

---

## Second-Batch Tickets — File These if First Batch Gets Traction

If the first 5 tickets get fast, useful answers, file this next wave. Titles + ranks only — bodies are drafted in the separate audit doc and can be polished before sending.

- Rank 10 — (TBD title — see audit doc)
- Rank 11 — (TBD title — see audit doc)
- Rank 16 — (TBD title — see audit doc)
- Rank 19 — (TBD title — see audit doc)
- Rank 20 — (TBD title — see audit doc)
- Rank 27 — (TBD title — see audit doc)
- Rank 32 — (TBD title — see audit doc)
- Rank 34 — (TBD title — see audit doc)
- Rank 35 — (TBD title — see audit doc)
- Rank 37 — (TBD title — see audit doc)
- Rank 38 — (TBD title — see audit doc)
- Rank 39 — (TBD title — see audit doc)

Pull the body for each from the deep-audit ticket-draft list before filing. Do **not** file the second batch until at least 2 of the first-batch tickets have answers — otherwise the channel gets noisy and the org may deprioritise us.

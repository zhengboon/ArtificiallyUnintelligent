# Org Tickets — First-Batch Drafts (Copy-Paste Ready)

These are the **5 file-first tickets** surfaced by the deep audit. Each section below contains a single ticket — ready to copy verbatim into the `#support-ticket` Discord channel.

For each ticket:

- **To file in:** the Discord channel.
- **Why we're asking:** one-sentence internal rationale (do NOT paste this into Discord — it's a reminder for whoever is filing).
- **Body (quoted block):** copy the contents of the block verbatim as the Discord message.

See the **Filing Recommendation** at the bottom for the suggested firing order and pacing — do **NOT** fire all 5 at once.

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
> We can read tag positions fine, but we have no information about the coordinate frame they're returned in. Specifically, we don't know: (1) how many anchors are deployed and where they sit in arena coordinates, (2) the arena's usable X-Y dimensi

---

## Filing Recommendation

**Suggested firing order:**

1. **Rank 14 — pre-prep policy.** Fire first. If the answer is "no pre-built code", our whole strategy collapses and we need every hour of the remaining days to replan. Two prior teams have asked without response — adding our voice raises priority.
2. **Rank 1 — VALID/INVALID rule.** Fire second. Correctness blocker for Challenge 1 scoring; the rule may already be drafted org-side and just needs releasing.
3. **Rank 7 — parallel vs sequential.** Drives role allocation and rehearsal plan.
4. **Rank 8 — scored-run policy.** Drives aggression, abort-path design, and crash budget.
5. **Rank 5 — UWB layout.** Needed for waypoint planning but only blocks late-stage tuning.

**Pacing — do NOT fire all 5 at once.**

- Fire **rank 14 + rank 1** as the first batch (the two highest-impact, both already prepared to be answered).
- Wait a few hours. If org responds quickly to either, fire **rank 7 + rank 8** as the second batch.
- Fire **rank 5** last, once at least one of the earlier batches has been answered, so we don't flood the channel and risk all five being deprioritised together.

If the first batch goes unanswered for >24 hours, escalate via DM to the organiser who posted the 2026-06-06 21:47 ticket-etiquette note (they are clearly active), or raise in person at any onsite briefing.

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

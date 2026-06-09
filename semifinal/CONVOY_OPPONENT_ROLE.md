# Convoy opponent role — slot #24 (vs THE WIENERS)

Discovered 2026-06-09 from the org pptx (`finals_brief_extracted.md` slide
7 + slide 14): each Challenge 2 assessment puts 5 RoboMaster ground robots
in the cage as the "convoy", and **2 of those 5 are driven by participants
from other teams**, not by autonomy. The other 3 travel autonomously.

Our slot mapping (slide 14):

- **Slot #3** — we (ARTIFICIALLYUNINTELLIGENT) are the testing team. STD
  operates 2 convoy robots adversarially against us.
- **Slot #24** — THE WIENERS are the testing team. **We operate 2 convoy
  robots adversarially against them.**

This doc is about slot #24 — our responsibility, not someone else's.

## What we know

- 5 ground robots loiter in the arena during each C2 assessment.
- 2 of those 5 are operated by participants from another team. At slot
  #24, that's us.
- The remaining 3 travel autonomously.
- The testing team's Hula swarm has 8 minutes (slide 6) to find and ArUco-tag
  the robots.
- The opponent role is adversarial: make ourselves hard to tag.

## What we don't know yet (Day-1 morning briefing questions)

File these as briefing-room questions at 0930-1030 on 2026-06-10:

1. **How are the controllable RoboMasters operated?** Joystick?
   Touchscreen? DJI RoboMaster app on a phone? Or a code interface? Most
   likely an org-provided physical controller — but confirm before slot
   #24 so we're not learning the input device live.
2. **Are there rules constraining the opponent?** Examples: no leaving
   the arena, no destroying / colliding with the testing team's drones,
   minimum movement (must keep moving vs allowed to camp), no
   piling-up against walls, no shielding behind autonomous convoy mates.
3. **Does the opponent score points** for evading successfully, or is the
   opponent role pure cost (zero upside, just a duty we owe THE WIENERS)?
4. **Can we coordinate** our two operators verbally during the run, or
   must we be silent / split up?
5. **Where do the operators stand?** Inside the cage, outside, at C2?
   Affects line-of-sight to the robot.

## Strategy guesses (refine Day-1 once rules are known)

Working theory, all pending the rule answers above:

- **Move continuously.** Stationary = easy ArUco lock. The Hula speed cap
  is 0.5 m/s (slide 6) — even slow movement makes the marker harder to
  centre.
- **Hug obstacles.** Hulas are not allowed to fly over obstacles (slide 6,
  recommended height 1.1 m, "strictly no flying over obstacles, scores
  invalidated"). Sit behind an obstacle and the Hula has to reposition.
- **Hug the boundary.** Forces the Hula into an awkward approach angle
  and limits its escape paths if it has to back off.
- **Coordinate the cage halves.** Two operators, two robots, split the
  arena left/right so we're not both crowding the same obstacle and
  leaving the other half wide open.
- **Don't break the rules to win.** Getting THE WIENERS DQ'd because we
  ran a robot into their Hula is unsporting and probably violates the
  rules anyway. The goal is adversarial difficulty, not sabotage.

## Who does what

- **A** (judge-talker / utility role): one of the two operators. A is
  already the one comfortable with judge-facing interaction so the
  operator-side rule briefing falls naturally to them.
- **Z or K**: the other operator. Whichever of us is freer at slot #24 —
  Z's mapping drone runs in C1 on Day 1 and C1 doesn't reappear, so by
  slot #24 (Day 2 afternoon) Z is the more likely candidate. K may be
  occupied debriefing the Hula swarm run we just finished.
- **15-minute huddle before slot #24** to agree the cage split, our
  movement patterns, and confirm we both understand the rules we got in
  the morning briefing.

## Pre-Day-1 prep

- Read `finals_brief_extracted.md` slide 7 once before Day 1 so the
  convoy-opponent setup isn't a surprise on the morning.
- During the 0930-1030 Day-1 briefing, ask the rule questions above.
- Find the RoboMaster controllers at our table — handle one before slot
  #24 so the first time we touch the controls isn't with THE WIENERS'
  scoreboard at stake.

## Slot timing context

Slot #24 is in Challenge 2 (Day 2, 1330-1600). With 26 slots in C2 over
2.5 hours, each slot averages about 5-6 minutes including changeover.
Slot #24 lands roughly in the last 15-20 minutes of the C2 window.
Plan to be at the cage at least 20 minutes early to huddle and to
prepare the controllers — we won't get another chance, and showing up
late means THE WIENERS get only autonomous opponents and we look
unprofessional.

## Open questions linked to this role

- Cross-ref `ORG_TICKETS_DRAFT.md` if any of the Day-1 briefing questions
  go unanswered — file a fresh org ticket per the close-and-reopen
  etiquette captured in `README.md` (2026-06-06 21:47 PM org drop).

---

*Source: `finals_brief_extracted.md` slides 7 + 14 (extracted from org
pptx 2026-06-09 22:06 SGT). Last updated 2026-06-09.*

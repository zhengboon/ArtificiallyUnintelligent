# POST-CALL STATUS — Thu 21 May 2026 ~23:50 SGT
# T-14h to qualifier (Fri 22 May 14:00 SGT)

## Where we are right now

- Video call with K + A just ended.
- **K is tuning his YOLO model overnight.** New `best.pt` will arrive
  before Fri morning. K's current `best.pt` is committed at
  `models/best.pt` (3 classes, "yellow barrel" / "red barrel" /
  "toxic barrel" with spaces).
- Z (you) is now doing a deep audit + fix-all-issues + implement-new-plans
  pass. This is your work session.
- A is presumably wrapping up the runbook reading and going to bed.

## Latest commits on main (`origin/main`)

```
750b1ff Reliability: pre-load YOLO before PX4 connect + flight clock logger
94f3b80 divergence_watchdog: skip the check while in velocity mode
a669057 Docs: T-15h status snapshot
2e5727a Wall planner: add stuck detection + escape maneuver
617249a Fix mavsdk_server overload + label remap on modern ultralytics
edf187a Wall-following: full integration as --pattern wall
c5fa970 Controller teardown fix, --pattern scan mode, thumbdrive scaffold
```

Plus a fresh `ks` branch at the same commit (`750b1ff`) — K will tune
his model on this branch and PR back when ready.

## What's verified working in sim tonight

| Test time | Pattern | Model | Result |
|---|---|---|---|
| 21:01 | square | verylousymodel | ✅ 2 yellow_barrel detections during landing, run finished cleanly |
| 21:11 | square | K's best.pt | ✅ ran clean, 0 detections (no yaw, model conservative) |
| 21:56 | wall | K's best.pt + label remap + to_thread | ✅ planner_wall ran 90+ s, 360 scan triggered + recovered, FSM transitioned |
| 22:16 | wall | (same + stuck-escape) | ✅ STUCK DETECTED, escape executed, drone broke out of stuck pocket, entered outer_corner state, moved at fwd=0.70 m/s |
| 22:03, 22:33, etc. | wall | various | ❌ mavsdk gRPC reset before arm — pre-load YOLO fix (`750b1ff`) is the targeted mitigation, NOT YET sim-tested |

## Issues fixed but not flight-tested

These are committed but no sim run has exercised them yet:

1. **YOLO pre-load before PX4 connect** (`750b1ff`) — should fix the
   recurring mavsdk crash by warming the OS page cache before any
   timing-sensitive PX4 interaction.
2. **flight_clock_logger background task** (`750b1ff`) — periodic 5s
   status line on stdout: `flight: T+12.5s detections: 1Y/0R map=4823`
3. **divergence_watchdog velocity-mode skip** (`94f3b80`) — was
   spuriously arming with err>5m every 3 sec during wall flight.

## Outstanding work — fix-all-issues + new-plans

### Issues to address tonight (per user "fix everything")

| Severity | Issue | Notes |
|---|---|---|
| 🚨 P0 | Flight-test the pre-load YOLO fix (`750b1ff`) | Untested. If pre-load works, mavsdk crash is solved. If not, need next-level fix. |
| ⚠️ P1 | Verify `flight_clock_logger` actually fires during flight | Untested. |
| ⚠️ P1 | Verify divergence watchdog skip works during velocity mode | Untested. Should NOT see "divergence watchdog armed" lines in wall runs. |
| ⚠️ P1 | K's wall_following `z>1.5` filter still drops close obstacles | Algorithm-level; escape maneuver papers over it. Not changing K's code. |
| ⓘ P2 | We don't know barrel count, can't program "found all" → max speed bonus unreachable | Phase 4 detection dedup not built. |
| ⓘ P2 | Multi-run sim degradation in dev VM | Won't affect qualifier (fresh VM). |
| ⓘ P2 | Doc staleness: tasks.md, context.md, various refs | Already partially addressed in `a669057` |
| ⓘ P2 | 27 dead workshop demo files in `codes/Codes/` | Cosmetic |

### New plans to implement (the "all new plans" part)

Things we discussed tonight but haven't built:

1. **Detection dedup by NED position** (Phase 4) — cluster detections
   within 1.5m of each other as "same barrel". Enables:
   - Unique-detection count visible to judges
   - Early-exit when both colors found (chase speed bonus)
2. **Retry logic on `arm()` / `begin_offboard()`** — catch grpc errors,
   wait, retry up to 3 times. Doesn't help if mavsdk_server is gone,
   but if it's a transient blip, helps.
3. **Save run_summary.json incrementally** during flight, not just at
   teardown — robust to crashes mid-run, judges can inspect any time.
4. **Optional live cv2.imshow map window** so judges see the map
   actively being built without needing to open the file. The user
   previously deferred this; revisit?
5. **Status file written every 5s** (`run_<ts>/STATUS.txt`) with
   plain-text human-readable summary — judge friendly even without a
   terminal.
6. **Cleanup pass** on `codes/Codes/` dead code, stale docs.
7. **Update `team/tasks.md` + `progress.md`** with tonight's call
   outcome.
8. **Pre-flight integration test script** (`thumbdrive/_smoke.sh`)
   that runs Phase 1 + 2 + 6 + 7 in 60 sec to validate before
   committing to a real run at the qualifier.

### Open environmental unknowns for tomorrow

- Will K's tuned model fire on the actual qualifier-day barrels?
- Will the org VM behave like our (now-flaky) dev VM, or like the
  cold-cache fresh VM we hard-rebooted into?
- How many barrels of each color does the qualifier have?

## Files modified or new today

```
searchctl/controller.py     — main controller, heavily modified
searchctl/wall_following.py — K's PR, untouched
searchctl/README.md         — Phase status updated
team/tasks.md               — T-15h banner
team/discord_drafts.md      — DS-1 marked RESOLVED
progress.md                 — tonight's entries
thumbdrive/QUICKSTART.txt   — user-facing instructions
thumbdrive/runbook.md       — full qualifier-day playbook
thumbdrive/README.md        — folder doc
thumbdrive/setup.sh         — at-venue install script
thumbdrive/make_thumbdrive.sh — regenerate this folder
thumbdrive/_*.sh            — VM helpers (clean, capture, run_wall, etc.)
thumbdrive/ArtificiallyUnintelligent.tar.gz — repo tarball (gitignored)
thumbdrive/best.pt + verylousymodel.pt      — model copies (gitignored)
thumbdrive/wheels/          — offline pip wheels (gitignored)
dumpcontext/00_INDEX.md..05_POST_CALL_STATUS.md — session-state snapshots
```

## Repo state

- Branch: `main` at `750b1ff`
- Branches on origin: `main`, `ks` (fresh from main, K will work here)
- Working tree: clean
- Thumbdrive packed: 116 MB (tarball + models + wheels + scripts)

## Critical-path checklist for tomorrow

- [ ] Copy `thumbdrive/` to 2× USB sticks
- [ ] Download repo zip from GitHub UI as 3rd fallback (private repo)
- [ ] Charge laptops + phones
- [ ] Print runbook on paper
- [ ] Bag: USBs, IDs, paper runbook, pen/pad, water/snack
- [ ] Meet at Somerset MRT 13:15 SGT
- [ ] Arrive Orchard Grand Court Lloyd I/II by 13:30
- [ ] Slot 14:00. 40 min total. Multi-run allowed.

## Memory file already saved

`C:\Users\zheng\.claude\projects\d--\memory\project_brainhack_2026_05_21_audit.md`
captures the rule changes + targets + key decisions for cross-session.

<!--OPDOC-BANNER-->
> ⚠️ **SUPERSEDED — to run the mapping drone use [OP_DOC.md](OP_DOC.md).** This file is kept for historical detail only; the live decision-tree runbook is OP_DOC.md.

# Day-1 Runbook — Pre-flight + Fallbacks

Companion to `runbook.md`. Do these BEFORE arming. One page. Print on paper.

---

## Real Day-1 schedule (from brief, slide 12)

| Time | Block |
|---|---|
| **0730** | Registration counter opens |
| **0930 – 1030** | Org briefing (validity rule + ArUco dict announced) |
| **1030 – 1200** | Testing (mapping OR hula — Uni teams choose) |
| **1200 – 1300** | Lunch (no testing) |
| **1300 – 1330** | Testing |
| **1330 – 1430** | Prep for Challenge 1 — **NO MAPPING DRONE FLYING** |
| **1430 – 1800** | **Challenge 1 — SCORED** |
| **~1800+** | Day ends |

**Slot ordering (from brief slide 13):** Challenge 1 order is 1=4FINGERS → 2=AAA → **3=ARTIFICIALLYUNINTELLIGENT** → 4=BOYD BUDDIES → 5=CALIBRUH → ... Expect our call ~10-15 min after slot 1 starts at 14:30 (≈14:40-14:45). Pre-flight (this file) must be GREEN by ~14:30 latest; ideally by end of the 1300-1330 testing window.

**Drone sharing (slide 22):** We share Hula 3,4 + Mapping 3,4 with BOYD BUDDIES (slot #4). Back-to-back. Drones come back to the cage with no buffer — handoff cleanly. Agree with their team mid-morning on whether they want to grab batteries during our run for a hot swap.

**Day 2 reminder (Challenge 2, 1330-1600):** We are slot #3 with STD as convoy opponent. At slot #24 we operate 2 convoy RoboMasters against THE WIENERS. CUAS booth is a 4% bonus — collect Day 1 if possible.

---

## Where the controller actually runs (assumption — confirm at venue)

**Dev path (what we tested):** D435 → USB → our personal laptop → `python -m mapping_drone --mock` for the mock leg, no flag (real mode is default) when D435 was plugged in. This was validation only. Note: D435 was our DEV camera; the venue drone carries D430/D450 with no RGB module.

**Venue path (expected):** D430 / D450 mounted on the **mapping drone airframe**. The drone has its own onboard Ubuntu 22.04 + ROS2 + pyrealsense2 + RKNN NPU per finals brief. We connect from the **C2 Terminal Windows host → NoMachine into the drone's onboard SBC → run `python3 -m mapping_drone` on the drone**. Our laptop's USB is not in the chain.

**Unknowns until Day-1 arena setup:**
- Whether the camera is exposed on the drone's `pyrealsense2.context().query_devices()` (likely yes — it's how the org's own getDepthAndDetect.py works) or only via a custom wrapper.
- Whether the drone has spare USB ports for our backup Intel camera (it almost certainly does not — assume not).
- Whether the drone's filesystem has space for our `runs/run_*/` artifacts or we need to `scp` them off after each run.

**Implication:** the IR-fallback decision (D430/D450 has no RGB) gets made on the drone, with the drone's own camera, not on our laptop. Our laptop testing did not exercise the IR-fallback path. Day-1 morning, first thing inside the NoMachine session, run the RGB-stream check against the drone's `rs.context()`. If only IR + depth → the `--use-ir-for-aruco` flag is NOT YET WIRED in controller.py (see D430_RGB_RISK.md sketch). If RGB is missing on Day-1, escalate to the org marshal immediately and request a bolt-on RGB camera or the spare camera unit; do NOT attempt to launch with a CLI flag that argparse will reject.

**Implication (backup camera):** Z's borrowed Intel camera is a dev fallback for laptop-side testing, NOT a swap-in for the drone. If the drone's onboard camera fails Day-1, that's an org-issued-hardware failure and we ask the marshal for the spare unit (sharing pool with Boyd Buddies). Don't try to plug our own USB camera into the drone.

---

## Pre-flight checks (do BEFORE arming)

- [ ] **UWB sniffer**: `python3 -m tools.uwb_sniffer` (or `python3 semifinal/tools/uwb_sniffer.py`). Confirm `uwb_tag` topic publishes; confirm NED axes match (n=pose.y, e=pose.x, alt=-pose.z). Override with `--topic <name>` if org renamed it.
- [ ] **CLI flags intact**: `python3 -m mapping_drone --help` from `semifinal/`. Verify `--real`, `--mock` (alias `--mock-all`), `--waypoints-from-json`, `--aruco-dict`, `--mavsdk-address`, `--mavsdk-addresses`, `--gimbal-pitch`, `--max-flight-time-s` are all listed. **Real mode is the default — actual drone runs need NO flag**. If any missing → wrong checkout / stale USB copy.
- [ ] **Marker-on-floor camera mount check**: place a known ArUco marker 1 m due north of drone GCS origin. Arm, hover at 4.0 m (matches the scored-run altitude above the 3.5 m floor), watch `STATUS.txt` / log. Confirm world XY of detection lands within **20 cm** of (n=1.0, e=0.0). If off → gimbal mount rotated or Realsense extrinsics wrong; do NOT proceed to scored slot.

---

## If MAVSDK won't connect

- [ ] Pass the full fallback list: `python3 -m mapping_drone.controller --mavsdk-addresses serial:///dev/ttyS6:921600,serial:///dev/ttyACM0:115200,serial:///dev/ttyUSB0:57600,udp://:14540,udp://:14550`. Controller tries each with 5 s timeout and logs which one connected.
- [ ] If all 5 fail: check the USB-serial cable is seated, verify the serial port appears (`ls /dev/ttyS* /dev/ttyACM* /dev/ttyUSB*`), check baud against the FC's mavlink param, try a different USB port.
- [ ] Last resort: ask K which serial pyhulax targets on the C2 Windows side and mirror that port/baud on the Ubuntu VM side.

---

## If validity rule is unknown at briefing

- [ ] Pre-staged: `semifinal/configs/valid_ids_unknown.json` (template with `{valid_ids:[], invalid_ids:[]}`).
- [ ] After briefing: copy to `configs/valid_ids_<date>.json`, populate `{valid_ids:[...], invalid_ids:[...]}` from the announced rule.
- [ ] Run controller with: `MAPPING_DRONE_VALIDITY=lookup MAPPING_DRONE_VALIDITY_LOOKUP=configs/valid_ids_<date>.json python3 -m mapping_drone.controller ...`
- [ ] No code edit needed — `validity.py` rule `lookup` reads + caches the JSON. Confirm `describe_rule()` output in log mentions the lookup file path.

---

## If ArUco dict is unknown at briefing

- [ ] Pre-printed sheets: `DICT_6X6_250`, `DICT_5X5_100`, `APRILTAG_36h11` (covers the most likely org picks).
- [ ] After briefing: pass `--aruco-dict <orgsAnnouncedDict>`. Normalization is case-insensitive and accepts all 20 standard dicts + `DICT_` prefix (e.g. `DICT_6X6_250`, `6x6_250`, `apriltag_36h11`, ` 36H11 ` all resolve).
- [ ] If `ValueError` at startup → the error message lists every accepted name. Copy-paste the announced name, retry.

---

## If waypoints differ from default

- [ ] Default (4-corner 2×2 box @ 4.0 m, above the 3.5 m floor) is pre-staged at `configs/waypoints_2x2_default.json`.
- [ ] After A's arena scout: copy current arena layout into `configs/waypoints_<date>.json` as `[[n_m, e_m, alt_m], ...]`.
- [ ] Pass to controller: `--waypoints-from-json configs/waypoints_<date>.json`. Loader replaces the built-in `DEFAULT_WAYPOINTS` fallback.
- [ ] Verify with a mock dry-run before the scored slot: `python3 -m mapping_drone.controller --mock --waypoints-from-json configs/waypoints_<date>.json`.

---

## Smoke order before first scored run

1. **UWB sniffer** — `python3 -m tools.uwb_sniffer` for 10 s. Confirm pose stream + NED axes.
2. **RealSense pipeline test** — `python3 -m mapping_drone.tests.smoke_realsense_stationary`. Confirm a profile started (640x480@30 / 848x480@30 / 1280x720@30 / 640x480@15 — log says which).
3. **MockMavsdk dry-run** — `python3 -m mapping_drone.controller --mock --waypoints-from-json configs/waypoints_2x2_default.json`. Confirm `runs/run_*/STATUS.txt` + `top_down.png` produced.
4. **RealMavsdk connect-only smoke** — `python3 -m mapping_drone.controller --mavsdk-addresses <list> --max-flight-time-s 5`. Realistic timing: process duration ≈ 30-45 s total (UWB await + health + arm + takeoff + 5 s mission wall + safe land + disarm). The drone WILL physically arm, take off, hover ~3 s, then land back — stand clear. The 5 s wall applies to the mission loop, not to wall-clock from process start. Requires UWB live, or the controller hangs in AWAITING_UWB. Goal: confirm MAVSDK negotiates one of the candidate addresses and the drone is controllable end-to-end. (No dedicated arm-disarm-only flag — we use the existing `--max-flight-time-s` watchdog as a hard wall on the mission phase.)
5. **First short scored attempt** — Configuration A from `runbook.md`. Watch `STATUS.txt` live.

Do not skip steps. Each step gates the next.

---

## Live remote debug

When someone wants to watch the controller log in real time from a second machine on the same tailnet (e.g. Z from the C2 terminal while A is on the airframe), pass `--tailscale` to fan the log out to the desktop log_sink:

```
python -m mapping_drone --tailscale \
  --mavsdk-addresses <fallback list> \
  --waypoints-from-json configs/waypoints_<date>.json
```

- Each log line is POSTed in addition to stdout + `log.txt` on the drone. Pre-existing `tools/log_broadcaster/wrap.sh` pattern: the sink appends to `D:/hackerverse/laptop_logs/<tag>.log` on the desktop.
- Default host is `100.79.202.101:9999` (desktop tailnet IP, sink already running). Override with `--tailscale-host <ip:port>` if the desktop has moved.
- Default tag is `mapping-drone-<run_ts>` so each run is its own log file on the sink. Override with `--tailscale-tag <name>` to merge several attempts into one file.
- Combine with `--verbose` to also include the per-frame / per-UWB-tick / per-velocity-command / per-WP arrival / state transition lines that are silent on the normal INFO floor:

```
python -m mapping_drone --verbose --tailscale \
  --waypoints-from-json configs/waypoints_<date>.json
```

- Sink failures (sink down, tailnet flaky) are silently swallowed; a one-shot INFO line `tailscale log sink unreachable at ... — swallowing further POST errors silently` is emitted on the first failure so the operator knows the broadcast isn't landing. Controller never crashes on a broken sink.
- The sink itself is `tools/log_broadcaster/log_sink.py` running on the desktop (port 9999, dir `D:/hackerverse/laptop_logs/`). If you don't see a file appear, check the sink is up: `curl http://100.79.202.101:9999/_health` — expect `ok`.

---

## Run artifact retrieval

- [ ] After each scored run: `latest=$(ls -td mapping_drone/runs/run_* | head -1); cp -r "$latest" /media/$USER/USB-LABEL/saved_runs_day1/`
- [ ] **Judge-facing artifacts** inside `run_<TS>/`:
  - `landing_pads.json` — Challenge 1 pad list + per-pad validity classification
  - `run_summary.json` — mission metadata (start/end, profile chosen, dict used, validity rule, MAVSDK address that connected)
- [ ] Both USBs get a copy. Do not overwrite previous runs — append timestamp to dirname if `cp` complains.
- [ ] Verify integrity before vacating: `python3 -c "import json; print(len(json.load(open('$latest/landing_pads.json')).get('pads', [])))"`.

---

## Late-breaking pre-flight (from 2026-06-08 org Q&A drops)

Three checks that come from the 2026-06-07 / 2026-06-08 org Q&A and are NOT covered by the older pre-flight list above. Do these in addition, not instead.

- [ ] **Verify drone exposes an RGB color stream (no IR-fallback flag wired yet).** Org confirmed 2026-06-08 12:18 the mapping drone uses Realsense D430 + D450 mixed across runs; neither bare module has an RGB sensor. Run `python -c "import pyrealsense2 as rs; ctx=rs.context(); d=ctx.query_devices()[0]; print([s.get_info(rs.camera_info.name) for s in d.query_sensors()])"`. If RGB present (venue added a bolt-on), proceed as normal. If only IR + depth: `--use-ir-for-aruco` is NOT YET IMPLEMENTED in controller.py (sketch only, see D430_RGB_RISK.md). Escalate to the org marshal immediately and request a venue-bolted RGB camera or the spare unit from the sharing pool. Do NOT attempt to pass the flag — argparse will reject it.
- [ ] **Confirm 4.0 m altitude in active waypoint JSON (above the 3.5 m floor).** Org set minimum flight height to 3.5 m (2026-06-08 12:18). Pre-staged templates are all at 4.0 m (verified — arena_3x3/4x4/6x6/8x8.json + waypoints_2x2_default.json). If a hand-built `waypoints_<DATE>.json` exists, double-check each `alt_m` >= 4.0. controller.py DEFAULT_WAYPOINTS is also at 4.0 m, so omitting `--waypoints-from-json` is also safe altitude-wise.
- [ ] **Pre-yaw at takeoff for the optimal first-scan direction.** Org confirmed 2026-06-08 12:17 launch direction is free (takeoff point fixed). Pick the heading that minimises first-leg flight time to the densest pad cluster A scouted, yaw the airframe to that heading before arming.

---

*Day-1 Runbook v1. Pairs with `runbook.md` Steps 1-3. If something here contradicts `runbook.md`, `runbook.md` wins for event flow; this file wins for fallback mechanics.*

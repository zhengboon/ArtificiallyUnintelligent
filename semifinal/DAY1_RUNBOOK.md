# Day-1 Runbook — Pre-flight + Fallbacks

Companion to `runbook.md`. Do these BEFORE arming. One page. Print on paper.

---

## Pre-flight checks (do BEFORE arming)

- [ ] **UWB sniffer**: `python3 -m tools.uwb_sniffer` (or `python3 semifinal/tools/uwb_sniffer.py`). Confirm `uwb_tag` topic publishes; confirm NED axes match (n=pose.y, e=pose.x, alt=-pose.z). Override with `--topic <name>` if org renamed it.
- [ ] **CLI flags intact**: `python3 -m mapping_drone --help` from `semifinal/`. Verify `--real`, `--mock-all`, `--waypoints-from-json`, `--aruco-dict`, `--mavsdk-address`, `--mavsdk-addresses`, `--gimbal-pitch`, `--max-flight-time-s` are all listed. If any missing → wrong checkout / stale USB copy.
- [ ] **Marker-on-floor camera mount check**: place a known ArUco marker 1 m due north of drone GCS origin. Arm, hover at 1.5 m, watch `STATUS.txt` / log. Confirm world XY of detection lands within **20 cm** of (n=1.0, e=0.0). If off → gimbal mount rotated or Realsense extrinsics wrong; do NOT proceed to scored slot.

---

## If MAVSDK won't connect

- [ ] Pass the full fallback list: `python3 -m mapping_drone.controller --real --mavsdk-addresses serial:///dev/ttyS6:921600,serial:///dev/ttyACM0:115200,serial:///dev/ttyUSB0:57600,udp://:14540,udp://:14550`. Controller tries each with 5 s timeout and logs which one connected.
- [ ] If all 5 fail: check the USB-serial cable is seated, verify the serial port appears (`ls /dev/ttyS* /dev/ttyACM* /dev/ttyUSB*`), check baud against the FC's mavlink param, try a different USB port.
- [ ] Last resort: ask K which serial pyhulax targets on the C2 Windows side and mirror that port/baud on the Ubuntu VM side.

---

## If validity rule is unknown at briefing

- [ ] Pre-staged: `semifinal/configs/valid_ids_unknown.json` (template with `{valid_ids:[], invalid_ids:[]}`).
- [ ] After briefing: copy to `configs/valid_ids_<date>.json`, populate `{valid_ids:[...], invalid_ids:[...]}` from the announced rule.
- [ ] Run controller with: `MAPPING_DRONE_VALIDITY=lookup MAPPING_DRONE_VALIDITY_LOOKUP=configs/valid_ids_<date>.json python3 -m mapping_drone.controller --real ...`
- [ ] No code edit needed — `validity.py` rule `lookup` reads + caches the JSON. Confirm `describe_rule()` output in log mentions the lookup file path.

---

## If ArUco dict is unknown at briefing

- [ ] Pre-printed sheets: `DICT_6X6_250`, `DICT_5X5_100`, `APRILTAG_36h11` (covers the most likely org picks).
- [ ] After briefing: pass `--aruco-dict <orgsAnnouncedDict>`. Normalization is case-insensitive and accepts all 20 standard dicts + `DICT_` prefix (e.g. `DICT_6X6_250`, `6x6_250`, `apriltag_36h11`, ` 36H11 ` all resolve).
- [ ] If `ValueError` at startup → the error message lists every accepted name. Copy-paste the announced name, retry.

---

## If waypoints differ from default

- [ ] Default (4-corner 2×2 box @ 1.5 m) is pre-staged at `configs/waypoints_2x2_default.json`.
- [ ] After A's arena scout: copy current arena layout into `configs/waypoints_<date>.json` as `[[n_m, e_m, alt_m], ...]`.
- [ ] Pass to controller: `--waypoints-from-json configs/waypoints_<date>.json`. Loader replaces the built-in `DEFAULT_WAYPOINTS` fallback.
- [ ] Verify with a mock dry-run before the scored slot: `python3 -m mapping_drone.controller --mock-all --waypoints-from-json configs/waypoints_<date>.json`.

---

## Smoke order before first scored run

1. **UWB sniffer** — `python3 -m tools.uwb_sniffer` for 10 s. Confirm pose stream + NED axes.
2. **RealSense pipeline test** — `python3 -m mapping_drone.tests.smoke_realsense_stationary`. Confirm a profile started (640x480@30 / 848x480@30 / 1280x720@30 / 640x480@15 — log says which).
3. **MockMavsdk dry-run** — `python3 -m mapping_drone.controller --mock-all --waypoints-from-json configs/waypoints_2x2_default.json`. Confirm `runs/run_*/STATUS.txt` + `top_down.png` produced.
4. **RealMavsdk connect-only** — `python3 -m mapping_drone.controller --real --mavsdk-addresses <list> --max-flight-time-s 5`. The controller will connect, attempt to arm + take off, then hit the 5 s wall and disarm cleanly. Goal: confirm MAVSDK negotiates one of the candidate addresses and the drone arms/disarms safely. (No dedicated arm-disarm-only flag — we use the existing `--max-flight-time-s` watchdog as a hard wall.)
5. **First short scored attempt** — Configuration A from `runbook.md`. Watch `STATUS.txt` live.

Do not skip steps. Each step gates the next.

---

## Run artifact retrieval

- [ ] After each scored run: `latest=$(ls -td mapping_drone/runs/run_* | head -1); cp -r "$latest" /media/$USER/USB-LABEL/saved_runs_day1/`
- [ ] **Judge-facing artifacts** inside `run_<TS>/`:
  - `landing_pads.json` — Challenge 1 pad list + per-pad validity classification
  - `run_summary.json` — mission metadata (start/end, profile chosen, dict used, validity rule, MAVSDK address that connected)
- [ ] Both USBs get a copy. Do not overwrite previous runs — append timestamp to dirname if `cp` complains.
- [ ] Verify integrity before vacating: `python3 -c "import json; print(len(json.load(open('$latest/landing_pads.json')).get('pads', [])))"`.

---

*Day-1 Runbook v1. Pairs with `runbook.md` Steps 1-3. If something here contradicts `runbook.md`, `runbook.md` wins for event flow; this file wins for fallback mechanics.*

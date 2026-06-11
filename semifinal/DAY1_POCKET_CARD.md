# Day-1 Pocket Card — Tape to C2 Terminal

**SLOT #3 — be ready by 1430** (prep-window cutoff). Drone slot expected ~1440-1455 depending on slot 1+2 timing. Prep window 1330-1430 = NO MAPPING DRONE FLYING.

One page. Glance, type, fly. **THE runbook is `OP_DOC.md`** (Step 0 fingerprint -> 1 sensors -> 2 check -> 3 frame -> 4 nofly -> 5 fly -> 6 artifacts, with lettered fallbacks) — go there for procedures. Setup is `DAY1_SETUP_SEQUENCE.md`. Strategy is `SCORING_PLAYBOOK.md`.

In EVERY terminal: `export ROS_LOCALHOST_ONLY=1` (also forced at entry; dodges cross-team DDS on the shared `ROS_DOMAIN_ID=0`). One process per terminal.

---

## CRITICAL CHECK (do FIRST, before any of the below)

- **Camera just works on D435 (RGB) and D450 (no-RGB) with no flag** — `RealsenseNode` AUTO-falls-back color->IR if every colour profile fails. `--use-ir-for-aruco` forces IR if you want to skip the fallback probe. Headless (no `cv2.imshow`); tolerates dropped frames.

---

## BEFORE FIRST RUN  (in order — each step gates the next)

Full sequence with fallbacks lives in `OP_DOC.md` (Step 0-4). Quick version:

```
# 0. Per-drone readiness fingerprint
tools/drone_fingerprint.sh

# 1. CHECK — MAVSDK connect on serial:///dev/ttyS6:921600 + print pose, NO arm
python3 -m mapping_drone.moveit_mission --check

# 2. NOFLY — camera + ArUco detect + map, NO arm (ground proof)
python3 -m mapping_drone.moveit_mission --nofly \
  --waypoints-from-json configs/arena_<N>x<N>.json
```

---

## SCORED RUN

```
python3 -m mapping_drone.moveit_mission --fly \
  --waypoints-from-json configs/arena_<N>x<N>.json
```

Pose defaults to `--pose auto` (MAVSDK FC fused NED, auto-fallback to `/uwb_tag`, then hold). Force one with `--pose fc` / `--pose uwb`. Altitude is ALWAYS from the FC (UWB has no Z).

`--aruco-dict` default is **`7X7_1000,6X6_250`** — BOTH dicts scanned every frame (we only guessed 7X7 from Discord). Org markers assumed `DICT_7X7_1000`, IDs 11/45/51/67/101 — **CONFIRM with marshal**. Pass `--aruco-dict <DICT>` (case-insensitive) only to override.

`--max-flight-time-s` default is **420 s** (60 s under the 480 s org cap) — no override needed. Pick the pre-staged `configs/arena_<N>x<N>.json` (3x3 / 4x4 / 6x6 / 8x8) closest to the announced arena size; altitude default **2.5 m** (cage ceiling 3.5 m; code hard-caps 3.2 m; use `--takeoff-alt 3.0` for higher). Confirm `alt_m` in the JSON before launch.

---

## VALIDITY RULE SWAP  (after marshal confirms IDs)

Default rule is already **`lookup` -> `configs/valid_ids_finals.json`** (NOT 'even' — 'even' would mark every odd org ID invalid). Just edit the JSON:

```
# 1. Edit configs/valid_ids_finals.json   {"valid_ids":[...], "invalid_ids":[...]}
#    with the marshal's real valid/invalid split, then run --fly as above.
# Env override (only if pointing elsewhere):
#   MAPPING_DRONE_VALIDITY=lookup MAPPING_DRONE_VALIDITY_LOOKUP=/abs/path.json
```

Confirm `describe_rule()` in log mentions the lookup file path.

---

## IF MAVSDK WON'T CONNECT

Default is `--mavsdk-address serial:///dev/ttyS6:921600`. Re-run `--check` against another endpoint:

```
python3 -m mapping_drone.moveit_mission --check \
  --mavsdk-address serial:///dev/ttyACM0:115200    # or udp://:14540 etc.
```

If it won't connect: reseat USB-serial, `ls /dev/ttyS* /dev/ttyACM* /dev/ttyUSB*`, check FC baud param, mirror K's pyhulax port/baud. See `OP_DOC.md` fallbacks. PX4-ROS2/XRCE fallback only: `python3 -m mapping_drone.px4_mission`.

---

## EMERGENCY ABORT

`Ctrl-C`  — SIGINT triggers land + disarm. Do not Ctrl-Z. Do not yank the radio.

Auto-land watchdogs (no action needed): battery <15%, pose-loss, position-stuck, offboard-setpoint-failure. Disarm only fires after `in_air=False`.

---

## BONUS COLLECTION (between slots)

- **CUAS booth — 4% bonus.** Above & Beyond: Skies & Space zone, MBS L4. Snap a photo of the drone at the Counter UAS booth + screenshot of the zone-explored page on the Brainhack Frontier Exploration System. Do this Day 1 if at all possible; do not let it slip to Day 2.

---

## AFTER EACH RUN

```
ls mapping_drone/runs/run_<TS>/
# expect: STATUS.txt  run_summary.json  landing_pads.json  top_down.png  log.txt  markers/
cp -r mapping_drone/runs/run_<TS>/ /media/$USER/USB-LABEL/saved_runs_day1/
python -c "import json; print(len(json.load(open('mapping_drone/runs/run_<TS>/landing_pads.json')).get('pads', [])))"
```

Both USBs get a copy. Never overwrite — append a suffix if `cp` collides.

---

*See `OP_DOC.md` for the full decision-tree + fallback mechanics. See `DAY1_SETUP_SEQUENCE.md` for 7:30-9:00 setup. This card wins for typing speed; OP_DOC.md wins for nuance.*

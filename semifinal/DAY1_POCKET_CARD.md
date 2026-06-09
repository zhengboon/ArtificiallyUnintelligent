# Day-1 Pocket Card — Tape to C2 Terminal

**SLOT #3 — be ready by ~1445** (C1 starts 1430, slot 3 ≈ 10-15 min in). Prep window 1330-1430 = NO MAPPING DRONE FLYING.

One page. Glance, type, fly. Reference is `DAY1_RUNBOOK.md`. Setup is `DAY1_SETUP_SEQUENCE.md`. Strategy is `SCORING_PLAYBOOK.md`.

---

## CRITICAL CHECK (do FIRST, before any of the below)

- **rs streams: RGB present?** `python -c "import pyrealsense2 as rs; ctx=rs.context(); d=ctx.query_devices()[0]; print([s.get_info(rs.camera_info.name) for s in d.query_sensors()])"`. If **NO** RGB (D430/D450 bare modules expose none — org 2026-06-08 12:18), add `--use-ir-for-aruco` to every controller command below.

---

## BEFORE FIRST RUN  (in order — each step gates the next)

```
# 1. RealSense on USB 3.x (must print 3.x, not 2.x)
python -c "import pyrealsense2 as rs; print(rs.context().query_devices()[0].get_info(rs.camera_info.usb_type_descriptor))"

# 2. UWB sniffer — 10 s, expect uwb_tag topic + NED axes (n=pose.y, e=pose.x, alt=-pose.z)
python tools/uwb_sniffer.py

# 3. RealSense pipeline (interactive — press ENTER per range; 1 s frame timeout)
python -m mapping_drone.tests.smoke_realsense_stationary

# 4. Full mock dry-run (no arm, writes runs/run_*/STATUS.txt + top_down.png)
python -m mapping_drone --mock --waypoints-from-json configs/waypoints_2x2_default.json

# 5. MAVSDK connect-only (real radio, 5 s wall, arms + disarms cleanly)
python -m mapping_drone --max-flight-time-s 5
```

---

## SCORED RUN

```
python -m mapping_drone \
  --aruco-dict <DICT_FROM_BRIEFING> \
  --waypoints-from-json configs/waypoints_<DATE>.json \
  --max-flight-time-s 240
```

`<DICT_FROM_BRIEFING>` — accepts `DICT_6X6_250`, `6x6_250`, `apriltag_36h11`, case-insensitive.

Altitude: `configs/arena_<SIZE>.json` now defaults to **4.0 m** (above the 3.5 m floor org set on 2026-06-08 12:18). Confirm `alt_m >= 4.0` in the JSON before launch.

---

## VALIDITY RULE SWAP  (after org publishes IDs)

```
# 1. Edit configs/valid_ids_<DATE>.json   {"valid_ids":[...], "invalid_ids":[...]}
# 2. Launch with lookup rule:
MAPPING_DRONE_VALIDITY=lookup \
MAPPING_DRONE_VALIDITY_LOOKUP=configs/valid_ids_<DATE>.json \
  python -m mapping_drone --aruco-dict <DICT> \
  --waypoints-from-json configs/waypoints_<DATE>.json --max-flight-time-s 240
```

Confirm `describe_rule()` in log mentions the lookup file path.

---

## IF MAVSDK WON'T CONNECT

```
python -m mapping_drone --mavsdk-addresses \
  serial:///dev/ttyS6:921600,serial:///dev/ttyACM0:115200,serial:///dev/ttyUSB0:57600,udp://:14540,udp://:14550
```

Controller tries each with 5 s timeout, logs which connected. If all 5 fail: reseat USB-serial, `ls /dev/ttyS* /dev/ttyACM* /dev/ttyUSB*`, check FC baud param, mirror K's pyhulax port/baud.

---

## EMERGENCY ABORT

`Ctrl-C`  — SIGINT triggers emergency_land + disarm. Do not Ctrl-Z. Do not yank the radio.

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

*See `DAY1_RUNBOOK.md` for fallback mechanics. See `DAY1_SETUP_SEQUENCE.md` for 7:30-9:00 setup. This card wins for typing speed; runbook wins for nuance.*

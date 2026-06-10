# Start Here — Mapping Drone, explained for a beginner

You don't need to understand the whole codebase. The code is **already written**. Your job is to
**run it in the right order** and read the results. This guide walks you from zero.

> When you want the deep version (every flag, every edge case), read
> [`MAPPING_DRONE_SETUP_GUIDE.md`](MAPPING_DRONE_SETUP_GUIDE.md). This file is the gentle on-ramp.

---

## 1. What are we actually doing? (Challenge 1)

A drone flies over the arena looking **straight down**. It:
1. spots the **ArUco markers** (printed square barcodes, like chunky QR codes) on the landing pads,
2. works out **where** each marker is in the room,
3. builds a **top-down map**, and
4. saves one **folder of results** for the judges.

Everything above is coded. You run one command and a `run_<timestamp>/` folder appears with all the outputs.

## 2. A few words you'll keep seeing

| Word | Plain meaning |
|------|---------------|
| **mapping drone** | the single drone you're setting up (not the little "Hula" swarm drones) |
| **ArUco marker** | a printed black-and-white square the drone detects. Ours are dictionary **`7X7_1000`**, IDs 11/45/51/67/101 |
| **UWB** | the indoor "GPS" — tells the drone its x/y position in the room |
| **RealSense** | the depth camera on the drone (sees distance + picture) |
| **MAVSDK** | the software that talks to the drone's flight controller. It reaches it over an **internal serial port** on the drone's onboard computer (`serial:///dev/ttyS6`) — via the Ethernet/NoMachine link to that computer, **NOT** a network IP. The `udp://` entries are pretend-drone (simulator) fallbacks only. |
| **gimbal / camera angle** | the mapping drone's camera faces straight **down and is FIXED**. `--gimbal-pitch -90` only TELLS the mapping math the camera points down — it does **not** drive a motor. (The tiltable, software-commandable gimbal is on the Hula swarm drones, not this one.) |
| **mock** | *pretend* hardware. Lets you run everything on a laptop with no drone |
| **NoMachine** | remote-desktop app you use to control the drone's onboard computer |
| **run folder** | `mapping_drone/runs/run_<date_time>/` — where results are saved |

## 3. The 3 levels — always do them in this order

1. **Pretend flight on a laptop** (no drone) → proves the code runs and shows you the outputs.
2. **Grounded drone test** (`--nofly`) → real camera/sensors, but it never leaves the ground.
3. **Real flight** → the actual scored run (only with your team, once everything above passed).

Don't skip ahead. If level 1 fails, level 3 will definitely fail.

---

## LEVEL 1 — Pretend flight on a laptop (no drone needed)

**Step 1.** Open a terminal (the black text window).

**Step 2.** Go into the project's `semifinal` folder. On this machine that's:
```bash
cd /home/jugaad/Downloads/ArtificiallyUnintelligent-main/semifinal
```
(On the competition laptop it'll be wherever you copied the code, e.g. `cd ~/brainhack/semifinal`.)

**Step 3.** Check the basics are installed. Copy-paste this whole line:
```bash
python3 -c "import cv2, numpy; from mapping_drone.mapping import ALL_SUPPORTED_DICT_NAMES as D; print(len(D), '7X7_1000' in D)"
```
- ✅ Good: it prints `20 True`.
- ❌ If you see `ModuleNotFoundError: cv2`: run `pip install opencv-contrib-python numpy` and try again.

**Step 4.** Run a pretend flight. This invents a fake drone + fake camera and flies a fake mission:
```bash
python3 -m mapping_drone --mock-all --aruco-dict 6X6_250 --runs-dir /tmp/mocktest
```
- Why `6X6_250` here and not `7X7_1000`? In pretend mode the fake camera draws a `6X6` test marker, so
  using `6X6_250` lets you actually *see* detections. (On the real drone you'll use `7X7_1000`.)
- You'll see lines scroll by like `sighting id=148 ... valid=True` and finally `MockMavsdk: landed`.
- This takes well under a minute.

**Step 5.** Look at what it produced:
```bash
ls /tmp/mocktest/run_*/
cat /tmp/mocktest/run_*/STATUS.txt
```
You should see files: `STATUS.txt`, `landing_pads.json`, `top_down.png`, `markers/`, `run_summary.json`.
`STATUS.txt` should say `State : DONE`. **That's a full successful pipeline run.** 🎉

If Level 1 works, the code is healthy. Move on when you have a drone.

---

## LEVEL 2 — Grounded drone test (`--nofly`) (real sensors, never flies)

Use this when you can power the drone but it **must not take off**. It runs the real camera/UWB and the
full detection pipeline, but **never arms, takes off, or moves**.

**Step 1.** Get onto the drone's computer with **NoMachine** (your team will have the connection set up).

**Step 2.** Open a terminal there and `cd` into `semifinal`.

**Step 3.** Point the drone's camera at a **printed `7X7_1000` marker** (ID 11, 45, 51, 67, or 101).

**Step 4.** Run the grounded test:
```bash
python3 -m mapping_drone --nofly --aruco-dict 7X7_1000 --max-flight-time-s 60
```
Press **Ctrl-C** to stop early. The drone will **not** move — that's the whole point of `--nofly`.

**Step 5.** Check the results folder (`mapping_drone/runs/run_<newest>/`):
```bash
cat mapping_drone/runs/run_*/landing_pads.json
ls  mapping_drone/runs/run_*/markers/
```
- ✅ Good: you see the marker IDs you showed the camera (e.g. `11`), and a saved `.jpg` of each.
- The x/y/z numbers won't be "correct" (the drone is on the ground, not flying) — **that's expected**.
  Level 2 proves *detection works on real hardware*, not navigation.

---

## LEVEL 3 — Real flight (the scored run) — do this WITH your team

Only after Levels 1 and 2 pass. A crash means no second try, so don't rush this alone. Two things must be
set first (your team lead / the marshal gives you the info — see the full guide §3 step 6):
- a **waypoints** file for the real arena size, and
- the **validity rule** (which marker IDs count as "valid").

Then the real run looks like this (one long command):
```bash
MAPPING_DRONE_VALIDITY=lookup \
MAPPING_DRONE_VALIDITY_LOOKUP=configs/valid_ids_10jun.json \
python3 -m mapping_drone \
  --aruco-dict 7X7_1000 \
  --waypoints-from-json configs/waypoints_10jun.json \
  --gimbal-pitch -90 \
  --mavsdk-addresses "serial:///dev/ttyS6:921600,serial:///dev/ttyACM0:115200,serial:///dev/ttyUSB0:57600"
```
(These are **serial** ports on the drone's onboard computer — the flight controller is internal serial, not a
network address. The full guide lists extra `udp://` entries; those are simulator/bench fallbacks that never
reach the real drone, so serial-only is correct at the venue.)
Run it inside `tmux` so it survives if NoMachine disconnects. `Ctrl-C` = emergency land.
**For everything about this step, use [`MAPPING_DRONE_SETUP_GUIDE.md`](MAPPING_DRONE_SETUP_GUIDE.md).**

---

## If something breaks — quick fixes

| You see | What it means | Do this |
|---------|---------------|---------|
| `ModuleNotFoundError: cv2` | OpenCV not installed | `pip install opencv-contrib-python numpy` |
| `cv2.aruco` not found | wrong OpenCV installed | `pip uninstall opencv-python` then `pip install opencv-contrib-python` |
| It hangs at "connecting MAVSDK…" | wrong/blocked drone port | use `--mavsdk-addresses "..."` (the list above), never the bare default |
| `No device connected` (camera) | RealSense unplugged / wrong USB | replug into a **blue USB-3** port |
| Every pad shows `valid=False` | wrong validity rule | set `MAPPING_DRONE_VALIDITY` (ask the marshal for the rule) |
| 0 markers detected on real drone | wrong dictionary, or no-RGB camera | confirm `--aruco-dict 7X7_1000`; if it's a **D450** camera see the full guide's camera section |
| `waypoints list is empty` | used the wrong waypoints file | don't use `waypoints_unknown.json`; make a real one (full guide §3 step 6) |

## Where to go next
- Full detail on every step, flag, and risk: [`MAPPING_DRONE_SETUP_GUIDE.md`](MAPPING_DRONE_SETUP_GUIDE.md).
- What the whole codebase contains: [`CODEBASE_ANALYSIS_10JUN.md`](CODEBASE_ANALYSIS_10JUN.md).
- The organiser's own messages/rules we captured: [`downloaded stuff/`](downloaded%20stuff/).

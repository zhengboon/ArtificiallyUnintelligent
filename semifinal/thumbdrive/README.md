# Finals Thumbdrive — Contents

This is what goes on the USB stick we plug into the C2 Terminal at Marina Bay Sands on 10-11 June 2026.

All 3 members must be present on BOTH days (10 + 11 June 2026, 9am-6pm) at Marina Bay Sands Expo Level 4. The C2 Terminal is Windows-host + Ubuntu 22.04 VM; the mapping drone is accessed via NoMachine from the C2 Terminal.

> Primary RoboMaster detection is ArUco (DICT_6X6_250) via `prototypes/aruco_*.py`. YOLO (`best.pt` / `best.onnx`) is insurance/fallback only, per org clarification 2026-06-06 05:00.

## Required contents (build before T-1 evening)

| Path | Source | Purpose |
|---|---|---|
| `setup.sh` | this dir | One-command bootstrap on the C2 Terminal |
| `controllers/mapping_drone/` | `../mapping_drone/` | Mapping drone code (Challenge 1). build.sh strips internal scratch docs (`FIX_SUMMARY.md`, `FIX_V3_SUMMARY.md`, `REVIEW_SUMMARY.md`) post-copy |
| `controllers/swarm_controller.py` | **TBD — NOT YET BUILT** (`../swarm_controller.py`) | Hula swarm code (Challenge 2A + 2B). BLOCKER for finals Day 2. Deadline T-2 (Mon 8 Jun). Until then USB is incomplete. |
| `controllers/uwb_api_hula_swarm/` | `../uwb_api_hula_swarm/` | Org's UWBParserThread (pyserial @ 921600) — UWB transport for Hula swarm on C2 Windows side. Needed by `swarm_controller.py` |
| `controllers/huladola.py` | `../huladola.py` | Current pyhulax exploration script (reference / starting point for `swarm_controller.py`) |
| `controllers/dola.py` | `../dola.py` | Minimal pyhulax single-drone reference (kept alongside `huladola.py` for fallback / sanity-check) |
| `models/best.pt` | `../../models/best.pt` | K's qualifier model (fallback only) |
| `models/best.onnx` | A produces by T-2 (INSURANCE ONLY) | A's RoboMaster YOLOv11 export (yolo11n.pt base) → org VM converts to .rknn at venue. NOT primary: per org 2026-06-06, RoboMaster detection is ArUco-based (DICT_6X6_250); see `prototypes/aruco_*.py`. Fallback: if `best.onnx` not ready by T-2 evening, ship `best.pt` only and rely on ArUco. |
| `docs/CHALLENGE_BREAKDOWN.md` | `../CHALLENGE_BREAKDOWN.md` | Authoritative rules from org slides |
| `docs/FINALS_PLAN.md` | `../FINALS_PLAN.md` | Per-person day-by-day plan |
| `docs/runbook.md` | `../runbook.md` | Day-of step-by-step (ALSO PRINT) |
| `docs/learning_materials_and_others.md` | `../learning_materials_and_others.md` | Verbatim Discord scrape L1-L5 + finals announcement |
| `docs/pyhulax/` | `../docs/pyhulax/` | Offline mirror of pyhulax SDK docs (full `reference/` subtree + index/sdk/assets) |
| `prototypes/` | `../prototypes/` | Drone-free validation scripts (smoke tests for D435 / ArUco) |
| `learning_material_3_uwb/kolomee.py` | `../learning_material_3_uwb/kolomee.py` | Org's canonical UWB+MAVSDK pattern (reference) |
| `learning_material_4_realsense/*.py` | `../learning_material_4_realsense/*.py` | Org's Realsense + RKNN reference scripts |
| `learning_material_5_yolo_rknn/` | `../learning_material_5_yolo_rknn/` | Org's YOLO→ONNX→RKNN conversion scripts |
| `Train_YOLO_Models_new.ipynb` | `../Train_YOLO_Models_new.ipynb` | Colab notebook for retraining at venue if needed |

## Build commands (run on dev laptop, T-2 Mon evening)

```bash
cd D:/hackerverse
bash semifinal/thumbdrive/build.sh    # creates a clean USB-ready folder at ./thumbdrive_build/
```

Then copy `./thumbdrive_build/` contents to USB#1 and USB#2.

## At venue (Wed 10 June, registration 7:30am)

Bring Photo ID + confirmation email. Smart casual, NO slippers/uncovered footwear. All 3 members should attend BOTH days (10 + 11 June).

The C2 Terminal has TWO sides that need different files:

- **Windows host side** runs the Hula swarm (`pyhulax` + `UWBParserThread.py`). It needs `controllers/swarm_controller.py` (once built), `controllers/uwb_api_hula_swarm/`, `controllers/huladola.py`, `docs/pyhulax/`, and the pyhulax env.
- **Ubuntu 22.04 VM** runs mapping-drone development (the mapping drone itself is reached via NoMachine). It needs `controllers/mapping_drone/`, `models/`, `prototypes/`, `learning_material_4_realsense/`, `learning_material_5_yolo_rknn/`, `Train_YOLO_Models_new.ipynb`.

```powershell
# On the C2 Terminal (Windows side, PowerShell):
# Check the USB drive letter in File Explorer first (commonly D:, E:, F:, or G:)
xcopy <USB-DRIVE>:\* C:\brainhack\ /E /Y
```

```bash
# Then on the Ubuntu 22.04 VM:
# TODO Day 1 AM: confirm VM<->host file transfer mechanism with org coordinator BEFORE running setup.sh.
#   /mnt/c only works under WSL, NOT a real VirtualBox/VMware/Hyper-V VM.
#   Options are: (a) shared folder mount, (b) USB passthrough into VM, (c) scp from Windows host.
#   Replace <SHARE> below with whatever path the chosen mechanism provides.
mkdir -p ~/brainhack && cp -r <SHARE>/brainhack/* ~/brainhack/
cd ~/brainhack && bash setup.sh
```

## Disk hygiene at venue (if "no space left" or VM is >90% full)

```bash
# In the C2 Terminal Ubuntu VM:
rm -rf ~/brainhack/runs/run_*       # old run artifacts
rm -f /tmp/*.log                    # tmp logs
pip cache purge                     # pip cache
```

```powershell
# On the C2 Terminal Windows side (PowerShell):
Remove-Item C:\brainhack\runs\run_* -Recurse -Force -ErrorAction SilentlyContinue   # old run artifacts (Hula swarm logs, UWBParser dumps, realsense .npy)
Remove-Item $env:TEMP\* -Recurse -Force -ErrorAction SilentlyContinue              # tmp files
conda clean --all -y                                                                # conda pkg + tarball cache (if pyhulax env is conda-based)
# Do NOT touch C:\brainhack\ root or models\ — only runs\run_* artifacts.
```

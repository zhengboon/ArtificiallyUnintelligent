# Finals Thumbdrive — Contents

This is what goes on the USB stick we plug into the C2 Terminal at Marina Bay Sands on 10-11 June 2026.

## Required contents (build before T-1 evening)

| Path | Source | Purpose |
|---|---|---|
| `setup.sh` | this dir | One-command bootstrap on the C2 Terminal |
| `controllers/mapping_drone/` | `../mapping_drone/` | Mapping drone code (Challenge 1) |
| `controllers/swarm_controller.py` | `../swarm_controller.py` | Hula swarm code (Challenge 2A + 2B) |
| `models/best.pt` | `../../models/best.pt` | K's qualifier model (fallback only) |
| `models/best.onnx` | A produces by T-2 | A's RoboMaster YOLOv11 export → org VM converts to .rknn at venue |
| `docs/CHALLENGE_BREAKDOWN.md` | `../CHALLENGE_BREAKDOWN.md` | Authoritative rules from org slides |
| `docs/FINALS_PLAN.md` | `../FINALS_PLAN.md` | Per-person day-by-day plan |
| `docs/runbook.md` | `../runbook.md` | Day-of step-by-step (ALSO PRINT) |
| `docs/learning_materials_and_others.md` | `../learning_materials_and_others.md` | Verbatim Discord scrape L1-L5 + finals announcement |
| `docs/pyhulax/` | `../docs/pyhulax/` | Offline mirror of pyhulax SDK reference (25 pages) |
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

## At venue (Wed 10 June 7:45am)

```bash
# On the C2 Terminal (Windows side):
# Open File Explorer → copy USB contents to C:\brainhack\
# Or via PowerShell:
xcopy E:\* C:\brainhack\ /E /Y

# Then in Ubuntu 22.04 VM on the C2 Terminal:
mkdir -p ~/brainhack && cp -r /mnt/c/brainhack/* ~/brainhack/
cd ~/brainhack && bash setup.sh
```

## Disk hygiene at venue (if "no space left" or VM is >90% full)

```bash
# In the C2 Terminal Ubuntu VM:
rm -rf ~/brainhack/runs/run_*       # old run artifacts
rm -f /tmp/*.log                    # tmp logs
pip cache purge                     # pip cache
```

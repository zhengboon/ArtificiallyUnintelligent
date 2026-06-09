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
| `uwb_api_hula_swarm/` | `../uwb_api_hula_swarm/` | Org's UWBParserThread (pyserial @ 921600) — UWB transport for Hula swarm on C2 Windows side. Needed by `swarm_controller.py`. Staged at USB top level (see `build.sh` line 18, 69), not under `controllers/`. |
| `controllers/huladola.py` | `../huladola.py` | Current pyhulax exploration script (reference / starting point for `swarm_controller.py`) |
| `controllers/dola.py` | `../dola.py` | Minimal pyhulax single-drone reference (kept alongside `huladola.py` for fallback / sanity-check) |
| `models/best.pt` | `../../models/best.pt` | K's qualifier model — historical only. ArUco is the sole RoboMaster detector per org 2026-06-06; see `prototypes/aruco_*.py`. A killed YOLO training 2026-06-06 22:13 (`learning_material_5_yolo_rknn/README.md` lines 32-34). `best.onnx` is no longer being produced for finals. |
| `docs/CHALLENGE_BREAKDOWN.md` | `../CHALLENGE_BREAKDOWN.md` | Authoritative rules from org slides |
| `docs/FINALS_PLAN.md` | `../FINALS_PLAN.md` | Per-person day-by-day plan |
| `docs/runbook.md` | `../runbook.md` | Day-of step-by-step (ALSO PRINT) |
| `docs/learning_materials_and_others.md` | `../learning_materials_and_others.md` | Verbatim Discord scrape L1-L5 + finals announcement |
| `docs/pyhulax/` | `../docs/pyhulax/` | Offline mirror of pyhulax SDK docs (full `reference/` subtree + index/sdk/assets) |
| `prototypes/` | `../prototypes/` | Drone-free validation scripts (smoke tests for D435 / ArUco) |
| `learning_material_3_uwb/kolomee.py` | `../learning_material_3_uwb/kolomee.py` | Org's canonical UWB+MAVSDK pattern (reference) |
| `learning_material_4_realsense/*.py` | `../learning_material_4_realsense/*.py` | Org's Realsense + RKNN reference scripts |
| `learning_material_5_yolo_rknn/` | `../learning_material_5_yolo_rknn/` | Org's YOLO→ONNX→RKNN conversion scripts (reference only — we are not retraining at venue per `learning_material_5_yolo_rknn/README.md` lines 32-34) |

## Build commands (run on dev laptop, T-2 Mon evening)

```bash
cd D:/hackerverse
bash semifinal/thumbdrive/build.sh    # creates a clean USB-ready folder at ./thumbdrive_build/
```

Then copy `./thumbdrive_build/` contents to USB#1 and USB#2.

## At venue (Wed 10 June, registration 7:30am)

Bring Photo ID + confirmation email. Smart casual, NO slippers/uncovered footwear. All 3 members should attend BOTH days (10 + 11 June).

The C2 Terminal has TWO sides that need different files:

- **Windows host side** runs the Hula swarm (`pyhulax` + `UWBParserThread.py`). It needs `controllers/swarm_controller.py` (once built), `uwb_api_hula_swarm/` (USB top level, not under `controllers/`), `controllers/huladola.py`, `docs/pyhulax/`, and the pyhulax env.
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

## VM <-> host file transfer (Day-1 plan)

The C2 Terminal is Windows host + Ubuntu 22.04 VM. The USB stick goes into the Windows side; mapping-drone code has to reach the VM. The TODO on line 58 leaves this open — here are the three mechanisms ranked, with the recommendation to try A first and fall back to B if A is broken.

### Option A — VirtualBox Shared Folders (or VMware Shared Folders) via Guest Additions (RECOMMENDED, primary)

Mount a Windows host folder (e.g. `C:\brainhack`) into the VM at `/media/sf_brainhack` (VirtualBox) or `/mnt/hgfs/brainhack` (VMware). Requires Guest Additions / open-vm-tools installed in the VM and the operator's user added to the `vboxsf` group.

- Pros: bidirectional, persistent across reboots, no per-file dance, no USB ownership fight, works for live edits during the day.
- Cons: needs Guest Additions installed in the VM (org may or may not have done this); user must be in `vboxsf` group or mount won't be readable; symlinks across the boundary can misbehave.

```bash
# On the Ubuntu VM:
ls /media/sf_brainhack    # VirtualBox default
ls /mnt/hgfs/brainhack    # VMware default
# If neither exists, fall back to Option B.
mkdir -p ~/brainhack && cp -r /media/sf_brainhack/* ~/brainhack/
```

### Option B — USB passthrough (mount the USB stick directly into the VM) (BACKUP)

In the VirtualBox/VMware menu, attach the USB device to the guest. The Windows host loses access while the VM owns it; the VM mounts it as `/media/<user>/<LABEL>` automatically.

- Pros: zero config inside the VM (no Guest Additions needed), the USB stick we already prepared is the transfer medium.
- Cons: one-direction in practice (USB is the source of truth, edits in the VM don't sync back to Windows); USB ownership conflicts with the host — Windows can't read it while VM has it attached; have to detach/reattach to swap directions.

```bash
# On the Ubuntu VM, after attaching the USB device from the VM menu:
lsblk                                # find the device, e.g. /dev/sdb1
ls /media/$USER/                     # auto-mounted label here
cp -r /media/$USER/<LABEL>/* ~/brainhack/
```

### Option C — `python -m http.server` on host loopback, `curl` from VM

On the Windows host, serve `C:\brainhack` over HTTP on a port the VM can reach (host-only network or NAT with port-forward). From the VM, `curl` or `wget` the files.

- Pros: zero config in the VM beyond `curl`, works even if Guest Additions and USB passthrough are both broken.
- Cons: one-direction only (host -> VM), no encryption, manual file-by-file or recursive wget mirror, breaks if the host firewall blocks the port or the VM network mode is wrong.

```powershell
# On the Windows host (PowerShell), from C:\brainhack:
python -m http.server 8000 --bind 127.0.0.1
# Note the host IP the VM sees (often 10.0.2.2 under NAT, or the host-only adapter IP).
```

```bash
# On the Ubuntu VM:
mkdir -p ~/brainhack && cd ~/brainhack
wget -r -np -nH --cut-dirs=1 http://10.0.2.2:8000/
```

### Day-1 morning checklist

Do this BEFORE running `setup.sh` so we don't burn registration-window time on transport.

1. Verify shared folder mount — on the VM run `ls /media/sf_brainhack` (VirtualBox) or `ls /mnt/hgfs/brainhack` (VMware). If it lists files, Option A is live.
2. Test 1 MB file copy — `dd if=/dev/urandom of=/tmp/test.bin bs=1M count=1 && cp /tmp/test.bin /media/sf_brainhack/test.bin && ls -la /media/sf_brainhack/test.bin` to confirm bidirectional write + size matches. Delete the test file after.
3. Fall back to Option B if A is broken — attach the USB stick to the VM via the VirtualBox/VMware menu, confirm it auto-mounts under `/media/$USER/`, and proceed with `cp -r` from there. If B is also broken (e.g. USB controller not exposed to guest), drop to Option C as last resort.

## Disk hygiene at venue (if "no space left" or VM is >90% full)

```bash
# In the C2 Terminal Ubuntu VM:
rm -rf ~/brainhack/controllers/mapping_drone/runs/run_*   # old run artifacts (matches RunWriter output path in setup.sh line 109)
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

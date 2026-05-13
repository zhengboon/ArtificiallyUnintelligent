# From the stock v3 VM to a working autonomous flight — exhaustive guide

**Audience:** you on a fresh Windows machine, or a teammate replicating
the setup. Assumes you have the v3 VM zip and VMware Workstation Pro
installed.

**Goal:** end at a state where you can arm the simulated x500_vision
drone, take off, and run `searchctl/controller.py` to fly a scripted
waypoint pattern.

**What this guide is:** every fix and workaround I (Claude) discovered
while getting the OP's v3 VM to actually fly. Includes the ones the
workshop docs miss. Roughly ordered: first-time setup → every-session
sequence → things to fix when they break.

> **Date discovered:** 2026-05-12 / 2026-05-13. If the OP updates the VM
> or publishes new fixes, parts of this guide may become obsolete.

---

## Table of contents

1. [Host prereqs (Windows side)](#1-host-prereqs-windows-side)
2. [Import the v3 VM into VMware](#2-import-the-v3-vm-into-vmware)
3. [Configure the VM before first boot](#3-configure-the-vm-before-first-boot)
4. [First boot — log in](#4-first-boot--log-in)
5. [Expand the VM disk (49 GB → 100 GB)](#5-expand-the-vm-disk-49-gb--100-gb)
6. [Install missing Python packages (ultralytics)](#6-install-missing-python-packages-ultralytics)
7. [Verify workshop world files are in place](#7-verify-workshop-world-files-are-in-place)
8. [Patch the workshop code (`is_global_position_ok`)](#8-patch-the-workshop-code-is_global_position_ok)
9. [Deploy our controller (`searchctl/`)](#9-deploy-our-controller-searchctl)
10. [Every-session boot sequence](#10-every-session-boot-sequence)
11. [Run the smoke test (`takeoff_and_land.py`)](#11-run-the-smoke-test-takeoff_and_landpy)
12. [Run the search controller](#12-run-the-search-controller)
13. [Troubleshooting — every error I hit + fix](#13-troubleshooting--every-error-i-hit--fix)
14. [Summary of every change from stock v3](#14-summary-of-every-change-from-stock-v3)

---

## 1. Host prereqs (Windows side)

- **OS:** Windows 10/11 64-bit, 16+ GB RAM, 100+ GB free on the target drive
- **VMware Workstation Pro:** version **17.6.4** (not 25H2 — older, more battle-tested for Gazebo 3D). Free for personal use via Broadcom (one-time signup).
- **Git** for the workspace + GitHub backup
- **Python 3.12** on the *host* (only needed if you run our Discord watcher; the VM has its own Python 3.10)

```powershell
# winget options
winget install Python.Python.3.12 --accept-source-agreements --accept-package-agreements
winget install GitHub.cli --accept-source-agreements --accept-package-agreements
# VMware Workstation Pro is NOT in winget — download from Broadcom directly
```

### Why 17.6 not 25H2

25H2 is newer (post-Nov 2024 rebrand by Broadcom) but had ~6 months less production hardening when we set this up. The v3 VM is built on 17.x. Match the host to the VM era → fewer "is this a VMware regression?" wormholes during the 9 days before qualifier.

---

## 2. Import the v3 VM into VMware

1. Get the v3 VM zip — `Drone-Ubuntu-22.04_v3.zip` (~18 GB) from the OP's Drive link:

   ```
   https://drive.google.com/file/d/1P8E7flFDi5FE0WGT8RZxtZdo-8WUj6GX/view
   ```

2. Move the zip to a drive with **at least 70 GB free** (the extracted form is ~48 GB; you want headroom). I used `D:\hackerverse\vm\`.

3. Extract. Windows Explorer's built-in zip is slow for 18 GB — use `tar` from PowerShell instead, it's bundled with Windows 10+ and is much faster:

   ```powershell
   cd D:\hackerverse\vm
   tar -xf Drone-Ubuntu-22.04_v3.zip
   ```

   On my machine: ~3 minutes for an 18 GB → 48 GB extract on NVMe.

4. After extraction you have a `Drone-Ubuntu-22.04/` folder containing:
   - `Drone-Ubuntu-22.04.vmx` ← **this is the file VMware opens**
   - 13 `*.vmdk` shards (~48 GB total — the virtual disk)
   - `.nvram`, `.vmsd`, `.vmxf`, log files

5. In VMware Workstation: **File → Open** → pick the `.vmx` file. The VM appears in your Library on the left.

---

## 3. Configure the VM before first boot

Right-click the VM in the Library → **Settings**:

| Setting | Recommendation | Why |
|---|---|---|
| Memory | **8 GB** | OP's instruction. More if you have it. |
| Processors | **4 cores** | Anything less and PX4 builds become painfully slow. |
| Display → **Accelerate 3D graphics** | **✓ ON** | Gazebo needs it. Without this, the sim is unusably laggy or won't render. |
| Display → Graphics memory | 1 GB+ | More if available. |
| Network | NAT (default) | Fine for everything. |
| USB | leave default | |

**Snapshot the VM right after import** before booting it (VM → Snapshot → Take Snapshot). Call it `pristine-v3`. If anything goes sideways later, revert is 30 seconds. (Note: once you've taken snapshots, you can't expand the disk — see §5 — so manage snapshots accordingly.)

---

## 4. First boot — log in

Power on the VM. Ubuntu boots. Login screen appears.

**Credentials (per workshop's `Workshop Laptop Requirements.docx`):**

| Field | Value |
|---|---|
| Username | `drone` |
| Password | `password` |

Yes really, the password is literally `password`. Same one is used for `sudo`.

**On first login**, the Ubuntu desktop appears. You'll see:
- A `Desktop/` folder with `codes/`, `QGroundControl-x86_64.AppImage`
- A home dir with `PX4-Autopilot/`, `worlds/`, `tools/`, `ros2_ws/`, `start_px4.sh`

**Don't run `start_px4.sh` yet** — the VM has a disk-space problem you should fix first (§5).

---

## 5. Expand the VM disk (49 GB → 100 GB)

The v3 VM ships with a 49 GB virtual disk that's already **95% full**. The very first `pip install` (e.g. `ultralytics` in §6) will hit `No space left on device` and likely uninstall numpy mid-failure. Fix the disk first.

### 5.1 Host-side expand

1. **Power off the VM** (System menu → Power Off → Shut Down, or `sudo shutdown -h now` in a terminal). Disk expand requires the VM off.

2. Delete any snapshots you took. VMware refuses to expand a disk with snapshots.

3. VMware Workstation → Settings → **Hard Disk** → **Utilities → Expand** → set to **100 GB**.

4. After "Expansion completed" message, click OK. The `.vmdk` files on disk grow.

5. Power the VM back on.

### 5.2 Guest-side resize

The host disk grew, but the partition inside Ubuntu didn't. Verify:

```bash
sudo parted /dev/sda print
```

You'll see `Disk /dev/sda: 107GB` but partition 3 still at 53.7 GB with 53 GB of free space at the end.

**Use `growpart`, NOT `parted resizepart`.** parted refuses to resize a mounted partition even in script mode. `growpart` is designed for online resize:

```bash
sudo apt update
sudo apt install -y cloud-guest-utils
sudo growpart /dev/sda 3
sudo resize2fs /dev/sda3
df -h /
```

Expected `df` output afterwards:
```
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda3        98G   42G   52G  45% /
```

49 → 98 GB, 4 GB free → 52 GB free. **No reboot needed.**

### 5.3 Why this is a one-time thing

The expansion sticks. Future sessions just boot to the 100 GB disk.

---

## 6. Install missing Python packages (ultralytics)

The v3 VM is **missing `ultralytics`** — the library the workshop's own `Detector.py` imports. Without it, every detection-related script crashes on `ModuleNotFoundError`.

```bash
pip install --user ultralytics
```

Important caveats discovered the hard way:

1. **First attempt may upgrade `numpy` from 1.x to 2.x.** That's actually fine — the rest of the workshop stack works with both. If you want to force 1.x:
   ```bash
   pip install --user 'numpy<2'
   ```
2. **If you hit `No space left on device`** during install, pip may have uninstalled `numpy` mid-failure. Recover:
   ```bash
   pip cache purge
   echo password | sudo -S apt clean
   pip install --user 'numpy<2'
   pip install --user ultralytics --no-deps
   pip install --user opencv-python-headless PyYAML requests scipy torch torchvision pillow pandas tqdm matplotlib seaborn psutil
   ```
3. **Don't install `opencv-python` (full)** — apt already installed `python3-opencv`. Use `opencv-python-headless` if you need a pip version (avoids GUI conflicts).

### 6.1 Verify

```bash
python3 -c "from ultralytics import YOLO; import numpy; print('numpy', numpy.__version__); m = YOLO('/home/drone/Desktop/codes/yolov10n.pt'); print('YOLO classes:', len(m.names))"
```

Expected output: `numpy 2.2.6` (or 1.26.4) and `YOLO classes: 80`.

---

## 7. Verify workshop world files are in place

The v3 VM has the `roboverse.sdf` world but the actual mesh (`base6.glb`) lives in **two** places, both required at different points:

- `~/worlds/groundmodel/meshes/base6.glb` — the path referenced by `roboverse.sdf`
- `~/PX4-Autopilot/Tools/simulation/gz/worlds/base6.glb` — redundant copy expected by some workshop scripts

Both should be present in v3. If you ever rebuild/reset PX4:

```bash
ls -lh ~/worlds/groundmodel/meshes/base6.glb
ls -lh ~/PX4-Autopilot/Tools/simulation/gz/worlds/base6.glb
```

Both should be 37 MB. If the PX4 worlds-dir one is missing, copy:

```bash
cp ~/worlds/groundmodel/meshes/base6.glb ~/PX4-Autopilot/Tools/simulation/gz/worlds/
```

### 7.1 x500_vision model — depth camera

The workshop's modified `x500_vision/model.sdf` should include `<include><uri>model://OakD-Lite</uri></include>`. Verify:

```bash
grep -c OakD-Lite ~/PX4-Autopilot/Tools/simulation/gz/models/x500_vision/model.sdf
```

Should print `1`. If `0`, the model is the stock PX4 version (no depth camera). Replace it with the OP's modified file (we have a copy in `optionB/x500_vision_model.sdf`):

```bash
# From host side via vmrun, or copy via shared folder:
cp /path/to/optionB/x500_vision_model.sdf ~/PX4-Autopilot/Tools/simulation/gz/models/x500_vision/model.sdf
```

### 7.2 OakD-Lite must exist

```bash
ls ~/PX4-Autopilot/Tools/simulation/gz/models/OakD-Lite/model.sdf
```

If missing, the workshop posted a lightweight version on May 12. Get it from the Discord link or our local copy at `optionB/OakD-Lite_model.sdf`.

---

## 8. Patch the workshop code (`is_global_position_ok`)

The vision drone has **no GPS**, so `is_global_position_ok` is never `True`. The workshop's reference scripts wait for it forever. Patch `takeoff_and_land.py`:

```bash
cd ~/Desktop/codes
cp takeoff_and_land.py takeoff_and_land.py.orig
sed -i 's/health.is_global_position_ok and //' takeoff_and_land.py
```

The patched line should now read:
```python
if health.is_home_position_ok:
```

instead of:
```python
if health.is_global_position_ok and health.is_home_position_ok:
```

**Other workshop scripts with the same problem** (patch as needed when you go to run them):
- `basic_offboard.py`
- `go_to.py`
- Most `get_*.py` examples

### 8.1 The `*_new.py` files — DO NOT just `cp` over the originals

The workshop has files like `drone_control_new.py`, `GlobalMapper_new.py`, etc. The OP says these are "updated codes." **But:** at least `drone_control_new.py` is **incomplete** — it's missing methods the originals had (`rotate_to_yaw`, others).

If you naively `cp drone_control_new.py drone_control.py`, `avoid.py` will crash with `AttributeError: 'Drone' object has no attribute 'rotate_to_yaw'`.

**Better:** keep the originals. We have `patch_drone_control.py` at the repo root that surgically patches just `arm_and_takeoff` in the original to wait for `is_armable`. Apply it from inside the VM:

```bash
# Copy patch_drone_control.py into the VM first
python3 /path/to/patch_drone_control.py
```

After patching:
```bash
grep -E 'is_armable|wait' ~/Desktop/codes/drone_control.py | head -5
```
should show the new health-wait logic, and `rotate_to_yaw` is still present.

### 8.2 What to keep from the `_new` files

`GlobalMapper_new.py`, `PointCloudPlanner_new.py`, `RRTExample_new.py` look complete and are fine to use directly:

```bash
cd ~/Desktop/codes
cp GlobalMapper.py GlobalMapper.py.preNew.bak && cp GlobalMapper_new.py GlobalMapper.py
cp PointCloudPlanner.py PointCloudPlanner.py.preNew.bak && cp PointCloudPlanner_new.py PointCloudPlanner.py
cp RRTExample.py RRTExample.py.preNew.bak && cp RRTExample_new.py RRTExample.py
```

(Only `drone_control_new.py` is the problematic one.)

---

## 9. Deploy our controller (`searchctl/`)

If you're building your own search controller (Phase 1 of our plan), deploy it into the VM. From the Windows host:

```powershell
$vmrun = "C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe"
$vmx = "D:\hackerverse\vm\Drone-Ubuntu-22.04\Drone-Ubuntu-22.04.vmx"

& $vmrun -T ws -gu drone -gp password runScriptInGuest $vmx /bin/bash "mkdir -p /home/drone/searchctl/logs"
& $vmrun -T ws -gu drone -gp password copyFileFromHostToGuest $vmx `
    "D:\hackerverse\searchctl\controller.py" `
    "/home/drone/searchctl/controller.py"
```

See `searchctl/README.md` for what Phase 1 does and how to grow it.

---

## 10. Every-session boot sequence

Every time you start a fresh sim session (after VM boot, or after Ctrl+C-ing a previous run):

### 10.1 Start the sim

In a VM terminal:

```bash
~/start_px4.sh
```

Menu prompts — answer:
- **Select vehicle:** `1` (x500_vision)
- **Select world:** the number for `roboverse`
- **Start QGroundControl:** `1` (Yes)

Wait **30–60 seconds**. Gazebo loads the space port. PX4 prints lots of init lines. Eventually you'll see:

```
INFO  [px4] Startup script returned successfully
pxh>
```

That's the PX4 shell. Now you type commands at it.

### 10.2 Critical PX4 console setup — every fresh sim

**These three commands are REQUIRED before the drone can arm.** Type at the `pxh>` prompt:

```
param set CBRK_SUPPLY_CHK 894281
param set SIM_BAT_MIN_PCT 100
commander set_ekf_origin 47.397742 8.545594 488.0
```

**Why each:**

| Command | Why |
|---|---|
| `param set CBRK_SUPPLY_CHK 894281` | Bypass PX4's power-supply preflight check. The SITL "battery" otherwise reports unhealthy and the drone can't arm. **The workshop docs don't mention this — discovered 2026-05-13 by tracing the `Preflight Fail: Battery unhealthy` error.** |
| `param set SIM_BAT_MIN_PCT 100` | Pin the simulated battery at 100% so it doesn't drain to "unhealthy" levels mid-flight. Same underlying issue as above; both are needed. |
| `commander set_ekf_origin 47.397742 8.545594 488.0` | Set the EKF origin (since vision drone has no GPS). Without this, `home_position_ok` stays False and arming is impossible. **This is the only one the workshop tells you about (slide 14 of LearningMaterial2).** |

**Note:** if you're running our `searchctl/controller.py`, the first two are applied **automatically via MAVSDK's param plugin** — only the EKF origin needs to be typed in the px4 console. (See §12.1.)

### 10.3 Verify

```
commander check
```

Expected output:
```
INFO  [commander] Preflight check: OK
```

If you see anything else, jump to §13.

### 10.4 QGroundControl

QGC should have started automatically with `start_px4.sh`. If it crashed (you saw a `l.qml:88: TypeError: Cannot read property 'cameras' of null` in the early log), restart it manually in a new terminal:

```bash
~/Desktop/QGroundControl-x86_64.AppImage &
```

The `&` runs it in background. **Without QGC, PX4's "No connection to GCS" preflight check fails** and arming is denied. This is the source of many "why can't I arm" tickets in Discord.

---

## 11. Run the smoke test (`takeoff_and_land.py`)

In a second VM terminal (or via vmrun from host):

```bash
cd ~/Desktop/codes
python3 takeoff_and_land.py
```

Expected (with the patch from §8 applied):
```
Connecting to PX4 SITL on udp://:14540 ...
Connected to drone
Waiting for system health checks...
System is healthy. Ready for commands.
-- Arming
Taking off...
Hovering for 5 seconds...
Landing...
Landed successfully. Script finished.
```

If it fails, see §13.

---

## 12. Run the search controller

### 12.1 Make sure EKF origin is set

The controller auto-applies battery workarounds but cannot set EKF origin from MAVSDK. Either:
- Type `commander set_ekf_origin 47.397742 8.545594 488.0` in px4> console once, OR
- Click anywhere on the QGC map → "Set Estimator Origin"

### 12.2 Run

From the VM (in a second terminal — sim must keep running):

```bash
cd ~/searchctl
python3 controller.py
```

What it does:
- Applies `CBRK_SUPPLY_CHK` and `SIM_BAT_MIN_PCT` via MAVSDK
- Waits up to 45 s for `is_armable=True`
- Arms, takes off to 2 m
- Starts a setpoint pumper at 10 Hz (the heartbeat the workshop's `avoid.py` doesn't have)
- Starts telemetry + watchdog tasks
- Flies a 4 m × 4 m square, rotating to face each leg
- Lands and disarms

Total flight: ~30 s. Logs to `~/searchctl/logs/run_<timestamp>.log`.

---

## 13. Troubleshooting — every error I hit + fix

### `commander check` says `Preflight Fail: Battery unhealthy`

Run the three PX4 params from §10.2. Done.

### `commander check` says `No connection to the GCS`

QGroundControl isn't running. Start it manually:
```bash
~/Desktop/QGroundControl-x86_64.AppImage &
```
Wait ~5 s for it to connect to PX4. `commander check` should now pass.

If QGC crashes with `l.qml:88: TypeError: Cannot read property 'cameras' of null`: this happens when QGC starts before Gazebo finishes loading. Wait until Gazebo is fully rendered (you can see the warehouse + drone), THEN start QGC.

### `commander check` says `horizontal position unstable`

EKF origin needs to be set or re-set. Run:
```
commander set_ekf_origin 47.397742 8.545594 488.0
```
Wait 5–10 s for EKF to converge (it polls the origin into the state estimate).

### MAVSDK script: `is_armable still False after Ns`

Cycle through:
1. Run `commander check` — if it says `Preflight check: OK`, the script is racing PX4. Increase timeout. If anything else, fix that.
2. If `commander check` reports "Resolve system health failures first" but no specific check, restart the sim entirely (Ctrl+C `start_px4.sh`, then `~/start_px4.sh` again). PX4 SITL can get into stuck health states after multiple failed arm/disarm cycles.

### `arm()` returns `COMMAND_DENIED`

Always due to one of the preflight checks failing. Same flow as above — `commander check` is the source of truth.

### Script fails with `ModuleNotFoundError: ultralytics`

§6. The v3 VM doesn't ship it.

### Script fails with `TypeError: Descriptors cannot be created directly` (gz.msgs10)

Protobuf version conflict. Set this env var BEFORE the script runs:
```bash
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
```

It's in `~/.bashrc` already, but **non-interactive shells (vmrun, cron) don't source it**. Always set it explicitly in scripts that import `gz.msgs10`.

### Disk fills up mid-pip-install (`No space left on device`)

§5. Expand the VM disk, then `pip cache purge && sudo apt clean` to recover any space lost during the failure.

### `parted resizepart` says "Partition is being used"

Use `growpart` instead. parted refuses to resize a mounted partition even in script mode. See §5.2.

### Drone arms, takes off, then auto-lands and disarms

PX4's offboard heartbeat timed out. Your script must send a setpoint at least every 0.5 s. If your main loop has any blocking operation longer than that, run the setpoint sender in a **background asyncio task** that calls `set_position_ned` at ~10 Hz.

This is what the workshop's `avoid.py` gets wrong. Our `searchctl/controller.py` solves it with the `setpoint_pumper` task.

### `time.sleep` instead of `await asyncio.sleep`

Same root cause as above — `time.sleep` blocks the asyncio event loop, MAVLink heartbeats stop being processed, PX4 failsafes. **Always use `await asyncio.sleep` in async code.**

### vmrun's `copyFileFromGuestToHost` says "A file was not found"

The script that was supposed to create the file in the guest didn't actually run (likely a quoting issue). Try the command directly in a VM terminal first — if it works there, the vmrun escape was the problem.

### Gazebo is black / extremely laggy

VMware Settings → Display → **Accelerate 3D graphics** must be ON. Reboot the VM after toggling.

### QGroundControl shows wrong drone or won't connect

PX4's mavlink is configured for 14550 (GCS) and 14540 (Onboard). QGC should auto-discover on 14550 (UDP). If you have a firewall in the VM, allow UDP 14540 + 14550.

### PX4 console scrolling locked / can't type

The PX4 console is just a regular terminal. Click into it to refocus. If the terminal is overwhelmed with log spam, you can pipe `~/start_px4.sh` to a file:
```bash
~/start_px4.sh 2>&1 | tee ~/px4.log
```
Now console + file get the output.

---

## 14. Summary of every change from stock v3

If a teammate clones the v3 VM and walks through this guide, here's what'll be different from the OP's shipped state by the end:

| Change | Where | Why |
|---|---|---|
| Disk grew 49 → 98 GB | `/dev/sda3` | v3 ships at 95% used; first pip install runs out of space. |
| `cloud-guest-utils` installed | apt | Provides `growpart` for online partition resize. |
| `ultralytics` installed | pip --user | The workshop's `Detector.py` needs it; v3 doesn't ship it. |
| `torch`, `torchvision`, `opencv-python-headless`, `seaborn`, etc. | pip --user | Ultralytics dependencies. |
| `numpy` may be 2.x instead of 1.26 | pip --user | Side effect of installing ultralytics. Both work. |
| `~/Desktop/codes/takeoff_and_land.py` patched | sed | Remove `is_global_position_ok` check (vision drone has no GPS). Backup at `.orig`. |
| `~/Desktop/codes/drone_control.py` patched | python script | Add `is_armable` wait to `arm_and_takeoff`. Backup at `.preNew.bak`. |
| `~/Desktop/codes/GlobalMapper.py`, `PointCloudPlanner.py`, `RRTExample.py` swapped to `_new.py` versions | cp | OP says these are updated. (`drone_control_new.py` is NOT used — incomplete.) |
| `~/searchctl/controller.py`, `README.md`, `logs/` | added | Our own search controller. |

| Per-session config (not persisted across PX4 restarts) | Where | Why |
|---|---|---|
| `param set CBRK_SUPPLY_CHK 894281` | px4> console | Bypass battery health check — drone unable to arm otherwise. |
| `param set SIM_BAT_MIN_PCT 100` | px4> console | Pin simulated battery at 100%. |
| `commander set_ekf_origin 47.397742 8.545594 488.0` | px4> console | Set the EKF origin since vision drone has no GPS. |

The two `param set` commands are automated by `searchctl/controller.py`. Only the EKF origin remains a one-line manual step per fresh sim.

---

## Appendix: file locations

| What | Path in VM | Path on Windows host (in repo) |
|---|---|---|
| Workshop reference codes | `~/Desktop/codes/` | `codes/Codes/` |
| PX4 worlds | `~/PX4-Autopilot/Tools/simulation/gz/worlds/` | mirror in `optionB/` for reference |
| Modified x500_vision model | `~/PX4-Autopilot/Tools/simulation/gz/models/x500_vision/model.sdf` | `optionB/x500_vision_model.sdf` |
| OakD-Lite model | `~/PX4-Autopilot/Tools/simulation/gz/models/OakD-Lite/model.sdf` | `optionB/OakD-Lite_model.sdf` |
| Our controller | `~/searchctl/controller.py` | `searchctl/controller.py` |
| QGroundControl | `~/Desktop/QGroundControl-x86_64.AppImage` | — |
| Sim launcher | `~/start_px4.sh` | `optionB/start_px4.sh` |
| Run logs | `~/searchctl/logs/run_*.log` | — (don't commit) |

---

## When to re-read this guide

- Onboarding a teammate to the workspace
- After a VM reset / re-import
- Before the qualifier — confirm every per-session command is in muscle memory
- After the OP publishes a v4 VM (parts of this guide may need updating)

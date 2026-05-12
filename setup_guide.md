# Setup Guide — RoboVerse Qualifier dev environment

**Target host:** Windows laptop running **VMware Workstation Pro**.
**Target guest:** **Ubuntu 22.04** — either the workshop's pre-built **v3 VM image** (recommended) or a fresh install with manual setup (Option B).
**Time budget:** 30–60 min for Path A (provided VM); 3–4 hrs for Path B (fresh install).

This is the workshop's officially supported path.

---

## 0. Pick a path

| Path | What you do | Time | Risk |
|---|---|---|---|
| **A. Provided v3 VM** ✅ recommended | Download the OP's pre-built `.vmwarevm` / `.ova`, import, boot. Codes already inside. | ~30 min + download | Low — same image hundreds of teams use |
| **B. Fresh Ubuntu 22.04 + Option B** | Install Ubuntu in VMware, run Option B install script chain. | 3–4 hrs | Medium — version mismatches, missing files |

**Default to Path A.** Use Path B only if you specifically want to know how everything is wired together, or the v3 image breaks for some reason.

---

## 1. Install VMware Workstation Pro on Windows

VMware Workstation Pro became **free for personal use** (Nov 2024 onwards, via Broadcom).

### 1.1 Get the installer

1. Go to https://www.broadcom.com/, sign up for a free Broadcom account if you don't have one.
2. Navigate: **Products → VMware Cloud Foundation → Free Software Downloads → Workstation Pro**.
3. Download the latest Windows installer (`.exe`).

> If Broadcom downloads are blocked for your account (some teams have hit this — see Discord), use the mirror in the workshop materials: a coordinator (`65drones5`) shared a Drive copy at `https://drive.google.com/file/d/1Ctd5-wXzrlDpBu2Lo2dbWg9_XWN17sem/view`.

### 1.2 Install

Run the installer with default options. Reboot if prompted. Launch Workstation Pro.

### 1.3 Verify

Workstation opens to a "Home" tab with "Create a New Virtual Machine" and "Open a Virtual Machine" tiles.

---

## 2. Path A — use the pre-built v3 VM (recommended)

### 2.1 Download the VM

From Discord (`#tech-discussion`, May 5 message from BH2026ROBOVERSE):

> https://drive.google.com/file/d/1P8E7flFDi5FE0WGT8RZxtZdo-8WUj6GX/view?usp=drive_link

It's a large file (likely 10–20 GB). Use a stable connection. Verify the file hash if the OP publishes one.

### 2.2 Extract and import

1. The download is typically a `.zip` containing a folder with `.vmx`, `.vmdk`, etc. Extract somewhere with **at least 60 GB free** (e.g. `D:\VMs\roboverse-v3\`). **Don't put it inside OneDrive / iCloud / Dropbox.**
2. In VMware: **File → Open**, navigate to the extracted `.vmx` file, click Open.
3. The VM appears in your library.

### 2.3 Configure resources before first boot

Right-click the VM → **Settings**:
- **Memory:** 8 GB (workshop says "allocate 8 GB" — you can go higher if your host has 32 GB)
- **Processors:** 4 cores minimum, 6–8 if available
- **Display:** check **Accelerate 3D graphics** (critical for Gazebo)
- **Hard Disk:** keep as-is (don't shrink)
- **Network:** NAT is fine
- **USB:** USB 3.1 is fine

### 2.4 Boot

Click **Power on this virtual machine**. Ubuntu boots, log in with the credentials the OP provided (typically `drone` / `drone` — confirm via the workshop materials or in `#general`).

### 2.5 Sanity check what's already inside

Open a terminal in the VM:

```bash
which gz                                    # /usr/bin/gz
gz sim --version                            # Gazebo Harmonic 8.x
ls ~/PX4-Autopilot                          # source tree should exist
ls ~/PX4-Autopilot/Tools/simulation/gz/worlds/    # roboverse.sdf, base6.glb expected
ls ~/PX4-Autopilot/Tools/simulation/gz/models/x500_vision/   # should have the modified model.sdf
ls ~/Desktop/codes 2>/dev/null || ls ~/codes 2>/dev/null     # workshop codes location
ls ~/start_px4.sh                           # launcher script
python3 -c "import mavsdk; print(mavsdk.__version__)"
python3 -c "from gz.transport13 import Node"
```

If everything resolves, you're done with install. **Skip Path B and go to Section 4**.

If the codes aren't where expected, find them:

```bash
find ~ -name "avoid.py" -not -path "*/.git/*"
find ~ -name "depth_receiver.py" -not -path "*/.git/*"
```

---

## 3. Path B — fresh Ubuntu 22.04 + manual install

Only do this if Path A is broken or unavailable.

### 3.1 Get Ubuntu 22.04 ISO

Download from https://releases.ubuntu.com/22.04/ — pick `ubuntu-22.04.4-desktop-amd64.iso` (or whichever 22.04.x is current).

### 3.2 Create the VM in VMware

1. **File → New Virtual Machine → Custom (advanced)**.
2. Hardware compatibility: latest.
3. Guest OS install: point to the ISO.
4. Guest OS: **Linux → Ubuntu 64-bit**.
5. VM name + location.
6. Processors: 4+, Memory: 8 GB.
7. Network: NAT.
8. Disk: **at least 80 GB**, "Store as a single file."
9. Customize hardware → **Display → Accelerate 3D graphics** ✓.
10. Finish, then power on. Walk through the Ubuntu installer (default options work).

### 3.3 After install, in the Ubuntu VM

These are the OP's Option B steps verbatim from [challenge/OptionB.docx](challenge/OptionB.docx), with annotations.

```bash
# 3.3.1 Dev essentials
sudo apt update && sudo apt upgrade -y
sudo apt install -y build-essential curl git wget software-properties-common
sudo apt install -y python3-pip python3-venv
sudo apt install -y python3-opencv
sudo apt install -y libgz-msgs10-dev
sudo apt install -y python3-gz-transport13 python3-gz-msgs10

# 3.3.2 PX4 (this step takes 15–25 min)
cd ~
git clone https://github.com/PX4/PX4-Autopilot.git --recursive
bash ./PX4-Autopilot/Tools/setup/ubuntu.sh
# Close and reopen the terminal after this finishes.

# 3.3.3 MAVSDK
pip install mavsdk
cd /tmp
wget https://github.com/mavlink/MAVSDK/releases/download/v3.17.1/libmavsdk-dev_3.17.1_ubuntu22.04_amd64.deb
sudo apt install -y ./libmavsdk-dev_3.17.1_ubuntu22.04_amd64.deb
sudo apt install -y libopencv-dev

# 3.3.4 Environment vars (forces OGRE renderer — more reliable in VMs)
cat >> ~/.bashrc <<'EOF'

# --- RoboVerse / PX4 + Gazebo env ---
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
export OGRE_RTT_MODE=Copy
export PX4_GZ_SIM_RENDER_ENGINE=ogre
export GZ_SIM_RENDER_ENGINE=ogre
EOF

sudo ln -s /usr/include/opencv4/opencv2/ /usr/include/opencv2/
source ~/.bashrc
```

> Skip the `ros-humble-ros-gzharmonic` install — not needed for Qualifier.
> Skip OpenVINS install — not needed for Qualifier.

### 3.4 Drop in the workshop-specific files

Copy from the [optionB/](optionB/) folder to where PX4 expects them:

```bash
# Place the launcher in $HOME and make it executable
cp /path/to/hackerverse/optionB/start_px4.sh ~/start_px4.sh
chmod +x ~/start_px4.sh

# World file + mesh
cp /path/to/hackerverse/optionB/roboverse.sdf ~/PX4-Autopilot/Tools/simulation/gz/worlds/
cp /path/to/hackerverse/optionB/base6.glb     ~/PX4-Autopilot/Tools/simulation/gz/worlds/

# Modified x500_vision model — adds the depth camera
cp /path/to/hackerverse/optionB/x500_vision_model.sdf \
   ~/PX4-Autopilot/Tools/simulation/gz/models/x500_vision/model.sdf
```

> **Critical:** the modified `model.sdf` is the May-6 fix the OP published. Without it, `x500_vision` won't have a depth camera and `depth_receiver.py` finds no topic.

### 3.5 Sanity check

```bash
which gz && gz sim --version
python3 -c "import mavsdk; print(mavsdk.__version__)"
python3 -c "from gz.transport13 import Node; print('gz py ok')"
ls ~/PX4-Autopilot/Tools/simulation/gz/worlds/{roboverse.sdf,base6.glb}
ls ~/PX4-Autopilot/Tools/simulation/gz/models/x500_vision/model.sdf
```

---

## 4. Get `hackerverse/` into the VM

The v3 VM already has the workshop codes. You still need to get our **maze generator**, **pastproject reference**, and **context.md** into the VM.

### 4.1 Set up a VMware shared folder (easiest)

In VMware: **VM → Settings → Options → Shared Folders → Always enabled → Add**. Point it at your Windows-side `hackerverse/` directory.

In the Ubuntu VM:

```bash
ls /mnt/hgfs/         # shared folders mount here
# Symlink for convenience:
ln -s /mnt/hgfs/hackerverse ~/hackerverse
ls ~/hackerverse      # should list maze_gen/, pastproject/, context.md, etc.
```

If `/mnt/hgfs/` is empty, install VMware Tools / open-vm-tools:

```bash
sudo apt install -y open-vm-tools open-vm-tools-desktop
sudo systemctl restart open-vm-tools
# Then re-toggle the shared folder in Settings.
```

### 4.2 Or just copy in via drag-drop

Drag the `hackerverse/` folder from Windows Explorer into the Ubuntu desktop. VMware Tools (installed by default in v3) handles the copy.

> ⚠️ **Don't run code from `/mnt/hgfs/`** — shared folder I/O is slow. Either symlink only the data dirs you need, or copy `maze_gen/` and `pastproject/` into the VM's native filesystem (`~/`).

---

## 5. First sim launch — verification

```bash
~/start_px4.sh
```

You'll be prompted:
1. **Select vehicle:** type `1` for `x500_vision`
2. **Select world:** pick `roboverse`
3. **Start QGroundControl?** type `y`

Expected behavior:
- Gazebo Harmonic GUI opens, showing the space port (warehouse with shelves and barrels)
- A drone appears at world origin
- PX4 console shows `INFO [commander] Ready for takeoff!` after a moment
- QGroundControl opens (separate window) and connects automatically
- Initial QGC status: **"Not Ready"** (because no GPS)

Ctrl+C in the terminal where `start_px4.sh` runs shuts everything down.

### 5.1 If Gazebo is black, lagging badly, or crashes

- VM Settings → Display → **Accelerate 3D graphics** must be ✓
- Allocate more memory (try 12 GB if your host can spare it)
- VMware → **Edit → Preferences → Display → Use all monitors in full screen** off if dual-monitor
- The OGRE env vars from §3.3.4 / §7 of the workshop doc must be in `.bashrc` (Path A: already there; Path B: you set them above)
- If still bad, in Workstation **VM → Settings → Hardware → Display**, try toggling "Accelerate 3D graphics" off/on, and changing graphics memory size

---

## 6. The EKF origin trick

The vision drone has no GPS, so PX4 won't arm until you tell it where home is. **Every time** you start the sim:

In the **PX4 console** (the same terminal where `start_px4.sh` is running), wait until you see `commander> ready`, then type:

```
commander set_ekf_origin 47.397742 8.545594 488.0
```

OR in QGroundControl: click anywhere on the map → "Set Estimator Origin".

QGC's status changes from "Not Ready" → "Ready to Fly". Your scripts will arm now.

> Permanent fix: write a small wrapper that watches for the prompt and pipes the command in. Worth doing once you've confirmed manual works.

---

## 7. First Python script — `takeoff_and_land`

Open a **second terminal** (the sim must keep running in the first):

```bash
cd ~/Desktop/codes        # or wherever the v3 codes live; on Path B, cd to wherever you copied them
python3 takeoff_and_land.py
```

Expected:
- `Connected to drone!`
- `Arming...`
- Drone takes off ~5 m, hovers, lands

### 7.1 If it fails on `Preflight Fail: horizontal position unstable`

EKF origin wasn't set, OR the script is checking `is_global_position_ok` (which is never True for vision drone). Comment that line out, keep `is_home_position_ok`. See [context.md](context.md) §"Critical Gotchas" #1.

### 7.2 If it fails on `ModuleNotFoundError: No module named 'mavsdk'`

You're in a venv that doesn't have `mavsdk`. Either install it inside the venv:

```bash
pip install mavsdk
```

Or use system Python. If you create a venv, **always** use `--system-site-packages` so the apt-installed `gz.transport13` and `gz.msgs10` are visible:

```bash
python3 -m venv --system-site-packages ~/venvs/roboverse
source ~/venvs/roboverse/bin/activate
```

---

## 8. Test the maze generator

The generator we built lives in [maze_gen/](maze_gen/). Stdlib Python; matplotlib optional for PNG previews.

```bash
cd ~/hackerverse/maze_gen     # adjust path to wherever you put it in the VM
pip install matplotlib        # only if you want the PNG previews
python3 generate_maze.py --seed 42
```

Outputs land in `maze_gen/output/`.

### 8.1 Use a generated maze in PX4 SITL

```bash
# Backup the original (one-time)
cp ~/PX4-Autopilot/Tools/simulation/gz/worlds/roboverse.sdf{,.backup}

# Drop in the generated world as the new 'roboverse'
cp output/maze_42.sdf ~/PX4-Autopilot/Tools/simulation/gz/worlds/roboverse.sdf

# Re-run the sim
~/start_px4.sh        # pick x500_vision, then roboverse
```

Or keep both available with a unique world name:

```bash
python3 generate_maze.py --seed 42 --world-name maze42
cp output/maze_42.sdf ~/PX4-Autopilot/Tools/simulation/gz/worlds/
~/start_px4.sh        # pick 'maze42' from the world menu
```

> ⚠️ The generator outputs **procedural geometry** — flat-colored cylinders for barrels, gray boxes for walls. The real `roboverse.sdf` uses the baked `base6.glb` mesh which looks photorealistic. Use generated mazes for **layout variety / search-strategy testing**; do final YOLO tuning against the real mesh.

---

## 9. Dev workflow

### 9.1 Inside the VM (recommended for everything)

Install VS Code in the Ubuntu VM:

```bash
sudo snap install code --classic
# OR via apt:
# wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > packages.microsoft.gpg
# sudo install -D -o root -g root -m 644 packages.microsoft.gpg /etc/apt/keyrings/packages.microsoft.gpg
# echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/packages.microsoft.gpg] https://packages.microsoft.com/repos/code stable main" | sudo tee /etc/apt/sources.list.d/vscode.list
# sudo apt update && sudo apt install -y code
```

Useful extensions: **Python**, **Pylance**, **GitLens**.

### 9.2 Two-terminal pattern

Split panes / two terminals open at all times:

- **Term 1**: `~/start_px4.sh` — keep sim running across script edits
- **Term 2**: your Python script — re-run on edit

When you edit code, you usually don't need to restart the sim. Just kill the script and re-run. Restart `start_px4.sh` only for clean state.

### 9.3 Snapshots

Take a VMware **snapshot** after a clean install (Path A) and after first successful flight (Path B). When something breaks, revert in 30 seconds.

```
VM → Snapshot → Take Snapshot...
```

Name them: `clean-install`, `first-flight-ok`, etc.

---

## 10. Troubleshooting cheat sheet

| Symptom | Likely cause | Fix |
|---|---|---|
| Black Gazebo window | 3D accel off / wrong renderer | VM Settings → Display → Accelerate 3D ✓ ; check OGRE env vars |
| `commander: command not found` in PX4 prompt | Typed in a regular shell, not the PX4 console | Make sure you're in the terminal that `start_px4.sh` opened, after the `pxh>` prompt appears |
| `Preflight Fail: horizontal position unstable` | EKF origin not set | Run `commander set_ekf_origin 47.397742 8.545594 488.0` |
| `is_global_position_ok` always False | Expected — vision drone has no GPS | Comment that check out, use `is_home_position_ok` |
| `ModuleNotFoundError: gz.transport13` | Inside a venv without system site packages | Recreate venv with `--system-site-packages` |
| `depth_receiver.py` finds no topic | Stock `x500_vision/model.sdf` lacks depth camera | Replace with the modified one from [optionB/x500_vision_model.sdf](optionB/x500_vision_model.sdf) |
| Sim drifts/oscillates badly | Hardware acceleration glitch | Reduce real_time_factor, allocate more cores, or restart the VM |
| QGC won't connect to drone | Heartbeat lost, wrong UDP | Ensure only one PX4 instance is running; check `udpin://0.0.0.0:14540` is reachable |
| `time.sleep` works but offboard fails | `time.sleep` blocks asyncio → heartbeat dies → PX4 fails over | Always use `await asyncio.sleep` in async code |

---

## 11. What's next

Once `takeoff_and_land.py` flies and a generated maze loads in the sim, you've cleared setup. From here:

1. Read [context.md](context.md) §"Next Concrete Steps" for the development plan.
2. Skim the reference scripts in `codes/` (in the v3 VM, or [codes/Codes/](codes/Codes/) here).
   - Start with `avoid.py`, `Detector.py`, `get_position_with_task.py`.
3. Sketch a `search_controller.py` combining:
   - Frontier exploration (port from [pastproject/remote_laptop_src/nodes/global_controller.py](pastproject/remote_laptop_src/nodes/global_controller.py))
   - 2-altitude search (low for yellow, high for red)
   - Detection deduplication keyed on NED position
   - Restart-resilient state (persist found barrels to disk; clock doesn't stop on crash)

---

## Quick reference — "I'm starting a session"

```bash
# 0. Boot the VM in VMware Workstation (use a snapshot to skip OS-update bloat)

# Term 1 — sim
~/start_px4.sh
# pick 1 (x500_vision), pick roboverse, y to QGC
# wait for "Ready for takeoff", then in the PX4 console:
commander set_ekf_origin 47.397742 8.545594 488.0

# Term 2 — your code
cd ~/Desktop/codes        # or wherever you keep yours
python3 takeoff_and_land.py
```

That's it. From there it's iterating on the controller.

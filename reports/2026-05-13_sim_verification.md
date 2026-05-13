# Session report — 2026-05-13 sim verification

**Driver:** Claude (via vmrun from Windows host into the v3 VM)
**Sim state when started:** user had `~/start_px4.sh` running with `x500_vision` + `roboverse` + QGroundControl, and had set EKF origin to `47.397742 8.545594 488.0`.

---

## What I did, what I expected, what happened

### 1. `takeoff_and_land.py` smoke test

**Did:**
- Backed up `~/Desktop/codes/takeoff_and_land.py` → `.orig`
- Patched it with `sed -i 's/health.is_global_position_ok and //'` to remove the GPS check (vision drone never has `is_global_position_ok`)
- Ran with a 60-second timeout

**Expected:**
- Connect to PX4 over UDP 14540
- Wait for health (now just `is_home_position_ok`)
- Arm → takeoff to ~5 m → hover 5 s → land
- Print landing confirmation

**Result:** ✅ Full pass.
```
Connected to drone
System is healthy. Ready for commands.
-- Arming
Taking off...
Hovering for 5 seconds...
Landing...
Landed successfully. Script finished.
```

**Why it could have failed (and didn't):** if EKF origin hadn't been set, `is_home_position_ok` would also be False forever. Confirms user did the EKF origin trick correctly.

### 2. YOLO load test

**Did:**
- `python3 -c "from ultralytics import YOLO; m = YOLO('yolov10n.pt'); print(...)"`

**Expected:** model loads, prints 80 COCO classes.

**Result (initial):** ❌ `ModuleNotFoundError: No module named 'ultralytics'`. The v3 VM doesn't have ultralytics pre-installed.

**Fix attempt 1:** `pip install --user ultralytics`. ❌ Failed mid-install with `No space left on device`. **And worse:** pip had already uninstalled `numpy` before failing, leaving the VM with no numpy at all.

**Disk diagnosis:** VM root partition was at 95% used (47 GB of 49 GB). Cleared `pip cache purge` and `apt clean` → 87%, 6 GB free.

**Fix attempt 2:** `pip install --user 'numpy<2'` → restored numpy 1.26.4.
Then `pip install --user ultralytics --no-deps` + selectively reinstalled torch/torchvision/etc.

**Result (final):** ✅
- `numpy 2.2.6` (got upgraded during torch install — fine; both 1.x and 2.x work for this stack)
- `YOLO('yolov10n.pt')` loads, 80 classes, sample `['person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck']`
- Disk now at 91%, 4.4 GB free

**Why the failure pattern matters:** the v3 VM is built with a 49 GB disk that's already 95% full. Any non-trivial pip/apt install will trip over disk pressure. Need to manage this going forward (especially before training YOLO weights, which needs torch).

### 3. Camera frame capture

**Did:**
- Subscribed to `/world/roboverse/model/x500_vision_0/link/camera_link/sensor/IMX214/image` via gz-transport Python
- Saved one frame to `/tmp/cam/spawn_view.jpg`
- Copied to host as `D:\hackerverse\spawn_view.jpg`

**Expected:** 1920×1080 RGB frame of whatever the drone is looking at.

**Result (initial):** ❌ `TypeError: Descriptors cannot be created directly` — protobuf version conflict in `gz.msgs10`. The OP's workshop install relies on the env var `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` (set in `~/.bashrc`), but `vmrun runScriptInGuest` doesn't source `.bashrc` for non-interactive shells.

**Fix:** explicitly `export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` at the top of the script.

**Result (final):** ✅ 306 KB JPG, 1920×1080. Image saved as `D:\hackerverse\spawn_view.jpg`.

**Key observations from the actual frame:**
- **2 red barrels with diamond toxic-warning signs** — these are the **distractors** (per the OP's emphatic "NOT THOSE BARRELS WITH TOXIC SIGN" message).
- **1 yellow barrel** (no sign, weathered/sooty appearance) — a **legitimate** ground-level target.
- All three sit at ground level near the spawn point — toxic distractors are placed alongside legitimate yellows specifically to fool naive detectors.
- Environment style: hexagonal-patterned dark gray walls with neon blue accents, white grid lines on the floor (the 4 m cells).

### 4. Roboverse world structure

**Did:**
- Read `~/PX4-Autopilot/Tools/simulation/gz/worlds/roboverse.sdf`
- Listed `~/worlds/groundmodel/meshes/`
- Ran `gz model --list`

**Expected:** discrete SDF models for each barrel, wall, shelf.

**Result:** The world is just `ground_plane + base + x500_vision_0`. Everything (walls, barrels, shelves, pillars, ground decals) is baked into a single 38 MB GLB mesh at `/home/drone/worlds/groundmodel/meshes/base6.glb`. No individual barrel models exist in the SDF.

**Why this matters:**
1. Can't enumerate barrel positions or counts from the SDF — must capture them via camera frames or parse the GLB binary.
2. The maze generator's approach (discrete cylinder + box models) **will look visually different** from the real world — that's fine for layout-strategy testing, not fine for matching textures/lighting that your YOLO sees.
3. Multiple base versions exist: `base4.glb` (4 MB), `base5.glb` (13 MB), `base6.glb` (38 MB) — the OP iterated on the world. **base6 is current.**

---

## Other VM state notes

| Component | State |
|---|---|
| Python | 3.10.12 |
| Gazebo Harmonic | 8.11.0 |
| MAVSDK Python | installed |
| `gz.transport13` Python bindings | works **but** requires `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` |
| `ultralytics` (YOLO) | **just installed** — was missing from v3 VM |
| `numpy` | 2.2.6 (was uninstalled mid-fail, restored) |
| `torch` 2.11.0 + `torchvision` 0.26.0 | installed as ultralytics deps |
| VM disk root `/` | 49 GB total, 4.4 GB free (91% used) |
| `~/Desktop/codes/` | 41 reference scripts present |
| Workshop worlds: roboverse, aprilworld, default, walls, kthspacelab, etc. | all in `~/PX4-Autopilot/Tools/simulation/gz/worlds/` |

---

## Loose ends to flag

1. **Disk pressure is a real risk.** Training a custom YOLO on the VM will likely fill the disk. Options:
   - Train on Google Colab using `Train_YOLO_Models.ipynb` (already in `codes/`)
   - Expand the VM virtual disk via VMware Workstation → Settings → Hard Disk → Expand
   - Move PX4 build artifacts elsewhere

2. **`takeoff_and_land.py.orig` is the unpatched version** in the VM. If you ever need to revert: `cp takeoff_and_land.py.orig takeoff_and_land.py`.

3. **The toxic-barrel color/visual** in the actual world is **red with a diamond sign**, not orange. Maze generator was wrong on this — fixing in this same session.

4. **A second `base6.glb`** is now sitting at `~/PX4-Autopilot/Tools/simulation/gz/worlds/base6.glb` (I copied it there yesterday). The SDF references the one in `~/worlds/groundmodel/meshes/` instead. The duplicate is harmless but redundant. Safe to delete from the worlds dir if you want to claw back 38 MB inside the VM:
   ```
   rm ~/PX4-Autopilot/Tools/simulation/gz/worlds/base6.glb
   ```

5. **`is_global_position_ok` check is removed only from `takeoff_and_land.py`.** Other scripts (`avoid.py`, `basic_offboard.py`, etc.) likely have the same check and will need the same patch when you run them.

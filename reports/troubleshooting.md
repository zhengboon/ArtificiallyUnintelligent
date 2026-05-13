# Troubleshooting guide

Things that can break, in rough order of likelihood, with the exact fix.
Keep this open in another tab during dev.

## Sim won't start / `start_px4.sh` errors

| Symptom | Fix |
|---|---|
| `make: *** [...] Error 1` during build | `cd ~/PX4-Autopilot && make clean && make distclean` then re-run `~/start_px4.sh`. Build artifacts may be stale. |
| Gazebo window opens then immediately closes | usually a model loading error. Check terminal for `Could not load model` lines. If `x500_vision`, ensure `~/PX4-Autopilot/Tools/simulation/gz/models/x500_vision/model.sdf` has `<include><uri>model://OakD-Lite</uri></include>` AND that `OakD-Lite/` exists in the same models dir. |
| Gazebo is black / extreme lag / OGRE errors | VMware Settings → Display → **Accelerate 3D graphics** must be ✓. Try increasing the graphics memory to max. Confirm `~/.bashrc` has `export PX4_GZ_SIM_RENDER_ENGINE=ogre`. |
| `start_px4.sh` shows "PX4 directory not found" | `~/PX4-Autopilot` got moved. Restore from a snapshot or re-clone with `git clone https://github.com/PX4/PX4-Autopilot.git --recursive`. |
| `commander: command not found` when typing `commander set_ekf_origin ...` | You're at a regular shell, not the PX4 console. Make sure you're in the terminal where `start_px4.sh` is running, AFTER the `pxh>` prompt appears. |

## Drone won't arm / fly

| Symptom | Fix |
|---|---|
| `Preflight Fail: horizontal position unstable` | EKF origin wasn't set. In the PX4 console: `commander set_ekf_origin 47.397742 8.545594 488.0`. Wait for `Set position estimate` log line. |
| Health check hangs forever in your script | The script is checking `is_global_position_ok`. Comment it out and keep only `is_home_position_ok`. (For the workshop's `takeoff_and_land.py`: `sed -i 's/health.is_global_position_ok and //' takeoff_and_land.py`) |
| Drone arms, takes off, but immediately enters Failsafe | Likely missed a setpoint. PX4 needs an offboard setpoint at least every 0.5 s. Never use `time.sleep` in async code — use `await asyncio.sleep`. Check your loop timing. |
| `Action error: ARM_DENIED` | QGC will tell you why in the bottom-left banner. Most common: not in offboard mode, or another pre-arm check failed. |

## Python import errors

| Symptom | Fix |
|---|---|
| `TypeError: Descriptors cannot be created directly` from `gz.msgs10` | protobuf version mismatch. Run with `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python python3 your_script.py`. This is in `~/.bashrc` but not loaded by non-interactive shells. |
| `ModuleNotFoundError: ultralytics` | `pip install --user ultralytics` (may need disk cleanup first — see below) |
| `ModuleNotFoundError: numpy` after a failed pip install | pip uninstalled it and the install crashed. `pip install --user 'numpy<2'` to restore. |
| `gz.transport13` not found | install via apt: `sudo apt install -y python3-gz-transport13 python3-gz-msgs10`. The system packages don't go through pip. |
| MAVSDK script fails to connect | Confirm sim is running (`pgrep -a px4` should show the PX4 binary). Confirm UDP port: MAVSDK uses 14540 by default, PX4 SITL streams to 14540 by default. No firewall in VMs but check `~/PX4-Autopilot/ROMFS/px4fmu_common/init.d-posix/px4-rc.mavlink` if changed. |

## VM disk space (likely problem)

The v3 VM ships with a 49 GB disk that's already 95% used. **Any non-trivial install will hit "No space left on device."**

| Quick wins (each ~1–3 GB) | Command |
|---|---|
| Purge pip cache | `pip cache purge` |
| Clean apt | `echo password \| sudo -S apt clean` |
| Remove PX4 build artifacts (slow rebuild next time) | `rm -rf ~/PX4-Autopilot/build` |
| Delete log files | `find ~/.ros/log -mtime +1 -delete` |
| Delete the redundant `base6.glb` in PX4 worlds dir | `rm ~/PX4-Autopilot/Tools/simulation/gz/worlds/base6.glb` |

| Permanent fix | How |
|---|---|
| Expand VM disk (full procedure, verified 2026-05-13) | (1) Power off the VM. (2) VMware → Settings → Hard Disk → **Expand** → new size. (3) Boot VM. (4) `sudo apt install -y cloud-guest-utils` (provides `growpart`). (5) `sudo growpart /dev/sda 3`. (6) `sudo resize2fs /dev/sda3`. (7) `df -h /` to confirm. **Important: use `growpart`, not `parted resizepart`** — parted refuses to operate on a mounted partition even in script mode. `growpart` is designed for online resize. |
| Move heavy stuff to a shared folder | VMware Settings → Options → Shared Folders → Add → point at host folder. Inside VM at `/mnt/hgfs/<name>`. Don't put PX4-Autopilot here (slow I/O); use for YOLO training data, weights, output images. |

## YOLO / Detection

| Symptom | Fix |
|---|---|
| Detector window doesn't appear | `cv2.imshow` needs DISPLAY. If running via SSH/vmrun, no GUI window. Set `enable_display=False` in Detector init and check the `detections/` folder for saved annotated `.jpg` files instead. |
| `yolov10n.pt` detects "bottle", "potted plant" etc., not "barrel" | That's COCO-classes. The OP said a barrel-tuned model is coming on Discord. Or train your own with `Train_YOLO_Models.ipynb` in Colab. |
| Detector window opens but is blank/empty | Image topic isn't publishing. Verify: `timeout 3 gz topic -l \| grep image`. The expected topic name is `/world/roboverse/model/x500_vision_0/link/camera_link/sensor/IMX214/image`. |
| Detector lags / freezes main loop | Image processing must be in a background thread/task. Use the `gzphotodetectorsaver.py` pattern (in `codes/`) — submit images to a worker, don't block on YOLO inference in the main control loop. |

## VMware host-side issues

| Symptom | Fix |
|---|---|
| `vmrun` from PowerShell hangs | Sometimes a stale guest tool state. `vmrun list` should show your VM as `Running`. If it hangs, restart the VM. |
| Can't get camera frame from host (`copyFileFromGuestToHost` fails) | The temp file in the guest got deleted or never created. Make sure the `runScriptInGuest` actually succeeded by saving its stdout to a known file first. |
| VMware Workstation crashes / blue screen | Update Workstation to the latest 17.x. Check for Windows updates. As a last resort, reboot Windows host. |

## Discord watcher

| Symptom | Fix |
|---|---|
| `Permission denied` on first listener run | Settings → Privacy & security → Notifications → **"Let apps access your notifications" = On** |
| Notifications never get captured | Confirm the Discord channel is NOT muted. Right-click channel → Notification Settings → "All Messages". |
| Playwright says `Not logged in — session expired` | Run `run_login.bat` again to re-authenticate. |
| Watcher captures the WRONG server | Re-run `run_login.bat`, ensure you're inside the BH2026ROBOVERSE server before pressing Enter. |
| Discord shows "suspicious activity" check | Stop the polling task immediately. Re-login in the desktop app. The notification listener is zero-risk and can stay running. |

## Last resort

If something's deeply broken in the VM:
1. **Take a snapshot** in VMware when things work. Roll back when they don't. (`VM → Snapshot → Take Snapshot...`)
2. The original v3 zip is still at `D:\hackerverse\vm\Drone-Ubuntu-22.04_v3.zip` (18 GB). Re-extracting gets you a fresh VM, at the cost of losing whatever you've installed since.
3. Open a support ticket on Discord (#support-ticket) — the OP responds within ~3 hours during 08:30–18:00.

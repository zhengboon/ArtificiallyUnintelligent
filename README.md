# BrainHack 2026 RoboVerse — Local Materials

Mirrored learning resources for the Flight Challenge (Qualifier).

## Layout

- `learning/` — Learning Materials 1–3 + Supplementary 1–2 (PDF slides + MP4 lecture videos)
- `challenge/` — Qualifier brief, workshop laptop requirements, Option B setup doc
- `codes/Codes/` — All reference scripts from the Drive folder (use `*_new.py` versions where present; they're the updated copies)
- `optionB/` — Files for the Build-Your-Own setup path (start_px4.sh, roboverse.sdf, base6.glb, modified x500_vision model.sdf)

## Not downloaded

- VM v3 image (intentionally skipped — set up elsewhere)
- VMware Fusion Pro installer (Mac-only)
- `vionode` (OpenVINS extra) — Drive returned "permission/quota" error from the CLI; grab via browser if needed: https://drive.google.com/file/d/1g9q5f2Gqqax78a0uBYnI6SIQ7iwHB3Y/view

## Key facts from the Discord context

- **Drone model:** must use `x500_vision` (no GPS). Qualifier rules forbid GNSS.
- **EKF origin:** vision drone needs `commander set_ekf_origin 47.397742 8.545594 488.0` to know its home (slide 14, LearningMaterial2). Comment out `is_global_position_ok` checks; keep `is_home_position_ok`.
- **Test the sim:** `~/start_px4.sh` → choose `x500_vision` → choose `roboverse` world.
- **Ubuntu 22.04 only.** 24.04/26.04 break Gazebo. WSL2 / Docker untested.
- **OS:** 16 GB RAM machine works fine; allocate 8 GB to the VM.
- **Detection target:** ordinary barrels (NOT the ones with toxic signs). Submission = bounding-box image file (e.g. `detectx.jpg`) and/or live display, ≥50% of barrel inside box.
- **Modified `x500_vision/model.sdf`** is required to expose the depth camera — vanilla PX4 model doesn't have it.

# Learning Material 4 — Realsense Camera

Source: org's `BH2026ROBOVERSE` Discord channel, 2026-06-03 22:27.
Drive folder: https://drive.google.com/drive/folders/1auSeEagUslLpDi19UgkY6lYkQLlan-dv?usp=sharing

**STATUS: files not yet pulled — Drive folder requires Google sign-in despite the `?usp=sharing` link.**

Either the org accidentally restricted the share, or Google's anti-scraping kicked in. Both `drive.google.com/drive/folders/...` and `embeddedfolderview` endpoints return the sign-in page when fetched anonymously.

---

## What we know without the files

From the org's text:

> The teams are to use the depth camera for depth assessment and to take photos, and more importantly to do mapping. pyrealsense2 allows to write python to control the camera. The big difference from gazebo is that pyrealsense allow to directly call it to locations.

Three confirmed responsibilities:
1. **Depth assessment** — read depth at pixels (we already prototyped in `semifinal/prototypes/aruco_realsense.py`)
2. **Photo capture** — RGB stream, save frames
3. **Mapping** — produce some map artifact for the judges

"Directly call it to locations" is fuzzy phrasing — most likely means `rs.rs2_deproject_pixel_to_point(intrinsics, [u,v], depth)`, which converts pixel + depth → 3D camera-frame coordinate. Our prototypes already do this manually with `(u-cx)*Z/fx`; the SDK has a helper.

This material is **bundled with the mapping drone** (see L3, L5). The Realsense lives on the mapping drone, not on the Hula swarm.

---

## How to fix the access issue

**For the user to do:**
1. Open https://drive.google.com/drive/folders/1auSeEagUslLpDi19UgkY6lYkQLlan-dv?usp=sharing in a logged-in browser.
2. Right-click each file → Download.
3. Drop the files into this directory (`semifinal/learning_material_4_realsense/`).
4. I'll auto-detect them and analyse.

**Alternative:** ask org to re-share with permissions set to "Anyone with the link can view" (not "Restricted").

---

## What we have in the meantime

Our `semifinal/prototypes/` already covers the basic patterns:

- [`realsense_verify.py`](../prototypes/realsense_verify.py) — confirms `pyrealsense2` install, intrinsics, a centre-pixel depth reading
- [`aruco_realsense.py`](../prototypes/aruco_realsense.py) — full pipeline: ArUco detection → depth at marker centre → 3D camera-frame coords via manual unprojection

The org's reference code (when we can download it) likely shows:
- Pipeline setup with both depth + RGB streams
- `rs.align` to align depth to colour (we already do this)
- `rs.rs2_deproject_pixel_to_point` helper (we use manual formula, equivalent)
- Possibly: `pointcloud()` API for full point-cloud export
- Possibly: filtering (decimation, spatial, temporal) for cleaner depth
- Possibly: `rs.colorizer()` for visualisation (we already use)
- Possibly: depth-to-disparity tricks for accuracy at distance

We'll fill these in once the files are pulled.

---

## Open questions

1. Is the Realsense on the **mapping drone only**, or also on a Hula? (L3+L5 context strongly suggests mapping drone only.)
2. What model — D435 (our existing camera), D430, D450? They share APIs; only matters for IMU + max-range edge cases.
3. What "mapping" artifact does the judge expect — top-down PNG? Point cloud `.ply`? Occupancy grid `.npy`?
4. Does the org's reference code use the `rs.pointcloud()` API for full point cloud export, or just per-pixel unproject?

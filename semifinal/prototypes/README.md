# Semi-final Prototypes

Standalone scripts that validate pieces of the semi-final stack BEFORE we have drones in hand. Run order is bottom-up: webcam → Realsense → fused ArUco+depth.

All scripts are dependency-light and printable to a single screen. Read before running.

## Files

| Script | What it validates | Drone needed? |
|---|---|---|
| `realsense_verify.py` | D435/D430/D450 + `pyrealsense2` install + intrinsics + a depth reading | ❌ no |
| `aruco_webcam.py` | `cv2.aruco` (DICT_6X6_250) detection on any webcam | ❌ no |
| `aruco_realsense.py` | ArUco + RealSense depth → 3D camera-frame coords (the real pattern) | ❌ no |

## Quick start

```bash
# Install deps once
pip install pyrealsense2 opencv-contrib-python numpy

# 1. Confirm the depth camera works
python3 realsense_verify.py            # one-shot
python3 realsense_verify.py --gui      # live preview

# 2. Confirm OpenCV ArUco works on a webcam
python3 aruco_webcam.py                # default webcam, DICT_6X6_250

# 3. End-to-end: ArUco from the Realsense + 3D unproject via depth
python3 aruco_realsense.py
python3 aruco_realsense.py --jsonl detections.jsonl   # log every detection
python3 aruco_realsense.py --no-gui                   # headless
```

## Where to get test markers

Either generate locally:
```python
import cv2, numpy as np
d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
img = cv2.aruco.generateImageMarker(d, 5, 400)  # id=5, 400x400 px
cv2.imwrite("marker_005.png", img)
```

Or download a sheet from https://chev.me/arucogen/ — pick "Original ArUco", 6x6, dict size 250.

Print at A4 with at least 5cm marker side; matte paper if possible.

## What "good" output looks like

### realsense_verify
```
Camera: Intel RealSense D435
Serial: 1234567890
FW:     5.16.0.1
Depth intrinsics: fx=384.55 fy=384.55 cx=320.50 cy=240.00  (640x480)
Color intrinsics: fx=608.12 fy=608.12 cx=323.71 cy=240.42  (640x480)

Depth frame: shape=(480, 640) dtype=uint16
Color frame: shape=(480, 640, 3) dtype=uint8
Center pixel (320,240) depth = 1247 mm = 1.247 m
  GOOD: realistic depth reading at centre

OK — Realsense is working.
```

### aruco_webcam (with marker ID 5 in view)
```
Webcam 0: 1280x720
Dictionary: DICT_6X6_250

Live — point camera at a printed marker. 'q'/Esc to quit, 's' to save.
+ marker(s) appeared: [5]
- marker(s) lost:    [5]
+ marker(s) appeared: [5, 12]
```

### aruco_realsense (marker held ~80cm in front)
```
Camera: Intel RealSense D435
Color intrinsics: fx=608.12 fy=608.12 cx=323.71 cy=240.42
Dictionary: DICT_6X6_250

+ ID=5  (X=+0.043, Y=-0.012, Z=0.821) m   distance=0.823 m
- ID=5 lost
+ ID=5  (X=+0.045, Y=-0.010, Z=0.815) m   distance=0.817 m
```

The 3D coords are in the **camera frame** (X=right, Y=down, Z=forward away from lens). To get world coords later, fuse with drone pose:

```
world_xyz = R_cam_to_drone @ cam_xyz + drone_position
```

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `RuntimeError: No device connected` | USB cable, port, or driver |
| `pipeline.start failed: ... could not negotiate` | Wrong resolution/fps for the device, or USB 2.0 (need 3.0+) |
| Center depth always 0 | Pointed at glass/mirror/dark surface, too close (<17cm), or USB 2.0 |
| Webcam window black | Wrong `--cam` index; try `--cam 1` or `--cam 2` |
| ArUco never detects | Wrong dictionary, marker too small/far, blur, glare, or marker printed badly |
| `module 'cv2.aruco' has no attribute 'ArucoDetector'` | Need `opencv-contrib-python` (not just `opencv-python`), version 4.7+ |

## When to delete these

These are validation prototypes, not part of the swarm controller. Once `semifinal/controller.py` integrates the same patterns, you can keep these around for re-verification but they're not on the dependency path.

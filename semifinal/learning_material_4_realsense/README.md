# Learning Material 4 — Realsense Camera (UNLOCKED + PULLED)

Source: org's `BH2026ROBOVERSE` Discord channel, 2026-06-03 22:27 (re-shared with corrected permissions 2026-06-05 04:45).
Drive folder: https://drive.google.com/drive/folders/1auSeEagUslLpDi19UgkY6lYkQLlan-dv

## Files

8 scripts. All are minimal, single-file examples that run standalone on a machine with `pyrealsense2 + opencv-python + numpy`.

| File | Purpose | Key APIs |
|---|---|---|
| `getRGB.py` | Capture + show RGB only | `rs.stream.color`, BGR8 |
| `getDepth.py` | Capture + show colourised depth + center pixel distance | `rs.stream.depth`, Z16, `depth_scale`, `colorizer` |
| `getInfra.py` | Capture left + right infrared frames | `rs.stream.infrared` 1/2, Y8 |
| `getSyncDepthColor.py` | Align depth ↔ color, overlay center distance on RGB | `rs.align(rs.stream.color)`, `depth_frame.get_distance(cx, cy)` |
| `getDepthPointCloud.py` | Generate point cloud vertices | `rs.pointcloud()`, `pc.calculate()`, `points.get_vertices()` |
| `generateTopDown.py` | **★ Top-down occupancy grid from depth — Challenge 1 template** | manual deproject + grid binning + morphological close/open |
| `getDepthAndDetect.py` | **★ YOLO RKNN + depth → 3D coord per detection** | `RKNNLite`, `decode_yolov11_rknn`, `rs.rs2_deproject_pixel_to_point` |
| `rknndecoder.py` | YOLOv11 RKNN output → boxes+scores+classes (NMS + sigmoid) | `cv2.dnn.NMSBoxes`, sigmoid, xywh→xyxy |

## Camera-frame convention (CRITICAL — from `generateTopDown.py` comments)

When the camera is **facing down** (the gimbal configuration for mapping):

```
        Camera frame:
              Z (Forward)
                 ^
                 |
                 |
                 O------> X (Right)
                /
               /
              Y (Down)
```

The top-down occupancy grid is in the **X-Z plane** (camera-Z = grid North, camera-X = grid East):

```
        Top-down grid:
               Forward (North) y
                    ^
                    |
                    |
        Left <-----+-----> Right (East) x
                    |
                    |
```

This is the canonical mapping. Match this exactly or our occupancy grid is rotated.

## `generateTopDown.py` — what to copy

Settings to use (org's defaults):
```python
WIDTH, HEIGHT = 640, 480
MAX_DEPTH = 5.0   # m
MIN_DEPTH = 0.2   # m
GRID_RESOLUTION = 0.05   # 5 cm/cell
GRID_WIDTH = GRID_HEIGHT = 200   # 10 m × 10 m
```

Pipeline:
1. `pipe.start()` with depth Z16 @ 30fps
2. Per frame:
   - depth in metres: `depth_m = depth_image * depth_scale`
   - mask valid: `(depth_m > 0.2) & (depth_m < 5.0)`
   - deproject all pixels: `x = (u-cx)*z/fx`, `y = (v-cy)*z/fy`, `z = depth_m`
   - bin into grid by `(x, z)` (camera-frame X = grid horizontal, camera-frame Z = grid vertical)
   - `cv2.morphologyEx CLOSE then OPEN` with 3×3 kernel to denoise
3. Visualise as 600×600 image with camera at bottom-center

For Challenge 1 we'll accumulate across frames as the drone flies (each frame's grid → global grid via UWB pose), then export the final grid + scan for ArUco landing pads.

## `getDepthAndDetect.py` — the canonical mapping-drone runtime pattern

Exactly what we need on the mapping drone:

```python
rknn = RKNNLite()
rknn.load_rknn("yolo11n.rknn")          # → swap "best.rknn" once K's model is converted
rknn.init_runtime()

pipe.start(); align = rs.align(rs.stream.color)

while True:
    frames = align.process(pipe.wait_for_frames())
    depth = frames.get_depth_frame()
    color = frames.get_color_frame()

    # YOLO via NPU
    input_img = cv2.resize(np.asanyarray(color.get_data()), (640, 640))
    img_input = np.expand_dims(cv2.cvtColor(input_img, cv2.COLOR_BGR2RGB).astype(np.uint8), axis=0)
    outputs = rknn.inference(inputs=[img_input])

    boxes, scores, classes = decode_yolov11_rknn(outputs, input_img.shape, (640, 640))

    for box, score, cls in zip(boxes, scores, classes):
        x1, y1, x2, y2 = box.astype(int)
        cx, cy = (x1+x2)//2, (y1+y2)//2
        distance = depth.get_distance(cx, cy)
        if distance <= 0: continue
        X, Y, Z = rs.rs2_deproject_pixel_to_point(depth_intrinsics, [cx, cy], distance)
        # camera-frame XYZ in metres — fuse with drone NED pose to get world coords
```

**Use `rs.rs2_deproject_pixel_to_point()` instead of manual `(u-cx)*Z/fx` math.** It's the org's chosen API; using it guarantees we match the conventions.

## `rknndecoder.py` notes

- Designed for **YOLOv11** — but `testrknn_with_display.py` in L5/detection has a parallel `post_process_yolov8` for YOLOv8. So both versions are supported.
- K's qualifier `best.pt` is YOLOv8 — use the YOLOv8 decoder, not the YOLOv11 one.
- The org applies **sigmoid on class scores** for the YOLOv11 path — this is an RKNN export quirk. Worth checking if our converted YOLOv8 needs the same.

## ArUco — NOT in this folder

The slides confirm ArUco is the Challenge 1 target type (landing-pad markers). But the org didn't include an ArUco script in L4/L5. The L2 Discord sample code is the reference. Our `prototypes/aruco_realsense.py` is the canonical implementation pattern.

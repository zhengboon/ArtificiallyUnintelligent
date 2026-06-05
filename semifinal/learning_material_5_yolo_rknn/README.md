# Learning Material 5 — YOLO ONNX/RKNN Conversion + Detection (UNLOCKED + PULLED)

Source: org's `BH2026ROBOVERSE` Discord channel, 2026-06-03 22:33 (re-shared with corrected permissions 2026-06-05 04:45).

Drive folders:
- Convert: https://drive.google.com/drive/folders/1JTDV6XueZWJyXB-L_yMaLAEum_lQntK3
- Detection: https://drive.google.com/drive/folders/1dVcath0iW3VGA3biqiCDCcZKRfzVPGEa

> **Important from org:** "These codes will be available on the machine provided by the organiser. It is the VM within that machine as this requires ubuntu 22.04 again."
>
> So we don't strictly need to install `rknn-toolkit2` on our laptops — it's already on the org-provided VM. But we should be familiar with the workflow so we don't waste venue time.

## Files

### `convert/` — `.pt → .onnx → .rknn`

| File | What |
|---|---|
| `convertyolotoonnx.py` | Minimal one-liner: `model.export(format="onnx", opset=12, simplify=True, dynamic=False, end2end=False)` |
| `convertyolotoonnx_2.py` | Annotated version with full args + comments. Use this for guidance. |
| `convertrknn.py` | Minimal `.onnx → .rknn` for **target rk3588**, mean=[0,0,0], std=[255,255,255], fp16 (no quant) |
| `convertrknn2.py` | Verbose+quantized variant with `optimization_level=3` + `quantized_dtype='w8a8'` for int8 |

### `detection/` — runtime YOLO on the mapping drone

| File | What |
|---|---|
| `rknndecoder.py` | YOLOv11 post-processing (sigmoid → NMS → scale boxes back) |
| `getDepthAndDetect.py` | Realsense + RKNN YOLO + per-detection 3D unprojection (same as `L4/getDepthAndDetect.py`) |
| `testrknn_with_display.py` | Standalone single-image RKNN test with built-in `post_process_yolov8` decoder |

## Key confirmed parameters

These are not assumptions anymore — they're in the org's code:

| Parameter | Value | Source |
|---|---|---|
| Target SoC | **`rk3588`** (alternatives listed: `rk3566`, `rk3568`, `rk3576`) | `convertrknn.py` line 8 |
| Mean values | **`[[0, 0, 0]]`** | both `convertrknn*.py` |
| Std values | **`[[255, 255, 255]]`** | both `convertrknn*.py` |
| Quantization | Default **fp16 (do_quantization=False)**, optional int8 w8a8 | `convertrknn*.py` |
| Optimization level | `3` (max) in v2 | `convertrknn2.py` |
| ONNX opset | `12` | `convertyolotoonnx.py` |
| ONNX dynamic axes | **`False`** (RKNN requires static shapes) | `convertyolotoonnx_2.py` |
| ONNX simplify | **`True`** (RKNN parser needs clean graph) | `convertyolotoonnx_2.py` |
| Input image size | **`640 × 640`** | `getDepthAndDetect.py`, `testrknn_with_display.py` |
| Inference framerate | **~50 fps** on RK3588 NPU (per slides) | slide 12 |
| Confidence threshold | `0.25` (NMS), `0.45` IOU | `rknndecoder.py` |
| Colourspace | **RGB** input (convert from BGR) | `getDepthAndDetect.py` line 395 |

## Conversion workflow (canonical)

```bash
# On host with rknn-toolkit2 (provided org VM, or our own Ubuntu 22.04)

# Step 1: PT → ONNX (uses ultralytics)
python convertyolotoonnx_2.py    # adjust path to best.pt

# Step 2: ONNX → RKNN (uses rknn-toolkit2)
python convertrknn.py            # produces best.rknn for rk3588

# Step 3: test on a sample image (no NPU host needed if mock — but use the VM)
python testrknn_with_display.py
```

## Runtime workflow (on the mapping drone)

```python
from rknnlite.api import RKNNLite
from rknndecoder import decode_yolov11_rknn, draw_detections   # or our YOLOv8 equivalent

rknn = RKNNLite()
rknn.load_rknn("best.rknn")
rknn.init_runtime()

# ... grab Realsense frames, run inference, decode, fuse with depth ...
```

## YOLOv8 vs YOLOv11 — important nuance

- K's qualifier `best.pt` is **YOLOv8** (Ultralytics, 3 classes)
- Org's `rknndecoder.py` is for **YOLOv11**
- Org's `testrknn_with_display.py` has a separate `post_process_yolov8` function for YOLOv8

→ For our `best.rknn` (from K's YOLOv8 model), use `post_process_yolov8` from `testrknn_with_display.py`, not the YOLOv11 decoder.

If we retrain on YOLOv11 (likely better for the new RoboMaster target class), use `decode_yolov11_rknn`.

## Open questions to answer at the venue

1. Confirm the C2 Terminal VM has `rknn-toolkit2` pre-installed (it should — org confirmed in their note)
2. Confirm the mapping drone has `rknnlite` pre-installed (it should — drone is Ubuntu 22.04 with ROS2 + OpenCV per slide 9)
3. Confirm `rs.rs2_deproject_pixel_to_point` exists in the venue's `pyrealsense2` version (should — it's part of standard API)
4. Check if our YOLOv8 conversion needs a sigmoid in post-process or not (test on first sample image)

## Cross-check with our prototypes

Our `semifinal/prototypes/aruco_realsense.py` already does the manual `(u-cx)*Z/fx` math. Org's pattern uses `rs.rs2_deproject_pixel_to_point(intr, [u,v], distance)` instead. Both produce identical results, but **prefer the org's API** in the final code for consistency with their reference patterns.

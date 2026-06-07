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

### `Train_YOLO_Models_new.ipynb` — historical org reference (NOT used in finals)

Included here as historical org reference only. YOLO training was killed by A on 2026-06-06 22:13 and is **not** part of the finals stack — the mapping drone now relies on ArUco-only detection via `mapping_drone/`. The notebook is kept in this folder because it belongs alongside the rest of the org's YOLO/RKNN material for archival continuity, not because anything in the runtime references it.

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

## YOLOv11 is the confirmed base (per org 2026-06-05 6:45 pm)

> "Hi, please use yolo11 as the base when you custom train. Please revisit the link in the learning material that has the rkn py files. There are updated version. The updated version ends with 2."
>
> — BH2026ROBOVERSE OP, in reply to K's question

**Decisions locked in:**
- Use `yolo11n.pt` as the training base (NOT `yolov8n.pt`)
- Use `convertyolotoonnx_2.py` (the `_2` variant) — annotated, full args, RKNN-friendly
- Use `convertrknn2.py` (the `_2` variant) — verbose, `optimization_level=3`, int8 option
- Use `decode_yolov11_rknn` from `rknndecoder.py` for post-processing
- K's qualifier `best.pt` (YOLOv8) is moot — A must retrain on YOLOv11 architecture for the RoboMaster targets

The `testrknn_with_display.py` `post_process_yolov8` function is still useful as reference but won't be our runtime path.

## Open questions to answer at the venue

1. Confirm the C2 Terminal VM has `rknn-toolkit2` pre-installed (it should — org confirmed in their note)
2. Confirm the mapping drone has `rknnlite` pre-installed (it should — drone is Ubuntu 22.04 with ROS2 + OpenCV per slide 9)
3. Confirm `rs.rs2_deproject_pixel_to_point` exists in the venue's `pyrealsense2` version (should — it's part of standard API)
4. Check if our YOLOv8 conversion needs a sigmoid in post-process or not (test on first sample image)

## Cross-check with our prototypes

Our `semifinal/prototypes/aruco_realsense.py` already does the manual `(u-cx)*Z/fx` math. Org's pattern uses `rs.rs2_deproject_pixel_to_point(intr, [u,v], distance)` instead. Both produce identical results, but **prefer the org's API** in the final code for consistency with their reference patterns.

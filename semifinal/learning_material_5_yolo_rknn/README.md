# Learning Material 5 — Object Detection on Mapping Drone (YOLO → ONNX → RKNN)

Source: org's `BH2026ROBOVERSE` Discord channel, 2026-06-03 22:33.
Drive folders:
- **Convert** (`.pt → .onnx → .rknn`): https://drive.google.com/drive/folders/1JTDV6XueZWJyXB-L_yMaLAEum_lQntK3?usp=drive_link
- **Detection** (run RKNN model): https://drive.google.com/drive/folders/1dVcath0iW3VGA3biqiCDCcZKRfzVPGEa?usp=drive_link

**STATUS: files not yet pulled — both folders auth-gated, user confirmed org sharing config set wrong, awaiting fix.**

---

## What we know without the files

From the org's text:

> YOLO is still an option for you to code code detection with your team. The compute module has NPU that can speed up the YOLO detection. But you need to convert the custom YOLO into ONNX and to RKNN format.

Three confirmed facts:
1. **Mapping drone has an NPU** for YOLO acceleration
2. **RKNN format** = Rockchip Neural Network format → SBC is a **Rockchip SoC**, most likely RK3588 (6 TOPS NPU, fastest), possibly RK3568 (slower)
3. **Two-step conversion**: `.pt → .onnx → .rknn`

Likely candidates for the mapping drone's compute module:
- Orange Pi 5 / Orange Pi 5 Plus (RK3588, 6 TOPS NPU)
- Radxa Rock 5B (RK3588, 6 TOPS NPU)
- Radxa CM5 (RK3588, 6 TOPS NPU)
- Possibly smaller: Orange Pi CM4 (RK3566, 1 TOPS), or others

---

## Conversion pipeline (general pattern, until org's code is pulled)

```
PyTorch YOLO (.pt)
       ↓ ultralytics .export()
ONNX (.onnx)
       ↓ rknn-toolkit2 .build() / .export_rknn()
RKNN (.rknn)
       ↓ copy to drone
On-board NPU inference
```

### Step 1: `.pt → .onnx`
```python
from ultralytics import YOLO
model = YOLO("best.pt")
model.export(format="onnx", imgsz=640, opset=12, simplify=True)
# -> best.onnx
```

### Step 2: `.onnx → .rknn`
```python
from rknn.api import RKNN
rknn = RKNN(verbose=True)
rknn.config(mean_values=[[0, 0, 0]], std_values=[[255, 255, 255]],
            target_platform="rk3588")          # or rk3568 etc
rknn.load_onnx(model="best.onnx")
rknn.build(do_quantization=True, dataset="calibration_images.txt")
rknn.export_rknn("best.rknn")
rknn.release()
```

Need a small calibration image set (~100 frames from typical conditions) for quantisation. K already has training data — can sample from that.

`rknn-toolkit2` runs on **x86 Linux** (not on the drone itself). Conversion happens on a host, output `.rknn` is then copied to the drone for inference.

### Step 3: On-drone inference
```python
from rknnlite.api import RKNNLite      # on-drone runtime
rknn_lite = RKNNLite()
rknn_lite.load_rknn("best.rknn")
rknn_lite.init_runtime(core_mask=RKNNLite.NPU_CORE_AUTO)
output = rknn_lite.inference(inputs=[frame])
```

`rknnlite` is the runtime that runs on the Rockchip drone. Lighter than `rknn-toolkit2`.

---

## What we need to build

### Prerequisites (one-time, on a host machine)
- Install `rknn-toolkit2` (x86 Linux, Python 3.8–3.11 — version constraints matter)
- Install `ultralytics` (already have for K's pipeline)

### Pipeline (after K finishes training)
1. K exports `best.pt` → `best.onnx` via ultralytics
2. Run org's conversion code (when pulled) on the ONNX → produce `best.rknn`
3. Copy `best.rknn` to the mapping drone
4. Wire the detection code (org's reference) into our mapping-drone controller
5. Tune confidence threshold + NMS for the actual targets

### Estimated time
- ONNX export: minutes (well-trodden path)
- RKNN conversion: a few hours including calibration set prep + version dependency wrangling (`rknn-toolkit2` is notoriously version-sensitive)
- Integration: depends on org's reference code — likely a few hours

---

## How to fix the access issue

**For the user to do (after org fixes the share):**
1. Open both Drive folders in a logged-in browser
2. Right-click each file → Download
3. Drop the convert/ files into `learning_material_5_yolo_rknn/convert/`
4. Drop the detection/ files into `learning_material_5_yolo_rknn/detection/`
5. I'll auto-detect and analyse

---

## Open questions

1. **Exact Rockchip SoC?** Affects `target_platform` in conversion. RK3588 most likely.
2. **Drone's OS image?** Some Rockchip boards ship Armbian, others ship Radxa OS or custom Ubuntu. Affects what Python/ROS2 version is available.
3. **Is the `.rknn` quantised (int8) or fp16?** Quantised is faster but less accurate; fp16 is the safer default for first iteration.
4. **What target classes does the org expect?** Until we know, K trains the same classes as qualifier (yellow/red barrel) and we hot-swap when scoring rubric drops.
5. **Does the org provide a pre-built `.rknn` for a baseline class set?** If yes, we can skip conversion for the smoke test and only convert when K's custom classes are ready.
6. **Inference rate target?** RK3588 NPU runs YOLOv8n at ~60-120 FPS quantised. Probably overkill for our needs (10-20 FPS is fine).

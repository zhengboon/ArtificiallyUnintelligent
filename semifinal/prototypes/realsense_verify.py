"""realsense_verify.py — Intel RealSense smoke test.

Camera compatibility:
  - D435 has an RGB sensor — default mode (depth + color) works.
  - D430 / D450 are depth+IR only (no RGB module) — pass `--ir-mode`
    to stream IR_LEFT (Y8) instead of color, otherwise pipeline.start()
    will raise "could not negotiate" on those modules. See
    semifinal/D430_RGB_RISK.md for the canonical sketch.

What it does:
  1. Opens the device, prints model + serial.
  2. Starts a depth + colour (or depth + IR if --ir-mode) stream at
     640x480 @ 30fps.
  3. Fetches the depth intrinsics (fx, fy, cx, cy).
  4. Grabs one frame; prints frame shape + dtype + a centre depth reading.
  5. Optionally shows a live OpenCV window with depth (colour-mapped) +
     RGB/IR side-by-side; press 'q' or Esc to quit.

What it confirms:
  - pyrealsense2 installed correctly
  - Camera is plugged in via USB 3.0 (else depth stream will fail to start
    or auto-drop to a lower rate)
  - Depth + colour (or depth + IR) both streaming
  - Intrinsics retrievable (we'll use them for pixel→3D unprojection)

Run:
    pip install pyrealsense2 opencv-python numpy
    python3 realsense_verify.py             # one-shot, no GUI (D435)
    python3 realsense_verify.py --gui       # live preview window
    python3 realsense_verify.py --ir-mode   # D430/D450 (no RGB sensor)

Exit codes:
    0  all good
    1  any failure (see stderr)
"""

import argparse
import sys

import numpy as np

try:
    import pyrealsense2 as rs
except ImportError:
    print("ERROR: pyrealsense2 not installed. Run: pip install pyrealsense2", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gui", action="store_true", help="Show live preview window.")
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument(
        "--ir-mode",
        action="store_true",
        help="D430/D450 fallback: stream IR_LEFT (Y8) instead of color "
             "(those modules have no RGB sensor). Also disables the IR "
             "projector emitter so the dot pattern doesn't blow ArUco "
             "contrast; depth quality may drop on textureless surfaces. "
             "See semifinal/D430_RGB_RISK.md.",
    )
    args = ap.parse_args()

    pipe = rs.pipeline()
    cfg = rs.config()
    cfg.enable_stream(rs.stream.depth, args.width, args.height, rs.format.z16, args.fps)
    if args.ir_mode:
        # IR_LEFT (index 1). Y8 = 8-bit grayscale, native to the stereo cam.
        # No RGB stream — the D430/D450 doesn't have one.
        cfg.enable_stream(rs.stream.infrared, 1, args.width, args.height, rs.format.y8, args.fps)
    else:
        cfg.enable_stream(rs.stream.color, args.width, args.height, rs.format.bgr8, args.fps)

    try:
        profile = pipe.start(cfg)
    except RuntimeError as e:
        print(f"ERROR: pipeline.start failed: {e}", file=sys.stderr)
        print("  Common causes: camera not plugged in, USB 2.0 (need 3.0+),", file=sys.stderr)
        print("  resolution/fps not supported, librealsense driver missing.", file=sys.stderr)
        return 1

    try:
        dev = profile.get_device()
        name = dev.get_info(rs.camera_info.name)
        serial = dev.get_info(rs.camera_info.serial_number)
        fw = dev.get_info(rs.camera_info.firmware_version)
        print(f"Camera: {name}")
        print(f"Serial: {serial}")
        print(f"FW:     {fw}")

        intr = profile.get_stream(rs.stream.depth).as_video_stream_profile().get_intrinsics()
        print(f"Depth intrinsics: fx={intr.fx:.2f} fy={intr.fy:.2f} "
              f"cx={intr.ppx:.2f} cy={intr.ppy:.2f}  ({intr.width}x{intr.height})")

        if args.ir_mode:
            ir_intr = profile.get_stream(rs.stream.infrared, 1).as_video_stream_profile().get_intrinsics()
            print(f"IR_LEFT intrinsics: fx={ir_intr.fx:.2f} fy={ir_intr.fy:.2f} "
                  f"cx={ir_intr.ppx:.2f} cy={ir_intr.ppy:.2f}  ({ir_intr.width}x{ir_intr.height})")
            # Turn the IR projector emitter OFF so the dot pattern doesn't
            # contaminate the IR image (ArUco / marker detection wants a
            # clean greyscale). Depth quality may drop on textureless
            # surfaces — switch to alternating-frame toggling if needed
            # (see D430_RGB_RISK.md Strategy B).
            try:
                dev.first_depth_sensor().set_option(rs.option.emitter_enabled, 0.0)
                print("IR emitter: OFF (projector pattern suppressed for clean IR image)")
            except Exception as exc:
                print(f"  warning: emitter off failed: {exc}", file=sys.stderr)
        else:
            color_intr = profile.get_stream(rs.stream.color).as_video_stream_profile().get_intrinsics()
            print(f"Color intrinsics: fx={color_intr.fx:.2f} fy={color_intr.fy:.2f} "
                  f"cx={color_intr.ppx:.2f} cy={color_intr.ppy:.2f}  ({color_intr.width}x{color_intr.height})")

        # Wait briefly for the auto-exposure to settle
        for _ in range(15):
            pipe.wait_for_frames()

        frames = pipe.wait_for_frames()
        depth_f = frames.get_depth_frame()
        if args.ir_mode:
            second_f = frames.get_infrared_frame(1)
            second_label = "IR"
        else:
            second_f = frames.get_color_frame()
            second_label = "Color"
        if not depth_f or not second_f:
            print(f"ERROR: missing depth or {second_label.lower()} frame after warmup", file=sys.stderr)
            return 1

        depth = np.asanyarray(depth_f.get_data())
        second = np.asanyarray(second_f.get_data())
        cy_px, cx_px = depth.shape[0] // 2, depth.shape[1] // 2
        d_mm = int(depth[cy_px, cx_px])
        d_m = d_mm / 1000.0
        print(f"\nDepth frame: shape={depth.shape} dtype={depth.dtype}")
        print(f"{second_label} frame: shape={second.shape} dtype={second.dtype}")
        print(f"Center pixel ({cx_px},{cy_px}) depth = {d_mm} mm = {d_m:.3f} m")
        if d_mm == 0:
            print("  (zero = no return — too close <0.17m, too dark, or reflective)")
        elif d_mm > 10_000:
            print("  (>10m — likely no return / sky / very distant)")
        else:
            print("  GOOD: realistic depth reading at centre")

        if args.gui:
            import cv2
            print("\nLive preview — press 'q' or Esc to quit, 's' to save a frame.")
            depth_colormap = rs.colorizer()
            left_label = "ir" if args.ir_mode else "color"
            while True:
                frames = pipe.wait_for_frames()
                df = frames.get_depth_frame()
                if args.ir_mode:
                    lf = frames.get_infrared_frame(1)
                else:
                    lf = frames.get_color_frame()
                if not df or not lf:
                    continue
                depth_vis = np.asanyarray(depth_colormap.colorize(df).get_data())
                left_raw = np.asanyarray(lf.get_data())
                if args.ir_mode:
                    # Synthesise a 3-channel BGR image from Y8 so the
                    # hstack with the depth colormap matches dimensions.
                    left_vis = cv2.cvtColor(left_raw, cv2.COLOR_GRAY2BGR)
                else:
                    left_vis = left_raw
                side = np.hstack([left_vis, depth_vis])
                cv2.putText(side, f"center depth: {int(np.asanyarray(df.get_data())[cy_px, cx_px])} mm",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.imshow(f"realsense_verify  [{left_label} | depth]", side)
                k = cv2.waitKey(1) & 0xFF
                if k in (27, ord('q')):
                    break
                if k == ord('s'):
                    import time
                    ts = time.strftime("%Y%m%d_%H%M%S")
                    cv2.imwrite(f"rs_{left_label}_{ts}.png", left_vis)
                    cv2.imwrite(f"rs_depth_{ts}.png", depth_vis)
                    print(f"  saved rs_{left_label}_{ts}.png + rs_depth_{ts}.png")
            cv2.destroyAllWindows()

        print("\nOK — Realsense is working.")
        return 0
    finally:
        pipe.stop()


if __name__ == "__main__":
    sys.exit(main())

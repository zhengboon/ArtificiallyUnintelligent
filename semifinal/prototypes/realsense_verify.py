"""realsense_verify.py — Intel RealSense D435 (or D430/D450) smoke test.

What it does:
  1. Opens the device, prints model + serial.
  2. Starts a depth + colour stream at 640x480 @ 30fps.
  3. Fetches the depth intrinsics (fx, fy, cx, cy).
  4. Grabs one frame; prints frame shape + dtype + a centre depth reading.
  5. Optionally shows a live OpenCV window with depth (colour-mapped) + RGB
     side-by-side; press 'q' or Esc to quit.

What it confirms:
  - pyrealsense2 installed correctly
  - Camera is plugged in via USB 3.0 (else depth stream will fail to start
    or auto-drop to a lower rate)
  - Depth + colour both streaming
  - Intrinsics retrievable (we'll use them for pixel→3D unprojection)

Run:
    pip install pyrealsense2 opencv-python numpy
    python3 realsense_verify.py             # one-shot, no GUI
    python3 realsense_verify.py --gui       # live preview window

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
    args = ap.parse_args()

    pipe = rs.pipeline()
    cfg = rs.config()
    cfg.enable_stream(rs.stream.depth, args.width, args.height, rs.format.z16, args.fps)
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

        color_intr = profile.get_stream(rs.stream.color).as_video_stream_profile().get_intrinsics()
        print(f"Color intrinsics: fx={color_intr.fx:.2f} fy={color_intr.fy:.2f} "
              f"cx={color_intr.ppx:.2f} cy={color_intr.ppy:.2f}  ({color_intr.width}x{color_intr.height})")

        # Wait briefly for the auto-exposure to settle
        for _ in range(15):
            pipe.wait_for_frames()

        frames = pipe.wait_for_frames()
        depth_f = frames.get_depth_frame()
        color_f = frames.get_color_frame()
        if not depth_f or not color_f:
            print("ERROR: missing depth or colour frame after warmup", file=sys.stderr)
            return 1

        depth = np.asanyarray(depth_f.get_data())
        color = np.asanyarray(color_f.get_data())
        cy_px, cx_px = depth.shape[0] // 2, depth.shape[1] // 2
        d_mm = int(depth[cy_px, cx_px])
        d_m = d_mm / 1000.0
        print(f"\nDepth frame: shape={depth.shape} dtype={depth.dtype}")
        print(f"Color frame: shape={color.shape} dtype={color.dtype}")
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
            while True:
                frames = pipe.wait_for_frames()
                df = frames.get_depth_frame()
                cf = frames.get_color_frame()
                if not df or not cf:
                    continue
                depth_vis = np.asanyarray(depth_colormap.colorize(df).get_data())
                color_vis = np.asanyarray(cf.get_data())
                side = np.hstack([color_vis, depth_vis])
                cv2.putText(side, f"center depth: {int(np.asanyarray(df.get_data())[cy_px, cx_px])} mm",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.imshow("realsense_verify  [color | depth]", side)
                k = cv2.waitKey(1) & 0xFF
                if k in (27, ord('q')):
                    break
                if k == ord('s'):
                    import time
                    ts = time.strftime("%Y%m%d_%H%M%S")
                    cv2.imwrite(f"rs_color_{ts}.png", color_vis)
                    cv2.imwrite(f"rs_depth_{ts}.png", depth_vis)
                    print(f"  saved rs_color_{ts}.png + rs_depth_{ts}.png")
            cv2.destroyAllWindows()

        print("\nOK — Realsense is working.")
        return 0
    finally:
        pipe.stop()


if __name__ == "__main__":
    sys.exit(main())

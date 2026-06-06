"""aruco_realsense.py — ArUco + RealSense depth → 3D camera-frame position.

The endgame prototype: same ArUco detection as aruco_webcam.py, but the colour
stream comes from a RealSense D435 (or D430/D450), depth is read at each
detected marker's centre pixel, and we unproject pixel + depth into a 3D
position in the camera's coordinate frame.

What it does per frame:
  1. wait_for_frames → align depth to colour
  2. detect ArUco markers in the colour image
  3. for each marker: centre pixel (u, v) + depth at that pixel
  4. unproject: X = (u-cx)*Z/fx, Y = (v-cy)*Z/fy, Z = depth_m
  5. log (id, u, v, depth_mm, X, Y, Z) on first sighting + on disappearance
  6. overlay bbox + 3D coords on the live preview

Run:
    pip install pyrealsense2 opencv-contrib-python numpy
    python3 aruco_realsense.py                   # live GUI
    python3 aruco_realsense.py --no-gui          # headless, prints only
    python3 aruco_realsense.py --jsonl out.jsonl # append every detection record

Notes:
  - The output (X, Y, Z) is in the CAMERA frame (not world / drone frame).
    To get world-frame, fuse with drone pose:
      world = R_camera_to_drone @ (X, Y, Z) + drone_position_world
  - Depth at the marker centre is sampled as a non-zero median over a 5x5
    window around (u, v) — more robust than a single pixel against the
    occasional zero-return. If the entire neighbourhood has no depth return
    (too close, reflective, or just bad luck), the script skips that marker.
    The JSONL `depth_mm` field reflects this local median, not a single pixel.
  - Depth + colour are aligned via rs.align so pixel coordinates map 1:1.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

try:
    import pyrealsense2 as rs
except ImportError:
    print("ERROR: pyrealsense2 not installed. Run: pip install pyrealsense2", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dict", default="6X6_250",
                    help="ArUco dictionary (org default: 6X6_250).")
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--no-gui", action="store_true", help="Run headless.")
    ap.add_argument("--jsonl", type=Path, default=None,
                    help="Append every detection record to this JSONL file.")
    args = ap.parse_args()

    aruco_dict_name = getattr(cv2.aruco, f"DICT_{args.dict}", None)
    if aruco_dict_name is None:
        print(f"ERROR: unknown ArUco dict DICT_{args.dict}", file=sys.stderr)
        return 1
    aruco_dict = cv2.aruco.getPredefinedDictionary(aruco_dict_name)
    detector = cv2.aruco.ArucoDetector(aruco_dict, cv2.aruco.DetectorParameters())

    pipe = rs.pipeline()
    cfg = rs.config()
    cfg.enable_stream(rs.stream.depth, args.width, args.height, rs.format.z16, args.fps)
    cfg.enable_stream(rs.stream.color, args.width, args.height, rs.format.bgr8, args.fps)
    try:
        profile = pipe.start(cfg)
    except RuntimeError as e:
        print(f"ERROR: pipeline.start failed: {e}", file=sys.stderr)
        return 1

    align = rs.align(rs.stream.color)
    color_intr = profile.get_stream(rs.stream.color).as_video_stream_profile().get_intrinsics()
    fx, fy = color_intr.fx, color_intr.fy
    cx, cy = color_intr.ppx, color_intr.ppy
    print(f"Camera: {profile.get_device().get_info(rs.camera_info.name)}")
    print(f"Color intrinsics: fx={fx:.2f} fy={fy:.2f} cx={cx:.2f} cy={cy:.2f}")
    print(f"Dictionary: DICT_{args.dict}")

    jsonl_f = args.jsonl.open("a", encoding="utf-8") if args.jsonl else None
    if jsonl_f:
        print(f"Appending detection records to {args.jsonl}")

    print("\nLive — 'q'/Esc to quit, 's' to save annotated frame.")
    seen: dict[int, tuple[float, float, float]] = {}  # id → last (X,Y,Z) m
    try:
        # Warmup for auto-exposure
        for _ in range(15):
            pipe.wait_for_frames()

        while True:
            frames = align.process(pipe.wait_for_frames())
            df = frames.get_depth_frame()
            cf = frames.get_color_frame()
            if not df or not cf:
                continue
            depth = np.asanyarray(df.get_data())   # uint16, mm
            color = np.asanyarray(cf.get_data())   # uint8, BGR

            gray = cv2.cvtColor(color, cv2.COLOR_BGR2GRAY)
            corners, ids, _ = detector.detectMarkers(gray)

            current: dict[int, tuple[float, float, float]] = {}
            if ids is not None:
                cv2.aruco.drawDetectedMarkers(color, corners, ids)
                for mc, mid in zip(corners, ids.flatten()):
                    mid = int(mid)
                    c = mc.reshape((4, 2))
                    u = int(c[:, 0].mean())
                    v = int(c[:, 1].mean())
                    if not (0 <= u < depth.shape[1] and 0 <= v < depth.shape[0]):
                        continue
                    # Non-zero median over a 5x5 window — more robust than a
                    # single pixel against sporadic zero-returns on shiny /
                    # near-range surfaces.
                    y0, y1 = max(0, v - 2), v + 3
                    x0, x1 = max(0, u - 2), u + 3
                    patch = depth[y0:y1, x0:x1]
                    nz = patch[patch > 0]
                    d_mm = int(np.median(nz)) if nz.size else 0
                    if d_mm == 0:
                        cv2.putText(color, f"ID={mid} no-depth",
                                    (u + 6, v - 6), cv2.FONT_HERSHEY_SIMPLEX,
                                    0.5, (0, 0, 255), 1)
                        continue
                    Z = d_mm / 1000.0
                    X = (u - cx) * Z / fx
                    Y = (v - cy) * Z / fy
                    current[mid] = (X, Y, Z)
                    cv2.circle(color, (u, v), 4, (0, 0, 255), -1)
                    cv2.putText(color, f"ID={mid}", (u + 6, v - 22),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
                    cv2.putText(color, f"({X:+.2f},{Y:+.2f},{Z:.2f})m",
                                (u + 6, v - 6), cv2.FONT_HERSHEY_SIMPLEX,
                                0.48, (0, 255, 255), 1)
                    if jsonl_f:
                        jsonl_f.write(json.dumps({
                            "ts": time.time(), "id": mid,
                            "u": u, "v": v, "depth_mm": d_mm,
                            "x_m": round(X, 4), "y_m": round(Y, 4), "z_m": round(Z, 4),
                        }) + "\n")
                        jsonl_f.flush()

            new = set(current) - set(seen)
            lost = set(seen) - set(current)
            for mid in sorted(new):
                X, Y, Z = current[mid]
                print(f"+ ID={mid}  (X={X:+.3f}, Y={Y:+.3f}, Z={Z:.3f}) m   "
                      f"distance={np.hypot(X, Z):.3f} m")
            for mid in sorted(lost):
                print(f"- ID={mid} lost")
            seen = current

            if not args.no_gui:
                hud = f"DICT_{args.dict}  |  detected: {sorted(current) or '-'}"
                cv2.putText(color, hud, (10, 25), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (255, 255, 255), 2)
                cv2.imshow("aruco_realsense", color)
                k = cv2.waitKey(1) & 0xFF
                if k in (27, ord('q')):
                    break
                if k == ord('s'):
                    ts = time.strftime("%Y%m%d_%H%M%S")
                    fn = f"aruco_rs_{ts}.png"
                    cv2.imwrite(fn, color)
                    print(f"  saved {fn}")
            else:
                # In headless mode, just keep looping with a brief sleep so
                # Ctrl-C can interrupt cleanly.
                time.sleep(0.01)
    except KeyboardInterrupt:
        print("\ninterrupted")
    finally:
        if jsonl_f:
            jsonl_f.close()
        if not args.no_gui:
            cv2.destroyAllWindows()
        pipe.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())

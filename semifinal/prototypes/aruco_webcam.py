"""aruco_webcam.py — ArUco DICT_6X6_250 detection prototype, webcam version.

Validates the OpenCV ArUco pipeline (the exact one the org showed in
Learning Material 2) before we wire it to the Realsense or drone video stream.
No depth here — just pixel-space detection. For 3D unproject use aruco_realsense.py.

What it does:
  1. Opens the system default webcam (--cam to pick a different index).
  2. Loads the cv2.aruco DICT_6X6_250 dictionary + default detector params.
  3. Per-frame: greyscale → detect markers → draw bbox + ID.
  4. Prints to stdout when a NEW marker ID first appears + when one disappears.
  5. 'q'/Esc to quit; 's' to save the current annotated frame.

Run:
    pip install opencv-contrib-python numpy
    python3 aruco_webcam.py                  # default webcam
    python3 aruco_webcam.py --cam 1          # second camera
    python3 aruco_webcam.py --dict 5X5_100   # other dictionary

Print or download DICT_6X6_250 markers (any ID 0-249) from:
    https://chev.me/arucogen/   (pick "Original ArUco", size 6x6, count 250)
or generate locally with cv2.aruco.generateImageMarker(dict, id, size_px).

Tips:
  - Marker size at least 5cm for ~1m distance.
  - Print on matte paper; gloss reflects badly.
  - Good even lighting; the detector is robust but not magic.
"""

import argparse
import sys
import time

import cv2
import numpy as np

DICT_NAMES = {
    "4X4_50":  cv2.aruco.DICT_4X4_50,
    "4X4_100": cv2.aruco.DICT_4X4_100,
    "4X4_250": cv2.aruco.DICT_4X4_250,
    "5X5_100": cv2.aruco.DICT_5X5_100,
    "5X5_250": cv2.aruco.DICT_5X5_250,
    "6X6_50":  cv2.aruco.DICT_6X6_50,
    "6X6_100": cv2.aruco.DICT_6X6_100,
    "6X6_250": cv2.aruco.DICT_6X6_250,  # org's default
    "6X6_1000": cv2.aruco.DICT_6X6_1000,
    "7X7_50":  cv2.aruco.DICT_7X7_50,
    "APRILTAG_36h11": cv2.aruco.DICT_APRILTAG_36h11,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", type=int, default=0, help="Webcam index (default 0).")
    ap.add_argument("--dict", default="6X6_250", choices=list(DICT_NAMES),
                    help="ArUco dictionary (org default: 6X6_250).")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.cam, cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if not cap.isOpened():
        print(f"ERROR: could not open webcam {args.cam}", file=sys.stderr)
        return 1

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Webcam {args.cam}: {actual_w}x{actual_h}")
    print(f"Dictionary: DICT_{args.dict}")

    aruco_dict = cv2.aruco.getPredefinedDictionary(DICT_NAMES[args.dict])
    params = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, params)

    seen_ids: set[int] = set()
    last_print = 0.0
    print("\nLive — point camera at a printed marker. 'q'/Esc to quit, 's' to save.")
    while True:
        ok, frame = cap.read()
        if not ok:
            print("frame grab failed", file=sys.stderr)
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, rejected = detector.detectMarkers(gray)

        current_ids: set[int] = set()
        if ids is not None:
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            for mc, mid in zip(corners, ids.flatten()):
                mid = int(mid)
                current_ids.add(mid)
                c = mc.reshape((4, 2))
                cx_px = int((c[0][0] + c[2][0]) / 2)
                cy_px = int((c[0][1] + c[2][1]) / 2)
                cv2.circle(frame, (cx_px, cy_px), 4, (0, 0, 255), -1)
                cv2.putText(frame, f"ID={mid} ({cx_px},{cy_px})",
                            (cx_px + 8, cy_px - 8), cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, (0, 255, 255), 1)

        new = current_ids - seen_ids
        lost = seen_ids - current_ids
        if new:
            print(f"+ marker(s) appeared: {sorted(new)}")
        if lost:
            print(f"- marker(s) lost:    {sorted(lost)}")
        seen_ids = current_ids

        # Status overlay
        hud = f"DICT_{args.dict}  |  detected: {sorted(current_ids) or '-'}  |  rejected: {len(rejected) if rejected is not None else 0}"
        cv2.putText(frame, hud, (10, 25), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (255, 255, 255), 2)

        cv2.imshow("aruco_webcam", frame)
        k = cv2.waitKey(1) & 0xFF
        if k in (27, ord('q')):
            break
        if k == ord('s'):
            ts = time.strftime("%Y%m%d_%H%M%S")
            fn = f"aruco_capture_{ts}.png"
            cv2.imwrite(fn, frame)
            print(f"  saved {fn}")

    cap.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())

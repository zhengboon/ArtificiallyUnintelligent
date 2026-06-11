import pyrealsense2 as rs
import cv2
import numpy as np

# -----------------------------
# ArUco detector (init once)
# -----------------------------
#aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
#aruco_params = cv2.aruco.DetectorParameters()
#detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)

# -----------------------------
# RealSense init (init once)
# -----------------------------
#pipeline = rs.pipeline()
#config = rs.config()

#config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
#config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)

#pipeline.start(config)
#align = rs.align(rs.stream.color)


# -----------------------------
# FUNCTION: detect + display
# -----------------------------
def detect_aruco_once(pipeline,align,detector, show=True):
    """
    Detect ArUco markers once and optionally display annotated image.

    Returns:
        ids (list), positions (list of (x,y)), distances (list in meters)
    """

    frames = pipeline.wait_for_frames()
    frames = align.process(frames)

    depth_frame = frames.get_depth_frame()
    color_frame = frames.get_color_frame()

    if not depth_frame or not color_frame:
        return [], [], []

    image = np.asanyarray(color_frame.get_data())

    corners, ids, _ = detector.detectMarkers(image)

    out_ids = []
    out_pos = []
    out_dist = []

    if ids is not None:
        cv2.aruco.drawDetectedMarkers(image, corners, ids)

        for i, c in enumerate(corners):
            pts = c[0]

            cx = int(np.mean(pts[:, 0]))
            cy = int(np.mean(pts[:, 1]))

            dist = depth_frame.get_distance(cx, cy)

            out_ids.append(int(ids[i][0]))
            out_pos.append((cx, cy))
            out_dist.append(dist)

            # Draw center point
            cv2.circle(image, (cx, cy), 6, (0, 0, 255), -1)

            # Label
            label = f"ID:{ids[i][0]} {dist:.2f}m"
            print(label)
            cv2.putText(image, label, (cx + 10, cy),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 255, 0), 2)

    if show:
        cv2.imshow("ArUco Detection", image)
        cv2.waitKey(1)

    return out_ids, out_pos, out_dist


# -----------------------------
# Example usage
# -----------------------------
if __name__ == "__main__":
    try:
        while True:
            ids, pos, dist = detect_aruco_once(show=True)

            for i in range(len(ids)):
                print(f"ID={ids[i]} Pos={pos[i]} Dist={dist[i]:.2f}m")

            if cv2.waitKey(1) & 0xFF == 27:
                break

    finally:
        pipeline.stop()
        cv2.destroyAllWindows()
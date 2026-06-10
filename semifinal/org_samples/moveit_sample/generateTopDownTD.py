import numpy as np
import pyrealsense2 as rs
import cv2
import os

def draw_bev_map(points_world, cam_x, cam_y, map_size=600, resolution=0.05):
    """Generates a top-down OpenCV image from 3D world coordinates.

    Parameters:
    -----------
    points_world : np.ndarray
        The (N, 3) point cloud array.
    cam_x, cam_y : float
        Current 2D positions of the camera to center the map.
    map_size : int
        Width and Height of the output OpenCV window in pixels.
    resolution : float
        Meters per pixel (e.g., 0.05 means each pixel represents a 5cm x 5cm
        area).
    """
    # Create an empty black image canvas
    bev_image = np.zeros((map_size, map_size, 3), dtype=np.uint8)

    # Define the center coordinate of the window as our camera position origin
    center_pixel = map_size // 2

    if points_world.size > 0:
        # 1. Calculate relative positions from the active camera
        rel_x = points_world[:, 0] - cam_x
        rel_y = points_world[:, 1] - cam_y

        # 2. Convert meters to pixel scaling indexes
        pixel_x = np.floor(rel_x / resolution).astype(np.int32) + center_pixel
        pixel_y = np.floor(rel_y / resolution).astype(np.int32) + center_pixel

        # 3. Filter out any points that exceed our window size boundary limits
        valid_indices = (
            (pixel_x >= 0)
            & (pixel_x < map_size)
            & (pixel_y >= 0)
            & (pixel_y < map_size)
        )
        px = pixel_x[valid_indices]
        py = pixel_y[valid_indices]

        # 4. Extract heights (Z values) of these valid points to color code them
        heights = points_world[valid_indices, 2]

        if px.size > 0:
            # Color points by height: higher obstacles appear brighter white
            # Normalize height between 0m and 2m to an 8-bit color intensity (50-255)
            intensity = np.clip((heights / 2.0) * 205 + 50, 50, 255).astype(
                np.uint8
            )

            # Assign values to the image (drawing obstacles in green/white tones)
            bev_image[py, px] = np.vstack(
                (intensity // 2, intensity, intensity // 2)
            ).T

    # 5. Draw a small blue circle indicating the camera's current position
    cv2.circle(bev_image, (center_pixel, center_pixel), 6, (255, 0, 0), -1)
    return bev_image


def get_world_points(
    depth_frame,
    depth_scale,
    u_coords,
    v_coords,
    fx,
    fy,
    cx,
    cy,
    cam_x,
    cam_y,
    cam_height,
    tilt_deg,
    yaw_deg,
):
    """Transforms a RealSense depth frame into a 3D world coordinate point cloud.

    Parameters:
    -----------
    depth_frame : np.ndarray
        The raw 16-bit depth image array.
    depth_scale : float
        Multiplier to convert raw depth to meters.
    u_coords, v_coords : np.ndarray
        Precomputed pixel meshgrid coordinates.
    fx, fy, cx, cy : float
        Camera intrinsic matrix values.
    cam_x, cam_y : float
        The current 2D position (X, Y) of the camera in the world grid (meters).
    cam_height : float
        The height of the camera lens above the floor (meters).
    tilt_deg : float
        Tilt angle in degrees (0 = looking straight down).
    yaw_deg : float
        Yaw rotation angle of the camera in degrees around the vertical axis.

    Returns:
    --------
    points_world : np.ndarray
        An (N, 3) numpy array containing [X, Y, Z] positions of valid points in
        meters.
    """
    # 1. Convert raw depth pixels to real-world meters (Z in camera space)
    Z_c = depth_frame.astype(np.float32) * depth_scale

    # 2. Filter out invalid depth pixels (0 indicates missing data/shadows)
    valid_mask = Z_c > 0.0
    Z_c_valid = Z_c[valid_mask]

    if Z_c_valid.size == 0:
        return np.empty((0, 3), dtype=np.float32)

    # 3. Project 2D pixels to 3D Camera Space (X_c, Y_c, Z_c)
    X_c_valid = (u_coords[valid_mask] - cx) * Z_c_valid / fx
    Y_c_valid = (v_coords[valid_mask] - cy) * Z_c_valid / fy

    # Combine into a shape of (3, N)
    points_camera = np.vstack((X_c_valid, Y_c_valid, Z_c_valid))

    # 4. Convert Angles to Radians
    tilt_rad = np.radians(tilt_deg)
    yaw_rad = np.radians(yaw_deg)

    # 5. Define Base Orientation (Camera facing straight down at 0° Tilt / 0° Yaw)
    # Camera X_c -> World X
    # Camera Y_c -> World Y
    # Camera Z_c -> World -Z (pointing down into the floor)
    R_base = np.array([[1, 0, 0], [0, 1, 0], [0, 0, -1]])

    # 6. Apply Tilt (Rotation around Camera X-axis)
    cos_t, sin_t = np.cos(tilt_rad), np.sin(tilt_rad)
    R_tilt = np.array([[1, 0, 0], [0, cos_t, -sin_t], [0, sin_t, cos_t]])

    # 7. Apply Yaw (Rotation around World Z-axis)
    cos_y, sin_y = np.cos(yaw_rad), np.sin(yaw_rad)
    R_yaw = np.array([[cos_y, -sin_y, 0], [sin_y, cos_y, 0], [0, 0, 1]])

    # Combine rotations: Yaw * Tilt * BaseOrientation
    R_total = R_yaw @ R_tilt @ R_base

    # 8. Apply Rotation to the Point Cloud
    points_rotated = R_total @ points_camera  # Shape: (3, N)

    # 9. Apply Translation (Camera position offset in the world map)
    X_w = points_rotated[0, :] + cam_x
    Y_w = points_rotated[1, :] + cam_y
    Z_w = points_rotated[2, :] + cam_height

    # Stack back to (N, 3) layout for easy voxel grouping
    points_world = np.vstack((X_w, Y_w, Z_w)).T

    return points_world

class WorldPointCloudMap:

    def __init__(self, voxel_size=0.03, floor_threshold=0.05):
        """Manages an accumulating 3D point cloud map with floor filtering.

        Parameters:
        -----------
        voxel_size : float
            The size of each 3D grid cell in meters.
        floor_threshold : float
            Points with a Z-value (height) lower than this value (meters)
            are considered part of the floor and are ignored.
        """
        self.voxel_size = voxel_size
        self.floor_threshold = floor_threshold
        self.voxel_grid = {}

    def add_points(self, new_points):
        if new_points.size == 0:
            return

        # --- FLOOR FILTER STEP ---
        # Keep only points where Z is strictly greater than our floor threshold height
        not_floor_mask = new_points[:, 2] > self.floor_threshold
        filtered_points = new_points[not_floor_mask]

        if filtered_points.size == 0:
            return

        # Compute discrete integer grid keys for filtered points
        grid_keys = np.floor(filtered_points / self.voxel_size).astype(np.int32)

        # Feed into spatial hash map
        for i in range(len(filtered_points)):
            key = (grid_keys[i, 0], grid_keys[i, 1], grid_keys[i, 2])
            self.voxel_grid[key] = filtered_points[i]

    def get_global_points(self):
        if not self.voxel_grid:
            return np.empty((0, 3), dtype=np.float32)
        return np.array(list(self.voxel_grid.values()), dtype=np.float32)
    
    def save_to_numpy(self, filename="global_map.npz"):
        """Saves the map to a fast, compressed NumPy binary file.

        Ideal for loading back into Python later.
        """
        points = self.get_global_points()
        if points.size == 0:
            print("Map is empty. Nothing to save.")
            return

        # Saves the array under the key 'points'
        np.savez_compressed(filename, points=points)
        print(
            f"Saved {len(points)} points to {filename} ({os.path.getsize(filename)/1024:.1f} KB)"
        )

    def save_to_xyz(self, filename="global_map.xyz"):
        """Saves the map to a standard text file format [X Y Z].

        Ideal for importing into MeshLab, CloudCompare, or 3D modeling apps.
        """
        points = self.get_global_points()
        if points.size == 0:
            print("Map is empty. Nothing to save.")
            return

        # Saves as plain text lines: "X.xxx Y.yyy Z.zzz"
        np.savetxt(filename, points, fmt="%.4f", delimiter=" ")
        print(f"Saved {len(points)} points to 3D point text file: {filename}")

    def load_from_numpy(self, filename="global_map.npz"):
        """Loads a previously saved map file back into active memory."""
        if not os.path.exists(filename):
            print(f"File {filename} not found.")
            return

        data = np.load(filename)
        loaded_points = data["points"]

        # Re-populate the internal voxel grid dictionary
        self.voxel_grid.clear()
        grid_keys = np.floor(loaded_points / self.voxel_size).astype(np.int32)
        for i in range(len(loaded_points)):
            key = (grid_keys[i, 0], grid_keys[i, 1], grid_keys[i, 2])
            self.voxel_grid[key] = loaded_points[i]

        print(
            f"Successfully loaded {len(loaded_points)} points from file into memory."
        )

def main():
    # ==========================================
    # 1. System Initialisation (Run Once)
    # ==========================================
    # (Your original camera setup code goes here...)
    WIDTH = 640
    HEIGHT = 480

    MAX_DEPTH = 5.0      # meters
    MIN_DEPTH = 0.2      # meters

    GRID_RESOLUTION = 0.05    # 5 cm/cell
    GRID_WIDTH = 200          # 10 m wide
    GRID_HEIGHT = 200         # 10 m forward


    pipeline = rs.pipeline()
    config = rs.config()

    config.enable_stream(
        rs.stream.depth,
        WIDTH,
        HEIGHT,
        rs.format.z16,
        30
    )

    profile = pipeline.start(config)
    depth_sensor = profile.get_device().first_depth_sensor()
    depth_scale = depth_sensor.get_depth_scale()

    intrinsics = (
        profile.get_stream(rs.stream.depth)
        .as_video_stream_profile()
        .get_intrinsics()
    )

    fx = intrinsics.fx
    fy = intrinsics.fy
    cx = intrinsics.ppx
    cy = intrinsics.ppy

    print("\nCamera Intrinsics")
    print("--------------------")
    print("fx =", fx)
    print("fy =", fy)
    print("cx =", cx)
    print("cy =", cy)

    # ==========================================
    # Precompute Pixel Coordinates
    # ==========================================

    u_coords, v_coords = np.meshgrid(
        np.arange(WIDTH),
        np.arange(HEIGHT)
    )

    u_coords = u_coords.astype(np.float32)
    v_coords = v_coords.astype(np.float32)

    global_map = WorldPointCloudMap(voxel_size=0.03, floor_threshold=0.06)

    try:
        while True:
            frames = pipeline.wait_for_frames()
            depth_frame = frames.get_depth_frame()
            if not depth_frame:
                continue

            depth_image = np.asanyarray(depth_frame.get_data())
#            current_x, current_y, current_yaw = get_latest_movement_telemetry()

            # Compute full point positions
            new_points = get_world_points(
                depth_image,
                depth_scale,
                u_coords,
                v_coords,
                fx,
                fy,
                cx,
                cy,
                cam_x=current_x,
                cam_y=current_y,
                cam_height=1.5,
                tilt_deg=0.0,
                yaw_deg=current_yaw,
            )

            # Add and let the class auto-strip out the floor values
            global_map.add_points(new_points)
            current_full_map = global_map.get_global_points()

            # Generate top-down representation frame
            bev_canvas = draw_bev_map(
                current_full_map, cam_x=current_x, cam_y=current_y
            )

            # Render window stream frame via OpenCV UI thread Engine
            cv2.imshow("3D Occupancy Grid (Top-Down BEV)", bev_canvas)

            # Break loop if 'q' key is pressed
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        pipeline.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()


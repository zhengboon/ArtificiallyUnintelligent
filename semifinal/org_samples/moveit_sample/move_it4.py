import asyncio
import math
import threading
from typing import Optional
from copy import deepcopy
from UWBPositionQuerier import UWBPositionQuerier
from mavsdk import System
from mavsdk.offboard import OffboardError, PositionNedYaw, VelocityNedYaw

import cv2
import pyrealsense2 as rs
from detectaruco import detect_aruco_once
import numpy as np
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from geometry_msgs.msg import PoseStamped
import threading
from typing import Optional
from copy import deepcopy
from generateTopDownTD import get_world_points, WorldPointCloudMap, draw_bev_map


# --- CONFIGURATION CONSTANTS ---
ALTITUDE_TARGET = 2.0
ALTITUDE_TOLERANCE = 0.10      # 10 cm vertical threshold
HORIZONTAL_TOLERANCE = 0.20    # 20 cm horizontal target radius acceptance
TAKEOFF_TIMEOUT = 15.0
WAYPOINT_TIMEOUT = 25.0        # Maximum time allowed per individual waypoint

# Dynamic Velocity Profiling Parameters
MAX_SPEED = 1.5                # Max travel speed (m/s) when far from waypoint
MIN_SPEED = 0.2                # Min approach crawl speed (m/s) near target
SLOW_DOWN_RADIUS = 2.0         # Distance (meters) from target to begin deceleration braking loop

WIDTH = 640
HEIGHT = 480

MAX_DEPTH = 5.0      # meters
MIN_DEPTH = 0.2      # meters

GRID_RESOLUTION = 0.05    # 5 cm/cell
GRID_WIDTH = 200          # 10 m wide
GRID_HEIGHT = 200         # 10 m forward


# -----------------------------
# ArUco detector (init once)
# -----------------------------
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_7X7_1000)
aruco_params = cv2.aruco.DetectorParameters()
detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)

print("INIT ARUCO DONE")
# -----------------------------
# RealSense init (init once)
# -----------------------------
pipeline = rs.pipeline()
config = rs.config()

config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)

profile = pipeline.start(config)
align = rs.align(rs.stream.color)
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

print("INIT RS DONE")

# --- TELEMETRY TAKEOFF MONITOR (No UWB) ---
async def wait_for_takeoff_altitude(drone):
    print("[Takeoff Tracker] Monitoring altitude...")
    async for position in drone.telemetry.position():
        current_alt = position.relative_altitude_m
        print(f"[Telemetry] Height: {current_alt:.2f}m / {ALTITUDE_TARGET}m")
        if abs(current_alt - ALTITUDE_TARGET) <= ALTITUDE_TOLERANCE:
            print("✔ Takeoff altitude achieved.")
            break
        await asyncio.sleep(0.1)

# --- 2D UWB DYNAMIC WAYPOINT TRACKER & CONTROLLER ---
async def navigate_and_wait_for_uwb_waypoint(drone: System, querier: UWBPositionQuerier, target_north: float, target_east: float):
    """
    Tracks horizontal progress via UWB and dynamically mutates velocity feed-forward limits 
    proportional to remaining distance to ensure smooth deceleration.
    """
    print(f"[UWB Flight Engine] Heading towards -> North: {target_north}m, East: {target_east}m")
    
    while True:
        pose_msg = querier.get_latest_pose()
        
        if pose_msg is None:
            print("[UWB Flight Engine] Warning: Lost UWB packets, holding current posture...")
            await asyncio.sleep(0.5)
            continue
            
        # Coordinates mapping: UWB X -> East, UWB Y -> North
        uwb_east = pose_msg.pose.position.x
        uwb_north = pose_msg.pose.position.y
        
        # Calculate horizontal error components and absolute Euclidean distance
        error_north = target_north - uwb_north
        error_east = target_east - uwb_east
        distance_error = math.sqrt(error_north**2 + error_east**2)
        
        # 1. Target Acceptance Check
        if distance_error <= HORIZONTAL_TOLERANCE:
            print(f"✔ Target waypoint hit! Final drift margin: {distance_error:.2f}m")
            break
            
        # 2. Proportional Velocity Scaling Math
        if distance_error >= SLOW_DOWN_RADIUS:
            # We are far away, command full speed
            calculated_speed = MAX_SPEED
        else:
            # Linear interpolation mapping between min and max speed based on distance remaining
            ratio = distance_error / SLOW_DOWN_RADIUS
            calculated_speed = MIN_SPEED + (MAX_SPEED - MIN_SPEED) * ratio

        # 3. Vector Composition (Decompose target velocity scalar into direct N/E tracks)
        if distance_error > 0:
            vel_north = (error_north / distance_error) * calculated_speed
            vel_east = (error_east / distance_error) * calculated_speed
        else:
            vel_north, vel_east = 0.0, 0.0

        print(f"[Profiling Tracker] Dist: {distance_error:.2f}m | Dynamic Set-Speed Limit: {calculated_speed:.2f} m/s")

        # 4. Inject Dynamic Constrained Command to Autopilot Setpoint Cache
        await drone.offboard.set_position_velocity_ned(
            PositionNedYaw(target_north, target_east, -ALTITUDE_TARGET, 0.0),
            VelocityNedYaw(vel_north, vel_east, 0.0, 0.0)
        )
            
        await asyncio.sleep(0.1)


# --- MAIN OFFBOARD FLIGHT SEQUENCE ---
async def run():
    drone = System()
    await drone.connect(system_address="serial:///dev/ttyS6:921600")

    print("Waiting for drone to connect...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print("Drone connected!")
            break

    print("Waiting for Local Position Lock...")
    async for health in drone.telemetry.health():
        if health.is_local_position_ok:
            print("✔ Local position estimate confirmed.")
            break

    await drone.action.set_takeoff_altitude(ALTITUDE_TARGET)
    
    # --- AUTOMATED ARRAY OF WAYPOINTS ---
    # Layout format: (North_Meters, East_Meters) relative to UWB Anchor 0
    waypoint_array = [
        (2.0, 2.0),   # Waypoint 1
        (3.0, 2.0),  # Waypoint 2
        (4.0, 2.0), # Waypoint 3
        (5.0, 2.0)    # Waypoint 4 (Return to Origin Home base)
    ]



    with UWBPositionQuerier(topic_name='uwb_tag') as querier:
        
        print("-- Arming Motors")
        await drone.action.arm()

        # Pre-stream state registration setup
        await drone.offboard.set_position_velocity_ned(
            PositionNedYaw(0.0, 0.0, 0.0, 0.0),
            VelocityNedYaw(0.0, 0.0, 0.0, 0.0)
        )

        print("-- Engaging Offboard Mode")
        try:
            await drone.offboard.start()
        except OffboardError as error:
            print(f"Offboard failed: {error._result.result}")
            await drone.action.disarm()
            return

        # STEP 1: TAKEOFF (Uses Internal rangefinder/optical flow, NOT UWB)
        print(f"-- Takeoff initiated to {ALTITUDE_TARGET}m")
        await drone.offboard.set_position_velocity_ned(
            PositionNedYaw(0.0, 0.0, -ALTITUDE_TARGET, 0.0),
            VelocityNedYaw(0.0, 0.0, -0.5, 0.0)
        )
        await asyncio.sleep(3.0)
#        try:
#            await asyncio.wait_for(wait_for_takeoff_altitude(drone), timeout=TAKEOFF_TIMEOUT)
#        except asyncio.TimeoutError:
#            print("❌ EMERGENCY: Takeoff sequence timeout.")
#            await emergency_abort(drone)
#            return

        # STEP 2: LOOP THROUGHOUT THE WAYPOINT ARRAY
        for idx, (wp_north, wp_east) in enumerate(waypoint_array, start=1):
            print(f"\n=============================================")
            print(f"Executing Array Waypoint Step {idx}/{len(waypoint_array)}")
            print(f"=============================================")            
            await drone.offboard.set_position_velocity_ned(
                PositionNedYaw(wp_north, wp_east, -2.0, 0.0),
                VelocityNedYaw(0.1, 0.1, 0.0, 0.0)
            )
            await asyncio.sleep(3.0)
            detect_aruco_once(pipeline=pipeline,align=align,detector=detector)
            frames = pipeline.wait_for_frames()
            frames = align.process(frames)
            depth_frame = frames.get_depth_frame()
            color_frame = frames.get_color_frame()
            depth_image = np.asanyarray(depth_frame.get_data())
            pose_msg = querier.get_latest_pose()

            if pose_msg is None:
                print("[UWB Flight Engine] Warning: Lost UWB packets, holding current posture...")
                await asyncio.sleep(0.5)
                continue
            current_x = pose_msg.pose.position.x
            current_y = pose_msg.pose.position.y
            current_yaw = 0
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
                cam_height=2.0,
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



        # STEP 3: MISSION COMPLETION & LANDING
        print("\nAll waypoints cleared successfully. Terminating Offboard & Landing.")
        try:
            await drone.offboard.stop()
        except OffboardError:
            pass
        await drone.action.land()


async def emergency_abort(drone):
    print("-- Executing autonomous emergency landing sequence...")
    try:
        await drone.offboard.stop()
    except OffboardError:
        pass
    await drone.action.land()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("Script interrupted manually.")
    finally:
        if rclpy.ok():
            rclpy.shutdown()

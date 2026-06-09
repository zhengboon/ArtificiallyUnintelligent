# A simple and short reference code of connecting to multiple hula drones in the wifi network.
# Make sure your laptop is in that network of hula drones and make sure all hula drones are online in that network
# This code uses pyhulax python library to connect to Hula Drone. 
# Refer to https://pyhulax.xenops.ae to learn how to use library to control movements of Hula drone swarm
# Ths code only shows you to get all video streams of all drones onto one computer so
# you can do multiple drone detection from one computer.
# You need pyhulax and dola.py

from pyhulax import DroneAPI
from pyhulax.core import Direction
import cv2
from dola import Dola
from pyhulax.video import VideoStream, VideoDisplay
from UWBParserThread import UWBParserThread
import time
import math
import os
import threading
from wall_following import (
    make_wf_state,
    wall_follower_tick,
)
from pyhulax.core import CameraPitchMode

# ============================================================
# Configuration
# ============================================================

# FIRST TIME SET UP:
# python challenge2_controller.py
#     ↓
# [UWB] Type y to measure landing zone coordinates now: y
#     ↓
# [UWB MEASURE] Place all drones on their landing zones.
# [UWB MEASURE] Press Enter when ready...
#     ↓
# [UWB MEASURE] Found 3 UWB tag(s).
# [UWB MEASURE] Copy these into LANDING_ZONES at top of file:

# LANDING_ZONES = [
#     (2.14, 0.98),   # block_id=3
#     (4.02, 1.05),   # block_id=7
#     (6.09, 0.97),   # block_id=12
# ]
#     ↓
# [UWB] Update LANDING_ZONES at top of file then re-run.

# EVERY SUBSEQUENT RUN:
# python challenge2_controller.py
#     ↓
# [UWB] Type y to measure... : (press Enter to skip)
#     ↓
# Mission runs normally
# Phase A completes, drones land
#     ↓
# auto_match_uwb_tags() runs automatically
#     ↓
# Phase B starts with correct UWB mapping

LANDING_ZONES = [
    (2.0, 1.0),  # Landing (x,y) coordinates for drone 1 -- TO DO: change according to actual arena map (w.r.t. to the UWB origin)
    (4.0, 1.0),  # Landing (x,y) coordinates for drone 2 -- TO DO: change according to actual arena map (w.r.t. to the UWB origin)
    (6.0, 1.0),  # Landing (x,y) coordinates for drone 3 -- TO DO: change according to actual arena map (w.r.t. to the UWB origin)
]

FLIGHT_ALTITUDE_CM = 110  # Recommended height is 110cm (1.1m)
POSITION_THRESHOLD_M = 0.3  # Distance to be considered close enough to a waypoint
MAX_FLIGHT_SPEED = 500   # -1000 to +1000 range, 500 = 50% speed
TOTAL_ROBOTS = 5  # Total number of RoboMasters
SNAPSHOT_DIR = "snapshots"  # Directory where our captured images will be stored

# ============================================================
# Aruco Configuration
# ============================================================

ARUCO_DICT = cv2.aruco.DICT_6X6_250
ROBOMASTER_IDS = {10, 11, 12, 13, 14}  # IDs on RoboMaster robots  -- -- TO DO: Change according to the actual RoboMaster IDs

# ============================================================
# Staggered Takeoff
# ============================================================

TAKEOFF_DELAY = 1.0  # seconds between each drone's takeoff

# ============================================================
# UWB Helpers
# ============================================================

def uwb_distance(pos1, pos2):
    """Euclidean distance between two UWB (x, y) positions in metres."""
    return math.sqrt((pos1[0]-pos2[0])**2 + (pos1[1]-pos2[1])**2)


def measure_landing_zones(uwb, scan_range=30):  # assuming the block_id is within 1-30 (TO DO: change accordingly)
    """
    Measure landing zone coordinates directly from the UWB system.
    Run this BEFORE the mission to fill LANDING_ZONES correctly.

    This guarantees landing zone coordinates are in the same
    UWB coordinate frame as drone positions — so auto_match_uwb_tags()
    works correctly later.

    How to use this function:
    1. Place all drones on their landing zones (powered on)
    2. Call this function
    3. Copy the printed coordinates into LANDING_ZONES
    4. Re-run the script to start the mission —
    auto_match_uwb_tags() handles drone-to-zone matching
    automatically after Phase A landing
    """
    print("\n[UWB MEASURE] Place all drones on their landing zones.")
    print("[UWB MEASURE] Press Enter when ready...")
    input()
    print("\n[UWB MEASURE] Reading UWB positions...")
    
    found = []
    for tag_id in range(scan_range):
        x, y, _ = uwb.get_tag_position(tag_id)
        if x is not None:
            found.append((tag_id, x, y))
    
    if not found:
        print("[UWB MEASURE] No UWB tags detected. Check UWB system.")
        return
    
    print(f"\n[UWB MEASURE] Found {len(found)} UWB tag(s).")
    print("[UWB MEASURE] Copy these into LANDING_ZONES at top of file:\n")
    print("LANDING_ZONES = [")
    for tag_id, x, y in found:
        print(f"({x:.2f}, {y:.2f}), # block_id={tag_id}")
    print("]\n")


def auto_match_uwb_tags(drone_list, drone_landing_zones, uwb, scan_range=30, threshold_m=0.5):  # TO DO: Change scan_range accordingly based on block_id of uwb tags
    """
    Automatically match each drone IP to its UWB block_id by
    comparing UWB tag positions to known landing zone positions.

    Called after Phase A when all drones have landed on their
    assigned zones — at that point each drone is sitting at a
    known location so position matching is unambiguous.

    Args:
        drone_list         -- list of drone IP strings
        drone_landing_zones -- dict of {ip_str: (x, y)} in metres
        uwb                -- UWBParserThread object
        scan_range         -- how many block_ids to scan (0 to scan_range-1)
        threshold_m        -- max distance (metres) to accept a match

    Populates UWB_TAG_IDS globally.
    """
    print("\n[UWB] Auto-matching drone IPs to UWB block_ids...")

    for ip_str in drone_list:
        zone = drone_landing_zones.get(ip_str)
        if zone is None:
            print(f"  [UWB] {ip_str} — no landing zone assigned, skipping.")
            continue

        best_tag = None
        best_dist = 999.0

        # Scan all possible block_ids and find closest to this landing zone
        for tag_id in range(scan_range):
            x, y, _ = uwb.get_tag_position(tag_id)
            if x is None:
                continue
            d = uwb_distance((x, y), zone)
            if d < best_dist:
                best_dist = d
                best_tag = tag_id

        if best_tag is not None and best_dist < threshold_m:
            UWB_TAG_IDS[ip_str] = best_tag
            print(f"  [UWB] {ip_str} -> block_id={best_tag} "
                  f"(dist={best_dist:.2f}m from landing zone {zone})")
        else:
            print(f"  [UWB] WARNING: {ip_str} — no UWB tag found within "
                  f"{threshold_m}m of landing zone {zone}. "
                  f"Phase B avoidance may not work correctly.")
    
    print(f"[UWB] Matching complete: {UWB_TAG_IDS}\n")


# ============================================================
# UWB TAG ID MAPPING
# Maps drone IP address to its physical UWB block_id.
# Filled automatically by auto_match_uwb_tags() after Phase A landing
# No manual configuration needed.
# ============================================================

UWB_TAG_IDS = {}

# ============================================================
# Phase A State Definitions
# ============================================================

STATE_TAKEOFF_A = "STATE_TAKEOFF_A"
STATE_FLY_TO_ZONE = "STATE_FLY_TO_ZONE"
STATE_LAND = "STATE_LAND"
STATE_WAIT_PHASE_B = "STATE_WAIT_PHASE_B"

# =================================================================================================
# Phase B State Definitions (the other wall-following states are imported from wall_following.py)
# =================================================================================================

STATE_TAKEOFF_B = "STATE_TAKEOFF_B"
STATE_WALL_FOLLOWING = "STATE_WALL_FOLLOWING"
WF_AVOID_DRONE = "WF_AVOID_DRONE"
STATE_MISSION_COMPLETE = "STATE_MISSION_COMPLETE"

# ============================================================
# Global Shared State
# ============================================================

robots_found = 0
snapshotted_ids = set()
phase_b_approved = False  # set True when operator presses Enter to start Phase B

def _wait_for_phase_b():
    """
    Runs in background thread — waits for operator to press Enter
    before Phase B begins. Loop keeps running while waiting so
    drones remain controllable (e.g. hover after landing).
    """
    global phase_b_approved
    input("\n[MISSION] All drones landed. Press Enter to start Phase B: ")
    phase_b_approved = True
    print("[MISSION] Phase B approved. Drones taking off shortly.\n")


# ============================================================
# Aruco Detection
# ============================================================

def make_aruco_detector():
    """Create Aruco detector once at startup and reuse every frame."""
    aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT)
    parameters = cv2.aruco.DetectorParameters()
    return cv2.aruco.ArucoDetector(aruco_dict, parameters)


def detect_aruco(frame, detector):
    """
    Detect ArUco markers in a frame.
    Returns list of dicts: [{ 'id': int, 'center': (cx, cy) }]
    Only returns markers in ROBOMASTER_IDS.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = detector.detectMarkers(gray)
    detections = []
    if ids is None:
        return detections
    for marker_corners, marker_id in zip(corners, ids.flatten()):
        if int(marker_id) not in ROBOMASTER_IDS:
            continue
        pts = marker_corners.reshape((4, 2))
        cx = int((pts[0][0] + pts[2][0]) / 2.0)
        cy = int((pts[0][1] + pts[2][1]) / 2.0)
        detections.append({'id': int(marker_id), 'center': (cx, cy)})
    return detections


# ============================================================
# Snapshot
# ============================================================
def save_snapshot(drone_id, frame, marker_id, detector):
    """Draw a green border around each detected marker and save with ArUco ID in filename."""
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    display = frame.copy()
    gray = cv2.cvtColor(display, cv2.COLOR_BGR2GRAY)
    c, i, _ = detector.detectMarkers(gray)
    
    if i is not None:
        cv2.aruco.drawDetectedMarkers(display, c, i)
    
    timestamp = int(time.time())
    filename = (f"{SNAPSHOT_DIR}/"
                f"robot_aruco{marker_id}_drone{drone_id+1}_{timestamp}.jpg")
    cv2.imwrite(filename, display)
    print(f"[SNAPSHOT] Aruco ID {marker_id} -> {filename}")
    return filename


# ============================================================
# Helpers
# ============================================================

def get_uwb_position(uwb, ip_str):
    """
    Get drone UWB position in metres.

    Translates drone IP address to its physical UWB block_id
    using UWB_TAG_IDS — populated automatically by
    auto_match_uwb_tags() after Phase A landing.

    Returns (x, y) or None if not available.
    """
    tag_id = UWB_TAG_IDS.get(ip_str)
    if tag_id is None:
        print(f"[UWB] WARNING: No UWB tag mapping for {ip_str}. "
              f"Update UWB_TAG_IDS.")
        return None
    x, y, _ = uwb.get_tag_position(tag_id)
    return (x, y) if x is not None else None
    

# =====================================================================
# Inter-Drone Avoidance Configuration (Using UWB data from each drone)
# =====================================================================
# Distance within which drones repel each other (metres)

DRONE_REPEL_DIST = 1.0

def check_drone_avoidance(ip_str, drone_id, current_pos, drone_list, drone_ids, uwb, states):
    """
    Check if a higher-priority drone is too close via UWB.
    If so transition this drone to WF_AVOID_DRONE (hover).

    Only the lower-priority drone (higher ID) yields —
    prevents deadlock where both drones avoid simultaneously.

    Returns True if avoidance was triggered.
    """
    if current_pos is None:
        return False
    
    for other_ip in drone_list:
        if other_ip == ip_str:
            continue
        other_id = drone_ids[other_ip]
        other_pos = get_uwb_position(uwb, other_ip)
        if other_pos is None:
            continue
        d = uwb_distance(current_pos, other_pos)
        if d < DRONE_REPEL_DIST:
            # Priority rule: higher ID yields to lower ID
            if drone_id > other_id:
                print(f"[Drone {drone_id+1}] Too close to Drone "
                      f"{other_id+1} ({d:.2f}m). Hovering.")
                states[ip_str] = WF_AVOID_DRONE
                return True
    return False
        

# ============================================================
# MAIN
# ============================================================

def main():
    global robots_found, snapshotted_ids, phase_b_approved
    
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    detector = make_aruco_detector()

    # Start UWB Parser
    uwb = UWBParserThread()
    if uwb.serial_port:
        uwb.start()
        time.sleep(2.0)   # wait for first frames
        print("Measure landing zones now? (y / Enter to skip): ", end="")
        if input().strip().lower() == "y":
            measure_landing_zones(uwb)
            print("Update LANDING_ZONES then re-run.")
            return
    else:
        print("No UWB device detected.")

    # Discover drones
    dola = Dola()
    dola.start()

    try:
        print("Searching for all drones")
        d = dola.get_all_ips( # Dola is drone explorer. Find all drones in the network
            listen_seconds=5
        )
    finally:
        dola.stop()

    drones = {}  # store all drones object for control (# ip_str -> DroneAPI)
    streams = {}  # store all video object for live straam access (# ip_str -> VideoStream)
    drone_list = []  # ordered list of ip_str

    for plane_id, ip in d.items():
        print(f"Plane {plane_id}: {ip}")
        ip_str = str(ip)
        drones[ip_str] = DroneAPI()
        drones[ip_str].connect(ip) # connect to ip address to gain control of drone
        drones[ip_str].set_barrier_mode(enabled=True)
        drones[ip_str].set_camera_angle(CameraPitchMode.DOWN_ABSOLUTE, 45)  # set gimbal camera of HULA drones to point 45 degrees downwards
        drone_list.append(ip_str)
        v = drones[ip_str].create_video_stream() # Get VideoStream object
        drones[ip_str].set_video_stream(True) # Turn on video stream
        if v is not None:
            streams[ip_str] = v # Store Videostream into a dict for future use
            streams[ip_str].start() #start video

    # YAW + UWB CONVENTION TEST -- run once on competition day, then remove
    print("\nRun yaw/UWB convention test? (y / Enter to skip): ", end="")
    if input().strip().lower() == "y":
        test_drone = drones[drone_list[0]]

        print("\n[TEST] Pick up the drone.")
        print("[TEST] Press Enter to read yaw + UWB position. Type q + Enter to stop.\n")

        while True:
            user = input()
            if user.strip().lower() == 'q':
                break
            yaw = test_drone.get_orientation().yaw
            # Scan all visible UWB tags and print their positions
            # since UWB_TAG_IDS not populated yet
            positions = []
            for tag_id in range(30):
                x, y, _ = uwb.get_tag_position(tag_id)
                if x is not None:
                    positions.append(f"block_id={tag_id}: ({x:.2f}, {y:.2f})")
            print(f"[TEST] yaw={yaw:.1f} degrees | UWB: {positions}")
            
    # Assign landing zones and wall-following direction
    drone_ids = {ip: idx for idx, ip in enumerate(drone_list)}
    drone_landing_zones = {}
    drone_wf_direction = {}  # +1 = left wall, -1 = right wall

    for idx, ip_str in enumerate(drone_list):
        if idx < len(LANDING_ZONES):
            drone_landing_zones[ip_str] = LANDING_ZONES[idx]
        drone_wf_direction[ip_str] = -1 if idx % 2 == 0 else 1  # Drones 1 and 3 will follow right wall
    
    # Per-drone state initialisation
    states = {ip: STATE_TAKEOFF_A for ip in drone_list}
    takeoff_trigger = {ip: time.time() + drone_ids[ip] * TAKEOFF_DELAY
                       for ip in drone_list}
    wf_states = {ip: make_wf_state() for ip in drone_list}

    # Main control loop (10 Hz)
    while True: # just to keep looping . Add your drone commands for each respective drones in this loop.
        now = time.time()
        for ip_str in drone_list:
            drone = drones[ip_str]
            drone_id = drone_ids[ip_str]

            # Speed monitoring -- remove once MAX_FORWARD_SPEED and MAX_FLIGHT_SPEED tuned
            try:
                v        = drone.get_velocity()
                speed_ms = math.sqrt(v.x**2 + v.y**2) / 100
                print(f"[Drone {drone_id+1}] speed={speed_ms:.2f} m/s")
            except:
                pass   # TelemetryUnavailable -- skip if no data yet
            state = states[ip_str]

            current_pos = get_uwb_position(uwb, ip_str)

            # write your control code here. For example, you can make the drone takeoff by calling d.takeoff() or move forward by d.move(Direction.FORWARD, 0.5) and etc. Refer to pyhulax documentation for more details on drone control commands.
            # IMPORTANT CONCEPT: Break your plan into states and use if else statement to control the flow of the drone. 
            # For example, you can have a state variable for each drone that starts at 0. When state is 0, you can make the drone takeoff and then set state to 1. 
            # When state is 1, you can make the drone move forward for 2 seconds and then set state to 2. 
            # This way you can have a sequence of commands for your drone and control the flow of the commands by changing the state variable.
            #  You can also use timers to change states after certain amount of time.

            # -----------------------------------------------
            # PHASE A
            # -----------------------------------------------

            if state == STATE_TAKEOFF_A:
                if takeoff_trigger[ip_str] <= now:
                    drone.takeoff(height_cm=FLIGHT_ALTITUDE_CM, blocking=True)
                    states[ip_str] = STATE_FLY_TO_ZONE
            
            elif state == STATE_FLY_TO_ZONE:
                zone = drone_landing_zones.get(ip_str)
                if zone is None or current_pos is None:
                    continue
                dx = zone[0] - current_pos[0]
                dy = zone[1] - current_pos[1]
                dist = math.sqrt(dx**2 + dy**2)
                if dist < POSITION_THRESHOLD_M:
                    drone.send_manual_control(x=0, y=0)  # stop
                    states[ip_str] = STATE_LAND
                else:
                    # Rotate global UWB velocity into drone body frame
                    # using current heading so forward/right are correct
                    heading = math.radians(drone.get_orientation().yaw)
                    vx_g = (dx / dist)  # unit vector East
                    vy_g = (dy / dist)  # unit vector North

                    # Rotation Matrix (verify on actual day) 
                    # Currently, this rotation matrix assumes yaw = 0 when drone faces the UWB x-axis direction (EAST))
                    # 2ND assumption: Positive yaw = counterclockwise rotation
                    # Rotate into drone body frame then scale to -1000/+1000
                    x_cmd = int(min(MAX_FLIGHT_SPEED, dist * 1000) *
                                  ( vx_g * math.cos(heading) + vy_g * math.sin(heading)))
                    y_cmd = int(min(MAX_FLIGHT_SPEED, dist * 1000) *
                                  (-vx_g * math.sin(heading) + vy_g * math.cos(heading)))
                    drone.send_manual_control(x=x_cmd, y=y_cmd)

            elif state == STATE_LAND:
                drone.land()
                states[ip_str] = STATE_WAIT_PHASE_B

            elif state == STATE_WAIT_PHASE_B:
                phase_a_active = {STATE_TAKEOFF_A, STATE_FLY_TO_ZONE, STATE_LAND}
                all_done = not any(
                    states[ip] in phase_a_active for ip in drone_list
                )
                if all_done:
                    # Run UWB matching once when all drones first land
                    if not UWB_TAG_IDS:
                        auto_match_uwb_tags(drone_list, drone_landing_zones, uwb)
                    # Start approval thread once — waits for operator
                    # to press Enter before Phase B begins.
                    # Thread runs in background so drones stay landed.
                    if not phase_b_approved:
                        # Only start the thread once (check if already started)
                        active = [t for t in threading.enumerate()
                                  if t.name == "phase_b_approval"]
                        if not active:
                            t = threading.Thread(
                                target=_wait_for_phase_b,
                                name="phase_b_approval",
                                daemon=True
                            )
                            t.start()
                    # Only transition when operator has approved
                    if phase_b_approved:
                        takeoff_trigger[ip_str] = (now + drone_ids[ip_str] * TAKEOFF_DELAY)
                        states[ip_str] = STATE_TAKEOFF_B

            # -----------------------------------------------
            # PHASE B
            # -----------------------------------------------
            
            elif state == STATE_TAKEOFF_B:
                if takeoff_trigger[ip_str] <= now:
                    drone.takeoff(height_cm=FLIGHT_ALTITUDE_CM, blocking=True)
                    wf_states[ip_str] = make_wf_state()
                    states[ip_str] = STATE_WALL_FOLLOWING

            elif state == STATE_WALL_FOLLOWING:
                if robots_found >= TOTAL_ROBOTS:
                    states[ip_str] = STATE_MISSION_COMPLETE
                    continue

                avoided = check_drone_avoidance(
                    ip_str, drone_id, current_pos, drone_list, drone_ids, uwb, states
                )
                if avoided:
                    continue

                direction = drone_wf_direction[ip_str]
                x_cmd, y_cmd, r_cmd = wall_follower_tick(
                    drone, wf_states[ip_str], direction, now
                )
                drone.send_manual_control(x=int(x_cmd), y=int(y_cmd), r=int(r_cmd))  # Send velocity

                # ArUco detection on live frame
                s = streams.get(ip_str)
                if s is None:
                    continue
                f = s.latest_frame
                if f is not None:
                    frame = f.to_rgb()
                    detections = detect_aruco(frame, detector)
                    new_ids    = [det['id'] for det in detections
                                  if det['id'] in ROBOMASTER_IDS
                                  and det['id'] not in snapshotted_ids]
                    for marker_id in new_ids:
                        snapshotted_ids.add(marker_id)
                        robots_found += 1
                        save_snapshot(drone_id, frame, marker_id, detector)
                    # Display with markers drawn
                    display = frame.copy()
                    gray = cv2.cvtColor(display, cv2.COLOR_BGR2GRAY)
                    c, i, _ = detector.detectMarkers(gray)
                    if i is not None:
                        cv2.aruco.drawDetectedMarkers(display, c, i)
                    cv2.imshow(str(ip_str), display)  # live display of each drone
                    cv2.waitKey(1)
            
            elif state == WF_AVOID_DRONE:
                still_too_close = False
                for other_ip in drone_list:
                    if other_ip == ip_str:
                        continue
                    other_pos = get_uwb_position(uwb, other_ip)
                    if other_pos is None or current_pos is None:
                        continue
                    if uwb_distance(current_pos, other_pos) < DRONE_REPEL_DIST:
                        still_too_close = True
                        break
                if not still_too_close:
                    states[ip_str] = STATE_WALL_FOLLOWING
                else:
                    drone.send_manual_control(x=0, y=0, r=0)  # hover

            elif state == STATE_MISSION_COMPLETE:
                drone.land()
                drone_list.remove(ip_str)
                break
        
        if len(drone_list) == 0:
            break

        time.sleep(0.05)   # 20Hz (every 50ms): matches send_manual_control recommended rate to ensure smooth flight
    
    cv2.destroyAllWindows()
        

if __name__ == "__main__":
    main()
    
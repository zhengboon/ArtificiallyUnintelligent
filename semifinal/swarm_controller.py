# Swarm Controller for DSTA Brainhack RoboVerse 2026 — Challenge 2
# 3 HULA drones simulate wall-following using UWB waypoints.
# Phase A: fly to landing zones using UWB navigation.
# Phase B: fly perimeter waypoints at varying margins, spin 360 at each waypoint.

from pyhulax import DroneAPI
from pyhulax.core import Direction, CameraPitchMode
import cv2
from dola import Dola
from pyhulax.video import VideoStream, VideoDisplay
from UWBParserThread import UWBParserThread
import time
import math
import os
import threading
import tempfile
import types
import signal

# ============================================================
# Arena Configuration
# ============================================================

# UWB origin offset — update on competition day
CAGE_ORIGIN_X = 5.5   # Cage 1=0.0, Cage 2=5.5, Cage 3=5.5
CAGE_ORIGIN_Y = 0.0   # Cage 1=0.0, Cage 2=0.0, Cage 3=5.5

# Arena boundary corners (UWB metres)
ARENA_X_MIN = 5.5
ARENA_X_MAX = 11.0
ARENA_Y_MIN = 0.0
ARENA_Y_MAX = 11.0

# Each drone follows a perimeter loop at a different margin
# Drone 1: outer  (0.5m), CCW
# Drone 2: middle (1.8m), CW
# Drone 3: inner  (1.0m), CCW
DRONE_MARGINS    = [0.5, 1.8, 1.0]
DRONE_ORBIT_DIRS = [-1, 1, -1]   # -1=CCW, +1=CW (in UWB coordinates where y increases upward)

# Waypoint spacing along perimeter
WAYPOINT_SPACING = 2.0   # metres

# ============================================================
# Mission Configuration
# ============================================================

LANDING_ZONES = [
    (1.3, 7.85),   # drone 1 -- TO DO: update on competition day
    (4.4, 4.4),    # drone 2 -- TO DO: update on competition day
    (1.95, 8.7),   # drone 3 -- TO DO: update on competition day
]

FLIGHT_ALTITUDE_CM   = 110
POSITION_THRESHOLD_M = 0.3
MAX_FLIGHT_SPEED     = 500   # Phase A navigation
MAX_FORWARD_SPEED    = 300   # Phase B movement
SPIN_SPEED           = 300   # yaw rate during 360 scan
SPIN_EVERY_N         = 3     # spin at every Nth waypoint
TOTAL_ROBOTS         = 5
SNAPSHOT_DIR         = "snapshots"
TAKEOFF_DELAY        = 1.0
CLIMB_TIME           = 5.0   # seconds after non-blocking takeoff
DRONE_REPEL_DIST     = 0.5   # metres — UWB avoidance trigger distance

# ============================================================
# ArUco Configuration
# ============================================================

ARUCO_DICT     = cv2.aruco.DICT_7X7_1000
ROBOMASTER_IDS = {11, 45, 51, 67, 101}  # DELETE 28

# ============================================================
# UWB Tag ID Mapping
# Hardcoded — given by admin on competition day
# Format: {drone_ip_str: uwb_block_id}
# ============================================================

UWB_TAG_IDS = {
    # EXAMPLE: (Need to get UWB id from admin)
    "192.168.1.101": 3,    # drone 1 IP → UWB block_id
    "192.168.1.102": 7,    # drone 2 IP → UWB block_id
    "192.168.1.103": 12,   # drone 3 IP → UWB block_id
}   # TO DO: fill in on competition day

# ============================================================
# Phase A State Definitions
# ============================================================

STATE_TAKEOFF_A    = "STATE_TAKEOFF_A"
STATE_TAKING_OFF_A = "STATE_TAKING_OFF_A"
STATE_FLY_TO_ZONE  = "STATE_FLY_TO_ZONE"
STATE_LAND         = "STATE_LAND"
STATE_WAIT_PHASE_B = "STATE_WAIT_PHASE_B"

# ============================================================
# Phase B State Definitions
# ============================================================

STATE_TAKEOFF_B        = "STATE_TAKEOFF_B"
STATE_TAKING_OFF_B     = "STATE_TAKING_OFF_B"
STATE_FLY_TO_WAYPOINT  = "STATE_FLY_TO_WAYPOINT"
STATE_SPIN_SCAN        = "STATE_SPIN_SCAN"
STATE_MISSION_COMPLETE = "STATE_MISSION_COMPLETE"

# ============================================================
# Global Shared State
# ============================================================

robots_found     = 0
snapshotted_ids  = set()
phase_b_approved = False

def _wait_for_phase_b():
    """Background thread — waits for operator Enter before Phase B."""
    global phase_b_approved
    input("\n[MISSION] All drones landed. Press Enter to start Phase B: ")
    phase_b_approved = True
    print("[MISSION] Phase B approved. Drones taking off shortly.\n")


# ============================================================
# Helper Functions
# ============================================================

def wrap_to_pi(angle):
    """Keep angle within -pi to +pi."""
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle


def uwb_distance(pos1, pos2):
    """Euclidean distance between two UWB (x, y) positions in metres."""
    return math.sqrt((pos1[0]-pos2[0])**2 + (pos1[1]-pos2[1])**2)


def get_uwb_position(uwb, ip_str):
    """Get drone UWB position. Returns (x, y) or None."""
    tag_id = UWB_TAG_IDS.get(ip_str)
    if tag_id is None:
        return None
    x, y, _ = uwb.get_tag_position(tag_id)
    return (x, y) if x is not None else None


def read_sensors(drone):
    """Read IR sensors. Returns (front, left, right) booleans."""
    obstacles = drone.get_obstacles()
    return obstacles.forward, obstacles.left, obstacles.right


# ============================================================
# Waypoint Generation
# ============================================================

def generate_perimeter_waypoints(margin, orbit_dir, spacing=WAYPOINT_SPACING):
    """
    Generate waypoints along the perimeter rectangle at given margin.
    Simulates wall-following using UWB waypoints instead of IR sensors.

    Args:
        margin    -- distance from arena boundary in metres
        orbit_dir -- -1=CCW, +1=CW (UWB coordinates, y increases upward)
        spacing   -- distance between waypoints in metres

    Returns list of (x, y) tuples.
    """
    x_min = ARENA_X_MIN + margin
    x_max = ARENA_X_MAX - margin
    y_min = ARENA_Y_MIN + margin
    y_max = ARENA_Y_MAX - margin

    waypoints = []

    # Bottom edge: left to right
    x = x_min
    while x <= x_max + 0.01:
        waypoints.append((round(x, 2), round(y_min, 2)))
        x += spacing

    # Right edge: bottom to top
    y = y_min + spacing
    while y <= y_max + 0.01:
        waypoints.append((round(x_max, 2), round(y, 2)))
        y += spacing

    # Top edge: right to left
    x = x_max - spacing
    while x >= x_min - 0.01:
        waypoints.append((round(x, 2), round(y_max, 2)))
        x -= spacing

    # Left edge: top to bottom
    y = y_max - spacing
    while y >= y_min + spacing - 0.01:
        waypoints.append((round(x_min, 2), round(y, 2)))
        y -= spacing

    # Reverse for CCW orbit
    if orbit_dir == 1:
        waypoints = list(reversed(waypoints))

    return waypoints


# ============================================================
# Obstacle Avoidance (IR-based, reactive)
# ============================================================

def compute_avoidance(front, left, right, orbit_dir):
    """
    Compute avoidance velocity based on IR sensor readings.
    Only used for unexpected obstacles — waypoints handle navigation.

    orbit_dir: -1=CCW (strafe left when front blocked)
               +1=CW  (strafe right when front blocked)

    Returns (x_cmd, y_cmd) or (None, None) if no obstacle.
    """
    if front and left and right:
        return -MAX_FORWARD_SPEED, 0        # boxed in — back up

    elif front and left:
        return 0, MAX_FORWARD_SPEED         # strafe right

    elif front and right:
        return 0, -MAX_FORWARD_SPEED        # strafe left

    elif front:
        # CCW (+1) → strafe left (-y)
        # CW  (-1) → strafe right (+y)
        return 0, -orbit_dir * MAX_FORWARD_SPEED

    elif left and right:
        return MAX_FORWARD_SPEED, 0         # fly forward

    elif left:
        return 0, MAX_FORWARD_SPEED         # strafe right

    elif right:
        return 0, -MAX_FORWARD_SPEED        # strafe left

    else:
        return None, None                   # no obstacle


# ============================================================
# Inter-Drone Avoidance
# ============================================================

def check_drone_avoidance(ip_str, drone_id, current_pos,
                           drone_list, drone_ids, uwb, states):
    """
    Check if a higher-priority drone is too close.
    Higher priority = lower drone_id.
    Returns True if avoidance triggered.
    """
    if current_pos is None:
        return False

    for other_ip in drone_list:
        if other_ip == ip_str:
            continue
        other_id  = drone_ids[other_ip]
        other_pos = get_uwb_position(uwb, other_ip)
        if other_pos is None:
            continue
        d = uwb_distance(current_pos, other_pos)
        if d < DRONE_REPEL_DIST and drone_id > other_id:
            print(f"[Drone {drone_id+1}] Too close to Drone "
                  f"{other_id+1} ({d:.2f}m). Hovering.")
            return True
    return False


# ============================================================
# UWB Navigation
# ============================================================

def navigate_to(drone, current_pos, target, max_speed):
    """
    Navigate toward target using UWB position.
    Returns True if arrived, False if still navigating.
    """
    if current_pos is None:
        return False

    dx   = target[0] - current_pos[0]
    dy   = target[1] - current_pos[1]
    dist = math.sqrt(dx**2 + dy**2)

    if dist < POSITION_THRESHOLD_M:
        drone.send_manual_control(x=0, y=0)
        return True

    # Rotate global UWB vector into drone body frame
    # Negate heading because HULA yaw is clockwise positive
    heading = -math.radians(drone.get_orientation().yaw)
    vx_g    = dx / dist
    vy_g    = dy / dist
    x_cmd   = int(min(max_speed, dist * 1000) *
                  ( vx_g * math.cos(heading) + vy_g * math.sin(heading)))
    y_cmd   = int(min(max_speed, dist * 1000) *
                  (-vx_g * math.sin(heading) + vy_g * math.cos(heading)))
    drone.send_manual_control(x=x_cmd, y=y_cmd)
    return False


# ============================================================
# ArUco Detection
# ============================================================

def make_aruco_detector():
    """Create ArUco detector. Supports old and new OpenCV."""
    aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT)
    if hasattr(cv2.aruco, 'DetectorParameters_create'):
        parameters = cv2.aruco.DetectorParameters_create()
    else:
        parameters = cv2.aruco.DetectorParameters()
    if hasattr(cv2.aruco, 'ArucoDetector'):
        return cv2.aruco.ArucoDetector(aruco_dict, parameters)
    else:
        return (aruco_dict, parameters)


def detect_aruco(frame, detector):
    """Detect ArUco markers. Returns list of {'id', 'center'} dicts."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    if isinstance(detector, tuple):
        aruco_dict, parameters = detector
        corners, ids, _ = cv2.aruco.detectMarkers(
            gray, aruco_dict, parameters=parameters)
    else:
        corners, ids, _ = detector.detectMarkers(gray)
    detections = []
    if ids is None:
        return detections
    for marker_corners, marker_id in zip(corners, ids.flatten()):
        print(f"[DEBUG] Detected marker ID: {marker_id}")
        if int(marker_id) not in ROBOMASTER_IDS:
            continue
        pts = marker_corners.reshape((4, 2))
        cx  = int((pts[0][0] + pts[2][0]) / 2.0)
        cy  = int((pts[0][1] + pts[2][1]) / 2.0)
        detections.append({'id': int(marker_id), 'center': (cx, cy)})
    return detections


def save_snapshot(drone_id, frame, marker_id, detector):
    """Save snapshot with ArUco markers drawn."""
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    display = frame.copy()
    gray    = cv2.cvtColor(display, cv2.COLOR_BGR2GRAY)
    if isinstance(detector, tuple):
        aruco_dict, parameters = detector
        c, i, _ = cv2.aruco.detectMarkers(
            gray, aruco_dict, parameters=parameters)
    else:
        c, i, _ = detector.detectMarkers(gray)
    if i is not None:
        cv2.aruco.drawDetectedMarkers(display, c, i)
    timestamp = int(time.time())
    filename  = (f"{SNAPSHOT_DIR}/"
                 f"robot_aruco{marker_id}_drone{drone_id+1}_{timestamp}.jpg")
    cv2.imwrite(filename, display)
    print(f"[SNAPSHOT] Aruco ID {marker_id} -> {filename}")
    return filename


# ============================================================
# Video Stream Fix
# ============================================================

def create_video_stream_fixed(drone, drone_id_num):
    """Create video stream with correct SDP format matching Hula.cpp."""
    v = drone.create_video_stream()

    def _create_sdp_file_fixed(self):
        videoport   = 9000 + drone_id_num * 2
        sdp_content = (
            f"m=video {videoport} RTP/AVP 98\n"
            f"a=rtpmap:98 H264/90000\n"
            f"a=framerate=30 packetization-mode=1\n"
            f"c=IN IP4 0\n"
        )
        fd, path = tempfile.mkstemp(suffix=".sdp", prefix="drone_video_")
        with os.fdopen(fd, 'w') as f:
            f.write(sdp_content)
        self._sdp_path = path
        return path

    v._create_sdp_file = types.MethodType(_create_sdp_file_fixed, v)
    return v


# ============================================================
# Emergency Landing
# ============================================================

drones = {}

def emergency_land(sig, frame):
    global drones
    print("\n[EMERGENCY] Ctrl+C detected. Landing all drones...")
    for drone in drones.values():
        try:
            drone.land()
        except:
            pass
    cv2.destroyAllWindows()
    exit(0)


# ============================================================
# MAIN
# ============================================================

def main():
    global robots_found, snapshotted_ids, phase_b_approved, drones
    signal.signal(signal.SIGINT, emergency_land)

    try:
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        detector = make_aruco_detector()

        # Start UWB Parser
        uwb = UWBParserThread(x_origin=CAGE_ORIGIN_X, y_origin=CAGE_ORIGIN_Y)
        if uwb.serial_port:
            uwb.start()
            time.sleep(2.0)

        else:
            print("No UWB device detected.")

        # Discover drones
        dola = Dola()
        dola.start()
        try:
            print("Searching for all drones")
            d = dola.get_all_ips(listen_seconds=5)
        finally:
            dola.stop()

        streams    = {}
        drone_list = []

        for plane_id, ip in d.items():
            print(f"Plane {plane_id}: {ip}")
            ip_str = str(ip)
            drones[ip_str] = DroneAPI()
            drones[ip_str].connect(ip)
            drones[ip_str].set_barrier_mode(enabled=True)
            drones[ip_str].set_camera_angle(CameraPitchMode.DOWN_ABSOLUTE, 45)
            drone_list.append(ip_str)
            v = create_video_stream_fixed(drones[ip_str], plane_id)
            drones[ip_str].set_video_stream(True)
            if v is not None:
                streams[ip_str] = v
                streams[ip_str].start()

        # Uncomment to run yaw/UWB convention test on competition day:
        # print("\nRun yaw/UWB convention test? (y / Enter to skip): ", end="")
        # if input().strip().lower() == "y":
        #     test_drone = drones[drone_list[0]]
        #     print("\n[TEST] Pick up drone. Press Enter to read. q+Enter to stop.\n")
        #     while True:
        #         user = input()
        #         if user.strip().lower() == 'q':
        #             break
        #         yaw = test_drone.get_orientation().yaw
        #         positions = []
        #         for tag_id in range(30):
        #             x, y, _ = uwb.get_tag_position(tag_id)
        #             if x is not None:
        #                 positions.append(f"block_id={tag_id}: ({x:.2f}, {y:.2f})")
        #         print(f"[TEST] yaw={yaw:.1f}° | UWB: {positions}")

        # Assign landing zones, orbit directions and waypoints per drone
        drone_ids           = {ip: idx for idx, ip in enumerate(drone_list)}
        drone_landing_zones = {}
        drone_orbit_dir     = {}
        drone_waypoints     = {}

        for idx, ip_str in enumerate(drone_list):
            if idx < len(LANDING_ZONES):
                drone_landing_zones[ip_str] = LANDING_ZONES[idx]

            margin    = DRONE_MARGINS[idx % len(DRONE_MARGINS)]
            orbit_dir = DRONE_ORBIT_DIRS[idx % len(DRONE_ORBIT_DIRS)]
            drone_orbit_dir[ip_str] = orbit_dir
            drone_waypoints[ip_str] = generate_perimeter_waypoints(
                margin, orbit_dir)

            print(f"Drone {idx+1} ({ip_str}): margin={margin}m | "
                  f"{'CW' if orbit_dir==1 else 'CCW'} | "
                  f"{len(drone_waypoints[ip_str])} waypoints")

        # Per-drone state initialisation
        states               = {ip: STATE_TAKEOFF_A for ip in drone_list}
        takeoff_trigger      = {ip: time.time() + drone_ids[ip] * TAKEOFF_DELAY
                                for ip in drone_list}
        climb_until          = {ip: None for ip in drone_list}
        current_wp_idx       = {ip: 0 for ip in drone_list}
        spin_total_rotation  = {ip: 0.0 for ip in drone_list}
        spin_prev_yaw        = {ip: 0.0 for ip in drone_list}

        # Main control loop (20 Hz)
        print("Starting main loop...")
        while True:
            now = time.time()

            for ip_str in drone_list:
                drone       = drones[ip_str]
                drone_id    = drone_ids[ip_str]
                state       = states[ip_str]
                current_pos = get_uwb_position(uwb, ip_str)

                # Speed monitoring — remove once speeds tuned
                try:
                    v        = drone.get_velocity()
                    speed_ms = math.sqrt(v.x**2 + v.y**2) / 100
                    print(f"[Drone {drone_id+1}] speed={speed_ms:.2f}m/s "
                          f"state={state}")
                except:
                    pass

                # -----------------------------------------------
                # PHASE A
                # -----------------------------------------------

                if state == STATE_TAKEOFF_A:
                    if takeoff_trigger[ip_str] <= now:
                        drone.takeoff(height_cm=FLIGHT_ALTITUDE_CM,
                                      blocking=False)
                        climb_until[ip_str] = now + CLIMB_TIME
                        states[ip_str]      = STATE_TAKING_OFF_A

                elif state == STATE_TAKING_OFF_A:
                    if now >= climb_until[ip_str]:
                        states[ip_str] = STATE_FLY_TO_ZONE

                elif state == STATE_FLY_TO_ZONE:
                    zone = drone_landing_zones.get(ip_str)
                    if zone is None or current_pos is None:
                        pass   # no UWB — wait
                    else:
                        arrived = navigate_to(
                            drone, current_pos, zone, MAX_FLIGHT_SPEED)
                        if arrived:
                            states[ip_str] = STATE_LAND

                elif state == STATE_LAND:
                    drone.land()
                    states[ip_str] = STATE_WAIT_PHASE_B

                elif state == STATE_WAIT_PHASE_B:
                    phase_a_active = {STATE_TAKEOFF_A, STATE_TAKING_OFF_A,
                                      STATE_FLY_TO_ZONE, STATE_LAND}
                    all_done = not any(
                        states[ip] in phase_a_active for ip in drone_list
                    )
                    if all_done:
                        if not phase_b_approved:
                            active = [t for t in threading.enumerate()
                                      if t.name == "phase_b_approval"]
                            if not active:
                                t = threading.Thread(
                                    target=_wait_for_phase_b,
                                    name="phase_b_approval",
                                    daemon=True
                                )
                                t.start()
                        if phase_b_approved:
                            takeoff_trigger[ip_str] = (now +
                                drone_ids[ip_str] * TAKEOFF_DELAY)
                            states[ip_str] = STATE_TAKEOFF_B

                # -----------------------------------------------
                # PHASE B
                # -----------------------------------------------

                elif state == STATE_TAKEOFF_B:
                    if takeoff_trigger[ip_str] <= now:
                        drone.takeoff(height_cm=FLIGHT_ALTITUDE_CM,
                                      blocking=False)
                        climb_until[ip_str] = now + CLIMB_TIME
                        states[ip_str]      = STATE_TAKING_OFF_B

                elif state == STATE_TAKING_OFF_B:
                    if now >= climb_until[ip_str]:
                        current_wp_idx[ip_str] = 0
                        states[ip_str]         = STATE_FLY_TO_WAYPOINT

                elif state == STATE_FLY_TO_WAYPOINT:
                    if robots_found >= TOTAL_ROBOTS:
                        states[ip_str] = STATE_MISSION_COMPLETE
                    else:
                        waypoints = drone_waypoints[ip_str]
                        idx       = current_wp_idx[ip_str] % len(waypoints)
                        target    = waypoints[idx]
                        orbit_dir = drone_orbit_dir[ip_str]

                        # Check inter-drone avoidance first
                        avoided = check_drone_avoidance(
                            ip_str, drone_id, current_pos,
                            drone_list, drone_ids, uwb, states
                        )
                        if avoided:
                            drone.send_manual_control(x=0, y=0, r=0)
                        else:
                            # Check IR sensors for unexpected obstacles
                            front, left, right = read_sensors(drone)
                            x_av, y_av = compute_avoidance(
                                front, left, right, orbit_dir)

                            if x_av is not None:
                                # Unexpected obstacle — avoid reactively
                                drone.send_manual_control(x=x_av, y=y_av, r=0)
                            else:
                                # No obstacle — navigate to waypoint
                                arrived = navigate_to(
                                    drone, current_pos, target,
                                    MAX_FORWARD_SPEED)
                                if arrived:
                                    # Only spin every Nth waypoint
                                    if current_wp_idx[ip_str] % SPIN_EVERY_N == 0:
                                        spin_total_rotation[ip_str] = 0.0
                                        spin_prev_yaw[ip_str] = (
                                            drone.get_orientation().yaw)
                                        states[ip_str] = STATE_SPIN_SCAN
                                    else:
                                        current_wp_idx[ip_str] += 1
                                        # stay in STATE_FLY_TO_WAYPOINT

                elif state == STATE_SPIN_SCAN:
                    if robots_found >= TOTAL_ROBOTS:
                        states[ip_str] = STATE_MISSION_COMPLETE
                    else:
                        current_yaw = drone.get_orientation().yaw
                        delta = abs(wrap_to_pi(
                            math.radians(current_yaw) -
                            math.radians(spin_prev_yaw[ip_str])
                        ))
                        spin_total_rotation[ip_str] += delta
                        spin_prev_yaw[ip_str]        = current_yaw

                        if spin_total_rotation[ip_str] >= 2 * math.pi:
                            # Full 360° done — move to next waypoint
                            drone.send_manual_control(x=0, y=0, r=0)
                            current_wp_idx[ip_str] += 1
                            states[ip_str] = STATE_FLY_TO_WAYPOINT
                        else:
                            drone.send_manual_control(x=0, y=0, r=SPIN_SPEED)

                elif state == STATE_MISSION_COMPLETE:
                    drone.land()
                    drone_list.remove(ip_str)
                    break

                # -----------------------------------------------
                # ArUco detection + live display
                # Runs every tick regardless of state
                # -----------------------------------------------
                s = streams.get(ip_str)
                if s is not None and s.latest_frame is not None:
                    # Convert RGB to BGR for correct colours
                    frame      = cv2.cvtColor(
                        s.latest_frame.to_rgb(), cv2.COLOR_RGB2BGR)
                    detections = detect_aruco(frame, detector)
                    new_ids    = [det['id'] for det in detections
                                  if det['id'] in ROBOMASTER_IDS
                                  and det['id'] not in snapshotted_ids]
                    for marker_id in new_ids:
                        snapshotted_ids.add(marker_id)
                        robots_found += 1
                        save_snapshot(drone_id, frame, marker_id, detector)
                        print(f"[Drone {drone_id+1}] Robots found: "
                              f"{robots_found}/{TOTAL_ROBOTS} "
                              f"| IDs: {snapshotted_ids}")
                    # Display with markers drawn
                    display = frame.copy()
                    gray    = cv2.cvtColor(display, cv2.COLOR_BGR2GRAY)
                    if isinstance(detector, tuple):
                        ad, pd = detector
                        c, i, _ = cv2.aruco.detectMarkers(
                            gray, ad, parameters=pd)
                    else:
                        c, i, _ = detector.detectMarkers(gray)
                    if i is not None:
                        cv2.aruco.drawDetectedMarkers(display, c, i)
                    cv2.imshow(str(ip_str), display)

            if len(drone_list) == 0:
                break

            cv2.waitKey(1)
            time.sleep(0.05)   # 20Hz

        cv2.destroyAllWindows()

    finally:
        print("\n[CLEANUP] Landing all drones...")
        for drone in drones.values():
            try:
                drone.land()
            except:
                pass
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

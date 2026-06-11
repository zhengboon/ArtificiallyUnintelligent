import math

# ============================================================
# WALL-FOLLOWING VARIABLES
# ============================================================

MAX_FORWARD_SPEED           = 300  # (-1000 to +1000, 300 = 30%)
MAX_TURN_RATE               = 300  # (-1000 to +1000, 300 = 30%)
IN_CORNER_ANGLE             = 0.8  # inside corner rotation (rad)
WAIT_FOR_MEASUREMENT_SECONDS = 1.0
ANGLE_VALUE_BUFFER          = 0.1  # heading margin (rad)

# ============================================================
# WALL-FOLLOWING STATE STRINGS
# ============================================================

WF_FORWARD            = "WF_FORWARD"
WF_HOVER              = "WF_HOVER"
WF_TURN_TO_FIND_WALL  = "WF_TURN_TO_FIND_WALL"
WF_TURN_TO_ALIGN      = "WF_TURN_TO_ALIGN"
WF_FORWARD_ALONG_WALL = "WF_FORWARD_ALONG_WALL"
WF_ROTATE_AROUND_WALL = "WF_ROTATE_AROUND_WALL"
WF_ROTATE_IN_CORNER   = "WF_ROTATE_IN_CORNER"
WF_FIND_CORNER        = "WF_FIND_CORNER"

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def wrap_to_pi(angle):
    """
    Keep angle within -pi to +pi.
    Equivalent to wraptopi() in Crazyflie C code.
    """
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle


def is_close_to(real_value, checked_value, margin):
    """
    Check if real_value is within margin of checked_value.
    Equivalent to logicIsCloseTo() in Crazyflie C code.
    """
    return abs(real_value - checked_value) < margin


# ============================================================
# HARDWARE INTERFACE FUNCTIONS
# ============================================================

def read_sensors(drone):
    """
    Read front and side IR sensors as booleans.

    Returns:
        front (bool) -- True = obstacle ahead
        left  (bool) -- True = obstacle on left
        right (bool) -- True = obstacle on right

    Equivalent to in wall_follower.c:
        frontRange = logGetUint(idFront) / 1000.0f
        sideRange  = logGetUint(idLeft or idRight) / 1000.0f

    The Crazyflie used actual distances. The HULA IR sensors
    return booleans so we use them directly for state transitions.
    set_barrier_mode(True) acts as the safety net for the
    other side (not monitored by wall-following logic).
    """
    obstacles = drone.get_obstacles()
    return obstacles.forward, obstacles.left, obstacles.right


def get_heading(drone):
    """
    Get current drone heading in degrees, converted to radians.

    Equivalent to estYawRad in wall_follower.c:
        heading_deg = logGetFloat(idStabilizerYaw)
        heading_rad = heading_deg * M_PI / 180.0f
    """
    orientation = drone.get_orientation()
    return math.radians(orientation.yaw)


# ============================================================
# PER-DRONE STATE
# ============================================================

def make_wf_state():
    """
    Create initial wall-following state dict for one drone.

    Equivalent to static variables in wallfollowing_multiranger_onboard.c:
        static float previous_heading      = 0.0   -> wf['prevHeading']
        static float angle                 = 0.0   -> wf['wallAngle']
        static bool  around_corner_go_back = false -> wf['aroundCornerBackTrack']
        static bool  first_run             = false -> wf['firstRun']
        float        state_start_time              -> wf['stateStartTime']
    """
    return {
        'state': WF_FORWARD,
        'firstRun': True,
        'prevHeading': 0.0,
        'wallAngle': 0.0,
        'stateStartTime': 0.0,
        'aroundCornerBackTrack': False,
    }


# ============================================================
# WALL-FOLLOWING STATE MACHINE

# Key simplification from C version:
#   - All distance comparisons replaced with boolean IR checks
#   - wallAngle fixed at 90 degrees (can't compute atan without distances)
#   - Same two-sensor approach: only front and side monitored
#   - Other side handled by set_barrier_mode(True) in main script
# ============================================================

def wall_follower_tick(drone, wf, direction, now):
    """
    One tick of the wall-following state machine.
    Call every loop iteration (20Hz) during Phase B.

    Equivalent to wall_follower() in Crazyflie's wallfollowing_multiranger_onboard.c

    Args:
        drone     -- DroneAPI object (for IR sensors and heading)
        wf        -- per-drone state dict from make_wf_state()
        direction -- +1 = follow left wall, -1 = follow right wall
        now       -- current time in seconds

    Returns:
        (x_cmd, y_cmd, r_cmd) -- velocity commands (-1000 to +1000)
                                  x = forward/back
                                  y = left/right
                                  r = yaw rotation
        Main script sends these via drone.send_manual_control().
    """
    # Read front and side sensors
    # Same two-sensor approach as Crazyflie:
    #   direction = +1 (left wall)  → monitor left sensor for wall distance
    #   direction = -1 (right wall) → monitor right sensor for wall distance
    front, left, right = read_sensors(drone)
    side = left if direction == 1 else right
    
    heading = get_heading(drone)

    # First run initialisation
    if wf['firstRun']:
        wf['prevHeading'] = heading
        wf['aroundCornerBackTrack'] = False
        wf['firstRun'] = False
        wf['stateStartTime'] = now

    state = wf['state']

    # Initialise velocity commands
    x_cmd, y_cmd, r_cmd = 0, 0, 0

    # ----------------------------------------------------------
    # STATE TRANSITIONS
    # Using boolean checks to determine state transitions
    # ----------------------------------------------------------

    if state == WF_FORWARD:
        if front:
            wf['state'] = WF_TURN_TO_FIND_WALL
            wf['stateStartTime'] = now
    
    elif state == WF_HOVER:
        pass

    elif state == WF_TURN_TO_FIND_WALL:
        # Both sensors see wall → start aligning
        if front and side:
            wf['prevHeading'] = heading
            # Fixed 90 degree turn
            # Crazyflie computed this from atan(front/side) but we have no distance values
            wf['wallAngle'] = direction * (math.pi / 2)
            wf['state'] = WF_TURN_TO_ALIGN
            wf['stateStartTime'] = now

        # Side sees wall but front is clear → outside corner
        if side and not front:
            wf['aroundCornerBackTrack'] = False
            wf['prevHeading'] = heading
            wf['state'] = WF_FIND_CORNER
            wf['stateStartTime'] = now

    elif state == WF_TURN_TO_ALIGN:
        heading_diff = wrap_to_pi(heading - wf['prevHeading'])
        if is_close_to(heading_diff, wf['wallAngle'], ANGLE_VALUE_BUFFER):
            wf['state'] = WF_FORWARD_ALONG_WALL
            wf['stateStartTime'] = now
    
    elif state == WF_FORWARD_ALONG_WALL:
        # Mutually exclusive: a front obstacle (inside corner) takes priority
        # over a lost side wall, so only ONE transition fires per tick.
        if front:
            wf['prevHeading'] = heading
            wf['state'] = WF_ROTATE_IN_CORNER
            wf['stateStartTime'] = now
        elif not side:
            # wall lost = side sensor reads False
            wf['state'] = WF_FIND_CORNER
            wf['stateStartTime'] = now

    elif state == WF_ROTATE_AROUND_WALL:
        if front:
            wf['state'] = WF_TURN_TO_FIND_WALL
            wf['stateStartTime'] = now

    elif state == WF_ROTATE_IN_CORNER:
        heading_diff = abs(wrap_to_pi(heading - wf['prevHeading']))
        if is_close_to(heading_diff, IN_CORNER_ANGLE, ANGLE_VALUE_BUFFER):
            wf['state'] = WF_TURN_TO_FIND_WALL
            wf['stateStartTime'] = now

    elif state == WF_FIND_CORNER:
        # side sensor detects wall = close enough to corner
        if side:
            wf['state'] = WF_ROTATE_AROUND_WALL
            wf['stateStartTime'] = now

    # ----------------------------------------------------------
    # STATE ACTIONS
    # ----------------------------------------------------------

    state = wf['state']  # re-read after possible transition

    if state == WF_FORWARD:
        # Fly straight -- no wall found yet
        x_cmd, y_cmd, r_cmd = MAX_FORWARD_SPEED, 0.0, 0.0

    elif state == WF_HOVER:
        x_cmd, y_cmd, r_cmd = 0.0, 0.0, 0.0 

    elif state == WF_TURN_TO_FIND_WALL:
        # Spin toward wall side
        # direction +1 (left wall)  → rotate left  (negative yaw)
        # direction -1 (right wall) → rotate right (positive yaw)
        x_cmd, y_cmd, r_cmd = 0.0, 0.0, direction * MAX_TURN_RATE

    elif state == WF_TURN_TO_ALIGN:
        # Wait briefly for sensor to stabilise then turn
        if now - wf['stateStartTime'] < WAIT_FOR_MEASUREMENT_SECONDS:
            x_cmd, y_cmd, r_cmd = 0.0, 0.0, 0.0
        else:
            x_cmd, y_cmd, r_cmd = 0.0, 0.0, direction * MAX_TURN_RATE

    elif state == WF_FORWARD_ALONG_WALL:
        # Move forward + correct side distance
        # boolean nudge -- nudge toward wall if lost, straight if present
        # Only checks the followed wall side.
        # set_barrier_mode handles unexpected obstacles on other side.
        if not side:
            # Wall lost -- nudge toward it
            # direction -1 (right wall) → nudge right (positive right)
            # direction +1 (left wall)  → nudge left  (negative right)
            right_cmd = -direction * (MAX_FORWARD_SPEED / 2.0)
            x_cmd, y_cmd, r_cmd = MAX_FORWARD_SPEED, right_cmd, 0.0
        else:
            # Wall present -- go straight
            x_cmd, y_cmd, r_cmd = MAX_FORWARD_SPEED, 0.0, 0.0

    elif state == WF_ROTATE_AROUND_WALL:
        # Arc around outside corner
        if not side:
            # Side wall lost during arc -- use heading to check backtrack
            heading_diff = abs(wrap_to_pi(heading - wf['prevHeading']))
            if heading_diff > IN_CORNER_ANGLE:
                wf['aroundCornerBackTrack'] = True
            if wf['aroundCornerBackTrack']:
                x_cmd, y_cmd, r_cmd = 0.0, 0.0, direction * (-MAX_TURN_RATE)
            else:
                x_cmd, y_cmd, r_cmd = 0.0, 0.0, direction * MAX_TURN_RATE
        else:
            # Side wall detected — arc forward
            wf['prevHeading'] = heading
            wf['aroundCornerBackTrack'] = False
            x_cmd, y_cmd, r_cmd = MAX_FORWARD_SPEED, 0.0, direction * (-MAX_TURN_RATE)

    elif state == WF_ROTATE_IN_CORNER:
        # Spin in place for inside corner
        x_cmd, y_cmd, r_cmd = 0.0, 0.0, direction * MAX_TURN_RATE

    elif state == WF_FIND_CORNER:
        # Rotate to face corner direction
        x_cmd, y_cmd, r_cmd = 0.0, 0.0, direction * (-MAX_TURN_RATE)
    
    else:
        # Unknown state -- hover for safety
        x_cmd, y_cmd, r_cmd = 0.0, 0.0, 0.0

    return x_cmd, y_cmd, r_cmd




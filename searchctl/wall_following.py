import math
import numpy as np


# =========================
# WALL DISTANCES
# =========================
def get_wall_distances(points):
    if len(points) == 0:
        return {'front': 10.0, 'front_right': 10.0, 'right': 10.0}

    pts = np.array(points)
    
    # Filter floor/ceiling
    y = pts[:, 1]
    pts = pts[np.abs(y) < 0.5]

    if len(pts) == 0:
        return {'front': 10.0, 'front_right': 10.0, 'right': 10.0}

    # Filter drone body
    z_all = pts[:, 2]
    pts = pts[z_all > 1.5]

    if len(pts) == 0:
        return {'front': 10.0, 'front_right': 10.0, 'right': 10.0}

    z = pts[:, 2]   # forward distance
    x = pts[:, 0]   # lateral: positive = right
    angle = np.degrees(np.arctan2(x, z))

    def min_dist_in_sector(lo, hi):
        mask = (angle >= lo) & (angle <= hi)
        if not np.any(mask):
            return 10.0
        return float(np.min(z[mask]))

    # Sectors sized to fit within ±36.5° FOV
    front = min_dist_in_sector(-20, 20)
    front_right = min_dist_in_sector(20, 35)

    # 'right' uses lateral x distance directly — wall beside drone
    # only consider points in the forward-right quadrant (z > 0, x > 0)
    right_mask = (x > 0) & (z > 0.6) & (angle >= 25)
    if np.any(right_mask):
        # distance to right wall = x coordinate of nearest rightward point
        right = float(np.min(x[right_mask]))
    else:
        right = 10.0

    return {
        'front':       front,
        'front_right': front_right,
        'right':       right,
    }


# =========================
# WALL FOLLOWER FSM
# =========================
class WallFollower:
    DESIRED_DIST  = 1.2
    LINEAR_SPEED  = 0.7
    STRAFE_SPEED  = 0.4
    TURN_SPEED    = 0.5   # rad/s for corner yaw
    KP            = 0.7
    WALL_LOST_DIST = DESIRED_DIST + 0.3
    CORNER_PHASE1_TICKS = 177   # forward: 257 originally
    CORNER_PHASE2_TICKS = 90   # yaw (added on top)
    CORNER_PHASE3_TICKS = 20   # forward (added on top)
    CORNER_TURN = 0.35

    def __init__(self):
        self.state = 'find_wall'
        self._pre_avoid_state = 'find_wall'
        self._corner_ticks = 0
        self._avoid_cooldown = 0 

    def compute(self, regions):
        front = regions['front']
        right = regions['right']

        # --- State transitions ---
        if self.state != 'avoid_front' and self.state != 'outer_corner' and front < 2.8:
            self._pre_avoid_state = self.state
            self.state = 'avoid_front'
        elif self.state == 'avoid_front' and front >= 1.8:
            self.state = self._pre_avoid_state
            self._avoid_cooldown = 40
        elif self.state == 'follow_wall' and right > self.WALL_LOST_DIST + 0.7:
            self.state = 'outer_corner'
            self._corner_ticks = 0
        elif self.state == 'outer_corner':
            self._corner_ticks += 1
            total = self.CORNER_PHASE1_TICKS + self.CORNER_PHASE2_TICKS + self.CORNER_PHASE3_TICKS
            if self._corner_ticks >= total:
                self.state = 'follow_wall'
        elif self.state not in ('outer_corner',) and right > self.WALL_LOST_DIST and self._avoid_cooldown == 0:
            self.state = 'find_wall'
        else:
            self.state = 'follow_wall'

        # Decrement cooldown
        if self._avoid_cooldown > 0:
            self._avoid_cooldown -= 1

        # --- Commands: (vx, vy, vz, yaw_rate) ---
        if self.state == 'avoid_front':
            # Rotate anticlockwise in place until front clears
            # vx=0, vy=0 — no translation during turn
            return (0.0, 0.0, 0.0, -self.TURN_SPEED)

        elif self.state == 'find_wall':
            # Move forward, gentle rightward strafe to find wall
            return (self.LINEAR_SPEED, self.STRAFE_SPEED * 0.5, 0.0, 0.0)

        elif self.state == 'outer_corner':
            t = self._corner_ticks
            if t < self.CORNER_PHASE1_TICKS:
                return (self.LINEAR_SPEED, 0.0, 0.0, 0.0)
            elif t < self.CORNER_PHASE1_TICKS + self.CORNER_PHASE2_TICKS:
                return (0.0, 0.0, 0.0, self.CORNER_TURN)
            else:
                return (self.LINEAR_SPEED, 0.0, 0.0, 0.0)
        # elif self.state == 'outer_corner':
        #     return (self.CORNER_FWD, 0.0, 0.0, self.CORNER_TURN)

        else:  # follow_wall
            # Strafe to maintain distance, move forward, no yaw
            error = right - self.DESIRED_DIST
            vy = self.KP * error
            vy = max(-self.STRAFE_SPEED, min(self.STRAFE_SPEED, vy))
            return (self.LINEAR_SPEED, vy, 0.0, 0.0)


# =========================
# VELOCITY SMOOTHER
# =========================
class VelocitySmoother:
    def __init__(self, alpha=0.2):
        self.alpha = alpha
        self.prev = np.zeros(4)

    def smooth(self, cmd):
        cmd = np.array(cmd)
        smoothed = self.alpha * cmd + (1 - self.alpha) * self.prev
        self.prev = smoothed
        return smoothed


# =========================
# BODY TO NED
# =========================
def body_to_ned(vx_body, vy_body, yaw_deg):
    """
    Rotate body-frame velocity into NED world-frame.
    vx_body = forward, vy_body = rightward, yaw_deg = current heading.
    drone.send_velocity() expects NED, so this must be applied
    before every velocity command.
    """
    yaw = math.radians(yaw_deg)
    north = vx_body * math.cos(yaw) - vy_body * math.sin(yaw)
    east  = vx_body * math.sin(yaw) + vy_body * math.cos(yaw)
    return north, east

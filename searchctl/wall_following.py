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
        'right':       right
    }


# =========================
# WALL FOLLOWER FSM
# =========================
class WallFollower:
    # --- K's tuning (preserved verbatim — do not change without sim test) ---
    DESIRED_DIST   = 1.2
    LINEAR_SPEED   = 0.7
    STRAFE_SPEED   = 0.4
    TURN_SPEED     = 0.7   # rad/s for in-place rotation
    KP             = 0.7
    WALL_LOST_DIST = DESIRED_DIST + 0.3   # = 1.5
    CORNER_PHASE1_TICKS = 140   # forward
    CORNER_PHASE2_TICKS = 105   # yaw
    CORNER_PHASE3_TICKS = 15    # forward
    CORNER_TURN    = 0.35

    # --- FSM safety thresholds (added on top of K's tuning) ---
    # 1) Stuck-in-follow_wall escape: if (front,right) barely change for 3s,
    #    drone is wedged at a corner/pillar. Escape via pure CCW yaw (no
    #    translation -> vision-EKF safe). 2s of yaw at 0.7 rad/s = ~80°.
    STUCK_WINDOW_TICKS    = 60     # 3.0s @ 20Hz
    STUCK_DELTA_M         = 0.15
    STUCK_FRONT_MAX_M     = 4.0    # only "stuck" if something plausibly blocking
    ESCAPE_TICKS          = 40     # 2.0s of pure CCW yaw
    ESCAPE_COOLDOWN_TICKS = 100    # 5.0s before stuck-detect can fire again

    # 2) avoid_front cap: drone may rotate in a corner pocket without front
    #    ever clearing. Cap so we don't spin forever.
    AVOID_FRONT_MAX_TICKS = 180    # 9.0s = ~360° at TURN_SPEED

    # 3) outer_corner phase-1 abort: K's phase 1 is 7s × 0.7 m/s = 4.9m of
    #    forward with no front check. If a wall appears mid-corner, abort.
    OUTER_CORNER_FRONT_ABORT_M = 1.5

    # 4) find_wall stall cap: if drone is "looking for a wall" for 20s and
    #    still hasn't found one, do an escape yaw to re-orient.
    FIND_WALL_STALL_TICKS = 400    # 20s

    def __init__(self):
        self.state = 'find_wall'
        self._pre_avoid_state = 'find_wall'
        self._corner_ticks = 0
        self._avoid_cooldown = 0
        # Stuck / escape bookkeeping
        self._stuck_history = []
        self._escape_ticks = 0
        self._escape_cooldown = 0
        self._avoid_front_ticks = 0
        self._find_wall_ticks = 0

    def _is_stuck(self):
        if len(self._stuck_history) < self.STUCK_WINDOW_TICKS:
            return False
        fronts = [h[0] for h in self._stuck_history]
        rights = [h[1] for h in self._stuck_history]
        if fronts[-1] >= self.STUCK_FRONT_MAX_M:
            return False
        if max(fronts) - min(fronts) >= self.STUCK_DELTA_M:
            return False
        if max(rights) - min(rights) >= self.STUCK_DELTA_M:
            return False
        return True

    def compute(self, regions):
        front = regions['front']
        right = regions['right']

        # ============================================================
        # ESCAPE STATE — pure CCW yaw, no translation. Terminal state
        # for ESCAPE_TICKS ticks, then -> find_wall + cooldown.
        # ============================================================
        if self.state == 'escape':
            self._escape_ticks += 1
            if self._escape_ticks >= self.ESCAPE_TICKS:
                self.state = 'find_wall'
                self._pre_avoid_state = 'find_wall'
                self._escape_ticks = 0
                self._escape_cooldown = self.ESCAPE_COOLDOWN_TICKS
                self._stuck_history.clear()
                self._avoid_front_ticks = 0
                self._find_wall_ticks = 0
                # fall through to emit a normal command for this tick
            else:
                return (0.0, 0.0, 0.0, self.TURN_SPEED)

        # Cooldown for escape (decremented each tick, allows next stuck-detect)
        if self._escape_cooldown > 0:
            self._escape_cooldown -= 1

        # ============================================================
        # STUCK DETECTION — only meaningful in follow_wall.
        # ============================================================
        if self.state == 'follow_wall' and self._escape_cooldown == 0:
            self._stuck_history.append((front, right))
            if len(self._stuck_history) > self.STUCK_WINDOW_TICKS:
                self._stuck_history.pop(0)
            if self._is_stuck():
                self.state = 'escape'
                self._escape_ticks = 0
                self._stuck_history.clear()
                return (0.0, 0.0, 0.0, self.TURN_SPEED)
        else:
            self._stuck_history.clear()

        # ============================================================
        # FIND_WALL STALL — too long without a wall, do an escape.
        # ============================================================
        if self.state == 'find_wall':
            self._find_wall_ticks += 1
            if (self._find_wall_ticks >= self.FIND_WALL_STALL_TICKS
                    and self._escape_cooldown == 0):
                self.state = 'escape'
                self._escape_ticks = 0
                self._find_wall_ticks = 0
                return (0.0, 0.0, 0.0, self.TURN_SPEED)
        else:
            self._find_wall_ticks = 0

        # ============================================================
        # OUTER_CORNER PHASE-1 FRONT SAFETY — abort if wall appears
        # during the long forward dash.
        # ============================================================
        if (self.state == 'outer_corner'
                and self._corner_ticks < self.CORNER_PHASE1_TICKS
                and front < self.OUTER_CORNER_FRONT_ABORT_M):
            self._pre_avoid_state = 'find_wall'
            self.state = 'avoid_front'
            self._avoid_front_ticks = 0
            self._corner_ticks = 0
            # fall through to emit avoid_front command

        # ============================================================
        # CORE FSM TRANSITIONS — rewritten to be explicit and not
        # accidentally fall through and overwrite avoid_front.
        # ============================================================
        if self.state == 'avoid_front':
            # Sticky: stay in avoid_front until front clears (1.8m hysteresis)
            # or the timeout fires. Never silently drop to find_wall.
            self._avoid_front_ticks += 1
            if front >= 1.8:
                self.state = self._pre_avoid_state
                self._avoid_cooldown = 40
                self._avoid_front_ticks = 0
            elif self._avoid_front_ticks >= self.AVOID_FRONT_MAX_TICKS:
                # Spun a full circle, still blocked — try find_wall to
                # break the loop. Next tick will re-trigger avoid_front
                # if still blocked, but at least state name changes.
                self.state = 'find_wall'
                self._pre_avoid_state = 'find_wall'
                self._avoid_cooldown = 40
                self._avoid_front_ticks = 0

        elif self.state == 'outer_corner':
            # Stay in outer_corner until 3-phase sequence completes
            self._corner_ticks += 1
            total = (self.CORNER_PHASE1_TICKS
                     + self.CORNER_PHASE2_TICKS
                     + self.CORNER_PHASE3_TICKS)
            if self._corner_ticks >= total:
                self.state = 'follow_wall'

        else:
            # state in {find_wall, follow_wall}
            # Front-wall trigger comes first (highest priority)
            if front < 2.0:
                self._pre_avoid_state = self.state
                self.state = 'avoid_front'
                self._avoid_front_ticks = 0
            elif self.state == 'follow_wall' and right > self.WALL_LOST_DIST + 0.7:
                # Right wall vanished beyond LOST+0.7 = clean outer corner
                self.state = 'outer_corner'
                self._corner_ticks = 0
            elif right > self.WALL_LOST_DIST and self._avoid_cooldown == 0:
                # Lost the right wall — switch back to find_wall
                self.state = 'find_wall'
            else:
                # Wall in range — track it
                self.state = 'follow_wall'

        if self._avoid_cooldown > 0:
            self._avoid_cooldown -= 1

        # ============================================================
        # Commands — UNCHANGED from K's tuning
        # ============================================================
        if self.state == 'avoid_front':
            return (0.0, 0.0, 0.0, -self.TURN_SPEED)

        elif self.state == 'find_wall':
            return (self.LINEAR_SPEED, self.STRAFE_SPEED * 0.5, 0.0, 0.0)

        elif self.state == 'outer_corner':
            t = self._corner_ticks
            if t < self.CORNER_PHASE1_TICKS:
                return (self.LINEAR_SPEED, 0.0, 0.0, 0.0)
            elif t < self.CORNER_PHASE1_TICKS + self.CORNER_PHASE2_TICKS:
                return (0.0, 0.0, 0.0, self.CORNER_TURN)
            else:
                return (self.LINEAR_SPEED, 0.0, 0.0, 0.0)

        else:  # follow_wall
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

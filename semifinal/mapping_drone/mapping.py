"""Mapping primitives: ArUco detection, world-frame occupancy grid, and the
camera->world transform used by the controller.

Coordinate conventions (see project CLAUDE.md):
    Camera frame: Z forward (out of lens), X right, Y down.
    World frame:  N north, E east, U up.
    Drone pose given as (n_m, e_m, down_m, yaw_deg) — down_m is PX4 NED down,
    altitude_up = -down_m.
    gimbal_pitch_deg: 0 = camera looking forward along drone +X (north when
    yaw=0), -90 = camera looking straight down.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class ArucoSighting:
    aruco_id: int
    pixel_center: tuple[int, int]
    bbox_xyxy: tuple[int, int, int, int]
    cam_xyz_m: Optional[tuple[float, float, float]]
    world_xyz_m: Optional[tuple[float, float, float]]
    confidence: float
    saved_image_path: Optional[str]
    first_seen_at: float


# ---------------------------------------------------------------------------
# ArUco detector
# ---------------------------------------------------------------------------
_ARUCO_DICTS = {
    "4X4_50": cv2.aruco.DICT_4X4_50,
    "4X4_100": cv2.aruco.DICT_4X4_100,
    "4X4_250": cv2.aruco.DICT_4X4_250,
    "5X5_250": cv2.aruco.DICT_5X5_250,
    "6X6_50": cv2.aruco.DICT_6X6_50,
    "6X6_100": cv2.aruco.DICT_6X6_100,
    "6X6_250": cv2.aruco.DICT_6X6_250,
    "6X6_1000": cv2.aruco.DICT_6X6_1000,
    "7X7_250": cv2.aruco.DICT_7X7_250,
}


class ArucoDetector:
    """Wraps cv2.aruco. Uses the new ArucoDetector API when available,
    otherwise falls back to the legacy detectMarkers signature."""

    def __init__(self, dict_name: str = "6X6_250") -> None:
        if dict_name not in _ARUCO_DICTS:
            raise ValueError(f"Unknown ArUco dict: {dict_name}")
        self.dict_name = dict_name
        aruco_dict_id = _ARUCO_DICTS[dict_name]

        if hasattr(cv2.aruco, "getPredefinedDictionary"):
            self._dictionary = cv2.aruco.getPredefinedDictionary(aruco_dict_id)
        else:  # very old OpenCV
            self._dictionary = cv2.aruco.Dictionary_get(aruco_dict_id)

        self._detector = None
        if hasattr(cv2.aruco, "ArucoDetector"):
            params = cv2.aruco.DetectorParameters()
            self._detector = cv2.aruco.ArucoDetector(self._dictionary, params)
        else:
            if hasattr(cv2.aruco, "DetectorParameters_create"):
                self._params = cv2.aruco.DetectorParameters_create()
            else:
                self._params = cv2.aruco.DetectorParameters()

    def detect_in_frame(
        self, frame
    ) -> list[tuple[int, tuple[int, int], tuple[int, int, int, int]]]:
        """Returns list of (aruco_id, pixel_center, bbox_xyxy)."""
        if frame is None or frame.color_bgr is None:
            return []
        gray = cv2.cvtColor(frame.color_bgr, cv2.COLOR_BGR2GRAY)

        if self._detector is not None:
            corners, ids, _ = self._detector.detectMarkers(gray)
        else:
            corners, ids, _ = cv2.aruco.detectMarkers(
                gray, self._dictionary, parameters=self._params
            )

        if ids is None or len(ids) == 0:
            return []

        out: list[tuple[int, tuple[int, int], tuple[int, int, int, int]]] = []
        for marker_id, corner_set in zip(ids.flatten(), corners):
            pts = corner_set.reshape(-1, 2)
            cx = int(round(float(pts[:, 0].mean())))
            cy = int(round(float(pts[:, 1].mean())))
            x1 = int(math.floor(float(pts[:, 0].min())))
            y1 = int(math.floor(float(pts[:, 1].min())))
            x2 = int(math.ceil(float(pts[:, 0].max())))
            y2 = int(math.ceil(float(pts[:, 1].max())))
            out.append((int(marker_id), (cx, cy), (x1, y1, x2, y2)))
        return out


# ---------------------------------------------------------------------------
# Camera <-> world transform
# ---------------------------------------------------------------------------
def camera_to_world(
    cam_xyz: tuple[float, float, float],
    drone_n: float,
    drone_e: float,
    drone_alt_m: float,
    drone_yaw_deg: float,
    gimbal_pitch_deg: float,
) -> tuple[float, float, float]:
    """Transform a point in camera frame (X=right, Y=down, Z=forward) into
    world frame (N=north, E=east, U=up).

    Rotation order: gimbal pitch around camera X, then yaw around world U.
    With gimbal_pitch_deg=0 the camera looks along the drone body +X axis
    (north when yaw=0); with gimbal_pitch_deg=-90 it looks straight down.

    drone_alt_m is the altitude above ground (positive up). Callers using PX4
    NED should pass -down_m here.

    Pitch rotation derivation
    -------------------------
    Treat gimbal_pitch_deg as the angle the camera +Z (lens-forward) axis is
    rotated downward from horizontal, expressed in the drone body frame
    (X forward, Y right, Z up).  Let p = radians(gimbal_pitch_deg).  The
    camera-to-body rotation that sends camera +Z to body (cos p, 0, sin p)
    and camera +Y (image-down) to body (sin p, 0, -cos p) is:

        x_b = cos(p) * z_c + sin(p) * y_c   (forward)
        y_b = x_c                            (right)
        z_b = sin(p) * z_c - cos(p) * y_c    (up)

    Sanity checks:
      * p=0, cam=(0, 1, 5)   -> x_b=5, z_b=-1  (1 m below drone, 5 m fwd)
      * p=-pi/2, cam=(0,0,2) -> x_b=0, z_b=-2  (2 m directly below drone)
      * p=-pi/2, cam=(0,1,0) -> x_b=-1, z_b=0  (image-bottom => behind drone)
    """
    x_c, y_c, z_c = cam_xyz
    pitch = math.radians(gimbal_pitch_deg)
    cp, sp = math.cos(pitch), math.sin(pitch)

    # Step 1: rotate from camera frame to a drone-body-aligned intermediate
    # frame (X_body forward, Y_body right, Z_body up).
    x_b = cp * z_c + sp * y_c
    y_b = x_c
    z_b = sp * z_c - cp * y_c

    # Step 2: yaw rotation around world up. yaw=0 means body +X aligns with N.
    # MAVSDK yaw is degrees clockwise from north when viewed from above, which
    # is the same handedness as a rotation that takes body +X to
    # (cos yaw)*N_hat + (sin yaw)*E_hat.
    yaw = math.radians(drone_yaw_deg)
    cy, sy = math.cos(yaw), math.sin(yaw)
    n_off = cy * x_b - sy * y_b
    e_off = sy * x_b + cy * y_b
    u_off = z_b

    return (drone_n + n_off, drone_e + e_off, drone_alt_m + u_off)


# ---------------------------------------------------------------------------
# Depth deprojection (mirror of realsense.deproject_pixel_to_camera_xyz, but
# kept here to avoid an import cycle — the integrator can rely on either).
# ---------------------------------------------------------------------------
def _deproject(intrinsics, u: float, v: float, depth_m: float) -> tuple[float, float, float]:
    """Local deprojection. Uses pyrealsense2 when intrinsics is the real type,
    falls back to a manual pinhole model for mock dict intrinsics."""
    if intrinsics is None or depth_m <= 0.0:
        return (0.0, 0.0, 0.0)

    # Real rs.intrinsics has 'fx', 'fy', 'ppx', 'ppy' attributes; try rs path.
    if hasattr(intrinsics, "fx") and hasattr(intrinsics, "ppx"):
        try:
            import pyrealsense2 as rs  # noqa: WPS433  (lazy on purpose)
            if isinstance(intrinsics, rs.intrinsics):
                pt = rs.rs2_deproject_pixel_to_point(
                    intrinsics, [float(u), float(v)], float(depth_m)
                )
                return (float(pt[0]), float(pt[1]), float(pt[2]))
        except Exception:
            pass
        fx = float(intrinsics.fx)
        fy = float(intrinsics.fy)
        cx = float(intrinsics.ppx)
        cy = float(intrinsics.ppy)
    elif isinstance(intrinsics, dict):
        fx = float(intrinsics["fx"])
        fy = float(intrinsics["fy"])
        cx = float(intrinsics.get("ppx", intrinsics.get("cx")))
        cy = float(intrinsics.get("ppy", intrinsics.get("cy")))
    else:
        raise TypeError(f"Unsupported intrinsics type: {type(intrinsics)!r}")

    x = (float(u) - cx) * depth_m / fx
    y = (float(v) - cy) * depth_m / fy
    z = depth_m
    return (x, y, z)


# ---------------------------------------------------------------------------
# Occupancy grid
# ---------------------------------------------------------------------------
_MIN_DEPTH_M = 0.2
_MAX_DEPTH_M = 5.0
_INTEGRATE_PIXEL_STEP = 4  # subsample depth image to keep integrate() cheap


class OccupancyGrid:
    """Top-down occupancy grid in world (N, E) space. Cell (0, 0) is the
    south-west corner; row index increases northward, column index eastward.

    Storage:
        hits: uint32 counts of depth returns per cell (height samples).
        height_sum: float32 sum of measured world-frame heights per cell, so
            mean height = height_sum / max(hits, 1).
        pads: list of (world_xyz, aruco_id, valid) for overlay rendering.
    """

    def __init__(
        self,
        resolution_m: float = 0.05,
        size_m: float = 20.0,
        origin_offset_m: tuple[float, float] = (0.0, 0.0),
    ) -> None:
        if resolution_m <= 0:
            raise ValueError("resolution_m must be positive")
        if size_m <= 0:
            raise ValueError("size_m must be positive")

        self.resolution_m = float(resolution_m)
        self.size_m = float(size_m)
        self.origin_offset_m = (float(origin_offset_m[0]), float(origin_offset_m[1]))

        self.cells = int(round(self.size_m / self.resolution_m))
        # World extents (centred on origin_offset): N from offset_n - size/2 to + size/2
        half = self.size_m / 2.0
        self._n_min = self.origin_offset_m[0] - half
        self._n_max = self.origin_offset_m[0] + half
        self._e_min = self.origin_offset_m[1] - half
        self._e_max = self.origin_offset_m[1] + half

        self.hits = np.zeros((self.cells, self.cells), dtype=np.uint32)
        self.height_sum = np.zeros((self.cells, self.cells), dtype=np.float32)
        self.pads: list[tuple[tuple[float, float, float], int, bool]] = []

    # -- public API --------------------------------------------------------
    def integrate(
        self,
        frame,
        drone_pose: tuple[float, float, float, float],
        gimbal_pitch_deg: float,
    ) -> None:
        """Accumulate depth points from a Realsense frame into the grid.

        drone_pose = (n_m, e_m, down_m, yaw_deg) where down_m follows the PX4
        NED convention (positive downward, so airborne is negative).  We
        immediately convert to altitude-above-origin (positive up) and use
        the same world-frame contract as :func:`camera_to_world`.
        """
        if frame is None or frame.depth_mm is None or frame.intrinsics is None:
            return

        n_m, e_m, down_m, yaw_deg = drone_pose
        # Convert PX4 NED down (positive down) -> altitude (positive up) so
        # that the rest of the integrator matches camera_to_world's contract
        # (drone_alt_m = altitude above the world-frame origin, positive up).
        alt_m = -float(down_m)

        depth_mm = frame.depth_mm
        if depth_mm.ndim != 2:
            return
        h, w = depth_mm.shape
        step = _INTEGRATE_PIXEL_STEP

        # Vectorised pixel grid (subsampled).
        vs = np.arange(0, h, step, dtype=np.int32)
        us = np.arange(0, w, step, dtype=np.int32)
        vv, uu = np.meshgrid(vs, us, indexing="ij")
        depth_patch = depth_mm[vv, uu].astype(np.float32) / 1000.0  # mm -> m

        mask = (depth_patch >= _MIN_DEPTH_M) & (depth_patch <= _MAX_DEPTH_M)
        if not mask.any():
            return

        # Pinhole deproject in camera frame. Build fx/fy/cx/cy from intrinsics.
        try:
            fx, fy, cx, cy = self._unpack_intrinsics(frame.intrinsics)
        except Exception as exc:
            logger.debug("integrate: unable to read intrinsics (%s)", exc)
            return

        uu_f = uu.astype(np.float32)
        vv_f = vv.astype(np.float32)
        z_c = depth_patch
        x_c = (uu_f - cx) * z_c / fx
        y_c = (vv_f - cy) * z_c / fy

        # Apply gimbal pitch (around camera X) then drone yaw (around world U).
        # This must match camera_to_world() exactly — see that function's
        # docstring for the derivation and sanity-check matrix.
        pitch = math.radians(gimbal_pitch_deg)
        cp, sp = math.cos(pitch), math.sin(pitch)
        x_b = cp * z_c + sp * y_c
        y_b = x_c
        z_b = sp * z_c - cp * y_c

        yaw = math.radians(yaw_deg)
        cy_w, sy_w = math.cos(yaw), math.sin(yaw)
        n_world = n_m + cy_w * x_b - sy_w * y_b
        e_world = e_m + sy_w * x_b + cy_w * y_b
        u_world = alt_m + z_b

        # Filter to grid extents.
        inside = (
            mask
            & (n_world >= self._n_min)
            & (n_world < self._n_max)
            & (e_world >= self._e_min)
            & (e_world < self._e_max)
        )
        if not inside.any():
            return

        n_sel = n_world[inside]
        e_sel = e_world[inside]
        u_sel = u_world[inside]

        rows = np.clip(
            ((n_sel - self._n_min) / self.resolution_m).astype(np.int32),
            0,
            self.cells - 1,
        )
        cols = np.clip(
            ((e_sel - self._e_min) / self.resolution_m).astype(np.int32),
            0,
            self.cells - 1,
        )

        # Accumulate. np.add.at handles duplicate indices.
        np.add.at(self.hits, (rows, cols), 1)
        np.add.at(self.height_sum, (rows, cols), u_sel.astype(np.float32))

    def mark_landing_pad(
        self,
        world_xyz_m: tuple[float, float, float],
        aruco_id: int,
        valid: bool,
    ) -> None:
        self.pads.append((tuple(float(v) for v in world_xyz_m), int(aruco_id), bool(valid)))

    def render(self) -> np.ndarray:
        """Return RGB-ish (BGR for cv2) visualisation. Higher hit count = brighter.
        Landing pads overlaid as filled circles (green=valid, red=invalid)."""
        img = np.zeros((self.cells, self.cells, 3), dtype=np.uint8)
        if self.hits.max() > 0:
            norm = np.clip(self.hits.astype(np.float32) / max(1.0, self.hits.max()), 0, 1)
            gray = (norm * 255.0).astype(np.uint8)
            img[..., 0] = gray
            img[..., 1] = gray
            img[..., 2] = gray

        # Flip rows so north is up in the image.
        img = np.flipud(img).copy()

        for (n, e, _u), aid, valid in self.pads:
            col = int(round((e - self._e_min) / self.resolution_m))
            row_world = int(round((n - self._n_min) / self.resolution_m))
            row_img = (self.cells - 1) - row_world
            if 0 <= row_img < self.cells and 0 <= col < self.cells:
                colour = (0, 200, 0) if valid else (0, 0, 220)
                cv2.circle(img, (col, row_img), 6, colour, thickness=-1)
                cv2.circle(img, (col, row_img), 7, (255, 255, 255), thickness=1)
                cv2.putText(
                    img,
                    str(aid),
                    (col + 8, row_img - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )
        return img

    def save_png(self, path: str) -> None:
        img = self.render()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), img)

    def save_npy(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        np.save(str(path), self.hits)

    def landing_pads_as_dicts(self) -> list[dict]:
        return [
            {
                "aruco_id": aid,
                "world_xyz_m": list(world),
                "valid": valid,
            }
            for world, aid, valid in self.pads
        ]

    # -- internals ---------------------------------------------------------
    @staticmethod
    def _unpack_intrinsics(intrinsics) -> tuple[float, float, float, float]:
        if hasattr(intrinsics, "fx") and hasattr(intrinsics, "ppx"):
            return (
                float(intrinsics.fx),
                float(intrinsics.fy),
                float(intrinsics.ppx),
                float(intrinsics.ppy),
            )
        if isinstance(intrinsics, dict):
            cx = float(intrinsics.get("ppx", intrinsics.get("cx")))
            cy = float(intrinsics.get("ppy", intrinsics.get("cy")))
            return (float(intrinsics["fx"]), float(intrinsics["fy"]), cx, cy)
        raise TypeError(f"Unsupported intrinsics type: {type(intrinsics)!r}")

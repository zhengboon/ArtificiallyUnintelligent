"""Realsense adapters for the mapping drone.

Provides a real pyrealsense2 implementation plus a mock that synthesises
frames with a real DICT_6X6_250 ArUco marker drawn into the colour image,
so end-to-end tests can run without a camera attached.
"""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Protocol

import cv2
import numpy as np

log = logging.getLogger(__name__)

# pyrealsense2 is optional: only the real node needs it. Importing lazily
# here means MockRealsenseNode (and importers that only touch the mock)
# work on a laptop without librealsense installed.
try:
    import pyrealsense2 as rs  # type: ignore
    _RS_AVAILABLE = True
except Exception as _exc:  # pragma: no cover - exercised only when pyrealsense2 missing
    rs = None  # type: ignore[assignment]
    _RS_AVAILABLE = False
    log.debug("pyrealsense2 not importable: %s", _exc)


@dataclass
class RealsenseFrame:
    color_bgr: np.ndarray
    depth_mm: np.ndarray
    intrinsics: object
    timestamp: float
    width: int
    height: int


class RealsenseAdapter(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def grab(self) -> RealsenseFrame | None: ...
    @property
    def color_intrinsics(self) -> object: ...


# --------------------------------------------------------------------------- #
# Real node
# --------------------------------------------------------------------------- #
class RealsenseNode:
    """Real Intel Realsense (D430/D435/D450) source.

    Streams depth + color, preferring 640x480 @ 30 Hz but falling back
    through a list of candidate profiles if the device/USB combo cannot
    negotiate the preferred one. Aligns depth to color so pixel (u,v) in
    the colour image indexes the same world point in the depth image.
    """

    # (width, height, fps) — tried in order. First entry is the legacy default.
    PROFILE_CANDIDATES: tuple[tuple[int, int, int], ...] = (
        (640, 480, 30),
        (848, 480, 30),
        (1280, 720, 30),
        (640, 480, 15),
    )

    # Back-compat: code that reads .WIDTH/.HEIGHT/.FPS before start() sees
    # the preferred profile; after start() these are overwritten with the
    # profile that actually negotiated.
    WIDTH = PROFILE_CANDIDATES[0][0]
    HEIGHT = PROFILE_CANDIDATES[0][1]
    FPS = PROFILE_CANDIDATES[0][2]

    def __init__(self) -> None:
        if not _RS_AVAILABLE:
            raise RuntimeError(
                "pyrealsense2 is not installed; use MockRealsenseNode for "
                "laptop testing or install librealsense on the drone."
            )
        self._pipeline = rs.pipeline()
        self._align = rs.align(rs.stream.color)
        self._profile: object | None = None
        self._intrinsics: object | None = None
        self._started = False
        self.profile_used: tuple[int, int, int] | None = None

    def _build_config(self, width: int, height: int, fps: int) -> "rs.config":
        cfg = rs.config()
        cfg.enable_stream(rs.stream.depth, width, height, rs.format.z16, fps)
        cfg.enable_stream(rs.stream.color, width, height, rs.format.bgr8, fps)
        return cfg

    def start(self) -> None:
        if self._started:
            return
        errors: list[str] = []
        for width, height, fps in self.PROFILE_CANDIDATES:
            cfg = self._build_config(width, height, fps)
            try:
                self._profile = self._pipeline.start(cfg)
            except Exception as exc:
                errors.append(f"{width}x{height}@{fps}: {exc}")
                log.warning(
                    "Realsense profile %dx%d @ %d Hz failed: %s",
                    width, height, fps, exc,
                )
                continue
            color_stream = self._profile.get_stream(rs.stream.color)
            self._intrinsics = color_stream.as_video_stream_profile().get_intrinsics()
            self.WIDTH = width
            self.HEIGHT = height
            self.FPS = fps
            self.profile_used = (width, height, fps)
            self._started = True
            log.info(
                "Realsense started: %dx%d @ %d Hz, fx=%.2f cx=%.2f",
                width, height, fps,
                self._intrinsics.fx, self._intrinsics.ppx,
            )
            return
        tried = ", ".join(f"{w}x{h}@{f}" for w, h, f in self.PROFILE_CANDIDATES)
        raise RuntimeError(
            f"Realsense pipeline.start() failed for all candidate profiles "
            f"[{tried}]. Errors: {'; '.join(errors)}"
        )

    def stop(self) -> None:
        if not self._started:
            return
        try:
            self._pipeline.stop()
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("Realsense stop failed: %s", exc)
        finally:
            self._started = False

    def grab(self) -> RealsenseFrame | None:
        if not self._started:
            return None
        try:
            frames = self._pipeline.wait_for_frames(timeout_ms=1000)
        except Exception as exc:
            log.warning("Realsense wait_for_frames failed: %s", exc)
            return None
        aligned = self._align.process(frames)
        color_frame = aligned.get_color_frame()
        depth_frame = aligned.get_depth_frame()
        if not color_frame or not depth_frame:
            return None
        color = np.asanyarray(color_frame.get_data())
        depth = np.asanyarray(depth_frame.get_data())
        return RealsenseFrame(
            color_bgr=color,
            depth_mm=depth.astype(np.uint16, copy=False),
            intrinsics=self._intrinsics,
            timestamp=time.monotonic(),
            width=self.WIDTH,
            height=self.HEIGHT,
        )

    @property
    def color_intrinsics(self) -> object:
        return self._intrinsics


# --------------------------------------------------------------------------- #
# Mock node
# --------------------------------------------------------------------------- #
class MockRealsenseNode:
    """Synthetic Realsense source that draws a real DICT_6X6_250 marker.

    Useful for end-to-end testing the YOLO/ArUco pipeline without a camera.
    Intrinsics are a SimpleNamespace mirroring rs.intrinsics field names
    (fx, fy, ppx, ppy, width, height, model, coeffs).
    """

    WIDTH = 640
    HEIGHT = 480
    MARKER_PX = 80
    DEFAULT_DEPTH_MM = 1500

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        # seeded numpy Generator so depth-hole locations are reproducible too
        self._np_rng = np.random.default_rng(seed)
        self._intrinsics = SimpleNamespace(
            fx=608.12,
            fy=608.12,
            ppx=323.71,
            ppy=240.42,
            width=self.WIDTH,
            height=self.HEIGHT,
            model="brown_conrady",
            coeffs=[0.0, 0.0, 0.0, 0.0, 0.0],
        )
        self._aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
        self._started = False

    def start(self) -> None:
        self._started = True
        log.info("MockRealsense started: %dx%d synthetic stream", self.WIDTH, self.HEIGHT)

    def stop(self) -> None:
        self._started = False

    def grab(self) -> RealsenseFrame | None:
        if not self._started:
            return None

        color = np.full((self.HEIGHT, self.WIDTH, 3), 80, dtype=np.uint8)
        # mild texture so depth-aware code sees something interesting
        noise = self._rng.randint(0, 30)
        color[..., 1] = np.clip(color[..., 1].astype(int) + noise, 0, 255).astype(np.uint8)

        marker_id = self._rng.randint(0, 249)
        marker_img = self._generate_marker(marker_id, self.MARKER_PX)
        max_x = self.WIDTH - self.MARKER_PX - 1
        max_y = self.HEIGHT - self.MARKER_PX - 1
        x0 = self._rng.randint(0, max_x)
        y0 = self._rng.randint(0, max_y)
        color[y0:y0 + self.MARKER_PX, x0:x0 + self.MARKER_PX] = cv2.cvtColor(
            marker_img, cv2.COLOR_GRAY2BGR
        )

        depth = np.full((self.HEIGHT, self.WIDTH), self.DEFAULT_DEPTH_MM, dtype=np.uint16)
        # sprinkle some zero (invalid-depth) pixels
        num_holes = self._rng.randint(20, 60)
        ys = self._np_rng.integers(0, self.HEIGHT, size=num_holes)
        xs = self._np_rng.integers(0, self.WIDTH, size=num_holes)
        depth[ys, xs] = 0

        return RealsenseFrame(
            color_bgr=color,
            depth_mm=depth,
            intrinsics=self._intrinsics,
            timestamp=time.monotonic(),
            width=self.WIDTH,
            height=self.HEIGHT,
        )

    @property
    def color_intrinsics(self) -> object:
        return self._intrinsics

    def _generate_marker(self, marker_id: int, side_px: int) -> np.ndarray:
        # opencv-contrib >=4.7 uses generateImageMarker; older uses drawMarker.
        if hasattr(cv2.aruco, "generateImageMarker"):
            return cv2.aruco.generateImageMarker(self._aruco_dict, marker_id, side_px)
        return cv2.aruco.drawMarker(self._aruco_dict, marker_id, side_px)


# --------------------------------------------------------------------------- #
# Deprojection helper
# --------------------------------------------------------------------------- #
def deproject_pixel_to_camera_xyz(
    intrinsics: object, u: int, v: int, depth_m: float
) -> tuple[float, float, float]:
    """Pixel + depth -> camera-frame (X, Y, Z) in metres.

    Uses rs.rs2_deproject_pixel_to_point when intrinsics is a real
    rs.intrinsics (so distortion coefficients are respected). Falls back
    to a pinhole projection for the mock SimpleNamespace intrinsics.
    """
    if _RS_AVAILABLE and isinstance(intrinsics, rs.intrinsics):
        x, y, z = rs.rs2_deproject_pixel_to_point(intrinsics, [float(u), float(v)], float(depth_m))
        return float(x), float(y), float(z)

    fx = getattr(intrinsics, "fx")
    fy = getattr(intrinsics, "fy")
    cx = getattr(intrinsics, "ppx")
    cy = getattr(intrinsics, "ppy")
    z = float(depth_m)
    x = (float(u) - float(cx)) * z / float(fx)
    y = (float(v) - float(cy)) * z / float(fy)
    return x, y, z

"""Realsense adapters for the mapping drone.

Provides a real pyrealsense2 implementation plus a mock that synthesises
frames with a real DICT_7X7_1000 ArUco marker (the org's finals dictionary)
drawn into the colour image, so end-to-end tests run without a camera.

Camera fleet (org confirmed 2026-06-10, see semifinal/D430_RGB_RISK.md):
    The shared fleet is a MIX of D435 (HAS an RGB sensor — colour path works
    unmodified) and D450 (depth-only stereo IR + projector, NO RGB sensor).
    There is NO D430. On a D450, the default colour profile makes
    pipeline.start() raise for every candidate, so RealsenseNode supports an
    IR fallback: construct with use_ir_for_aruco=True (wired to the
    --use-ir-for-aruco CLI flag). When True:
      * _build_config() enables rs.stream.infrared index 1 (Y8) instead of
        rs.stream.color.
      * start() aligns to rs.stream.infrared and grabs the depth sensor so
        the emitter can be toggled.
      * grab() turns the IR projector OFF (its dot pattern would corrupt
        ArUco), pulls infrared_frame(1) + depth, and synthesises a 3-channel
        BGR from the IR grayscale so ArucoDetector and the rest of the
        pipeline keep working with NO change to mapping.py.
    The mock path is unaffected — only the real RealsenseNode learns IR mode.
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

    def __init__(self, use_ir_for_aruco: bool = False) -> None:
        if not _RS_AVAILABLE:
            raise RuntimeError(
                "pyrealsense2 is not installed; use MockRealsenseNode for "
                "laptop testing or install librealsense on the drone."
            )
        # IR fallback for D450 (no-RGB) cameras: align depth to the IR stream
        # and synthesise BGR from IR so ArUco/mapping are unchanged.
        self._use_ir = bool(use_ir_for_aruco)
        self._pipeline = rs.pipeline()
        # IR mode: do NOT align — left IR (index 1) is the depth reference
        # imager, already co-registered with depth at the same resolution.
        # align(infrared) returns a null IR frame, which broke the D450 path.
        self._align = None if self._use_ir else rs.align(rs.stream.color)
        self._profile: object | None = None
        self._intrinsics: object | None = None
        self._depth_sensor: object | None = None
        self._grab_count = 0
        self._started = False
        self.profile_used: tuple[int, int, int] | None = None

    def _verify_color_frames(self) -> bool:
        """A D450 (no RGB) can 'start' a colour profile but never deliver a
        colour frame. Confirm one actually arrives so start() can fall to IR."""
        try:
            for _ in range(3):
                frames = self._pipeline.wait_for_frames(timeout_ms=1500)
                if frames.get_color_frame():
                    return True
        except Exception:
            return False
        return False

    def _reassert_emitter_off(self) -> None:
        """Keep the IR projector off (its dot pattern corrupts ArUco). Some
        firmware re-enables it; re-assert periodically (cheap, throttled)."""
        self._grab_count += 1
        if self._depth_sensor is None or (self._grab_count % 30) != 1:
            return
        try:
            if self._depth_sensor.supports(rs.option.emitter_enabled):
                self._depth_sensor.set_option(rs.option.emitter_enabled, 0.0)
        except Exception:
            pass

    def _build_config(self, width: int, height: int, fps: int) -> "rs.config":
        cfg = rs.config()
        cfg.enable_stream(rs.stream.depth, width, height, rs.format.z16, fps)
        if self._use_ir:
            # D450 has no RGB: use left IR (index 1), Y8 grayscale.
            cfg.enable_stream(rs.stream.infrared, 1, width, height, rs.format.y8, fps)
        else:
            cfg.enable_stream(rs.stream.color, width, height, rs.format.bgr8, fps)
        return cfg

    def start(self) -> None:
        if self._started:
            return
        # REDUNDANT camera paths: try the requested mode (color unless
        # --use-ir-for-aruco), and if EVERY profile fails, AUTO-fall back to IR
        # — so the same code works on a D435 (RGB) and a D450 (no RGB) with no
        # operator flag. If IR was already requested, we only try IR.
        modes = [self._use_ir] if self._use_ir else [False, True]
        all_errors: list[str] = []
        for ir_mode in modes:
            self._use_ir = ir_mode
            # IR mode is NOT aligned (raw IR+depth are already co-registered).
            self._align = None if ir_mode else rs.align(rs.stream.color)
            label = "IR/no-RGB" if ir_mode else "color"
            for width, height, fps in self.PROFILE_CANDIDATES:
                cfg = self._build_config(width, height, fps)
                try:
                    self._profile = self._pipeline.start(cfg)
                except Exception as exc:
                    all_errors.append(f"{label} {width}x{height}@{fps}: {exc}")
                    continue
                if ir_mode:
                    ir_stream = self._profile.get_stream(rs.stream.infrared, 1)
                    self._intrinsics = ir_stream.as_video_stream_profile().get_intrinsics()
                    # Turn the IR projector OFF (dot pattern corrupts ArUco).
                    try:
                        self._depth_sensor = self._profile.get_device().first_depth_sensor()
                        if self._depth_sensor.supports(rs.option.emitter_enabled):
                            self._depth_sensor.set_option(rs.option.emitter_enabled, 0.0)
                    except Exception as exc:  # pragma: no cover - hardware-specific
                        log.warning("could not disable IR emitter: %s", exc)
                else:
                    color_stream = self._profile.get_stream(rs.stream.color)
                    self._intrinsics = color_stream.as_video_stream_profile().get_intrinsics()
                    # D450 can start colour but never deliver frames -> fall to IR.
                    if not self._verify_color_frames():
                        all_errors.append(f"{label} {width}x{height}@{fps}: started but no colour frames")
                        try:
                            self._pipeline.stop()
                        except Exception:
                            pass
                        continue
                self.WIDTH, self.HEIGHT, self.FPS = width, height, fps
                self.profile_used = (width, height, fps)
                self._started = True
                log.info(
                    "Realsense started: %dx%d @ %d Hz, fx=%.2f cx=%.2f (%s)",
                    width, height, fps, self._intrinsics.fx, self._intrinsics.ppx, label,
                )
                return
            if not ir_mode and len(modes) > 1:
                log.warning("all COLOR profiles failed — AUTO-falling back to IR (no-RGB camera?)")
        raise RuntimeError(
            "Realsense pipeline.start() failed for all profiles in all modes. "
            f"Errors: {'; '.join(all_errors)}"
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
            # 2s timeout — the very first frame after start() can take >1s
            # as autoexposure + alignment settle.
            frames = self._pipeline.wait_for_frames(timeout_ms=2000)
        except Exception as exc:
            log.warning("Realsense wait_for_frames failed: %s", exc)
            return None
        if self._use_ir:
            # Raw frameset (no align): left IR + depth are co-registered.
            depth_frame = frames.get_depth_frame()
            ir_frame = frames.get_infrared_frame(1)
            if not ir_frame or not depth_frame:
                return None
            self._reassert_emitter_off()
            ir = np.asanyarray(ir_frame.get_data())          # Y8 grayscale
            color = cv2.cvtColor(ir, cv2.COLOR_GRAY2BGR)     # synth 3-channel BGR
        else:
            aligned = self._align.process(frames)
            depth_frame = aligned.get_depth_frame()
            color_frame = aligned.get_color_frame()
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
    """Synthetic Realsense source that draws a real DICT_7X7_1000 marker
    cycling through the org's finals IDs (11/45/51/67/101).

    Useful for end-to-end testing the ArUco pipeline without a camera.
    Intrinsics are a SimpleNamespace mirroring rs.intrinsics field names
    (fx, fy, ppx, ppy, width, height, model, coeffs).
    """

    WIDTH = 640
    HEIGHT = 480
    MARKER_PX = 80
    DEFAULT_DEPTH_MM = 1500
    FINALS_IDS = (11, 45, 51, 67, 101)

    def __init__(self, seed: int | None = None, dict_name: str = "7X7_1000") -> None:
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
        _dict_id = getattr(cv2.aruco, f"DICT_{dict_name}", cv2.aruco.DICT_7X7_1000)
        self._aruco_dict = cv2.aruco.getPredefinedDictionary(_dict_id)
        self._seq = 0
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

        # cycle the real finals IDs so e2e tests exercise the actual markers
        marker_id = self.FINALS_IDS[self._seq % len(self.FINALS_IDS)]
        self._seq += 1
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

"""BrainHack 2026 RoboVerse - Final Challenge mapping drone package.

Canonical mapping-drone controller for Challenge 1 (Reconnaissance):
survey the arena, build a top-down depth map, and report per-landing-pad
ArUco marker IDs with validity classification.

Public re-exports below let callers do e.g.

    from mapping_drone import ArucoSighting, RunWriter
    from mapping_drone import MockUwbNode, MockRealsenseNode

without reaching into submodules. The full controller entry points
(``main`` / ``run``) are also re-exported so the package can be invoked
as ``python -m mapping_drone`` (which dispatches to ``__main__.py``).
"""

from __future__ import annotations

from .uwb import UwbAdapter, UwbNode, MockUwbNode
from .realsense import (
    RealsenseAdapter,
    RealsenseFrame,
    RealsenseNode,
    MockRealsenseNode,
    deproject_pixel_to_camera_xyz,
)
from .mapping import ArucoSighting, ArucoDetector, OccupancyGrid, camera_to_world
from .validity import decide_landing_validity, describe_rule
from .run_writer import RunWriter
# Primary entry point is the org-aligned MAVSDK mission. controller.py is
# LEGACY (retired as an entry point) — do not re-export it here.
from .moveit_mission import main

__all__ = [
    # uwb
    "UwbAdapter",
    "UwbNode",
    "MockUwbNode",
    # realsense
    "RealsenseAdapter",
    "RealsenseFrame",
    "RealsenseNode",
    "MockRealsenseNode",
    "deproject_pixel_to_camera_xyz",
    # mapping
    "ArucoSighting",
    "ArucoDetector",
    "OccupancyGrid",
    "camera_to_world",
    # validity
    "decide_landing_validity",
    "describe_rule",
    # run writer
    "RunWriter",
    # entry point (moveit_mission)
    "main",
]



"""Entry point so ``python -m mapping_drone`` runs the org-aligned mission.

Repointed 2026-06-10: the org's official sample (move_it4.py) flies via MAVSDK on
ttyS6, so ``moveit_mission`` is the primary. Legacy ``controller.py`` is retired as an
entry point. For the PX4-ROS2/XRCE-only fallback, run ``python -m mapping_drone.px4_mission``.
"""

from .moveit_mission import main

raise SystemExit(main())

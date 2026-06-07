"""Placeholder for K's Hula swarm controller. NOT YET BUILT.

This module is a stub so import-paths and CI/smoke harnesses that reference
``semifinal.swarm_controller`` resolve cleanly while the real implementation
is still being written by K. Replace ``main`` with the live Hula swarm
controller once it lands. Until then ``python swarm_controller.py`` exits
with status 1 so any orchestration script fails loudly rather than silently
no-op'ing.
"""

from __future__ import annotations

import sys


def main() -> int:
    """Stub entry point — prints a NOT YET BUILT banner and returns 1."""
    print("swarm_controller: NOT YET BUILT - placeholder for K's implementation. Exiting 1.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

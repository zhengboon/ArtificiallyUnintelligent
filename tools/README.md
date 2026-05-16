# tools/

One-off scripts that were useful at a specific moment and are kept here in case
we need them again. Not part of the normal run flow — `searchctl/controller.py`
does the actual work.

## Scripts

### `patch_drone_control.py`
- **Created:** 2026-05-13
- **Used by:** Z
- **What it does:** Surgically replaces the body of `arm_and_takeoff()` in `~/Desktop/codes/drone_control.py` (the workshop's reference) to add a `is_armable` wait before `arm()`. Keeps all the other methods (`rotate_to_yaw`, `send_velocity`, etc.) that the workshop's `*_new.py` version is missing.
- **Why it exists:** the OP's `drone_control_new.py` is incomplete (missing `rotate_to_yaw`); naively swapping it crashes `avoid.py`. This patch is the safer alternative.
- **Usage:** `python3 patch_drone_control.py` (inside the VM)

### `diag_arm.py`
- **Created:** 2026-05-13
- **Used by:** Z
- **What it does:** Connects to PX4 SITL via MAVSDK, prints all health flags, attempts to arm, listens for STATUS_TEXT messages. Useful when arming silently fails — surfaces the exact PX4 reason ("Battery unhealthy", "horizontal position unstable", etc.).
- **Usage:** `export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python && python3 diag_arm.py` (inside the VM)

## When to use these

Drop them onto the VM via `vmrun copyFileFromHostToGuest` when you need:
- A reset / re-patch of workshop's `drone_control.py` after an OP update
- A minimal probe to figure out why arming is being denied

Both scripts are self-contained — no dependencies beyond what the v3 VM already has.

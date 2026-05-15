"""
Patch the original drone_control.py to add a health-wait BEFORE arm.
This keeps all the existing methods (rotate_to_yaw etc.) intact and
only changes arm_and_takeoff to actually wait for is_armable=True before
trying to arm.
"""
import re
import sys

path = "/home/drone/Desktop/codes/drone_control.py"
src = open(path).read()

# Match the existing arm_and_takeoff body and replace it.
old = re.search(
    r"(    async def arm_and_takeoff\(self\):\n)(.*?)(\n    async def land)",
    src, re.DOTALL
)
if not old:
    print("ERROR: could not locate arm_and_takeoff in", path)
    sys.exit(1)

new_body = """    async def arm_and_takeoff(self):
        # Wait until PX4 reports the drone is armable (vision-drone safe wait).
        import asyncio as _aio
        for _ in range(120):  # max ~30 sec @ 4Hz
            async for h in self.drone.telemetry.health():
                if getattr(h, "is_armable", False):
                    break
                if h.is_home_position_ok and h.is_local_position_ok:
                    break
                await _aio.sleep(0.25)
                break  # re-poll
            else:
                continue
            break
        await self.drone.action.arm()
        await self.drone.action.takeoff()
        await _aio.sleep(20)
        print("Takeoff")
        # Required before offboard.start()
        await self.drone.offboard.set_velocity_ned(VelocityNedYaw(0.0, 0.0, 0.0, 0.0))
        await self.drone.offboard.start()
"""

src_new = src[:old.start()] + new_body + "\n" + src[old.end()-len(old.group(3)):]
open(path, "w").write(src_new)
print("patched")

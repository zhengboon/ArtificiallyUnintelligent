#!/usr/bin/env bash
# ============================================================================
# DRONE READINESS FINGERPRINT
# Run the MOMENT a drone is swapped in, BEFORE launching anything.
# Answers: "is a package/setup missing on this drone?"  (deterministic)
#   vs    "is data not flowing?"  (interference — re-check after launch)
# Does NOT arm, takeoff, or fly. Read-only. Safe on the no-fly drone.
#
#   bash tools/drone_fingerprint.sh
# ============================================================================
set +e
export ROS_LOCALHOST_ONLY=1          # isolate our DDS from other teams immediately

ok(){ echo "  ok      $*"; }
miss(){ echo "  MISSING $*"; }

echo "==================== DRONE FINGERPRINT ===================="
echo "host=$(hostname)  user=$(whoami)  date=$(date '+%F %T')"
echo "ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}  ROS_LOCALHOST_ONLY=${ROS_LOCALHOST_ONLY}  RMW=${RMW_IMPLEMENTATION:-default}"

echo; echo "---- 1. REPO PATH (case varies per drone!) ----"
FOUND_REPO=""
for p in ~/AD/semifinal ~/ad/semifinal ~/roboverse26/semifinal ~/AD ~/ad; do
  if [ -d "$p" ]; then echo "  FOUND: $p"; [ -z "$FOUND_REPO" ] && FOUND_REPO="$p"; fi
done
[ -z "$FOUND_REPO" ] && echo "  (no known repo path found — run 'ls ~')"

echo; echo "---- 2. ROS2 WORKSPACE + PACKAGES ----"
source /opt/ros/humble/setup.bash 2>/dev/null
if source ~/ros2_ws/install/setup.bash 2>/dev/null; then ok "sourced ~/ros2_ws"; else miss "~/ros2_ws/install (colcon build needed)"; fi
[ -n "$(command -v ros2)" ] && ok "ros2 CLI" || miss "ros2 CLI"
ros2 pkg prefix px4_msgs    >/dev/null 2>&1 && ok "px4_msgs (needed for /fmu/* path)"     || miss "px4_msgs"
ros2 pkg prefix nlink_parser>/dev/null 2>&1 && ok "nlink_parser (UWB)"                     || miss "nlink_parser"

echo; echo "---- 3. PYTHON DEPS ----"
for m in mavsdk pyrealsense2 rclpy cv2 numpy; do
  python3 -c "import $m" 2>/dev/null && ok "$m" || miss "$m"
done

echo; echo "---- 4. SERIAL PORTS ----"
# ttyS1=XRCE/FC  ttyS4=UWB(nlink)  ttyS6=MAVSDK
for d in /dev/ttyS1 /dev/ttyS4 /dev/ttyS6; do
  [ -e "$d" ] && ok "$d ($(stat -c '%a' "$d" 2>/dev/null) $(stat -c '%U' "$d" 2>/dev/null))" || miss "$d"
done

echo; echo "---- 5. CAMERA (model + RGB?) ----"
python3 - <<'PY' 2>&1 | sed 's/^/  /'
try:
    import pyrealsense2 as rs
    devs=list(rs.context().devices)
    if not devs: print("NO RealSense device connected (USB?)")
    for d in devs:
        name=d.get_info(rs.camera_info.name)
        try: usb=d.get_info(rs.camera_info.usb_type_descriptor)
        except Exception: usb="?"
        sensors=[s.get_info(rs.camera_info.name) for s in d.query_sensors()]
        rgb=any(("RGB" in s) or ("Color" in s) for s in sensors)
        flag="" if usb.startswith("3") else "  <-- NOT USB3, bandwidth risk"
        print(f"{name} | USB {usb} | RGB={'YES' if rgb else 'NO (D450?)'}{flag}")
except ModuleNotFoundError:
    print("pyrealsense2 MISSING")
except Exception as e:
    print("camera check error:", e)
PY

echo; echo "---- 6. FC over MAVSDK (read-only, no arm; up to 25s) ----"
timeout 25 python3 - <<'PY' 2>&1 | sed 's/^/  /'
import asyncio
from mavsdk import System
async def main():
    d=System()
    await d.connect(system_address="serial:///dev/ttyS6:921600")
    conn=False
    async for s in d.core.connection_state():
        if s.is_connected: conn=True; print("MAVSDK CONNECTED on ttyS6"); break
    if not conn: return
    async for h in d.telemetry.health():
        print(f"local_position_ok={h.is_local_position_ok} armable={h.is_armable} "
              f"gyro_cal={h.is_gyrometer_calibration_ok} home_ok={h.is_home_position_ok}")
        break
asyncio.run(main())
PY
echo "  (no 'MAVSDK CONNECTED' line above = FC not reachable on ttyS6)"

echo; echo "==================== INTERPRET ===================="
echo "  Any 'MISSING' in 2/3 = setup problem on THIS drone (build/install), NOT interference."
echo "  All present but no DATA later = interference -> confirm ROS_LOCALHOST_ONLY=1 is set"
echo "  in EVERY terminal + the start scripts, then re-run the data-flow check below."
echo
echo "  DATA-FLOW check (run AFTER 'start_micro' + 'start_uwb' in their own terminals):"
echo "    export ROS_LOCALHOST_ONLY=1; source ~/ros2_ws/install/setup.bash"
echo "    # PRIMARY pose is FC fused NED (--pose auto/fc). Check IT first:"
echo "    timeout 10 ros2 topic echo /fmu/out/vehicle_local_position --qos-reliability best_effort | grep -m1 xy_valid"
echo "    # If FC fused NED streams, the drone is FLYABLE on --pose auto/fc EVEN if /uwb_tag is empty."
echo "    # /uwb_tag is the FALLBACK pose source (arena frame) — check it second:"
echo "    timeout 10 ros2 topic echo /uwb_tag --qos-reliability best_effort   # streaming?"
echo "    ros2 topic info -v /uwb_tag                                         # publisher count"
echo "=========================================================="

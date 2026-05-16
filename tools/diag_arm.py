import asyncio
from mavsdk import System

async def main():
    drone = System()
    await drone.connect(system_address='udpin://0.0.0.0:14540')
    async for s in drone.core.connection_state():
        if s.is_connected:
            break
    print('connected')

    async for h in drone.telemetry.health():
        print('Health flags:')
        print('  is_armable                 =', getattr(h, 'is_armable', None))
        print('  is_global_position_ok      =', h.is_global_position_ok)
        print('  is_home_position_ok        =', h.is_home_position_ok)
        print('  is_local_position_ok       =', h.is_local_position_ok)
        print('  is_gyrometer_calibration   =', h.is_gyrometer_calibration_ok)
        print('  is_accelerometer_calib_ok  =', h.is_accelerometer_calibration_ok)
        print('  is_magnetometer_calib_ok   =', h.is_magnetometer_calibration_ok)
        break

    async def listen():
        async for st in drone.telemetry.status_text():
            print('STATUS [%s] %s' % (st.type, st.text))
    listen_task = asyncio.create_task(listen())
    await asyncio.sleep(0.5)

    try:
        print('-- attempting arm()')
        await drone.action.arm()
        print('   armed!')
    except Exception as e:
        print('   arm failed: %s' % e)

    await asyncio.sleep(4)
    listen_task.cancel()

asyncio.run(main())

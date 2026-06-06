# UWB API for Hula Swarm (`UWBParserThread`)

Source: org's `BH2026ROBOVERSE` Discord channel, 2026-06-06 11:28 am.
Drive folder: https://drive.google.com/drive/folders/1zDKviPq21uByHwgymhtu-8G7j0YLncXN

Contents:
- [`UWBParserThread.py`](UWBParserThread.py) — the reference parser implementation (4.3 KB, 112 lines)
- [`UWB_API_Hula_swarm.pdf`](UWB_API_Hula_swarm.pdf) — API reference manual (26 KB)

---

## What this is

A USB-serial-backed UWB position parser that runs on the **C2 Terminal Windows side**, polling a UWB receiver via UART at **921600 baud**. The receiver streams binary frames containing position data for **up to 30 tagged objects** in the arena. Our swarm controller queries the parser for any tag's `(x, y, last_update_timestamp)` in metres.

**This is DIFFERENT from the mapping drone's UWB:**

| | Mapping drone UWB | Hula swarm UWB |
|---|---|---|
| Transport | ROS2 topic `uwb_tag` | **USB-serial @ 921600 baud** |
| Library | `rclpy` + `geometry_msgs/PoseStamped` | **`pyserial`** |
| Subscriber pattern | Async stream callbacks | **Thread polling a binary frame** |
| Unit | metres | metres (mm in wire, divided by 1000) |
| API | `pose.position.x/.y/.z` | **`get_tag_position(tag_id) -> (x, y, ts)`** |
| Where it runs | Onboard the mapping drone (Ubuntu) | **C2 Terminal Windows** |
| Z axis | Yes (down_m via PX4 NED) | **No — XY only** (matches mapping drone UWB which is also XY only) |

## Frame protocol (from `UWBParserThread.parse_data`)

- Header: `0x55` (ASCII 'U') — 1 byte
- Function mark: `0x00` — 1 byte
- Per-tag record (up to 30): `block_id (1) | role (1) | pos_x_mm (3) | pos_y_mm (3) | pos_z_mm (3) | distances (16)` = 27 bytes (total 810 bytes)
- Inactive slots filled with `0xFF`
- Trailing payload: 83 bytes (NOT parsed by `UWBParserThread.parse_data`; likely anchor data / RSSI / reserved per PDF — TBC)
- Checksum: `0xEE` byte at end — 1 byte
- Total frame: 896 bytes (1 + 1 + 30*27 + 83 + 1)

Note: `parse_data` only walks through offset 812 then checks `buffer[-1] == 0xEE`; bytes 812-894 are present on the wire but ignored by the reference parser. Confirm exact layout against `UWB_API_Hula_swarm.pdf` before relying on those bytes.

## Usage (canonical)

```python
from UWBParserThread import UWBParserThread

parser = UWBParserThread(serial_port=None, baud_rate=921600)  # auto-detect COM port
if parser.serial_port:
    parser.start()
    try:
        while True:
            x, y, ts = parser.get_tag_position(tag_id=0)
            if x is not None:
                print(f"Tag 0: x={x:.2f} y={y:.2f} t={ts}")
            time.sleep(0.1)
    finally:
        parser.stop()
        parser.join()
```

The constructor optionally takes `x_origin` + `y_origin` for coordinate offset (handy if the UWB receiver's origin doesn't match the arena's chosen reference frame). Note the reference implementation sets these to 0.0 internally regardless of the args — the offsets aren't actually applied in `parse_data`. If we need an offset, we apply it client-side: `x_world = x_uwb - x_origin`.

## Open questions

1. **What tag_ids do the 3 Hula drones have?** Org needs to publish a mapping (presumably labelled on the drones at venue).
2. **Do the RoboMaster ground robots have UWB tags too?** If yes, swarm controller knows exactly where they are without needing visual detection → ArUco is just for confirmation/identification.
3. **What is the coordinate frame origin?** Where is (0, 0) in the arena? Probably calibrated at venue against a known landmark.
4. **What COM port does the C2 Terminal expose?** Auto-detect looks for "USB" in the port description — should "just work" but worth confirming Day 1 morning.
5. **Update rate?** PDF doesn't say. We poll `get_tag_position` from our control loop at whatever rate we want; the parser thread updates `tag_data` whenever a new frame arrives (transport budget is ~10 ms/frame — 896 bytes @ 921600 baud 8-N-1 ≈ 100 Hz wire-rate ceiling — but the UWB receiver firmware almost certainly publishes slower; common UWB position rates are 10–20 Hz. Measure on Day 1 with a timestamp delta.).

## How this slots into our stack

**Swarm controller (K's track, on C2 Terminal):**
- Owns the `UWBParserThread` instance
- Per Hula drone: known UWB tag_id → poll position → use as feedback for waypoint navigation (velocity P-controller, same pattern as `kolomee.py` but consuming Hula-side UWB instead of ROS2)
- Per ground robot (IF tagged): use UWB to know rough world XY → fly Hula toward it → use ArUco on Hula camera to confirm
- If RoboMasters are NOT UWB-tagged: rely purely on ArUco visual detection from Hula camera as Hulas execute a search pattern

**Mapping drone controller (Z's track):** unaffected — keeps using ROS2 `uwb_tag` topic.

## What this means for A's track

ArUco-on-ground-robots was confirmed by org 2026-06-06 5:00 am. Combined with this UWB API:
- **A's YOLO model is no longer the primary detection path.** Detection of ground robots happens via `cv2.aruco` on the Hula's camera feed.
- A's annotation tool is still useful as **insurance** (in case ArUco detection has issues — too small, occluded, wrong angle), but is no longer critical-path.
- A's bandwidth can shift to: training a backup YOLO model (low priority), assisting K with swarm orchestration, or arena scouting Day 1 morning.

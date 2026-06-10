# Hula Drone Instruction Manual (mirror)

> Source: <https://ds-api.hg-fly.net/manuals/Hula_EN.html> (fetched 2026-06-10).
> Manufacturer: Shenzhen HighGreat Innovation Technology Development Co., Ltd.
> This is a fetched/summarised mirror — the live page is the authority if reachable.
> NOTE: this manual is consumer-app oriented; the developer SDK is `pyhulax`
> (<https://pyhulax.xenops.ae>, mirrored at `semifinal/docs/pyhulax/`), not documented here.

---

## WiFi connection (step by step)

**Direct connection mode (default):**
1. Press and hold the power button on the back of the aircraft for **2 seconds** to power on.
2. Lamp cover flashes **purple** = direct-connection mode active.
3. Connect your PC/mobile device to the aircraft's WiFi network.
4. Default WiFi password: **`12345678`**.
5. Launch the Hula APP; status indicator turns **solid green** when connected.

**Mode switching:**
- Press the power button **three times quickly** (while powered on) to toggle modes.
- Direct-connection mode: purple lamp flashing (device connects straight to the aircraft AP).
- Networking mode: **white** lamp flashing (both your device and the aircraft join an
  external router — this is the mode you want for swarm control over venue WiFi).

**Reset:**
- WiFi reset: hold the reset button inside the reset hole for **5 seconds**.
- Firmware rollback: hold for **10 seconds** to revert to the previous firmware.

---

## Key specifications

| Component | Details |
|-----------|---------|
| Communication range | 50 m max |
| Flight height | 10 m max |
| Positioning | Optical flow + QR code (expandable to UWB) |
| Camera | 1920×1080 photos; 720P/30fps video; 1080P HD image transmission |
| Battery | 1200 mAh, 3.8 V Li-ion; ~9–10 min flight time |
| Antenna | PCB; 2.4 GHz / 5.8 GHz |
| Weight | 100 g (±3 g) with battery |
| Operating temp | 0–40 °C |

---

## Camera / gimbal

The manual lists a "gimbal system" and "front camera" but gives **no explicit gimbal/camera
control steps** beyond noting 1080P transmission and the in-app "Album". Programmatic gimbal
tilt (face-down for floor targets) is done through the `pyhulax` SDK
(`set_camera_angle(...)`), confirmed by org ("the gimbal can be tilted down to face down
with codes", 2/6 9:45am) — not via this consumer manual.

---

## Charging & battery

- USB direct charging (Micro USB): ~1 h 40 min.
- Dedicated charging box: ~1 h (needs 5 V / 3 A adapter). Use the HighGreat dedicated box.
- Indicators: solid red = charging; red off = charged.
- Stop use immediately if the battery is wet, swollen, leaking, smelly, or deformed.

---

## App / firmware

- Android/iOS app: <https://download.hg-fly.net/app/hula_app.html>
- PC app (Windows 10+ 64-bit): <https://download.hg-fly.net/app/hula_pc.html>
- Requirements: iOS 15.0+ / Android 11+ / Windows 10+ (64-bit).
- Firmware: the app auto-detects the latest version; tap **[Download]** and follow prompts.
- Scratch programming is supported via the PC software (consumer feature, not the SDK).

---

## Credentials / SDK / ports

- WiFi password: `12345678`. **No** API keys / SSH / developer endpoints in this manual.
- **No SDK docs, API endpoints, or port numbers** are in this consumer manual. For
  development use `pyhulax` (SDK reference <https://pyhulax.xenops.ae>). The swarm
  discovery protocol (UDP **8668**, msg ID 232) is documented in `semifinal/dola.py`, not
  here.

---

## Safety notes

- Children under 14 supervised by an adult.
- Fly no higher than 10 m AGL.
- Keep ≥ 2 m from pedestrians.
- Do not fly in thunderstorms / typhoons.

## Propellers

- "75 mmR" blades on top-left and bottom-right; "75 mm" blades on top-right and bottom-left.
- Do NOT remove propellers by hand — use the provided removal tool.

## Support

- Email: service@hg-fly.com · Phone: (+86) 19924918168

# KEY UPDATES (10 June) — actionable facts for the mapping drone

These are the **new, code-affecting** facts extracted from the 10-June organiser drops.
Full verbatim source: `discord_messages_raw.md`.

---

## 🔴 1. Navigate with `set_position_ned`, NOT velocity control

**Org (10/6 5:58am):** "Refer to `moveit.py` on how to use `set_position_ned` to fly the
mapping drone. **Far more accurate and easier. I do not recommend velocity flying in
`kolomee.py`** as now the mapping drone has enhanced capability. Sorry."

- This **reverses** Learning Material 3 (3/6), which said position commands were disabled
  for safety and that we must close the loop ourselves with velocity setpoints.
- Our current stack `semifinal/mapping_drone/controller.py` is a **velocity-setpoint
  P-controller** (the `kolomee.py` pattern). Per this update that approach is now
  *not recommended*.
- **Action:** the reference file is `moveit.py` (Google Drive — pull on the org VM /
  dedicated laptop). The MAVSDK call is `drone.offboard.set_position_ned(PositionNedYaw(
  north_m, east_m, down_m, yaw_deg))`. We should add a position-NED control path to the
  controller (or a `--control-mode position|velocity` flag) and prefer position mode at the
  venue. Keep the velocity path as a fallback.
- Note the NED sign convention is unchanged: `down_m` is **negative when airborne**
  (altitude 1.5 m → down_m = −1.5).

---

## 🟠 2. ArUco dictionary is ANNOUNCED: `DICT_7X7_1000`

**Org (10/6 5:50am):** "Use DICT: `cv2.aruco.DICT_7X7_1000`. ids are 11, 45, 51, 67, 101."

- This **resolves** the long-standing "dictionary TBD Day-1" open question.
- Title history (note the confusion): posted under "Challenge 2 & 3", briefly retitled
  "Challenge 1", then Bryan set it back to **"Challenge 2 & 3"**. Earlier org statements
  said the *same physical markers* sit beside both Challenge 1 and Challenge 2 landing pads,
  so `7X7_1000` is the safe default for the mapping drone (Challenge 1) too — **but verbally
  confirm with the marshal Day-1 that Challenge 1 uses the same dict.**
- Our code already supports `7X7_1000` via `--aruco-dict` (one of the 20 keyed dicts).
  **Action — launch the controller with `--aruco-dict 7X7_1000`** instead of the `6X6_250`
  default.

### Marker IDs and physical locations
| ID  | x (m) | y (m) |
|-----|-------|-------|
| 11  | 1.35  | 4.4   |
| 45  | 1.3   | 7.85  |
| 51  | 4.4   | 4.4   |
| 67  | (not published) | |
| 101 | (not published) | |

- Implied arena extent: at least ~**4.4 m (x) × 7.85 m (y)** — **bigger than our 2×2 test
  square** and larger than the `arena_3x3`/`4x4` pre-staged waypoint files. The closest
  pre-staged file is likely `arena_8x8.json`; trim/edit to the real dimensions Day-1.
- These known (id → world xy) pairs are a **ground-truth check** for the detection +
  `camera_to_world` pipeline: fly over marker 11 and confirm the reported world coord lands
  near (1.35, 4.4).
- Validity rule (`validity.decide_landing_validity`) is still the placeholder
  (even=valid / odd=invalid). With IDs {11,45,51,67,101} that placeholder would mark
  **all five invalid** (all odd). **Confirm the real validity rule Day-1** and set it via
  `MAPPING_DRONE_VALIDITY=` or by editing the function body.

---

## 🟢 3. Other confirmations relevant to the mapping drone

- **Map layout NOT provided** (6/6 11:40am) — Challenge 1 is to discover it. Plan an
  exploration pass; the marker coords above seed where the pads are.
- **Takeoff point is the same for all teams**, but you **may launch facing your desired
  yaw** (8/6 12:17pm). Pick a yaw that simplifies the survey sweep.
- **Drones are shared; laptops are dedicated** (5/6 6:55pm). You get a testing slot on the
  actual drone — every line that touches hardware should already work before the slot.
- **Detection of ground robots is ArUco-based** ("hula drone to detect aruco marker on
  ground robots", 6/6 5:00am). YOLO/RKNN is backup only.
- **Camera models confirmed (user, 10/6): D435 + D450** (mixed fleet, drones shared). **D435 has RGB** →
  the current color pipeline works as-is. **D450 has no RGB** (per `D430_RGB_RISK.md`) → the color pipeline
  raises and yields zero ArUco until the IR fallback is wired (`--use-ir-for-aruco` is currently
  docstring-only, not implemented). Identify the camera per assigned drone; patch if D450.
- **"How to code and use the Drones at the Final"** (10/6 5:40am) and the **Finals
  brief.pptx** are the authoritative day-of procedure — read them at the venue. The brief
  was already extracted into `semifinal/finals_brief_extracted.md`.
- **Concept submission** due **11 June 1:30pm** (one entry per team) — non-technical but
  a hard deadline.

---

## TL;DR launch line (subject to Day-1 confirmation)

```bash
# from inside semifinal/ on the drone VM, after staging the arena waypoints
MAPPING_DRONE_VALIDITY=<rule_from_marshal> \
python -m mapping_drone --aruco-dict 7X7_1000 \
    --waypoints-from-json configs/waypoints_2026-06-10.json \
    --gimbal-pitch -90
```
Plus: pull `moveit.py` from the org Drive and switch the controller to `set_position_ned`
navigation (see item 1) before the scored run if time permits.

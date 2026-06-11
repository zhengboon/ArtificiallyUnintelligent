# downloaded stuff/

Organiser docs + announcements captured from the BrainHack 2026 RoboVerse channel,
saved here on **2026-06-10** per request. Google-Drive-hosted material is **referenced but
not downloaded** (auth-walled — pull those on the org-provided VM / dedicated laptop). The
single non-Google link (the Hula consumer manual) is mirrored.

## Files

| File | What's in it |
|------|--------------|
| [`KEY_UPDATES_for_mapping_drone.md`](KEY_UPDATES_for_mapping_drone.md) | **Read first.** The 3 code-affecting Day-1 facts: (1) navigate with `set_position_ned` not velocity, (2) ArUco dict = `DICT_7X7_1000` + IDs 11/45/51/67/101 + locations, (3) other confirmations. |
| [`discord_messages_raw.md`](discord_messages_raw.md) | Verbatim capture of all pasted organiser + Q&A messages, chronological, with the Google Drive links listed. |
| [`hula_manual_EN.md`](hula_manual_EN.md) | Mirror of the Hula consumer manual (WiFi join, gimbal, charging, app links). |

## Google Drive references (NOT downloaded — pull on the org VM)

| Topic | Link | Key file |
|-------|------|----------|
| L1 Hula swarm | <https://drive.google.com/drive/folders/19ni5GmRy8cBzX98TybsToQa4a17LbYi5> | `huladola.py` (already in `semifinal/huladola.py`) |
| L3 mapping drone UWB+MAVSDK | <https://drive.google.com/drive/folders/1H6H6E06RHp5r97ch2_ZA1-rEIuHQHbxO> | `kolomee.py` (already in `semifinal/learning_material_3_uwb/`) |
| L4 Realsense | <https://drive.google.com/drive/folders/1auSeEagUslLpDi19UgkY6lYkQLlan-dv> | already in `semifinal/learning_material_4_realsense/` |
| L5 YOLO→ONNX→RKNN convert | <https://drive.google.com/drive/folders/1JTDV6XueZWJyXB-L_yMaLAEum_lQntK3> | convert scripts (in `semifinal/learning_material_5_yolo_rknn/convert/`) |
| L5 RKNN detection | <https://drive.google.com/drive/folders/1dVcath0iW3VGA3biqiCDCcZKRfzVPGEa> | detection scripts (in `learning_material_5_yolo_rknn/detection/`) |
| UWB API (Hula swarm) | <https://drive.google.com/drive/folders/1zDKviPq21uByHwgymhtu-8G7j0YLncXN> | PDF (already in `semifinal/uwb_api_hula_swarm/`) |
| Final Challenge rules/slides | <https://docs.google.com/presentation/d/18INz16tbHPeHHWlFkEI6EKhlFgD6ZFKx/> | extracted → `semifinal/finals_brief_extracted.md` |
| **How to code & use the drones at the Final** | <https://drive.google.com/drive/folders/1yniPcwEI0FQVAV0wstxLEqeYlHhAsBRl> | ⏳ **NOT yet pulled** — get on the VM Day-1 |
| **`moveit.py` (set_position_ned reference)** | <https://drive.google.com/file/d/1luOUZJUX1sEygnVEvcejlteD_bcwUfIH/> | ⏳ **NOT yet pulled** — needed for new nav approach |
| Concept submission form | <https://docs.google.com/forms/d/e/1FAIpQLSdcG_BlsMwh_YN_aCOMQLjL0-A8T9XUI_ZSNC3rpUpDXSVeYw/> | due **11 Jun 1:30pm**, one entry/team |

## ⏳ Two items to pull on the org VM Day-1
1. **`moveit.py`** — the `set_position_ned` reference; org now prefers it over velocity flying.
2. **"How to code and use the Drones at the Final"** pdf/ppt — the authoritative day-of procedure.

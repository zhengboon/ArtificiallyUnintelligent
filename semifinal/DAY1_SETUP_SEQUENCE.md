# Day-1 Setup Sequence — 7:30am to 9:00am

Companion to `DAY1_RUNBOOK.md` (which covers execution + fallbacks). This file covers the SETUP phase only: arrival → first scored slot ready. One page. Print on paper.

---

## 7:30 — Arrival + registration

- Photo ID + confirmation email in hand at the door.
- **A** collects lanyards at registration desk (talker role).
- **K + Z** head straight to assigned setup zone with gear cart. Do not wait for A.

---

## 7:45-8:15 — Hardware setup

- [ ] **Mapping drone camera reachability**: confirm the mapping drone has booted and is reachable via NoMachine from the C2 Terminal — the drone's onboard D430/D450 (no RGB) will be queried during the 8:35-8:50 validation block. The USB-3 type-descriptor one-liner (see step 4 of the validation block below) runs inside the NoMachine session against the drone's pyrealsense2, not against the C2 Terminal. Our D435 stays in the bag (dev fallback only; venue uses D430/D450).
- [ ] **Mapping drone radio link**: 5.88 GHz link to GCS. Org will likely walk us through pairing — K stays at the drone, follows org instructions, confirms link LED solid.
- [ ] **Hula drones**: power on, join the venue 5 GHz WiFi SSID announced at briefing. K confirms each drone visible to the swarm controller before handing off.

---

## 8:15-8:35 — Code transfer (USB → C2 Terminal → VM)

Copy these 3 trees from USB to `C:\team\semifinal\` on the Windows host:

1. `semifinal/` — full tree (mapping_drone, tools, configs, tests, runbooks).
2. `models/` — currently empty; YOLO path killed per `runbook.md`. Skip if absent.
3. `configs/` — already inside `semifinal/`, but re-verify `waypoints_2x2_default.json`, `waypoints_unknown.json`, `valid_ids_unknown.json` are present.

Then load into the Ubuntu 22.04 VM. Primary mechanism: VirtualBox/VMware shared folder mount (see `thumbdrive/README.md` → "VM <-> host file transfer" → Option A). Verify on VM with `ls /media/sf_brainhack` (VBox) or `ls /mnt/hgfs/brainhack` (VMware). If Option A fails, fall back to Option B (USB passthrough) per the same doc.

---

## 8:35-8:50 — Environment validation (run from `semifinal/` on the VM)

Single command per check. If any fails, fix before proceeding.

- [ ] `python -m mapping_drone --help` — CLI parses; `--real`, `--mock` (alias `--mock-all`), `--waypoints-from-json`, `--aruco-dict`, `--mavsdk-addresses`, `--gimbal-pitch`, `--max-flight-time-s` all listed. Real mode is the default — actual drone runs need NO flag.
- [ ] `python -c "from mapping_drone.mapping import ALL_SUPPORTED_DICT_NAMES; print(len(ALL_SUPPORTED_DICT_NAMES))"` — must print `20`.
- [ ] `python tools/uwb_sniffer.py` for 10 s — confirm `uwb_tag` topic publishes; NED axes match (n=pose.y, e=pose.x, alt=-pose.z). Ctrl-C to stop.
- [ ] `python -c "import pyrealsense2 as rs; print(rs.context().query_devices()[0].get_info(rs.camera_info.usb_type_descriptor))"` — must print a `3.x` string. If `2.x` → wrong USB port, replug.

---

## 8:50-9:00 — First-run prep

- [ ] Read briefing materials handed out at registration. Capture:
  - Announced ArUco dict name (verbatim, including underscores/case).
  - Validity rule (which IDs count, which don't).
  - Arena dimensions + waypoint constraints.
- [ ] Populate `configs/valid_ids_2026-06-10.json` from `valid_ids_unknown.json` template.
- [ ] Populate `configs/waypoints_2026-06-10.json` by copying `waypoints_2x2_default.json` (or the nearest pre-staged `arena_NxN.json`) and editing in place. **Do NOT use `waypoints_unknown.json`** — it is intentionally `[]` (empty list) and the controller's `_parse_waypoints_json` will raise `ValueError: waypoints list is empty` if you launch with it.
- [ ] Decide first Run Configuration: A (Safe) / B (Aggressive) / C (Recovery) per `runbook.md` section "Run configurations". The actual pre-staged waypoint files in `configs/` are `arena_3x3.json` / `arena_4x4.json` / `arena_6x6.json` / `arena_8x8.json` + `waypoints_2x2_default.json` (all at 4.0 m) — pick the closest match to the announced arena dimensions and pass it via `--waypoints-from-json`.

---

## Role assignments during 7:30-9:00

- **K** — hardware: drone batteries, USB connections, mapping drone radio link, Hula WiFi join.
- **Z** — software: USB → VM transfer, environment validation, config file staging.
- **A** — comms: registration, briefing notes, capture org's Day-1 announcements (dict + validity rule + arena dims), photo-log the arena for post-run review.

---

*Day-1 Setup Sequence v1. Hands off to `DAY1_RUNBOOK.md` at 9:00am sharp.*

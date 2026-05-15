# Deep review — 2026-05-15

Cross-referenced our repo docs against the Discord source-of-truth in
`info_2026-05-15/*.md` (user's manual dumps of 6 channels) and the
existing `info_2026-05-08/msg_*.md` snapshots. Light integrity check on
all workshop files we downloaded.

## TL;DR

| Area | Status |
|---|---|
| Workshop file downloads | ✅ all present, correctly sized, ID-matched |
| Discord-only attachments (3 v2 .py files from `65drones5`) | ❌ still missing, can't be auto-downloaded |
| Critical date in our docs | ❌ **WRONG** — fixed |
| Disk-space risk framing | 🟡 needs sharpening — OP has officially answered the general case |
| Camera topic name documentation | 🟢 ours is correct; multiple variants now documented |
| New OP guidance not yet in our docs | 🟡 several items, incorporated |

---

## Section A — Findings from the new Discord dumps

### A1. CRITICAL: booking/rescheduling deadline is wrong in our docs

**Our docs claim:** cancellation cutoff = `2026-05-20 (Tue) 14:00` (our 48-hour math from the 65drones page).

**Official deadline (`65drones1` in #general, 13/5/2026 4:51 PM):**

> "The deadline for booking/rescheduling is **21st May, 10am**. Teams which have not booked the slot by 21 May, 10am will be assigned random available slots, at organizer's discretion."

→ Real deadline is **2026-05-21 (Thu) 10:00 SGT**, not 2026-05-20 14:00. Affects `progress.md`, `team/tasks.md`, `challenge/qualifier_booking.md`. Fixing all three.

### A2. OP officially answered the "disk fills up" question

**`BH2026ROBOVERSE` in #general AND #tech-discussion, 13/5/2026 6:00 PM:**

> "If your VM reports low on diskspace, it is because the PX4-Autopilot generates lots of logs while running the PX4 SITL. The logs can grow up to many GBs. Please regularly maintain the logs folder. PX4 SITL logs folder is at `~/PX4-Autopilot/build/px4_sitl_default/rootfs/log/`. ... `rm -rf ~/PX4-Autopilot/build/px4_sitl_default/rootfs/log/*` to free up diskspace."

This **partially** answers our DS-1 ticket. Two distinct disk problems exist:

| Disk problem | OP-answered? | Our mitigation |
|---|---|---|
| Cumulative PX4 logs (~hundreds MB per run, grows over many runs) | ✅ yes, with the rm command above | add to troubleshooting + setup guide as routine maintenance |
| Install-time disk (ultralytics + torch = ~3 GB, doesn't fit in stock 49 GB / 95% full VM) | ❌ no, not addressed | DS-1 still valid; sharpen the question |

→ Sharpening DS-1 ticket to ask specifically about the install-time issue + whether the demo machine has ultralytics pre-installed.

### A3. NEW: camera topic name varies by drone × world

**`BH2026ROBOVERSE` in #general, 11/5/2026 7:05 AM:**

| Drone | World | Topic name |
|---|---|---|
| `x500_vision` | `roboverse` | `/world/roboverse/model/x500_vision_0/link/camera_link/sensor/IMX214/image` |
| `x500_depth` | `roboverse` | `/world/roboverse/model/x500_depth_0/...` |
| `x500_vision` | empty | `/world/default/model/x500_vision_0/...` |
| `x500_depth` | empty | `/world/default/model/x500_depth_0/...` |

Use `gz topic -l` to discover the right one. Our controller uses the first variant (correct for Qualifier). Worth documenting the others.

### A4. NEW: OP confirms `gzphotodetectorsaver.py` is "a very important hint"

**`BH2026ROBOVERSE` in #general, 11/5/2026 2:52 PM:**

> "it is up now at coding discussion. THAT IS a very important hint there."

Our Phase 2 controller follows this pattern (YOLO inference in a worker thread, callback on detection). Already aligned. Worth flagging in our docs that the design isn't novel; we're following the OP's recommended pattern.

### A5. NEW: OAK-D Lite lightweight model.sdf available

**`BH2026ROBOVERSE` in #coding-discussion, 11/5/2026 3:21 PM:**

> "those who wish to make the camera stream lightweight and does not hinder the main loop. You can download this OAK-D Lite model.sdf file which change to resolution to 640 x 480 from 1920x1080 and reduce the update to 10 [Hz]."

We already have this at `optionB/OakD-Lite_model.sdf` (downloaded 12/5). It's a drop-in replacement for the default camera config. Performance win on the VM. Should mention it in the guide.

### A6. NEW: depth/avoidance parameter units confirmed

**`BH2026ROBOVERSE` in #coding-discussion, 11/5/2026 6:48 AM:**

> "in meters … critical_distance means it will recommend to stop when anything in 1.5m. … local_ned_position is in m. yaw is in degree. not in radians when it is raw from callback stream. safety_distance is to tell you should slow down."

We use these units correctly in `searchctl/controller.py`. Worth documenting for future-self.

### A7. Pre-U vs University category distinction

**`BH2026ROBOVERSE` in #general, 10/5/2026 12:24 PM:**

> "diff lies the type of barrels that must be detected. refer to qualifier documents for details."

Confirms the Qualifier.pdf info: Uni needs ≥1 yellow AND ≥1 red; Pre-U needs ≥1 of either. No update needed.

### A8. Outstanding "Stay tune" answers — still unanswered

Two pending OP responses we'll need by ~21 May:

1. **`GeekSquad_JustusJojo`, 12/5 5:53 PM:** "How many yellow and red barrels are in the qualifier world and at what height the red barrels are placed at" → OP said "Stay tune" 13/5 7:55 AM. Still unanswered.
2. **`yangweiindustries_YewSuYi`, 12/5 11:13 PM:** "will the map released 1 day before include the obstacle crates?" → OP said "Stay tune" 13/5 7:46 AM. Still unanswered.

Both expected to be answered when the qualifier map releases (~21 May).

### A9. VM password officially confirmed

`67_CaddenChua` (community), 14/5/2026 8:22 PM: `password`. Matches what's in our setup guide. No change.

---

## Section B — Light integrity check on downloaded files

Cross-referenced every Drive file ID mentioned in `info_*/` against what's actually on disk in `challenge/`, `learning/`, `optionB/`, `codes/Codes/`.

| Drive ID | Expected local file | Status |
|---|---|---|
| `1DxnMibJpXH9PugCcfVmmoUU21hCxMwxb` | challenge/Qualifier.pdf | ✅ 304 KB |
| `1cD0tbnaJ4YdFdSGzKT7jnUgtKkluqfoe` | challenge/WorkshopLaptopRequirements.docx | ✅ 215 KB |
| `1lvjfIEcEv6QeF2QjHxYI2UtAIjLqwJE-VjjfdrfOIFQ` | challenge/OptionB.docx | ✅ 8 KB |
| `1FZSGrbFIs4ZPrIEvhJBMP_UUnMJVrm8y` | learning/LearningMaterial1.pdf | ✅ 2.3 MB |
| `19rXITCt-tTjwEQEAMY_JtzL0XwMHAzOP` | learning/LearningMaterial2.pdf | ✅ 4.7 MB |
| `12Tnb_8z239MVhDjt9dlWVTx1A3QGZwFU` | learning/LearningMaterial3.pdf | ✅ 2.9 MB |
| `1oTRKmI9P4pzof4iyUjCcFA3LoSK-Wifa` | learning/Supplementary1.pdf | ✅ 1.9 MB |
| `1Wwhi8UP_420Z1I7Ltv0p_jX9O1aNiOHu` | learning/Supplementary2.pdf | ✅ 1.4 MB |
| `1F_U5Wo3HKmb4T9VKCM6fw0mVe6pQ7dHd` | learning/Lecture1.mp4 | ✅ 639 MB |
| `1Lq3zCMT1HE5JCj51NLj02Uu0ZjS4IpxF` | learning/Lecture2.mp4 | ✅ 514 MB |
| `1_T9ZutDXnntTySuQaS_GlrYn_q0EPS4d` | learning/Lecture3.mp4 | ✅ 256 MB |
| `1nNhcKNeTyKeAWETOkE0zaIf4nNEiEK8o` | learning/Supplementary1.mp4 | ✅ 159 MB |
| `1mg4j3YkCEBzMHGUA0IHiSktUSyMIXGUF` | learning/Supplementary2.mp4 | ✅ 77 MB |
| `1vtl3Hw_1HEfyq7qTj0Ye-qQwv3nx7dCm` | codes/Codes/ (folder) | ✅ 41 files |
| `1-STWqRmjrgcnznnhaCnKsF_MGWxjSiD-` | optionB/start_px4.sh | ✅ 1.9 KB |
| `1j-MobgqNepdknvCfo79LOcZZ-_xu99hw` | optionB/roboverse.sdf | ✅ 4.8 KB |
| `1PtJ2iuJAyeOyn5z_jbKVGFR3nfdCBjwh` | optionB/base6.glb | ✅ 36 MB |
| `1nrfymHqjmLKWZdkMMNAUIGv3Epgt_jI6` | optionB/x500_vision_model.sdf | ✅ 0.6 KB |
| `1hOn6E5Um0yH_XmPusAkhYqiljkIZ6FL3` | codes/Codes/gzphotodetectorsaver.py | ✅ 4.1 KB |
| `1l_JehgGEGO5luwuLOQ6aeYoGJyW41lZD` | optionB/OakD-Lite_model.sdf | ✅ 2.4 KB |
| `1P8E7flFDi5FE0WGT8RZxtZdo-8WUj6GX` | vm/Drone-Ubuntu-22.04_v3.zip | ✅ 18.4 GB + extracted |

### Intentionally skipped

| Drive ID | What | Why skipped |
|---|---|---|
| `1g9q5f2Gqqax78a0uBYnI6SIQ7iwHB3Y` | vionode (OpenVINS) | Not needed for Qualifier per OP. Failed on first attempt; not retried. |
| `1Ctd5-wXzrlDpBu2Lo2dbWg9_XWN17sem` | VMware Fusion Pro mirror | Mac-only. We're on Windows. |
| `1jNn2Bk_Nkf3FC-8VBc3xNOclzNugtq_N` | qcow2 VM image | ARM-Mac only. |

### MISSING — Discord-only attachments (no Drive link)

Three v2 files posted by `65drones5` on 10/5/2026 6:00 PM in both `#coding-discussion` and `#general`:

- `get_position_with_task_v2.py` (5.78 KB) — telemetry latency improvement
- `GlobalMapperV2.py` (7.29 KB) — depth-camera-to-map visualization
- `mapper.py` (5.75 KB) — example main loop using the above

These are Discord file uploads, not Drive links — can't be auto-downloaded. **Action:** open Discord desktop app, navigate to `#coding-discussion`, scroll to 10/5/2026 6:00 PM, download each attachment, drop into `codes/Codes/`.

---

## Section C — Fixes being applied

| # | File | Change |
|---|---|---|
| 1 | `progress.md` | Replace 2026-05-20 14:00 cancellation cutoff with 2026-05-21 10:00 official deadline. Add OP's PX4 log cleanup as a standing maintenance item. |
| 2 | `team/tasks.md` | Same date fix. Reframe DS-1 risk: split "log-fill disk" (OP-answered) from "install-time disk" (still open). Add log cleanup as routine task. |
| 3 | `team/discord_drafts.md` | Rewrite DS-1 to focus on the install-time question; acknowledge the OP already answered the log-fill case. |
| 4 | `challenge/qualifier_booking.md` | Update cancellation cutoff to match official deadline. |
| 5 | `guides/vm_from_zero_to_flight.md` | Add log cleanup command. Add camera topic name disambiguation table. Add OAK-D Lite lightweight option. |
| 6 | `reports/troubleshooting.md` | Add log cleanup as the official disk-pressure fix. |

No code changes — controller and watcher are aligned with OP guidance.

---

## Section D — What we still owe

- Ask K to download the 3 v2 .py files from Discord and add to `codes/Codes/`.
- Send the sharpened DS-1 support ticket (Z, when at Discord).
- Watch for OP's answers to the two "stay tune" questions (barrel count + obstacle crates), expected ~21 May with map release.
- Action item: A or Z to actually book the slot before 21 May 10:00 (we have the booking page, just need to commit).

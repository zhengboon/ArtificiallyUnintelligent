# Learning Materials and Others — Discord Scrape

Consolidated verbatim copy of org's `BH2026ROBOVERSE` Discord posts about the **Final Challenge** (we got pushed straight here from qualifier). Source: BH2026ROBOVERSE channel(s).

Preserved as-is for reference. Do not edit the message bodies — they are the authoritative source of org intent. Annotations live at the bottom.

---

## Learning Materials 1 — Hula Swarm Control

> **BH2026ROBOVERSE** OP — 2/6/2026 9:17 am
>
> Semi-Final need your team to code to control a swarm of Hula drones from a computer and do detections. Please start to learn on how to do so by reading huladola.py in https://drive.google.com/drive/folders/19ni5GmRy8cBzX98TybsToQa4a17LbYi5?usp=drive_link . That py contains illustrate the core on how to do swarm control code and the link to a website that describes all of the sdk.

(Google Drive — folder titled "Hula Swarm Control and Video Streams". Contains `huladola.py` and `dola.py`. Both pulled into [`semifinal/huladola.py`](huladola.py) and [`semifinal/dola.py`](dola.py).)

> **BH2026ROBOVERSE** OP — 2/6/2026 9:18 am
>
> If you have hula, please try try.
> If you have hula but not sure how to hook hula drone to wifi network, read the hula manual. If that manual not clear, drop a message and I will advise.

> **BH2026ROBOVERSE** OP — 2/6/2026 9:28 am
>
> Why am I sending out this? It is because Hula drone cannot work with MAVSDK. Therefore, I send this out to gives heads-up.

> **BH2026ROBOVERSE** OP — 2/6/2026 9:45 am
>
> One more thing - Hula drone has camera. There is a gimbal attached to the camera. The gimbal can be tilted down to face down with codes.

---

## Learning Materials 2 — Potential Detection Targets

> **BH2026ROBOVERSE** OP — 2/6/2026 9:34 am
>
> Practise training a object detection model. Besides that, detection of fiducial markers (QR code, Aruco marker, AprilTag) are likely target. OpenCV has libraries to detect to Aruco marker and read QR code.
>
> Sample python code of detecting Aruco marker using OpenCV

```python
import cv2

self.arucoDict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
self.parameters = cv2.aruco.DetectorParameters()
self.detector = cv2.aruco.ArucoDetector(self.arucoDict, self.parameters)


img = self.colorimage.copy()
corners, ids,  = self.detector.detectMarkers(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
if ids is not None:
       cv2.aruco.drawDetectedMarkers(img, corners, ids) # draw bounding box
        if len(corners) > 0:
            ids = ids.flatten()


            for (markerCorner, markerID) in zip(corners, ids):
                corners = markerCorner.reshape((4, 2))
                (topLeft, topRight, bottomRight, bottomLeft) = corners
                topRight = (int(topRight[0]), int(topRight[1]))
                bottomRight = (int(bottomRight[0]), int(bottomRight[1]))
                bottomLeft = (int(bottomLeft[0]), int(bottomLeft[1]))
                topLeft = (int(topLeft[0]), int(topLeft[1]))
                cX = int((topLeft[0] + bottomRight[0]) / 2.0)
                cY = int((topLeft[1] + bottomRight[1]) / 2.0)
                center_v = cY
                center_u = cX
                depth_mm = self.depth_image[center_v, center_u] # get the distance to the image
                if depth_mm == 0:
                    continue
                depth_m = float(depth_mm) / 1000.0
                X = (center_u - self.cx) * depth_m / self.fx #convert to actual distance
                Y = (center_v - self.cy) * depth_m / self.fy
                Z = depth_m
```

> We post learning materials for semi final as soon as when they are available. Stay Tune!

> **BH2026ROBOVERSE** OP — 2/6/2026 9:42 am
>
> Though the semi final involves physical real drone and drone swarm control, your team have learnt most of it takes for semi final such as mapping, MAVSDK in python, and processing depth image and etc. Please revise the supplementary learning material 1 and 2 on mapping and coordinate frame transformation.
>
> We will post learning materials that are add-ons to qualifier - such as how to get get depth data from Realsense Depth Camera (D430 and D450) using pyrealsense2 python sdk, swarm control of hula drones, as and when the materaisl are available

---

## Learning Material 3 — Controlling Mapping Drone using UWB and mavsdk

> **BH2026ROBOVERSE** OP — 3/6/2026 10:23 pm
>
> The mapping drone has a UWB tag that able to realtime update on the drone position within the arena indoor. The tag still unable to let you use position command in mavsdk to control it for safety and your competition efficiency. The control approach will be first query the drone's current position (x-y-z), and then correct the difference between the current location and desired position using velocity command. Study the reference code in this https://drive.google.com/drive/folders/1H6H6E06RHp5r97ch2_ZA1-rEIuHQHbxO?usp=drive_link . This code can give you strong basis.

(Google Drive — file `kolomee.py`, pulled into [`semifinal/learning_material_3_uwb/kolomee.py`](learning_material_3_uwb/kolomee.py).)

---

## Learning Material 4 — Realsense Camera

> **BH2026ROBOVERSE** OP — 3/6/2026 10:27 pm
>
> Reference material: https://drive.google.com/drive/folders/1auSeEagUslLpDi19UgkY6lYkQLlan-dv?usp=sharing
>
> The teams are to use the depth camera for depth assessment and to take photos, and more importantly to do mapping. pyrealsense2 allows to write python to control the camera. The big difference from gazebo is that pyrealsense allow to directly call it to locations.

> **FlyingExplorers_ChuaTseHui** — 4/6/2026 9:21 am
> @BH2026ROBOVERSE Hi thanks for the materials! But I'm unable to access the Google drive link posted (I think we need to change the link sharing permission settings, thanks!).

> **BH2026ROBOVERSE** OP — 5/6/2026 4:45 am
> Hi, I have corrected the access rights. All should be able to access now. Thanks.

(Now accessible — pulled into [`semifinal/learning_material_4_realsense/`](learning_material_4_realsense/).)

---

## Learning Material 5 — Object Detection on mapping drone

> **BH2026ROBOVERSE** OP — 3/6/2026 10:33 pm
>
> YOLO is still an option for you to code code detection with your team. The compute module has NPU that can speed up the YOLO detection. You need to convert the custom YOLO into ONNX and to RKNN format. You can refer to this link for reference code to convert: https://drive.google.com/drive/folders/1JTDV6XueZWJyXB-L_yMaLAEum_lQntK3?usp=drive_link
>
> **(These codes will be available on the machine provided by the organiser. It is the VM within that machine as this requires ubuntu 22.04 again)**
>
> After convert, you would like to detect using the rknn model. The codes for detection can be found here: https://drive.google.com/drive/folders/1dVcath0iW3VGA3biqiCDCcZKRfzVPGEa?usp=drive_link

> **FlyingExplorers_ChuaTseHui** — 4/6/2026 9:20 am
> @BH2026ROBOVERSE Hi thanks for the materials! But I'm unable to access both the Google drive links posted (I think we need to change the link sharing permission settings, thanks!).

> **BH2026ROBOVERSE** OP — 5/6/2026 4:45 am
> Hi, I have corrected the access rights. All should be able to access now. Thanks.

(Now accessible — pulled into [`semifinal/learning_material_5_yolo_rknn/`](learning_material_5_yolo_rknn/).)

---

## 🔥 Org confirmation — University category (5/6/2026 AM)

> **BH2026ROBOVERSE** OP — 5/6/2026 (AM)
>
> University category confirmed.

(Locks our bracket — we compete in the University tier.)

---

## 🔥 Org clarifications — mapping drone stack + C2 Terminal + NoMachine (5/6/2026 PM)

> **BH2026ROBOVERSE** OP — 5/6/2026 (PM)
>
> The mapping drone runs Ubuntu 22.04 with ROS2 and OpenCV onboard. YOLO detection runs through the RKNN NPU at approximately 50 FPS.

> **BH2026ROBOVERSE** OP — 5/6/2026 (PM)
>
> The C2 Terminal is a Windows host with an Ubuntu 22.04 VM (not dual-boot, not WSL). Access the mapping drone from the C2 Terminal via NoMachine.

**Confirms:**
- Mapping-drone software stack: **Ubuntu 22.04 + ROS2 + OpenCV + RKNN NPU @ ~50 FPS** (RKNN performance budget locked).
- C2 Terminal layout: **Windows host + Ubuntu 22.04 VM** running side-by-side. The VM is where RKNN conversion + any ROS2 work lives; the Windows side is where `pyhulax` + `UWBParserThread.py` (pyserial @921600) live.
- Mapping-drone access path: **NoMachine from C2 Terminal** (so we don't SSH directly — remote-desktop into it).

---

## 🔥 Q&A — testing time slots + dedicated laptops (5/6/2026 5:13 pm – 6:55 pm)

> **FlyingExplorers_ChuaTseHui** — 5/6/2026 5:13 pm
>
> Hi @BH2026ROBOVERSE, during the Finals, will each team be allowed to test their code for Challenges 1 and 2 on the actual drones in the arena prior to judging? If so, are there time slots or trial limits we should be aware of?
> Will drones be shared across teams, or will each team have a dedicated drone assigned to them for the duration of the Finals?
> Thank you!

> **BH2026ROBOVERSE** OP — 5/6/2026 6:55 pm
>
> All teams have testing time slots and are to use actual drones during the testing slot. Annoucement on the testing time slot will be made soon. **Drones will be shared and teams are given time to load their codes onto mapping drones. All teams are given dedicated laptops. Task 2 and Task 3 can executed completed off the dedicated laptops.**

**Confirms:**
- Drones are SHARED across teams (we don't get sole possession of a drone — slot-based access)
- Each team gets a dedicated laptop (= the C2 Terminal we already knew about)
- Testing slots will be announced
- "Task 1 / 2 / 3" matches our Challenge 1 / 2A / 2B nomenclature (3 tasks total). Task 2 + Task 3 run off the dedicated laptop = C2 Terminal handles the swarm side.

## 🔥 Q&A — YOLOv11 + use _2.py scripts (5/6/2026 5:02 pm – 6:45 pm)

> **ArtificiallyUnintelligent_BockKS** — 5/6/2026 5:02 pm (that's K!)
>
> for the finals, is it recommended that we used the previous colab notebook used for training the yolo model?
> i noticed that in rknndecoder.py, there is a decode_yolov11_rknn() function, hence i was wondering if we should use yolov11 instead
> can i also confirm that this time, we need to train the model to detect the RoboMaster Ground Robots, and the valid / invalid Aruca Markers?

> **BH2026ROBOVERSE** OP — 5/6/2026 6:45 pm
>
> Hi, **please use yolo11 as the base when you custom train.** Please revisit the link in the learning material that has the rkn py files. **There are updated version. The updated version ends with 2.**

**Confirms:**
- **Use YOLOv11** (not YOLOv8) as the base for custom training. K's qualifier YOLOv8 model needs retrain on YOLOv11 architecture.
- **Use `_2.py` variants** of conversion scripts: `convertyolotoonnx_2.py` and `convertrknn2.py`. These are the canonical paths.
- ArUco question NOT directly answered — org didn't confirm or deny. Our read: **don't train YOLO on ArUco** (use OpenCV `cv2.aruco` instead, as in their L2 sample). YOLO is for the RoboMaster ground robots.

---

## 🔥 IMPORTANT — Update on RoboVerse Challenge - the Final Challenge

> **BH2026ROBOVERSE** OP — 5/6/2026 5:07 am
>
> Please study refer to https://docs.google.com/presentation/d/18INz16tbHPeHHWlFkEI6EKhlFgD6ZFKx/edit?usp=drive_link&ouid=115061820506798878118&rtpof=true&sd=true for details on rules and technical information of the Final Challenge

(The Final Challenge slide deck — pulled into [`semifinal/final_challenge_slides.pdf`](final_challenge_slides.pdf). This is the **official rules + technical spec** document.)

---

## Updated mental model — TWO drone platforms + org-provided VM

| | **Hula swarm** | **Mapping drone** |
|---|---|---|
| Quantity | Multiple | One |
| SDK | `pyhulax` | `mavsdk` (Python) |
| Position source | Optical flow + optional QR | **UWB tag** (real-time arena coords) |
| Position interface | `drone.get_position()` | **ROS2 topic `uwb_tag`** PoseStamped subscriber |
| Control style | Discrete `move(direction, dist)` | **Velocity setpoints**, P-controller |
| Depth camera | Built-in optical flow | **Realsense D430/D450** |
| Compute location | Our laptop | **Onboard SBC with NPU** (Rockchip RK3588 likely) |
| Detection model | **ArUco via OpenCV** (primary, per 6/6 5:00 am clarification); YOLO via `pyhulax.video.YOLODetector` (.pt) as backup/insurance | **ArUco via OpenCV** (primary for landing-validity confirmation); YOLO via RKNN on NPU as backup |
| Connection | TCP/UDP over WiFi | **Serial** over `/dev/ttyS6:921600` |

> Note: per the 6/6 5:00 am org clarification ("hula drone to detect aruco marker on ground robots"), YOLO is de-escalated to insurance/backup on both platforms; ArUco markers (default `DICT_6X6_250`, exact dictionary TBD Day-1) are the primary RoboMaster detection method.

### IMPORTANT clarification from L5 (5/6/2026)
The **RKNN conversion codes are on the org-provided machine**, not something we run on our own laptop. That machine runs a **Ubuntu 22.04 VM** (same constraint as qualifier). So:

- We bring K's `best.pt` (and ideally `best.onnx`) on a USB stick to the venue
- We use the org's VM to do the `.pt → .onnx → .rknn` conversion
- This greatly reduces our RKNN setup risk — we don't need to install `rknn-toolkit2` on our own laptops anymore
- BUT: we need to be familiar with the conversion workflow so we don't waste venue time figuring it out fresh

---

---

## 🔥 Q&A — 2026-06-05 evening + 2026-06-06 AM (multiple)

> **STINKIES_TanFengYuan** — 5/6/2026 10:20 pm
> Hi @BH2026ROBOVERSE does all the members of the team have to be there on both days?

> **BH2026ROBOVERSE** OP — 5/6/2026 10:22 pm
> It is best that all members of team can be there on both days as there are plenty to do.

> **STINKIES_TanFengYuan** — 5/6/2026 10:35 pm
> @BH2026ROBOVERSE Are we supposed to prepare any code before 10 & 11 June or only start working on the code during that period
> *(no answer yet — but slides + L1-L5 make clear: pre-prep heavily)*

> **FlyingExplorers_ChuaTseHui** — 5/6/2026 10:45 pm
> Hi @BH2026ROBOVERSE , may I check if the fiducial markers on the robot convoy are also aruco marker for the HuLa drone to detect or are they a different kind of fiducial marker like maybe QR code? Will there be fiducial markers on the ground robot?

> **BH2026ROBOVERSE** OP — 6/6/2026 5:00 am
> **hula drone to detect aruco marker on ground robots.**

> **WannabEngineers_MokeYiTing** — 6/6/2026 11:35 am
> Hi @BH2026ROBOVERSE , may I check
> Will we be given the map layout and dimensions for the finals?

> **BH2026ROBOVERSE** OP — 6/6/2026 11:40 am
> **Map layout will not be provided.**

---

## 🔥 UWB API for hula swarm (released 2026-06-06 11:28 am)

> **BH2026ROBOVERSE** OP — 6/6/2026 11:28 am
>
> https://drive.google.com/drive/folders/1zDKviPq21uByHwgymhtu-8G7j0YLncXN PLEASE read the pdf in that drive to find out more

Both files pulled into [`semifinal/uwb_api_hula_swarm/`](uwb_api_hula_swarm/). See [the analysis README there](uwb_api_hula_swarm/README.md) for the full breakdown.

**Key facts:**
- Hula swarm UWB uses **`pyserial`** at **921600 baud**, NOT ROS2 (very different from mapping drone)
- Frame: 896 bytes, header 0x55, checksum 0xEE, up to 30 tag records per frame
- Per-tag record: `block_id (1) | role (1) | pos_x_mm (3) | pos_y_mm (3) | pos_z_mm (3) | distances (16)` (27 bytes)
- Parser exposes `get_tag_position(tag_id) -> (x_m, y_m, ts)` — thread-safe via `data_lock`
- Runs on **C2 Terminal Windows side** (auto-detects "USB" COM port)
- ⚠️ The `x_origin` / `y_origin` constructor args exist but aren't applied internally — apply offsets client-side if needed

**Architectural implication:** the C2 Terminal swarm controller knows the (x, y) of every UWB-tagged object in the arena via this parser — likely all 3 Hula drones + possibly the RoboMaster ground robots. We poll position from our control loop. Combined with the ArUco-on-robots clarification (5 am same day), Challenge 2B becomes: UWB-navigate near a tag → use Hula camera ArUco detection to confirm identity → snapshot.

**Open question for org:** do the RoboMaster ground robots have UWB tags? If yes, the entire Challenge 2B simplifies to "fly to known coords, detect ArUco for confirmation". If no, the Hula needs a search pattern + visual-only acquisition.

---

## 💬 Team chat — 2026-06-06 (A's annotation tool + K's ArUco-only realisation)

> **[6/6/2026 3:57 am] Abi Bas:** This is what I used to auto annotate image files for my past image detection project
> **[6/6/2026 3:58 am] Abi Bas:** So when we collect images we just spin around the item. We don't have to manually click many photos and upload to laptop and rename
>
> **[6/6/2026 2:00 pm] kai sheng:** coool
> **[6/6/2026 2:00 pm] kai sheng:** is it able to tell where the object is and draw bounding boxes around it?
> **[6/6/2026 2:01 pm] kai sheng:** lol roboflow alr has an inbuilt object detection system
> **[6/6/2026 2:01 pm] kai sheng:** here roboflow
> **[6/6/2026 2:01 pm] kai sheng:** my friend used roboflow previously for auto annotation
>
> **[6/6/2026 2:11 pm] Abi Bas:** Ohh nope, that's manual 😢 this is just helping us transfer and rename images to laptop faster
> **[6/6/2026 2:11 pm] Abi Bas:** But I can see if I can make an automated way to do that. So you want images with bounded box and text?
>
> **[6/6/2026 2:13 pm] kai sheng:** not exactly
> **[6/6/2026 2:13 pm] kai sheng:** coz when u annotate the images, u need to then export the dataset in yolo format, which contains info abt the classes and the location of the bounding boxes
> **[6/6/2026 2:14 pm] kai sheng:** i think can try this, it was recommended in my EE3703 course slides
> **[6/6/2026 2:14 pm] Abi Bas:** Alrights
> **[6/6/2026 2:15 pm] kai sheng:** I think we dunnid to capture images of the robomasters, but rather the aruco markers on them

**Key takeaway:** K independently lands on the ArUco-only insight from this morning's org clarification — "we dunnid to capture images of the robomasters, but rather the aruco markers on them". This confirms:
- A's YOLO pipeline is even more demoted: not just insurance, but possibly unnecessary if we standardise on ArUco markers (which are well-known fiducials, no training required).
- A's annotation-tool work (the auto image rename + transfer) is still useful for ANY image collection pass, but the RoboMaster-detection use case it was sized for is gone.
- Roboflow flagged as an alternative auto-annotation tool. K's EE3703 course slides reference it. Out of scope for finals (we have ArUco), but a known-good option if we ever need real YOLO labelling.

This aligns with our docs cascade today: A's RoboMaster YOLO is no longer critical-path. See [`CHALLENGE_BREAKDOWN.md`](CHALLENGE_BREAKDOWN.md) §Challenge 2B Detection + [`FINALS_PLAN.md`](FINALS_PLAN.md) §1 Workload split.

---

## 💬 Team chat — 2026-06-06 evening + 2026-06-07 early AM (YOLO killed, swarm search algo, laptop reliability)

> **[6/6/2026 9:35 pm] kai sheng:** im not sure if we are supposed to be working on any codes at the moment
> **[6/6/2026 9:35 pm] zhengboon:** They say prepare
>
> **[6/6/2026 9:36 pm] kai sheng:** i will try to work on the search algo for the hula swarm drones
> **[6/6/2026 9:36 pm] zhengboon:** I loaning my friend Intel depth camera if y'all test codes
>
> **[6/6/2026 10:13 pm] Abi Bas:** Nope not using yolo
>
> **[7/6/2026 0:13 am] Abi Bas:** facing some issues on my laptop. It's been repeating quite often

### Key takeaways
- **YOLO officially dead** per A's "Nope not using yolo" (6/6 22:13). A may still poke at TensorFlow / ImageAI / OpenCV alternatives, but those are exploratory — there is no YOLO insurance pipeline anymore. Confirms what the 6/6 5:00 am org clarification already pointed at: ArUco-only for RoboMaster detection.
- **A's laptop is a reliability risk** (7/6 00:13, "It's been repeating quite often"). Day-1 contingency: assume A may lose the ability to run anything off own laptop. Anything A is responsible for needs to be runnable from the org-provided dedicated laptop (C2 Terminal) or from another teammate's machine.
- **Backup depth camera secured** — Z is loaning a friend's Intel depth camera (close-to-D435, not the exact model) for code-test sessions before 10 June. Redundancy for the Realsense D430/D450 we'll get at venue.
- **K starting Hula swarm search algorithm** (6/6 21:36). This is the search-pattern piece for Challenge 2B (no map layout from org + RoboMaster ground robots may or may not carry UWB tags → visual search likely required). Tracks against the same open question already logged with the UWB API block above.
- **Still open:** do challenges run **parallel or sequential**? Z asked "are we doing 2 challenges at once or 1 then 2?" — unanswered in team chat, needs a fresh org ticket. Materially affects whether one team member can hand off between platforms or whether we need both running simultaneously.

---

## 🔥 Q&A — 2026-06-06 evening + 2026-06-07 AM (ArUco beside landing pads + marker size/dict + ticket etiquette)

> **FlyingExplorers_ChuaTseHui** — 6/6/2026 2:50 pm
> *(re: ArUco markers near landing pads for Challenge 2)*

> **BH2026ROBOVERSE** OP — 6/6/2026 9:34 pm
>
> Yes, there is aruco marker near the "landing" pad. You can use aruco marker for landing aid if you choose to. Do note the aruco marker is not that marker that is mentioned in the pyhulax that kinda of "auto" land.

> **RoyalRecruits** — 6/6/2026 6:15 pm
> *(re: ArUco marker physical size + dictionary)*

> **BH2026ROBOVERSE** OP — 6/6/2026 9:32 pm
>
> 20cm x 20cm. The exact dictionary will be announced on the day.

> **BH2026ROBOVERSE** OP — 6/6/2026 9:47 pm
>
> *(ticket etiquette)* Please close old support tickets and open fresh ones for new questions, so the queue stays prioritised.

**Confirms:**
- **ArUco markers exist beside Challenge 2 landing pads too** (not just Challenge 1's landing pads). Same fiducial-aided landing pattern on BOTH platforms — Hula uses `cv2.aruco` directly rather than the `pyhulax` landing-marker auto-land helper. The org explicitly distinguishes "this ArUco" from "the pyhulax auto-land marker" — they are different markers; we detect this ArUco ourselves and command the descent.
- **Marker physical size: 20cm × 20cm.** Useful range estimate: with the D435 RGB stream (640×480, ~70° HFOV), a 20cm marker spans a few hundred pixels at 1m and drops below ~30 px around 5–6m, where detection becomes unreliable. Mapping-drone scan altitude should keep markers inside that reliable detection band.
- **Exact ArUco dictionary will be announced ON THE DAY** — NOT pre-confirmed as `DICT_6X6_250`. The L2 sample code's `DICT_6X6_250` is illustrative, not authoritative. Our code must accept a runtime dictionary override and route it through `cv2.aruco.getPredefinedDictionary(...)`.
- **Ticket etiquette:** close stale support tickets; open a fresh ticket per new question.

**Current code state (audited 2026-06-07):**
- `mapping_drone/mapping.py`'s `ArucoDetector` accepts an `--aruco-dict` override (also exposed via `controller.py`). The lookup table currently supports **9 of the 20 possible dictionaries** the org could announce:
  - Supported (uppercase short-form, exact match): `4X4_50`, `4X4_100`, `4X4_250`, `5X5_250`, `6X6_50`, `6X6_100`, `6X6_250`, `6X6_1000`, `7X7_250`.
  - **Not supported (will raise `ValueError`):** `4X4_1000`; `5X5_50`, `5X5_100`, `5X5_1000`; `7X7_50`, `7X7_100`, `7X7_1000`; all four AprilTag variants (`APRILTAG_16h5`, `APRILTAG_25h9`, `APRILTAG_36h10`, `APRILTAG_36h11`).
  - **Also not normalised:** lowercase short-form (`6x6_250`), long-form (`DICT_6X6_250`), and hyphenated/alias variants are all rejected. The lookup is a strict `dict_name not in _ARUCO_DICTS` check on uppercase keys.
- **Action item before 10 June:** broaden `_ARUCO_DICTS` to cover all 16 ArUco sizes + 4 AprilTag variants, normalise case, and strip an optional `DICT_` prefix — otherwise there's a ~55% chance the announced dict is rejected outright at the venue. (Open as a fresh support ticket only if we need clarification on the announcement timing; the code fix is on us.)

**Still open with org (re-asked but unanswered):**
- STINKIES — *"what codes should we come prepared with on 10 June?"* (re-asked 6/6/2026 2:13 pm). Slides + L1–L5 imply heavy pre-prep; org has not given an explicit checklist.

---

## Source channels (for future scrapes)

| Channel | What lives there |
|---|---|
| `#general` | Announcements (qualifying results, schedule changes) |
| `#self-learning-materials` | Numbered learning materials (this scrape) |
| `#support-ticket` | Team-level Q&A — our open questions go here |
| `#tech-discussion` | Other teams' technical chatter; sometimes useful |
| `#coding-discussion` | Code-level Q&A |

If/when more materials drop, append below verbatim. Keep annotations at the bottom of each block.

---

## Update log

| Date | Update | By |
|---|---|---|
| 2026-06-02 | Initial: L1 + L2 (Hula swarm + fiducial markers) | Z |
| 2026-06-03 | L3 + L4 + L5 announced. Two-drone architecture revealed. L3 pulled (kolomee.py); L4 + L5 folders auth-locked. | Z |
| 2026-06-05 | Org corrected access rights — L4 + L5 now accessible. Org also dropped the Final Challenge slides deck. Consolidated this file as the canonical Discord scrape. | Z |
| 2026-06-05 (AM) | Confirmed University category. | Z |
| 2026-06-05 (PM) | YOLOv11 base + `_2.py` canonical conversion scripts; mapping-drone stack confirmed (Ubuntu 22.04 + ROS2 + OpenCV + RKNN NPU ~50 FPS); C2 Terminal = Windows host + Ubuntu 22.04 VM; mapping drone accessed from C2 via NoMachine; drones shared, dedicated laptop per team. | Z |
| 2026-06-06 (AM) | Major scope clarifications + new material drop: (1) Hula drones detect ArUco markers on ground robots (NOT YOLO) — A's training pivots away from RoboMaster YOLO. (2) Map layout NOT provided. (3) All 3 team members should attend both days. (4) New UWB API for Hula swarm released: `UWBParserThread.py` (USB-serial @921600, NOT ROS2). Pulled into `semifinal/uwb_api_hula_swarm/`. | Z |
| 2026-06-06 (PM) → 2026-06-07 (AM) | Three org drops captured: (1) ArUco markers exist beside Challenge 2 landing pads as landing aid (use `cv2.aruco` directly, not the pyhulax auto-land helper). (2) Marker size 20cm × 20cm; **exact dictionary announced on the day** — code must accept any of 16 ArUco + 4 AprilTag variants. (3) Org asks teams to close stale tickets and open fresh ones per question. Audit: `_ARUCO_DICTS` currently supports only 9/20 possible dictionaries — action item to broaden before 10 June. | Z |

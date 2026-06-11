# BrainHack 2026 RoboVerse — Discord/Telegram message capture (verbatim)

> Captured 2026-06-10. Source: organiser channel (BH2026ROBOVERSE / Bryan / 65drones1) + team Q&A.
> This file is a faithful copy of the messages the team pasted. Google Drive links are
> **listed but NOT downloaded** (auth-walled). The single non-Google link (Hula manual) is
> mirrored in `hula_manual_EN.md`. Extracted/actionable facts are in `KEY_UPDATES_for_mapping_drone.md`.

---

## Learning Materials 2 — Potential Detection Targets
**BH2026ROBOVERSE (OP) — 2/6/2026 9:34 am**

Practise training a object detection model. Besides that, detection of fiducial markers
(QR code, Aruco marker, AprilTag) are likely target. OpenCV has libraries to detect to
Aruco marker and read QR code.

Sample python code of detecting Aruco marker using OpenCV:

```python
import cv2

self.arucoDict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
self.parameters = cv2.aruco.DetectorParameters()
self.detector = cv2.aruco.ArucoDetector(self.arucoDict, self.parameters)

img = self.colorimage.copy()
corners, ids, _ = self.detector.detectMarkers(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
if ids is not None:
    cv2.aruco.drawDetectedMarkers(img, corners, ids)  # draw bounding box
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
            depth_mm = self.depth_image[center_v, center_u]  # distance to the image
            if depth_mm == 0:
                continue
            depth_m = float(depth_mm) / 1000.0
            X = (center_u - self.cx) * depth_m / self.fx  # convert to actual distance
            Y = (center_v - self.cy) * depth_m / self.fy
            Z = depth_m
```

---

## Learning Materials 1 — Hula Swarm Control
**BH2026ROBOVERSE (OP) — 2/6/2026 9:17 am**

Semi-Final need your team to code to control a swarm of Hula drones from a computer and do
detections. Please start to learn on how to do so by reading `huladola.py` in
<https://drive.google.com/drive/folders/19ni5GmRy8cBzX98TybsToQa4a17LbYi5?usp=drive_link> .
That py contains illustrate the core on how to do swarm control code and the link to a
website that describes all of the sdk.

**BH2026ROBOVERSE (OP) — 2/6/2026 9:18 am**
If you have hula, please try try. If you have hula but not sure how to hook hula drone to
wifi network, read the hula manual. If that manual not clear, drop a message and I will advise.

**BH2026ROBOVERSE (OP) — 2/6/2026 9:28 am**
Why am I sending out this? It is because Hula drone cannot work with MAVSDK. Therefore, I
send this out to gives heads-up.

**BH2026ROBOVERSE (OP) — 2/6/2026 9:45 am**
One more thing — Hula drone has camera. There is a gimbal attached to the camera. The
gimbal can be tilted down to face down with codes.

---

## Learning Material 3 — Controlling Mapping Drone using UWB and mavsdk
**BH2026ROBOVERSE (OP) — 3/6/2026 10:23 pm**

The mapping drone has a UWB tag that able to realtime update on the drone position within
the arena indoor. The tag still unable to let you use position command in mavsdk to control
it for safety and your competition efficiency. The control approach will be first query the
drone's current position (x-y-z), and then correct the difference between the current
location and desired position using velocity command. Study the reference code in this
<https://drive.google.com/drive/folders/1H6H6E06RHp5r97ch2_ZA1-rEIuHQHbxO?usp=drive_link> .
This code can give you strong basis.

> ⚠️ SUPERSEDED on 10/6 — see "USE set_position_ned" announcement below and
> `KEY_UPDATES_for_mapping_drone.md`.

---

## Learning Material 5 — Object Detection on mapping drone
**BH2026ROBOVERSE (OP) — 3/6/2026 10:33 pm**

YOLO is still an option for you to code code detection with your team. The compute module
has NPU that can speed up the YOLO detection. You need to convert the custom YOLO into ONNX
and to RKNN format. You can refer to this link for reference code to convert:
<https://drive.google.com/drive/folders/1JTDV6XueZWJyXB-L_yMaLAEum_lQntK3?usp=drive_link>
(These codes will be available on the machine provided by the organiser. It is the VM
within that machine as this requires ubuntu 22.04 again)
After convert, you would like to detect using the rknn model. The codes for detection can
be found here: <https://drive.google.com/drive/folders/1dVcath0iW3VGA3biqiCDCcZKRfzVPGEa?usp=drive_link>

---

## Learning Material 4 — Realsense Camera
**BH2026ROBOVERSE (OP) — 3/6/2026 10:27 pm**

Reference material: <https://drive.google.com/drive/folders/1auSeEagUslLpDi19UgkY6lYkQLlan-dv?usp=sharing>
The teams are to use the depth camera for depth assessment and to take photos, and more
importantly to do mapping. pyrealsense2 allows to write python to control the camera. The
big difference from gazebo is that pyrealsense allow to directly call it to locations.

---

## UWB API for hula swarm
**BH2026ROBOVERSE (OP) — 6/6/2026 11:28 am**

<https://drive.google.com/drive/folders/1zDKviPq21uByHwgymhtu-8G7j0YLncXN?usp=drive_link>
PLEASE read the pdf in that drive to find out more.

---

## IMPORTANT: Update on RoboVerse Challenge — the Final Challenge
**BH2026ROBOVERSE (OP) — 5/6/2026 5:07 am** (pinned)

Please study refer to
<https://docs.google.com/presentation/d/18INz16tbHPeHHWlFkEI6EKhlFgD6ZFKx/edit?usp=drive_link>
for details on rules and technical information of the Final Challenge.

---

## IMPORTANT: How to code and use the Drones at the Final
**BH2026ROBOVERSE (OP) — 5:40 am (10/6)**

Follow the steps closely in the pdf or ppt:
<https://drive.google.com/drive/folders/1yniPcwEI0FQVAV0wstxLEqeYlHhAsBRl?usp=drive_link>

---

## IMPORTANT: USE set_position_ned to navigate the mapping drone at Final.
**BH2026ROBOVERSE (OP) — 5:58 am (10/6)**

Refer to `moveit.py`
<https://drive.google.com/file/d/1luOUZJUX1sEygnVEvcejlteD_bcwUfIH/view?usp=drive_link>
on how to use `set_position_ned` to fly the mapping drone. Far more accurate and easier. I
do not recommend velocity flying in `kolomee.py` as now the mapping drone has enhanced
capability. Sorry.

> 🔴 MAJOR REVERSAL of the 3/6 Learning Material 3 guidance. See
> `KEY_UPDATES_for_mapping_drone.md`.

---

## IMPORTANT: Details brief on RoboVerse 26
**Bryan (OP) — Yesterday 9:25 pm**
Hi finalist, please see the attachment for details on the finals challenge. We look forward
to seeing you tomorrow. All the best! 🫡
Attachment: **Finals brief.pptx** (4.69 MB)

**Bryan (OP) — Yesterday 10:24 pm**
Hi all please read the finals brief. If you have any further questions we will answer it
during the Q&A tomorrow. Thank you!

**Bryan (OP) — 9:23 am** Hi all, we will start the briefing at 930am. Do be seated by then.

---

## Submission of concept
**65drones1 (OP) — 9:46 am (10/6)**
<https://docs.google.com/forms/u/0/d/e/1FAIpQLSdcG_BlsMwh_YN_aCOMQLjL0-A8T9XUI_ZSNC3rpUpDXSVeYw/formResponse>
Every team should submit one entry. (Brainhack Roboverse — concept explanation. Each team
allowed one entry; if multiple entries, only the first is considered.)

**65drones1 (OP) — 9:49 am** Deadline for submission of concept plan — **11 June, 1:30 pm**.

---

## IMPORTANT: IDs for Challenge 2 & 3 Aruco Markers
**BH2026ROBOVERSE (OP) — 5:50 am (10/6)**

Use DICT: `cv2.aruco.DICT_7X7_1000`
ids are **11, 45, 51, 67, 101**

- *BH2026ROBOVERSE changed the post title → "IMPORTANT: IDs for Challenge 1 Aruco Markers" (5:58 am)*
- *Bryan changed the post title → "IMPORTANT: IDs for Challenge 2 & 3 Aruco Markers" (9:29 am)*

**BH2026ROBOVERSE (OP) — 10:12 am (10/6)**
The location of markers are:
- `11` — x: **1.35 m**  y: **4.4 m**
- `45` — x: **1.3 m**  y: **7.85 m**   *(typo in source "1,3m")*
- `51` — x: **4.4 m**  y: **4.4 m**

---

## HULA Drone Instruction manual
**65drones1 (OP) — 10:14 am (10/6)**
<https://ds-api.hg-fly.net/manuals/Hula_EN.html>  *(non-Google — mirrored in `hula_manual_EN.md`)*

---

## Q&A thread (organiser ↔ teams)

**FlyingExplorers_ChuaTseHui — 4/6 9:20/9:21 am:** Can't access the Google drive links
(sharing permissions). → **BH2026ROBOVERSE — 5/6 4:45 am:** Corrected access rights. All
should be able to access now.

**FlyingExplorers — 5/6 5:13 pm:** During Finals, will each team test their code for
Challenges 1 and 2 on the actual drones before judging? Time slots / trial limits? Drones
shared or dedicated?
→ **BH2026ROBOVERSE — 5/6 6:55 pm:** All teams have testing time slots and use actual drones
during the testing slot. Announcement on testing time slot soon. **Drones will be shared**;
teams given time to load their codes onto mapping drones. All teams given **dedicated
laptops**. Task 2 and Task 3 can be executed/completed off the dedicated laptops.

**STINKIES_TanFengYuan — 5/6 10:20 pm:** Do all team members have to be there both days?
→ **BH2026ROBOVERSE — 5/6 10:22 pm:** Best that all members attend both days — plenty to do.

**STINKIES — 5/6 10:35 pm:** Prepare code before 10 & 11 June or start during? *(answered
later: come prepared)*

**FlyingExplorers — 5/6 10:45 pm:** Are the fiducial markers on the robot convoy aruco or
something else (QR)? Markers on the ground robot?
→ **BH2026ROBOVERSE — 6/6 5:00 am:** **Hula drone to detect aruco marker on ground robots.**

**WannabEngineers_MokeYiTing — 6/6 11:35 am:** Will we be given the map layout and
dimensions for finals?
→ **BH2026ROBOVERSE — 6/6 11:40 am:** **Map layout will not be provided.**

**STINKIES — 6/6 2:13 pm:** What codes should we come prepared with on 10 June? *(no direct
answer captured)*

**FlyingExplorers — 6/6 2:50 pm:** For challenge 2, will there be aruco markers beside the
helicopter pads (like challenge 1) for the Hula drone to detect for landing?
→ **BH2026ROBOVERSE — 6/6 9:34 pm:** Yes, there is aruco marker near the "landing" pad. You
can use aruco marker for landing aid if you choose to. Do note the aruco marker is **not**
that marker mentioned in the `pyhulax` that kind of "auto" land.

**FlyingExplorers — 7/6 6:03 pm:** For challenge 1, one task is for the Mapping Drone to
return a top-down depth map. Does it need a stereo output map (like the finalist challenge
slide) or can it be a matplotlib graph where each point plotted represents an obstacle
(like Supplementary Material 1, `top_down.py`)? *(no direct answer captured)*

**Calibruh_DylanLim — 7/6 8:15 pm:** How much time will each team be given for testing?
→ **BH2026ROBOVERSE — 8/6 12:17 pm:** We announce testing period details soon.

**FlyingExplorers — 7/6 8:56 pm:** Can we launch the drones at a specific location (and yaw
direction) of our choice for both challenge 1 and 2a, or is launch fixed by organisers?
→ **BH2026ROBOVERSE — 8/6 12:17 pm:** You can launch facing your desired direction, but
**takeoff point is the same for all**.

**STINKIES — 5/6 10:35 pm question re prep** → org guidance: come prepared (see 5/6 6:55 pm).

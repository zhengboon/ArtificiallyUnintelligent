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

(The Final Challenge slide deck — pulled into [`semifinal/final_challenge_slides.pptx`](final_challenge_slides.pptx). This is the **official rules + technical spec** document.)

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
| Detection model | YOLO via `pyhulax.video.YOLODetector` (.pt) | **YOLO via RKNN** on NPU |
| Connection | TCP/UDP over WiFi | **Serial** over `/dev/ttyS6:921600` |

### IMPORTANT clarification from L5 (5/6/2026)
The **RKNN conversion codes are on the org-provided machine**, not something we run on our own laptop. That machine runs a **Ubuntu 22.04 VM** (same constraint as qualifier). So:

- We bring K's `best.pt` (and ideally `best.onnx`) on a USB stick to the venue
- We use the org's VM to do the `.pt → .onnx → .rknn` conversion
- This greatly reduces our RKNN setup risk — we don't need to install `rknn-toolkit2` on our own laptops anymore
- BUT: we need to be familiar with the conversion workflow so we don't waste venue time figuring it out fresh

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
| 2026-06-05 (PM) | Confirmed University category. Org confirmed YOLOv11 (not v8) for custom training + `_2.py` variants of conversion scripts are canonical. Org confirmed drones are shared / testing slots TBA / dedicated laptops per team (= C2 Terminal). | Z |

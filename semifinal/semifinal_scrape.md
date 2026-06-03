# Semi-Final — Org Discord Scrape

Verbatim copy of org's Discord posts about the semi-final scope. Source: BH2026ROBOVERSE channel(s), posted 2026-06-01 (one day before this file was written).

Preserved as-is for reference. Do not edit the message bodies — they are the authoritative source of org intent.

---

## Learning Materials 1 — Hula Swarm Control

> **BH2026ROBOVERSE** OP — Yesterday at 9:17 am
>
> Semi-Final need your team to code to control a swarm of Hula drones from a computer and do detections. Please start to learn on how to do so by reading huladola.py in https://drive.google.com/drive/folders/19ni5GmRy8cBzX98TybsToQa4a17LbYi5?usp=drive_link . That py contains illustrate the core on how to do swarm control code and the link to a website that describes all of the sdk.

(Google Drive — folder titled "Hula Swarm Control and Video Streams". Contains `huladola.py` and `dola.py`. Both have been pulled into [`semifinal/huladola.py`](huladola.py) and [`semifinal/dola.py`](dola.py).)

> **BH2026ROBOVERSE** OP — Yesterday at 9:18 am
>
> If you have hula, please try try.
> If you have hula but not sure how to hook hula drone to wifi network, read the hula manual. If that manual not clear, drop a message and I will advise.

> **BH2026ROBOVERSE** OP — Yesterday at 9:28 am
>
> Why am I sending out this? It is because Hula drone cannot work with MAVSDK. Therefore, I send this out to gives heads-up.

> **BH2026ROBOVERSE** OP — Yesterday at 9:45 am
>
> One more thing - Hula drone has camera. There is a gimbal attached to the camera. The gimbal can be tilted down to face down with codes.
>
> We post learning materials for semi final as soon as when they are available. Stay Tune!

> **BH2026ROBOVERSE** OP — Yesterday at 9:42 am
>
> Though the semi final involves physical real drone and drone swarm control, your team have learnt most of it takes for semi final such as mapping, MAVSDK in python, and processing depth image and etc. Please revise the supplementary learning material 1 and 2 on mapping and coordinate frame transformation.
>
> We will post learning materials that are add-ons to qualifier - such as how to get get depth data from Realsense Depth Camera (D430 and D450) using pyrealsense2 python sdk, swarm control of hula drones, as and when the materaisl are available.

---

## Learning Materials 2 — Potential Detection Targets

> **BH2026ROBOVERSE** OP — Yesterday at 9:34 am
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

---

## Key takeaways (our annotations, not org's words)

1. **MAVSDK incompatible.** Our entire qualifier control stack does not carry over for low-level drone control. Wrapper logic + asyncio patterns can be adapted but the actual API calls must move to pyhulax.
2. **Drone has a tiltable gimbal** controlled by code — `set_camera_angle()` in pyhulax. Useful for floor-level targets.
3. **Revise Supp 1 + Supp 2.** They're in [`learning/Supplementary1.pdf`](../learning/Supplementary1.pdf) and [`learning/Supplementary2.pdf`](../learning/Supplementary2.pdf). Supp 1 covers VIO (relevant because Hula uses VIO for position). Supp 2 covers mapping + occupancy grid (occupancy-grid mapping was flagged as the natural Final Challenge next step).
4. **More materials coming.** Org will post `pyrealsense2` how-to + deeper Hula swarm material as separate drops. Watch the channel.
5. **Fiducial markers likely target.** ArUco / QR / AprilTag. OpenCV handles ArUco and QR; AprilTag needs `pip install apriltag` (or `pupil-apriltags`).
6. **Dictionary in sample:** `DICT_6X6_250`. Confirm at venue — may differ.
7. **Sample shows depth → 3D unprojection** using camera intrinsics `(fx, fy, cx, cy)`. Identical formula to what we used in qualifier mapping pipeline; reusable.

---

---

## Learning Materials 3 — Controlling Mapping Drone using UWB and mavsdk

> **BH2026ROBOVERSE** OP — 2026-06-03 22:23 (10:23 pm)
>
> The mapping drone has a UWB tag that able to realtime update on the drone position within the arena indoor. The tag still unable to let you use position command in mavsdk to control it for safety and your competition efficiency. The control approach will be first query the drone's current position (x-y-z), and then correct the difference between the current location and desired position using velocity command. Study the reference code in this https://drive.google.com/drive/folders/1H6H6E06RHp5r97ch2_ZA1-rEIuHQHbxO?usp=drive_link . This code can give you strong basis.

(Google Drive — folder contains [`kolomee.py`](learning_material_3_uwb/kolomee.py) which has been pulled in.)

**Big reveal:** there is a SEPARATE "mapping drone" distinct from the Hula swarm. It uses MAVSDK (not pyhulax), has a UWB tag for real-time indoor position, and is controlled via closed-loop velocity commands.

---

## Learning Materials 4 — Realsense Camera

> **BH2026ROBOVERSE** OP — 2026-06-03 22:27 (10:27 pm)
>
> Reference material: https://drive.google.com/drive/folders/1auSeEagUslLpDi19UgkY6lYkQLlan-dv?usp=sharing
>
> The teams are to use the depth camera for depth assessment and to take photos, and more importantly to do mapping. pyrealsense2 allows to write python to control the camera. The big difference from gazebo is that pyrealsense allow to directly call it to locations.

**Status:** Drive folder requires Google sign-in (org may have shared restrictively, or anti-scraping kicked in). Files not yet pulled. **Need to fetch manually.**

**Org's framing:** Realsense is used for (1) depth assessment, (2) photo capture, (3) **mapping** — confirming it's bundled with the **mapping drone**, not the Hula swarm. "Directly call it to locations" likely means: deproject pixel + depth + intrinsics → world point (using `rs.rs2_deproject_pixel_to_point()`), which our `aruco_realsense.py` prototype already does.

---

## Learning Materials 5 — Object Detection on mapping drone

> **BH2026ROBOVERSE** OP — 2026-06-03 22:33 (10:33 pm)
>
> YOLO is still an option for you to code code detection with your team. The compute module has NPU that can speed up the YOLO detection. But you need to convert the custom YOLO into ONNX and to RKNN format. You can refer to this link for reference code to convert: https://drive.google.com/drive/folders/1JTDV6XueZWJyXB-L_yMaLAEum_lQntK3?usp=drive_link
>
> After convert, you would like to detect using the rknn model. The codes for detection can be found here: https://drive.google.com/drive/folders/1dVcath0iW3VGA3biqiCDCcZKRfzVPGEa?usp=drive_link

**Status:** Both folders auth-gated. Files not yet pulled. **Need to fetch manually.**

**Big reveal:** the mapping drone is a **Rockchip-based SBC** (RKNN = Rockchip Neural Network format). Likely RK3588 / RK3568 onboard — Orange Pi 5 / Radxa Rock or similar. K's `best.pt` needs a two-step conversion: `.pt → .onnx → .rknn` to run on-board with NPU acceleration.

**Implication for A's training:** K can keep training PyTorch YOLO; the conversion step is independent. But the **target output format** for deployment is RKNN, not `.pt`.

---

## Updated mental model — TWO drone platforms

| | **Hula swarm** | **Mapping drone** |
|---|---|---|
| Quantity | Multiple (swarm) | One (singular) |
| SDK | `pyhulax` | `mavsdk` (Python) |
| Position source | Optical flow + optional QR | **UWB tag** (real-time arena coords) |
| Position interface | `drone.get_position()` | **ROS2 topic `uwb_tag` PoseStamped subscriber** |
| Control approach | High-level `move_to(x,y,z)` | **Velocity setpoints** (`set_velocity_ned`), P-controller loop |
| Depth camera | Built-in optical flow | **Realsense D430/D450/D435** |
| Compute | Onboard flight controller | **Compute module with NPU** (Rockchip) |
| Detection model | YOLO via `pyhulax.video.YOLODetector` (.pt) | **YOLO via RKNN** (NPU-accelerated, .pt → .onnx → .rknn) |
| Connection | TCP/UDP over WiFi | **Serial over `/dev/ttyS6:921600`** (per kolomee.py) |
| What it does | Search the arena, find targets | **Build map + photos + collected depth, possibly precision-place** |

So the team likely splits effort:
- **Mapping drone** does the careful mapping with Realsense + UWB precision + RKNN YOLO on-board
- **Hula swarm** does broad-area searching with multiple drones in parallel

---

## Source channels (for future scrapes)

| Channel | What lives there |
|---|---|
| `#general` | Announcements (qualifying results, schedule changes) |
| `#self-learning-materials` | Numbered learning materials (this scrape) |
| `#support-ticket` | Team-level Q&A — our open questions go here |
| `#tech-discussion` | Other teams' technical chatter; sometimes useful |
| `#coding-discussion` | Code-level Q&A |

If/when more semi-final materials drop, append to this file under a new `## Learning Materials N — <title>` section. Keep verbatim. Annotations only at the bottom of each block.

---

## Update log

| Date | Update | By |
|---|---|---|
| 2026-06-02 | Initial scrape: Learning Materials 1 + 2 (Hula swarm + fiducial markers) | Z |
| 2026-06-03 | Added Learning Materials 3 + 4 + 5. Two-drone architecture revealed (Hula swarm + mapping drone with UWB+Realsense+NPU). L3 file pulled (`kolomee.py`); L4 + L5 folders auth-gated, need manual download. | Z |

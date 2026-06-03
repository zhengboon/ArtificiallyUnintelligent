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

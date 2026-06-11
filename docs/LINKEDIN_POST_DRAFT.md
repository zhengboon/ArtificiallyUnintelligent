# LinkedIn post drafts

Three flavours. Pick one, tweak, post. The shorter ones are LinkedIn-native; the longer one is more about-page-style if you want to use it on a personal site too.

---

## Version A — short & punchy (~150 words)

Spent the last week with two teammates building a two-stage autonomous drone mission for BrainHack 2026's RoboVerse Drone Challenge at Marina Bay Sands.

A mapping drone surveys the cage — depth camera + UWB + onboard Orange Pi running our Python control loop over MAVSDK. Output: a top-down depth map and a JSON listing each landing pad's world coordinates and validity.

That JSON feeds a swarm of three Hula drones in stage 2. The swarm lands on the valid pads, then sweeps the cage to find and snapshot five RoboMaster ground robots — each carrying an ArUco marker.

We optimised for *not crashing*. Every critical path has a fallback (pose, camera, dictionary, transport), and the safety watchdogs live inside the control loop rather than on a checklist.

Writeup with the architecture diagrams: [link to GitHub Pages]

#robotics #autonomy #drones #brainhack #computervision

---

## Version B — story-driven (~250 words)

Five days. Three people. Two drones. One coordinate world.

That's the elevator pitch for what my team and I built for BrainHack 2026's RoboVerse Drone Challenge at Marina Bay Sands this week.

**Stage 1: Reconnaissance.** A mapping drone — Realsense depth camera, UWB localisation, MAVSDK over serial to the PX4 flight controller — flies a deterministic lawnmower sweep over a netted cage. On each frame it deprojects depth into a top-down occupancy grid, scans for ArUco landing-pad markers, and writes a machine-readable JSON of pad coordinates and validity. Output is a judge-readable artifact AND the input contract for stage 2.

**Stage 2: Deployment & Ambush.** A swarm of three Hula drones consumes that JSON, lands on the three valid pads, then transitions into a coordinated 360° spin-scan hunt for five RoboMaster ground robots, each carrying an ArUco marker.

The most interesting engineering decisions weren't the drone control loops — they were the failure modes. Indoor UWB frames are notoriously ambiguous, so we built a survey tool that *measures* the frame at venue setup instead of assuming it. The cage walls are see-through netting, so we used deterministic sweeps instead of SLAM (depth sensors hallucinate through net). The official ArUco dictionary was announced on the day, so the mapping pipeline scans *two* dictionaries every frame.

Crash = no re-assessment. So safety lives in the control loop, not on a checklist.

Full architecture writeup: [link to GitHub Pages]

#robotics #autonomy #drones #brainhack #computervision #engineering

---

## Version C — leading with people (~200 words)

Spent the last week with two friends building a fully autonomous two-stage drone mission for BrainHack 2026.

Z (me) on the mapping drone — perception, control, the safety loop.
K on the Hula swarm — three-drone coordination, central video aggregation.
A on operations + concept — runbook, on-the-day judge interface.

Three people, one repo, two challenges, one coordinate world.

The mission: a mapping drone surveys a netted cage, identifies five ArUco-marked landing pads, classifies each as valid or invalid for landing. Then three Hula drones land on the valid pads and hunt five RoboMaster ground robots, each carrying its own ArUco marker. Snapshots of each robot's marker are the tagging artifact.

Five days of prep, ~140 commits, multi-pass adversarial code reviews that caught real silent killers (a validity rule that classified every pad as "invalid", a documented CLI flag that didn't actually exist, an altitude default above the cage net).

Result: every fallback we built got exercised, every assumption we measured rather than guessed paid off, and we left the venue with the team intact and the drone unbent.

Architecture writeup: [link to GitHub Pages]

#robotics #autonomy #drones #brainhack #teamwork

---

## Notes on placement

- Replace `[link to GitHub Pages]` with your live URL once Pages is enabled. Format: `https://zhengboon.github.io/ArtificiallyUnintelligent/`
- LinkedIn truncates after the first ~3 lines on mobile — make sure your most interesting hook is at the top.
- Photos welcome: a drone shot, a screenshot of the architecture diagram, or a venue photo are all good. LinkedIn algorithm prefers media-attached posts.
- Tag the org if appropriate: `#BrainHack` is widely used.
- Posting time: SG / Asia evening (~8-10pm SGT) is the sweet spot for SG-based reach.

If you want a version that's more / less technical, a four-image carousel script, or a thread for X / Mastodon, say so.

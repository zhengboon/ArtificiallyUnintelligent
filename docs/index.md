---
layout: default
title: Home
description: A two-stage autonomous drone mission for BrainHack 2026 — mapping drone reconnaissance + Hula swarm deployment & ambush.
---

<section class="hero">
  <div class="hero-row">
    <div class="hero-text">
      <span class="hero-eyebrow">BrainHack 2026 · RoboVerse · University Finals</span>
      <h1>Two drones. One coordinate world.</h1>
      <p class="lead">A mapping drone surveys the arena and classifies the landing pads. Then a swarm of three Hula drones lands on the valid pads and hunts a convoy of ground robots. Two challenges, one intelligence-driven pipeline.</p>
      <div class="hero-actions">
        <a class="btn btn-primary" href="{{ '/architecture' | relative_url }}">See the architecture</a>
        <a class="btn btn-secondary" href="https://github.com/zhengboon/ArtificiallyUnintelligent" target="_blank" rel="noopener">View on GitHub</a>
      </div>
    </div>
    <figure class="hero-photo">
      <img src="images/hero-team.jpg" alt="The ArtificiallyUnintelligent team in DSTA BrainHack jackets, three teammates standing under the lit BRAINHACK arch at Marina Bay Sands Expo Level 4 on Day 1 of the finals">
      <figcaption class="hero-photo-caption">ArtificiallyUnintelligent · BRAINHACK arch · MBS Expo L4</figcaption>
    </figure>
  </div>
</section>

## What we built

Two operational halves of a modular, redundant autonomy stack:

> **Challenge 1 — Reconnaissance**
> A mapping drone (Realsense + UWB + PX4 over MAVSDK) flies a deterministic lawnmower sweep at controlled altitude, deprojects depth into a top-down occupancy grid, scans every frame for ArUco markers in two dictionaries, and writes a machine-readable `landing_pads.json` describing each pad's world coordinates and validity.

> **Challenge 2 — Deployment & Ambush**
> A swarm of three Hula drones takes the recon output, lands on three valid pads, then transitions into a wall-following + 360° spin-scan hunt for five RoboMaster ground robots — each carrying an ArUco marker — with all video aggregated centrally for detection.

Both stages share the **same arena UWB frame** (origin = centre). The C1 → C2 handoff is a coordinate lookup, not a re-survey.

---

## Five design principles

| # | Principle | What it prevents |
|---|---|---|
| **1** | Intelligence drives the strike | Building C1 and C2 independently and re-surveying twice |
| **2** | Coverage over cleverness | Reactive-sensing failures from see-through netting |
| **3** | Degrade, don't fail | Single-point hardware drops ending the run |
| **4** | Safe-first | Crash → zero points → no recovery |
| **5** | Frame discipline | Silent axis errors that look like "everything is wrong" |

[Full design rationale →]({{ '/principles' | relative_url }})

---

## At a glance

| | Challenge 1 — Mapping | Challenge 2 — Swarm |
|---|---|---|
| **Hardware** | 1 mapping drone · Realsense D430/D450 · UWB tag · RKNN NPU | 3 Hula drones · central video aggregation |
| **Pose** | FC-NED fused ↔ UWB ENU→NED (auto-switching) | UWB serial (`tag_id → x,y`) |
| **Control** | MAVSDK offboard · velocity setpoints @ 0.3 m/s cap | pyhula `send_manual_control` |
| **Detection** | `cv2.aruco` (DICT_7×7_1000 + 6×6_250) on depth-deprojected frames | ArUco on aggregated drone video |
| **Path** | Lawnmower sweep · centred-origin waypoints | Wall-follow + 360° spin-scan |
| **Output** | `top_down.png` + `landing_pads.json` (judge artifact) | Snapshot per detected RoboMaster |

[System architecture →]({{ '/architecture' | relative_url }})

---

## By the numbers

<div class="stats">
  <div class="stat"><span class="stat-num">5</span><span class="stat-label">Days of prep</span></div>
  <div class="stat"><span class="stat-num">3</span><span class="stat-label">Teammates</span></div>
  <div class="stat"><span class="stat-num">2</span><span class="stat-label">Drone platforms</span></div>
  <div class="stat"><span class="stat-num">~140</span><span class="stat-label">Commits</span></div>
  <div class="stat"><span class="stat-num">~3.5k</span><span class="stat-label">C1 LOC</span></div>
  <div class="stat"><span class="stat-num">20</span><span class="stat-label">ArUco dicts supported</span></div>
  <div class="stat"><span class="stat-num">5</span><span class="stat-label">Safety watchdogs</span></div>
  <div class="stat"><span class="stat-num">11</span><span class="stat-label">Org clarifications handled live</span></div>
</div>

---

## Dive deeper

- [**Architecture**]({{ '/architecture' | relative_url }}) — full system diagram, module-by-module
- [**Challenge 1 — Mapping drone**]({{ '/c1-mapping' | relative_url }}) — algorithms + flight envelope + redundancy
- [**Challenge 2 — Hula swarm**]({{ '/c2-swarm' | relative_url }}) — deploy + hunt + central detection
- [**Design principles**]({{ '/principles' | relative_url }}) — the five rules driving every decision
- [**Engineering log**]({{ '/engineering' | relative_url }}) — trade-offs, prep-week surprises, lessons
- [**Gallery**]({{ '/gallery' | relative_url }}) — venue, team, hardware, swarm controller in the wild

---

## Team

**ArtificiallyUnintelligent** — three-person team, University category.

| | Role |
|---|---|
| **Z** | Challenge 1 mapping drone · cross-platform glue · runbook |
| **K** | Challenge 2 Hula swarm controller · on-day pilot |
| **A** | Operations · concept submission · judge interface |

<p align="center">
<img src="images/team.jpg" alt="ArtificiallyUnintelligent team in DSTA BrainHack jackets in front of the RoboVerse backdrop at MBS Expo Level 4, one teammate holding up a printed ArUco marker, another holding a RoboMaster ground robot, with the rest of the team's hardware staged on the platform in front of them">
<br><sub><i>The team in front of the RoboVerse backdrop — one ArUco marker, one RoboMaster, and the rest of the day's hardware on the platform</i></sub>
</p>

---

## Recognition

DSTA issued every team member a verifiable digital **University Finalist** credential via Credsverse — awarded 16 June 2026, signed by Ng Chad-Son, Chief Executive of DSTA. Click any card to verify on Credsverse.

<div class="cred-grid">
  <a class="cred-card" href="https://credsverse.com/credentials/b5c1044e-0b4f-4f63-b3cc-ebe811ecb6c5?recipient=true" target="_blank" rel="noopener">
    <img src="images/credential-dsta-brainhack2026-zheng.webp" alt="BrainHack 2026 RoboVerse Certificate of Participation — University Finalist, awarded to Tan Zheng Boon on 16 June 2026 by DSTA">
    <div class="cred-body">
      <div class="cred-name">Tan Zheng Boon</div>
      <div class="cred-meta">BrainHack 2026 · RoboVerse · University Finalist</div>
      <span class="cred-verify">Verify on Credsverse →</span>
    </div>
  </a>
  <a class="cred-card" href="https://credsverse.com/credentials/d6868a57-8741-47a8-b6b7-4feeac665ce9" target="_blank" rel="noopener">
    <img src="images/credential-dsta-brainhack2026-kai.webp" alt="BrainHack 2026 RoboVerse Certificate of Participation — University Finalist, awarded to Bock Kai Sheng on 16 June 2026 by DSTA">
    <div class="cred-body">
      <div class="cred-name">Bock Kai Sheng</div>
      <div class="cred-meta">BrainHack 2026 · RoboVerse · University Finalist</div>
      <span class="cred-verify">Verify on Credsverse →</span>
    </div>
  </a>
  <a class="cred-card" href="https://credsverse.com/credentials/6a469f62-90b4-40dc-a9a1-1b009fd67acd" target="_blank" rel="noopener">
    <img src="images/credential-dsta-brainhack2026-abi.webp" alt="BrainHack 2026 RoboVerse Certificate of Participation — University Finalist, awarded to Abirami Baskaran on 16 June 2026 by DSTA">
    <div class="cred-body">
      <div class="cred-name">Abirami Baskaran</div>
      <div class="cred-meta">BrainHack 2026 · RoboVerse · University Finalist</div>
      <span class="cred-verify">Verify on Credsverse →</span>
    </div>
  </a>
</div>

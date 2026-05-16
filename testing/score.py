#!/usr/bin/env python3
"""
testing/score.py — RoboVerse Qualifier Scorer
==============================================
Takes a controller run log + maze ground-truth JSON and computes the
predicted qualifier score.

Usage:
    python3 score.py --log logs/run_20260522_140000/detections.jsonl \
                     --map testing/maze_set/maze_001.json

    # Or pipe a quick stub test:
    python3 score.py --test

Output:
    A score report printed to stdout. Use --json for machine-readable output.

Run log format (one JSON object per line, .jsonl):
    {"t": 12.4, "class": "yellow_barrel", "north": 4.1, "east": 8.3, "down": -1.0, "conf": 0.87}
    {"t": 31.0, "class": "red_barrel",    "north": 16.2, "east": 4.0, "down": -3.5, "conf": 0.91}
    {"t": 45.2, "class": "toxic_barrel",  "north": 20.0, "east": 12.0, "down": -3.5, "conf": 0.76}

    Fields:
      t      — seconds elapsed since run start (float)
      class  — "yellow_barrel", "red_barrel", or "toxic_barrel"
      north  — NED north coordinate of detection (metres, float)
      east   — NED east coordinate of detection (metres, float)
      down   — NED down coordinate of detection (metres, float; negative = above ground)
      conf   — YOLO confidence score 0.0–1.0

Maze ground-truth JSON format (from maze_gen/output/*.json):
    {
      "yellow_barrels": [
        {"id": "y1", "north": 4.0, "east": 8.0},
        {"id": "y2", "north": 20.0, "east": 4.0}
      ],
      "red_barrels": [
        {"id": "r1", "north": 8.0, "east": 16.0},
        {"id": "r2", "north": 28.0, "east": 24.0}
      ],
      "toxic_barrels": [
        {"id": "t1", "north": 20.0, "east": 12.0}
      ]
    }

    Note: barrel positions are 2D (north, east only). Height/down is not used
    for ground-truth matching because yellow = always ground, red = always elevated.
    Matching uses horizontal distance only (see MATCH_RADIUS_M below).
"""

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Constants — adjust if qualifier rules change
# ---------------------------------------------------------------------------

POINTS_YELLOW = 50          # points per unique yellow barrel detected
POINTS_RED = 100            # points per unique red barrel detected
BONUS_POINTS_PER_TICK = 20  # bonus points per 30-second tick under 5 min
BONUS_TICK_SECONDS = 30     # tick size in seconds
BONUS_CUTOFF_SECONDS = 300  # 5 minutes — must finish ALL of one colour by here

MATCH_RADIUS_M = 1.5        # detections within this radius of a ground-truth
                             # barrel = same barrel (deduplication)

RUN_DURATION_SECONDS = 600  # 10 minutes total


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Detection:
    t: float
    cls: str          # "yellow_barrel", "red_barrel", "toxic_barrel"
    north: float
    east: float
    down: float
    conf: float


@dataclass
class GroundTruthBarrel:
    barrel_id: str
    north: float
    east: float
    cls: str          # "yellow_barrel" or "red_barrel"
    matched_at: Optional[float] = None   # timestamp of first matching detection
    matched_detection_index: Optional[int] = None


@dataclass
class ScoreReport:
    # Barrel counts
    yellow_barrels_in_map: int = 0
    red_barrels_in_map: int = 0
    toxic_barrels_in_map: int = 0

    yellow_detected: int = 0
    red_detected: int = 0
    toxic_false_positives: int = 0      # toxic barrels incorrectly detected

    # Unmatched detections (no ground-truth barrel nearby — possible false positives)
    yellow_unmatched: int = 0
    red_unmatched: int = 0

    # Timing
    all_yellow_time: Optional[float] = None   # seconds when last yellow was found
    all_red_time: Optional[float] = None      # seconds when last red was found

    # Score breakdown
    base_yellow_points: int = 0
    base_red_points: int = 0
    bonus_yellow_points: int = 0
    bonus_red_points: int = 0
    total_score: int = 0

    # Eligibility
    eligible: bool = False   # True if ≥1 yellow AND ≥1 red detected

    # Warnings
    warnings: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def horizontal_distance(d: Detection, gt: GroundTruthBarrel) -> float:
    """Euclidean distance in the horizontal (north-east) plane only."""
    return math.sqrt((d.north - gt.north) ** 2 + (d.east - gt.east) ** 2)


def load_run_log(path: str) -> list[Detection]:
    """Load a .jsonl run log file. Each line is one detection JSON object."""
    detections = []
    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                obj = json.loads(line)
                detections.append(Detection(
                    t=float(obj["t"]),
                    cls=str(obj["class"]),
                    north=float(obj["north"]),
                    east=float(obj["east"]),
                    down=float(obj.get("down", 0.0)),
                    conf=float(obj.get("conf", 1.0)),
                ))
            except (KeyError, ValueError) as e:
                print(f"[WARN] Line {lineno} in log skipped: {e}", file=sys.stderr)
    detections.sort(key=lambda d: d.t)
    return detections


def load_maze(path: str) -> tuple[list[GroundTruthBarrel], int]:
    """
    Load a maze ground-truth JSON.
    Returns (list_of_gt_barrels, toxic_count).
    """
    with open(path) as f:
        data = json.load(f)

    barrels = []
    for b in data.get("yellow_barrels", []):
        barrels.append(GroundTruthBarrel(
            barrel_id=b["id"], north=b["north"], east=b["east"], cls="yellow_barrel"
        ))
    for b in data.get("red_barrels", []):
        barrels.append(GroundTruthBarrel(
            barrel_id=b["id"], north=b["north"], east=b["east"], cls="red_barrel"
        ))

    toxic_count = len(data.get("toxic_barrels", []))
    return barrels, toxic_count


def compute_bonus(finish_time: Optional[float]) -> int:
    """
    Given the time (seconds) when all barrels of one colour were found,
    return the speed bonus points.
    Returns 0 if finish_time is None or >= BONUS_CUTOFF_SECONDS.
    """
    if finish_time is None or finish_time >= BONUS_CUTOFF_SECONDS:
        return 0
    seconds_saved = BONUS_CUTOFF_SECONDS - finish_time
    ticks = int(seconds_saved // BONUS_TICK_SECONDS)
    return ticks * BONUS_POINTS_PER_TICK


def score_run(detections: list[Detection],
              gt_barrels: list[GroundTruthBarrel],
              toxic_count: int) -> ScoreReport:
    """
    Core scoring logic. Matches detections to ground-truth barrels,
    deduplicates, computes base + bonus points.
    """
    report = ScoreReport()

    report.yellow_barrels_in_map = sum(1 for b in gt_barrels if b.cls == "yellow_barrel")
    report.red_barrels_in_map    = sum(1 for b in gt_barrels if b.cls == "red_barrel")
    report.toxic_barrels_in_map  = toxic_count

    yellow_gt = [b for b in gt_barrels if b.cls == "yellow_barrel"]
    red_gt    = [b for b in gt_barrels if b.cls == "red_barrel"]

    # Process detections in time order
    for i, det in enumerate(detections):

        if det.cls == "toxic_barrel":
            # Toxic barrels: no points awarded, but count false positives
            # (detecting a toxic barrel wastes time; no direct score penalty
            #  per current rules, but we flag it as a warning)
            report.toxic_false_positives += 1
            continue

        if det.cls not in ("yellow_barrel", "red_barrel"):
            report.warnings.append(
                f"t={det.t:.1f}s: Unknown class '{det.cls}' — skipped."
            )
            continue

        # Choose the correct ground-truth pool
        gt_pool = yellow_gt if det.cls == "yellow_barrel" else red_gt

        # Find the closest unmatched ground-truth barrel within MATCH_RADIUS_M
        best_gt = None
        best_dist = float("inf")
        for gt in gt_pool:
            if gt.matched_at is not None:
                continue   # already confirmed — skip
            dist = horizontal_distance(det, gt)
            if dist < best_dist:
                best_dist = dist
                best_gt = gt

        if best_gt is not None and best_dist <= MATCH_RADIUS_M:
            # Matched — mark this ground-truth barrel as found
            best_gt.matched_at = det.t
            best_gt.matched_detection_index = i
        else:
            # No nearby ground-truth barrel — unmatched detection
            # Could be a false positive or a barrel the maze JSON doesn't list
            if det.cls == "yellow_barrel":
                report.yellow_unmatched += 1
            else:
                report.red_unmatched += 1

    # Count confirmed detections
    report.yellow_detected = sum(1 for b in yellow_gt if b.matched_at is not None)
    report.red_detected    = sum(1 for b in red_gt    if b.matched_at is not None)

    # Timing: when were ALL barrels of each colour confirmed?
    if report.yellow_detected == report.yellow_barrels_in_map and report.yellow_barrels_in_map > 0:
        report.all_yellow_time = max(
            b.matched_at for b in yellow_gt if b.matched_at is not None
        )
    if report.red_detected == report.red_barrels_in_map and report.red_barrels_in_map > 0:
        report.all_red_time = max(
            b.matched_at for b in red_gt if b.matched_at is not None
        )

    # Base points
    report.base_yellow_points = report.yellow_detected * POINTS_YELLOW
    report.base_red_points    = report.red_detected    * POINTS_RED

    # Bonus points
    report.bonus_yellow_points = compute_bonus(report.all_yellow_time)
    report.bonus_red_points    = compute_bonus(report.all_red_time)

    # Total
    report.total_score = (
        report.base_yellow_points +
        report.base_red_points +
        report.bonus_yellow_points +
        report.bonus_red_points
    )

    # Eligibility (University category)
    report.eligible = (report.yellow_detected >= 1 and report.red_detected >= 1)

    # Warnings
    if report.toxic_false_positives > 0:
        report.warnings.append(
            f"{report.toxic_false_positives} toxic barrel detection(s) — no points, "
            f"but wasted camera time. Check K's confidence threshold."
        )
    if report.yellow_unmatched > 0:
        report.warnings.append(
            f"{report.yellow_unmatched} yellow detection(s) had no matching ground-truth barrel "
            f"within {MATCH_RADIUS_M} m. Possible false positives, or maze JSON is incomplete."
        )
    if report.red_unmatched > 0:
        report.warnings.append(
            f"{report.red_unmatched} red detection(s) had no matching ground-truth barrel "
            f"within {MATCH_RADIUS_M} m. Possible false positives, or maze JSON is incomplete."
        )
    if not report.eligible:
        report.warnings.append(
            "⚠️  NOT ELIGIBLE for Qualifier ranking — need ≥1 yellow AND ≥1 red barrel detected."
        )

    return report


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def format_report(report: ScoreReport, gt_barrels: list[GroundTruthBarrel]) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("  ROBOVERSE QUALIFIER — PREDICTED SCORE REPORT")
    lines.append("=" * 60)

    lines.append("\n📦 BARRELS IN MAP")
    lines.append(f"  Yellow barrels:  {report.yellow_barrels_in_map}")
    lines.append(f"  Red barrels:     {report.red_barrels_in_map}")
    lines.append(f"  Toxic barrels:   {report.toxic_barrels_in_map}  (no points — do NOT detect)")

    lines.append("\n🎯 DETECTIONS")
    lines.append(f"  Yellow detected: {report.yellow_detected} / {report.yellow_barrels_in_map}")
    lines.append(f"  Red detected:    {report.red_detected} / {report.red_barrels_in_map}")
    if report.toxic_false_positives:
        lines.append(f"  Toxic hits:      {report.toxic_false_positives}  ← false positives!")

    lines.append("\n⏱  TIMING")
    if report.all_yellow_time is not None:
        t = report.all_yellow_time
        lines.append(f"  All yellows found at: {t:.1f}s ({t/60:.1f} min)")
        saved = BONUS_CUTOFF_SECONDS - t
        if saved > 0:
            lines.append(f"  → {saved:.0f}s under 5 min = {int(saved // BONUS_TICK_SECONDS)} bonus tick(s)")
    else:
        lines.append("  All yellows found: NO  (not all yellow barrels detected)")

    if report.all_red_time is not None:
        t = report.all_red_time
        lines.append(f"  All reds found at:    {t:.1f}s ({t/60:.1f} min)")
        saved = BONUS_CUTOFF_SECONDS - t
        if saved > 0:
            lines.append(f"  → {saved:.0f}s under 5 min = {int(saved // BONUS_TICK_SECONDS)} bonus tick(s)")
    else:
        lines.append("  All reds found:    NO  (not all red barrels detected)")

    lines.append("\n💰 SCORE BREAKDOWN")
    lines.append(f"  Yellow base:   {report.yellow_detected} × {POINTS_YELLOW} = {report.base_yellow_points} pts")
    lines.append(f"  Red base:      {report.red_detected} × {POINTS_RED} = {report.base_red_points} pts")
    lines.append(f"  Yellow bonus:  {report.bonus_yellow_points} pts")
    lines.append(f"  Red bonus:     {report.bonus_red_points} pts")
    lines.append(f"  {'─' * 30}")
    lines.append(f"  TOTAL:         {report.total_score} pts")

    lines.append("\n🏁 ELIGIBILITY")
    if report.eligible:
        lines.append("  ✅ ELIGIBLE for Qualifier ranking")
    else:
        lines.append("  ❌ NOT ELIGIBLE — need ≥1 yellow AND ≥1 red")

    if report.warnings:
        lines.append("\n⚠️  WARNINGS")
        for w in report.warnings:
            lines.append(f"  • {w}")

    lines.append("\n📋 PER-BARREL DETAIL")
    for b in gt_barrels:
        if b.matched_at is not None:
            status = f"✅ found at t={b.matched_at:.1f}s"
        else:
            status = "❌ missed"
        lines.append(f"  [{b.cls[:1].upper()}] {b.barrel_id:6s}  ({b.north:.1f}N, {b.east:.1f}E)  {status}")

    lines.append("=" * 60)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Built-in stub test
# ---------------------------------------------------------------------------

STUB_LOG = [
    # Yellow barrels detected early
    {"t": 45.0,  "class": "yellow_barrel", "north": 4.1,  "east": 8.2,  "down": -1.0, "conf": 0.91},
    {"t": 78.5,  "class": "yellow_barrel", "north": 20.1, "east": 3.9,  "down": -1.1, "conf": 0.85},
    # Duplicate detection of y1 — should be deduped (same barrel, within 1.5 m)
    {"t": 90.0,  "class": "yellow_barrel", "north": 4.3,  "east": 8.0,  "down": -1.0, "conf": 0.88},
    # Red barrel detected in pass 2
    {"t": 340.0, "class": "red_barrel",    "north": 8.1,  "east": 16.0, "down": -3.5, "conf": 0.93},
    # Toxic barrel — false positive
    {"t": 410.0, "class": "toxic_barrel",  "north": 20.0, "east": 12.0, "down": -3.5, "conf": 0.76},
    # Second red barrel missed (not in log)
]

STUB_MAP = {
    "yellow_barrels": [
        {"id": "y1", "north": 4.0,  "east": 8.0},
        {"id": "y2", "north": 20.0, "east": 4.0},
    ],
    "red_barrels": [
        {"id": "r1", "north": 8.0,  "east": 16.0},
        {"id": "r2", "north": 28.0, "east": 24.0},
    ],
    "toxic_barrels": [
        {"id": "t1", "north": 20.0, "east": 12.0},
    ],
}

def run_stub_test():
    """Run scorer against hard-coded stub data and print report."""
    print("[STUB TEST] Running with built-in example data...\n")

    import tempfile, os

    # Write stub log to a temp .jsonl file
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as lf:
        for entry in STUB_LOG:
            lf.write(json.dumps(entry) + "\n")
        log_path = lf.name

    # Write stub map to a temp .json file
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as mf:
        json.dump(STUB_MAP, mf)
        map_path = mf.name

    try:
        detections = load_run_log(log_path)
        gt_barrels, toxic_count = load_maze(map_path)
        report = score_run(detections, gt_barrels, toxic_count)
        print(format_report(report, gt_barrels))

        # Assertions for CI
        assert report.yellow_detected == 2,  f"Expected 2 yellows, got {report.yellow_detected}"
        assert report.red_detected == 1,     f"Expected 1 red, got {report.red_detected}"
        assert report.eligible == True,      "Expected eligible"
        assert report.base_yellow_points == 100
        assert report.base_red_points == 100
        assert report.bonus_yellow_points > 0, "Expected yellow speed bonus (found at ~78s)"
        assert report.toxic_false_positives == 1
        print("\n✅ All stub assertions passed.")
    finally:
        os.unlink(log_path)
        os.unlink(map_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="RoboVerse Qualifier scorer — predicts score from a run log + maze JSON."
    )
    parser.add_argument("--log", "-l", help="Path to run log (.jsonl)")
    parser.add_argument("--map", "-m", help="Path to maze ground-truth JSON")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON instead of pretty text")
    parser.add_argument("--test", action="store_true", help="Run built-in stub test (no files needed)")
    args = parser.parse_args()

    if args.test:
        run_stub_test()
        return

    if not args.log or not args.map:
        parser.error("--log and --map are required (or use --test for a stub run)")

    detections = load_run_log(args.log)
    gt_barrels, toxic_count = load_maze(args.map)
    report = score_run(detections, gt_barrels, toxic_count)

    if args.json:
        import dataclasses
        print(json.dumps(dataclasses.asdict(report), indent=2))
    else:
        print(format_report(report, gt_barrels))


if __name__ == "__main__":
    main()

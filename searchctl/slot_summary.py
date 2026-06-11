"""
Slot summary — scan every run_<ts>/run_summary.json under searchctl/ and
report the best attempt by estimated score (per the qualifier PDF rubric):
   50 pts per unique yellow barrel
   100 pts per unique red barrel
   eligibility floor of >=1 of each colour (else 0)
   + bonus: 20 pts per 30s under 5min if ALL of a colour are detected
       (we can't know N_target, so this estimate assumes the count at land
       is the total. Upper bound — actual could be lower.)

Usage at venue (in the VM):
    python3 slot_summary.py

The output goes to stdout AND to ./slot_summary.txt next to the script so
the judge-talker can show the judge a single file at the end of the slot.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


SEARCHCTL_DIR = Path(__file__).resolve().parent


def _score_run(summary: dict) -> tuple[int, int, int, dict]:
    """Return (base_pts, est_bonus_pts, total_pts, details)."""
    unique = summary.get("unique_detections", {}) or {}
    y = int(unique.get("yellow_barrel", 0))
    r = int(unique.get("red_barrel", 0))
    eligible = y >= 1 and r >= 1
    base = (50 * y + 100 * r) if eligible else 0

    # Bonus — only awarded for finding ALL of a colour in <5 min. We don't
    # know the true total N_target, so we assume the count at land is the
    # total (best-case). Real bonus could be 0 if we missed any.
    flight_s = summary.get("flight_seconds")
    bonus = 0
    bonus_detail = {}
    if eligible and flight_s is not None and flight_s < 300.0:
        # 20 pts per 30 s under 5 min. 5min - flight_s = saved.
        ticks = int((300.0 - flight_s) // 30)
        per_colour = ticks * 20
        # We award the bonus to BOTH colours (assumption: all found of each).
        bonus = 2 * per_colour
        bonus_detail = {
            "ticks_under_5min": ticks,
            "per_colour_bonus": per_colour,
            "assumes_found_all_of_both": True,
        }

    return base, bonus, base + bonus, {
        "yellow": y, "red": r, "toxic": int(unique.get("toxic_barrel", 0)),
        "eligible": eligible, "flight_seconds": flight_s,
        "raw_detection_count": summary.get("detection_count", 0),
        "bonus_detail": bonus_detail,
    }


def main() -> int:
    runs = sorted(SEARCHCTL_DIR.glob("run_*/run_summary.json"))
    if not runs:
        print("No run_*/run_summary.json files found under", SEARCHCTL_DIR)
        return 1

    rows = []
    for path in runs:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            rows.append({"path": str(path), "error": f"parse failed: {e}"})
            continue
        base, bonus, total, details = _score_run(data)
        rows.append({
            "path": str(path),
            "run_ts": data.get("run_ts"),
            "base_pts": base,
            "est_bonus_pts": bonus,
            "total_est_pts": total,
            **details,
        })

    # Best by total
    scored = [r for r in rows if "error" not in r]
    best = max(scored, key=lambda r: r["total_est_pts"], default=None)

    lines = ["=" * 60, "BrainHack 2026 RoboVerse — slot summary", "=" * 60, ""]
    for r in rows:
        if "error" in r:
            lines.append(f"  [SKIP] {r['path']}: {r['error']}")
            continue
        flag = " ⬅ BEST" if best is not None and r is best else ""
        f_s = r.get("flight_seconds")
        flight_str = f"{f_s:5.1f}s" if isinstance(f_s, (int, float)) else "?"
        lines.append(
            f"  run {r['run_ts']}: {r['yellow']}Y/{r['red']}R/{r['toxic']}T  "
            f"flight={flight_str}  eligible={'Y' if r['eligible'] else 'N'}  "
            f"base={r['base_pts']:3d}  bonus(est)={r['est_bonus_pts']:3d}  "
            f"total~{r['total_est_pts']:3d}{flag}"
        )
    lines.append("")
    if best is not None:
        lines.append(f"Recommended for judge: {best['path']}")
        lines.append(f"  estimated score: {best['total_est_pts']} pts "
                     f"(base {best['base_pts']} + bonus {best['est_bonus_pts']})")
        if best["est_bonus_pts"] > 0:
            lines.append("  WARNING: bonus assumes 'found all of each colour' — "
                         "actual bonus may be lower if more barrels existed.")
    lines.append("")

    output = "\n".join(lines) + "\n"
    print(output, end="")
    out_path = SEARCHCTL_DIR / "slot_summary.txt"
    try:
        out_path.write_text(output, encoding="utf-8")
        print(f"(also written to {out_path})")
    except Exception as e:
        print(f"(could not write {out_path}: {e})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

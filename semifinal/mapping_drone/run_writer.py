"""Run artifact writer for the BrainHack 2026 mapping drone.

Owns the on-disk run_<ts>/ directory: STATUS.txt (judge-readable plaintext,
refreshed every ~5s by the controller), run_summary.json (full machine record),
top_down.png/.npy (final occupancy grid), landing_pads.json (per-pad records),
and markers/marker_<id>_<seq>.jpg image snapshots.

All public methods are thread-safe via a single RLock so the controller's
asyncio loop and any background writer task can call into the same instance.

Schema note: the validity field is named 'validity_classification' in every
file we write (STATUS.txt, run_summary.json, landing_pads.json). For backward
compatibility with callers that still pass dicts using the legacy key 'valid'
(e.g. controller._unique_pads), the STATUS.txt path accepts either key.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, Path):
        return str(obj)
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, tuple):
        return list(obj)
    return str(obj)


def _fmt_xyz(xyz: tuple[float, float, float] | None) -> str:
    if xyz is None:
        return "n/a"
    return f"N={xyz[0]:+.2f}m E={xyz[1]:+.2f}m U={xyz[2]:+.2f}m"


def _fmt_pose(pose: tuple[float, float, float, float] | None) -> str:
    if pose is None:
        return "n/a"
    # Third element is altitude positive-up, matching controller.py which
    # passes `-self.state.drone_down` and _fmt_xyz above which also uses U=.
    n, e, u, yaw = pose
    return f"N={n:+.2f}m E={e:+.2f}m U={u:+.2f}m yaw={yaw:+.1f}deg"


def _pad_is_valid(pad: dict[str, Any]) -> bool:
    """Accept either the canonical 'validity_classification' key or the legacy
    'valid' key (used by some callers / older snapshots)."""
    if "validity_classification" in pad:
        return bool(pad.get("validity_classification"))
    return bool(pad.get("valid"))


class RunWriter:
    """Persists all run artifacts under a single timestamped directory."""

    def __init__(self, run_dir: Path, run_ts: str) -> None:
        self.run_dir = Path(run_dir)
        self.run_ts = run_ts
        self.markers_dir = self.run_dir / "markers"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.markers_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()
        # All sightings ever recorded, in insertion order.
        self._sightings: list[dict[str, Any]] = []
        # Per-aruco-id record holding latest pose + validity.
        self._pads: dict[int, dict[str, Any]] = {}
        self._status_path = self.run_dir / "STATUS.txt"
        self._summary_path = self.run_dir / "run_summary.json"
        self._pads_path = self.run_dir / "landing_pads.json"
        self._log_path = self.run_dir / "log.txt"
        self._created_at = datetime.now(timezone.utc).isoformat()

        # Seed STATUS so judges who open it before takeoff see something useful.
        self.write_status({
            "state": "INITIALISING",
            "flight_seconds_or_none": None,
            "drone_pose_or_none": None,
            "num_sightings": 0,
            "unique_pads": [],
            "battery_pct": None,
        })

    # ------------------------------------------------------------------
    # STATUS.txt
    # ------------------------------------------------------------------
    def write_status(self, snapshot: dict[str, Any]) -> None:
        """Atomically rewrite STATUS.txt from a snapshot dict."""
        state = snapshot.get("state", "UNKNOWN")
        flight_s = snapshot.get("flight_seconds_or_none")
        pose = snapshot.get("drone_pose_or_none")
        num_sightings = snapshot.get("num_sightings", 0)
        unique_pads = snapshot.get("unique_pads", []) or []
        battery = snapshot.get("battery_pct")
        next_action = snapshot.get("next_action")

        valid_pads = [p for p in unique_pads if _pad_is_valid(p)]
        invalid_pads = [p for p in unique_pads if not _pad_is_valid(p)]

        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("BRAINHACK 2026 - MAPPING DRONE - RUN STATUS")
        lines.append("=" * 60)
        lines.append(f"Run ID         : {self.run_ts}")
        lines.append(f"Updated (UTC)  : {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
        lines.append(f"State          : {state}")
        if flight_s is None:
            lines.append("Flight time    : not yet airborne")
        else:
            lines.append(f"Flight time    : {float(flight_s):6.1f} s")
        lines.append(f"Drone pose     : {_fmt_pose(pose)}")
        if battery is None:
            lines.append("Battery        : unknown")
        else:
            lines.append(f"Battery        : {float(battery):5.1f} %")
        lines.append("")
        lines.append(f"Sightings total: {int(num_sightings)}")
        lines.append(f"Unique pads    : {len(unique_pads)}  "
                     f"(valid={len(valid_pads)}, invalid={len(invalid_pads)})")
        lines.append("")

        lines.append("-- VALID LANDING PADS --")
        if not valid_pads:
            lines.append("  (none yet)")
        else:
            for p in sorted(valid_pads, key=lambda r: r.get("aruco_id", -1)):
                lines.append(
                    f"  id={p.get('aruco_id'):>4}  {_fmt_xyz(p.get('world_xyz_m'))}"
                )
        lines.append("")

        lines.append("-- INVALID LANDING PADS --")
        if not invalid_pads:
            lines.append("  (none yet)")
        else:
            for p in sorted(invalid_pads, key=lambda r: r.get("aruco_id", -1)):
                lines.append(
                    f"  id={p.get('aruco_id'):>4}  {_fmt_xyz(p.get('world_xyz_m'))}"
                )
        lines.append("")

        if next_action:
            lines.append(f"Next action    : {next_action}")
            lines.append("")
        lines.append("=" * 60)
        text = "\n".join(lines) + "\n"

        with self._lock:
            self._atomic_write_text(self._status_path, text)

    # ------------------------------------------------------------------
    # Sightings
    # ------------------------------------------------------------------
    def add_sighting(self, sighting: Any, validity: bool) -> None:
        """Record one ArucoSighting + its validity classification.

        When a higher-confidence sighting replaces a previously stored pad
        record, we preserve `first_seen_at` from the original sighting and
        increment `sighting_count` instead of resetting it. `last_seen_at`
        always tracks the most recent observation timestamp.
        """
        with self._lock:
            rec = self._sighting_to_dict(sighting, validity)

            # _sighting_to_dict may omit required fields (e.g. aruco_id) if the
            # source sighting was malformed. Guard against that here so we never
            # crash on a missing canonical key.
            pad_id = rec.get("aruco_id")
            if pad_id is None:
                logger.warning("skipping malformed sighting: missing aruco_id")
                return

            self._sightings.append(rec)

            world_xyz = rec.get("world_xyz_m")
            prev = self._pads.get(pad_id)
            # Prefer the sighting that actually has a world position; otherwise
            # keep the most recent observation.
            keep_new = (
                prev is None
                or (world_xyz is not None and prev.get("world_xyz_m") is None)
                or (world_xyz is not None
                    and rec.get("confidence", 0.0) >= prev.get("confidence", 0.0))
            )
            new_ts = rec.get("first_seen_at")
            if keep_new:
                if prev is None:
                    first_seen = new_ts
                    sighting_count = 1
                else:
                    # Replacement: preserve original first_seen_at and bump count.
                    first_seen = prev.get("first_seen_at", new_ts)
                    sighting_count = int(prev.get("sighting_count", 0)) + 1
                # canonical schema keys: aruco_id, world_xyz_m, pixel_center, bbox, image_path, validity_classification
                self._pads[pad_id] = {
                    "aruco_id": pad_id,
                    "world_xyz_m": world_xyz,
                    "pixel_center": rec.get("pixel_center"),
                    "bbox": rec.get("bbox_xyxy"),
                    "image_path": rec.get("saved_image_path"),
                    "first_seen_at": first_seen,
                    "last_seen_at": new_ts,
                    "confidence": rec.get("confidence", 0.0),
                    "validity_classification": bool(validity),
                    "sighting_count": sighting_count,
                }
            else:
                prev["last_seen_at"] = new_ts if new_ts is not None else prev.get("last_seen_at")
                prev["sighting_count"] = int(prev.get("sighting_count", 0)) + 1
                prev["validity_classification"] = bool(validity)
                # Strip legacy key if it survived from an earlier write.
                prev.pop("valid", None)

            # Persist landing_pads.json on every sighting so the file is always
            # current even if the run is killed.
            self._write_pads_locked()

    def save_marker_image(
        self,
        color_bgr: np.ndarray,
        aruco_id: int,
        seq: int,
        bbox_xyxy: tuple[int, int, int, int] | None = None,
    ) -> str:
        """Save a BGR image with a stable filename. Returns the saved path.

        If `bbox_xyxy` is provided, a green rectangle and the ArUco id text
        are drawn onto a copy of the frame before saving so reviewers can
        immediately see which marker the snapshot pertains to. The raw frame
        passed in is never mutated.
        """
        fname = f"marker_{int(aruco_id):04d}_{int(seq):04d}.jpg"
        path = self.markers_dir / fname
        with self._lock:
            try:
                img = color_bgr
                if bbox_xyxy is not None and color_bgr is not None:
                    try:
                        img = color_bgr.copy()
                        x1, y1, x2, y2 = (int(v) for v in bbox_xyxy)
                        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        label = f"id={int(aruco_id)}"
                        # Place text just above the bbox, clamped to image.
                        tx = max(0, x1)
                        ty = max(15, y1 - 6)
                        cv2.putText(
                            img,
                            label,
                            (tx, ty),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (0, 255, 0),
                            2,
                            cv2.LINE_AA,
                        )
                    except Exception:
                        logger.exception(
                            "bbox overlay failed for id=%s; saving raw frame",
                            aruco_id,
                        )
                        img = color_bgr
                ok = cv2.imwrite(str(path), img)
                if not ok:
                    logger.warning("cv2.imwrite returned False for %s", path)
            except Exception:
                logger.exception("Failed to write marker image %s", path)
        return str(path)

    # ------------------------------------------------------------------
    # Finalisation
    # ------------------------------------------------------------------
    def finalise(
        self,
        occupancy_grid: Any,
        total_flight_s: float,
        aborted: bool,
        abort_reason: str | None = None,
    ) -> None:
        """Write final top_down.{png,npy}, landing_pads.json, run_summary.json.

        ``abort_reason`` is recorded verbatim when aborted=True; when aborted
        is False or the caller doesn't know the reason the field is written as
        null so judge tooling never has to distinguish missing-vs-empty.
        """
        with self._lock:
            top_down_png = self.run_dir / "top_down.png"
            top_down_npy = self.run_dir / "top_down.npy"

            try:
                occupancy_grid.save_png(str(top_down_png))
            except Exception:
                logger.exception("Failed to save top_down.png")
            try:
                occupancy_grid.save_npy(str(top_down_npy))
            except Exception:
                logger.exception("Failed to save top_down.npy")

            self._write_pads_locked()

            # Normalise: empty-string reasons become null; non-aborted runs
            # also clear any stray reason so the field is unambiguous.
            reason_out: str | None
            if aborted and abort_reason:
                reason_out = str(abort_reason)
            else:
                reason_out = None

            summary = {
                "run_ts": self.run_ts,
                "created_at_utc": self._created_at,
                "finalised_at_utc": datetime.now(timezone.utc).isoformat(),
                "total_flight_s": float(total_flight_s),
                "aborted": bool(aborted),
                "abort_reason": reason_out,
                "num_sightings": len(self._sightings),
                "num_unique_pads": len(self._pads),
                "artifacts": {
                    "top_down_png": str(top_down_png),
                    "top_down_npy": str(top_down_npy),
                    "landing_pads_json": str(self._pads_path),
                    "status_txt": str(self._status_path),
                    "markers_dir": str(self.markers_dir),
                    "log_txt": str(self._log_path),
                },
                "landing_pads": sorted(
                    (self._pad_for_serialization(p) for p in self._pads.values()),
                    key=lambda r: r.get("aruco_id", -1),
                ),
                "sightings": list(self._sightings),
            }
            self._atomic_write_text(
                self._summary_path,
                json.dumps(summary, indent=2, default=_json_default) + "\n",
            )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _sighting_to_dict(self, sighting: Any, validity: bool) -> dict[str, Any]:
        """Coerce an ArucoSighting dataclass (or any duck-typed equivalent).

        Required fields (aruco_id, pixel_center, bbox_xyxy, first_seen_at) are
        not silently replaced with fabricated zeros if missing — instead a
        warning is logged and the field is omitted from the serialized record.
        """
        def g(name: str, default: Any = None) -> Any:
            if isinstance(sighting, dict):
                return sighting.get(name, default)
            return getattr(sighting, name, default)

        # Sentinel for "missing".
        _MISSING = object()

        out: dict[str, Any] = {}

        aruco_id_raw = g("aruco_id", _MISSING)
        if aruco_id_raw is _MISSING or aruco_id_raw is None:
            logger.warning(
                "sighting missing required field 'aruco_id'; skipping field"
            )
        else:
            try:
                out["aruco_id"] = int(aruco_id_raw)
            except (TypeError, ValueError):
                logger.warning(
                    "sighting aruco_id=%r is not coercible to int; skipping field",
                    aruco_id_raw,
                )

        pixel_center_raw = g("pixel_center", _MISSING)
        if pixel_center_raw is _MISSING or pixel_center_raw is None:
            logger.warning(
                "sighting (id=%s) missing 'pixel_center'; skipping field",
                out.get("aruco_id"),
            )
        else:
            try:
                out["pixel_center"] = tuple(pixel_center_raw)
            except TypeError:
                logger.warning(
                    "sighting (id=%s) pixel_center=%r not iterable; skipping field",
                    out.get("aruco_id"),
                    pixel_center_raw,
                )

        bbox_raw = g("bbox_xyxy", _MISSING)
        if bbox_raw is _MISSING or bbox_raw is None:
            logger.warning(
                "sighting (id=%s) missing 'bbox_xyxy'; skipping field",
                out.get("aruco_id"),
            )
        else:
            try:
                out["bbox_xyxy"] = tuple(bbox_raw)
            except TypeError:
                logger.warning(
                    "sighting (id=%s) bbox_xyxy=%r not iterable; skipping field",
                    out.get("aruco_id"),
                    bbox_raw,
                )

        cam_xyz_raw = g("cam_xyz_m")
        if cam_xyz_raw is not None:
            try:
                out["cam_xyz_m"] = tuple(cam_xyz_raw)
            except TypeError:
                logger.warning(
                    "sighting (id=%s) cam_xyz_m=%r not iterable; skipping field",
                    out.get("aruco_id"),
                    cam_xyz_raw,
                )
        else:
            out["cam_xyz_m"] = None

        world_xyz_raw = g("world_xyz_m")
        if world_xyz_raw is not None:
            try:
                out["world_xyz_m"] = tuple(world_xyz_raw)
            except TypeError:
                logger.warning(
                    "sighting (id=%s) world_xyz_m=%r not iterable; skipping field",
                    out.get("aruco_id"),
                    world_xyz_raw,
                )
                out["world_xyz_m"] = None
        else:
            out["world_xyz_m"] = None

        try:
            out["confidence"] = float(g("confidence", 0.0))
        except (TypeError, ValueError):
            logger.warning(
                "sighting (id=%s) confidence not coercible; skipping field",
                out.get("aruco_id"),
            )

        out["saved_image_path"] = g("saved_image_path")

        first_seen_raw = g("first_seen_at", _MISSING)
        if first_seen_raw is _MISSING or first_seen_raw is None:
            logger.warning(
                "sighting (id=%s) missing 'first_seen_at'; skipping field",
                out.get("aruco_id"),
            )
        else:
            try:
                out["first_seen_at"] = float(first_seen_raw)
            except (TypeError, ValueError):
                logger.warning(
                    "sighting (id=%s) first_seen_at=%r not coercible to float; "
                    "skipping field",
                    out.get("aruco_id"),
                    first_seen_raw,
                )

        out["validity_classification"] = bool(validity)
        return out

    @staticmethod
    def _pad_for_serialization(pad: dict[str, Any]) -> dict[str, Any]:
        """Project the in-memory pad record onto the canonical on-disk schema:
        {aruco_id, world_xyz_m, pixel_center, bbox, image_path,
         validity_classification, first_seen_at, last_seen_at, confidence,
         sighting_count}.

        add_sighting writes only the canonical keys in-memory, so no legacy
        key fallbacks are needed here.
        """
        out: dict[str, Any] = {
            "aruco_id": pad.get("aruco_id"),
            "world_xyz_m": pad.get("world_xyz_m"),
            "pixel_center": pad.get("pixel_center"),
            "bbox": pad.get("bbox"),
            "image_path": pad.get("image_path"),
            "validity_classification": pad.get("validity_classification"),
            "first_seen_at": pad.get("first_seen_at"),
            "last_seen_at": pad.get("last_seen_at"),
            "confidence": pad.get("confidence"),
            "sighting_count": pad.get("sighting_count"),
        }
        return out

    def _write_pads_locked(self) -> None:
        pads_out = sorted(
            (self._pad_for_serialization(p) for p in self._pads.values()),
            key=lambda r: r.get("aruco_id", -1),
        )
        payload = {
            "run_ts": self.run_ts,
            "count": len(self._pads),
            "pads": pads_out,
        }
        self._atomic_write_text(
            self._pads_path,
            json.dumps(payload, indent=2, default=_json_default) + "\n",
        )

    @staticmethod
    def _atomic_write_text(path: Path, text: str) -> None:
        """Write via a sibling tmp file + replace, so judges never see a half file."""
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(path)
        except Exception:
            logger.exception("Atomic write failed for %s", path)
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass

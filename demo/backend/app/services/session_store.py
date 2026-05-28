"""In-memory session and leaderboard storage."""

from __future__ import annotations

import io
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import cv2
import numpy as np

from math import ceil

SECONDS_PER_IMAGE = 1.5


def game_time_limit(image_count: int) -> int:
    return ceil(image_count * SECONDS_PER_IMAGE)

from app.models.schemas import (
    AggregateMetrics,
    DatasetSummary,
    ImageInfo,
    ImageMetrics,
    LeaderboardEntry,
    ResultsResponse,
    SessionResponse,
)
from app.services.dataset_fingerprint import compute_dataset_id, dataset_label
from app.services.leaderboard_store import (
    DatasetLeaderboard,
    LeaderboardRecord,
    entries_to_response,
    load_all_leaderboards,
    save_leaderboard,
)
from app.services.scoring import compute_leaderboard_score
from app.services.segmentation import run_segmentation
from app.services.upload_parser import MatchedPair

STORAGE_ROOT = Path(__file__).resolve().parents[3] / "storage"


@dataclass
class SessionImage:
    stem: str
    image_path: Path
    gt_path: Path
    bbox: tuple[int, int, int, int] | None = None
    metrics: dict[str, float] | None = None
    mask_path: Path | None = None
    overlay_path: Path | None = None
    skipped: bool = False


@dataclass
class Session:
    session_id: str
    display_name: str
    images: list[SessionImage]
    dir: Path
    dataset_id: str
    dataset_label: str
    phase: Literal["game", "processing", "done"] = "game"


class SessionStore:
    """Process-local sessions; leaderboards keyed by dataset and persisted to disk."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._leaderboards: dict[str, DatasetLeaderboard] = load_all_leaderboards()
        STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

    def create_session(
        self,
        display_name: str,
        pairs: list[MatchedPair],
    ) -> Session:
        session_id = uuid.uuid4().hex
        session_dir = STORAGE_ROOT / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "results").mkdir(exist_ok=True)

        ds_id = compute_dataset_id(pairs)
        ds_label = dataset_label(pairs)
        stems = [p.stem for p in pairs]

        images: list[SessionImage] = []
        for pair in pairs:
            img_path = session_dir / f"{pair.stem}{pair.image_ext}"
            gt_path = session_dir / f"{pair.stem}_gt{pair.gt_ext}"
            img_path.write_bytes(pair.image_bytes)
            gt_path.write_bytes(pair.gt_bytes)
            images.append(
                SessionImage(
                    stem=pair.stem,
                    image_path=img_path,
                    gt_path=gt_path,
                )
            )

        session = Session(
            session_id=session_id,
            display_name=display_name,
            images=images,
            dir=session_dir,
            dataset_id=ds_id,
            dataset_label=ds_label,
        )
        self._sessions[session_id] = session

        if ds_id not in self._leaderboards:
            self._leaderboards[ds_id] = DatasetLeaderboard(
                dataset_id=ds_id,
                dataset_label=ds_label,
                stems=stems,
                entries=[],
            )

        return session

    def get_session(self, session_id: str) -> Session:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")
        return session

    def set_bbox(
        self,
        session_id: str,
        index: int,
        bbox: tuple[int, int, int, int],
    ) -> None:
        session = self.get_session(session_id)
        if index < 0 or index >= len(session.images):
            raise IndexError(f"Image index out of range: {index}")
        x1, y1, x2, y2 = bbox
        if x2 - x1 < 2 or y2 - y1 < 2:
            raise ValueError("Bounding box must be at least 2x2 pixels.")
        session.images[index].bbox = bbox
        session.images[index].skipped = False

    def retry_session(self, session_id: str) -> Session:
        session = self.get_session(session_id)
        results_dir = session.dir / "results"
        if results_dir.exists():
            for f in results_dir.iterdir():
                f.unlink()
        for img in session.images:
            img.bbox = None
            img.metrics = None
            img.mask_path = None
            img.overlay_path = None
            img.skipped = False
        session.phase = "game"
        return session

    def run_batch_segmentation(self, session_id: str) -> None:
        session = self.get_session(session_id)
        session.phase = "processing"
        results_dir = session.dir / "results"

        for img in session.images:
            img.metrics = None
            img.mask_path = None
            img.overlay_path = None
            img.skipped = img.bbox is None

        for img in session.images:
            if img.bbox is None:
                continue
            image_bytes = img.image_path.read_bytes()
            gt_bytes = img.gt_path.read_bytes()
            try:
                mask, overlay, _, metrics = run_segmentation(
                    image_bytes,
                    gt_bytes,
                    img.bbox,
                )
            except Exception:
                img.skipped = True
                continue

            mask_path = results_dir / f"{img.stem}_mask.png"
            overlay_path = results_dir / f"{img.stem}_overlay.png"
            cv2.imwrite(str(mask_path), mask)
            cv2.imwrite(str(overlay_path), overlay)
            img.mask_path = mask_path
            img.overlay_path = overlay_path
            img.metrics = metrics

        session.phase = "done"

    def build_session_response(self, session: Session) -> SessionResponse:
        bbox_count = sum(1 for img in session.images if img.bbox is not None)
        return SessionResponse(
            session_id=session.session_id,
            display_name=session.display_name,
            image_count=len(session.images),
            time_limit_sec=game_time_limit(len(session.images)),
            phase=session.phase,
            images=[
                ImageInfo(
                    index=i,
                    stem=img.stem,
                    has_bbox=img.bbox is not None,
                )
                for i, img in enumerate(session.images)
            ],
            bbox_count=bbox_count,
        )

    def build_results_response(self, session_id: str) -> ResultsResponse:
        session = self.get_session(session_id)
        status: Literal["processing", "done", "idle"] = (
            "processing" if session.phase == "processing" else "done"
            if session.phase == "done"
            else "idle"
        )

        image_metrics: list[ImageMetrics] = []
        scored: list[dict[str, float]] = []

        for i, img in enumerate(session.images):
            if img.skipped or img.metrics is None:
                image_metrics.append(
                    ImageMetrics(
                        index=i,
                        stem=img.stem,
                        iou=0.0,
                        dice=0.0,
                        pixel_error=0.0,
                        mask_url="",
                        overlay_url="",
                        skipped=True,
                    )
                )
                continue
            scored.append(img.metrics)
            image_metrics.append(
                ImageMetrics(
                    index=i,
                    stem=img.stem,
                    iou=img.metrics["iou"],
                    dice=img.metrics["dice"],
                    pixel_error=img.metrics["pixel_error"],
                    mask_url=f"/api/sessions/{session_id}/results/{i}/mask",
                    overlay_url=f"/api/sessions/{session_id}/results/{i}/overlay",
                    skipped=False,
                )
            )

        aggregate = None
        if scored and session.phase == "done":
            mean_iou = float(np.mean([m["iou"] for m in scored]))
            scored_count = len(scored)
            image_count = len(session.images)
            aggregate = AggregateMetrics(
                mean_iou=mean_iou,
                mean_dice=float(np.mean([m["dice"] for m in scored])),
                mean_pixel_error=float(np.mean([m["pixel_error"] for m in scored])),
                scored_count=scored_count,
                image_count=image_count,
                leaderboard_score=compute_leaderboard_score(
                    mean_iou, scored_count, image_count
                ),
            )

        return ResultsResponse(
            session_id=session_id,
            status=status,
            images=image_metrics,
            aggregate=aggregate,
        )

    def submit_leaderboard(self, session_id: str, display_name: str) -> LeaderboardEntry:
        session = self.get_session(session_id)
        if session.phase != "done":
            raise ValueError("Session must be finished before submitting to leaderboard.")
        results = self.build_results_response(session_id)
        if results.aggregate is None or results.aggregate.scored_count == 0:
            raise ValueError("No scored images to submit.")

        record = LeaderboardRecord(
            display_name=display_name,
            leaderboard_score=results.aggregate.leaderboard_score,
            mean_iou=results.aggregate.mean_iou,
            scored_count=results.aggregate.scored_count,
            image_count=len(session.images),
            submitted_at=datetime.now(timezone.utc),
        )

        board = self._leaderboards[session.dataset_id]
        board.entries.append(record)
        save_leaderboard(board)

        ranked = entries_to_response(board.entries)
        entry = next(
            e
            for e in ranked
            if e.display_name == display_name and e.submitted_at == record.submitted_at.isoformat()
        )
        return entry

    def get_leaderboard(self, dataset_id: str) -> tuple[str, list[LeaderboardEntry]]:
        board = self._leaderboards.get(dataset_id)
        if board is None:
            return dataset_id, []
        return board.dataset_label, entries_to_response(board.entries)

    def list_datasets(self) -> list[DatasetSummary]:
        """All known upload sets that have at least been played once."""
        summaries: list[DatasetSummary] = []
        for board in self._leaderboards.values():
            summaries.append(
                DatasetSummary(
                    dataset_id=board.dataset_id,
                    dataset_label=board.dataset_label,
                    image_count=len(board.stems),
                    entry_count=len(board.entries),
                )
            )
        summaries.sort(
            key=lambda d: (-d.entry_count, d.dataset_label.lower()),
        )
        return summaries

    def build_masks_zip(self, session_id: str) -> bytes:
        session = self.get_session(session_id)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for img in session.images:
                if img.mask_path and img.mask_path.is_file():
                    zf.write(img.mask_path, arcname=f"{img.stem}_mask.png")
        buf.seek(0)
        return buf.getvalue()


store = SessionStore()

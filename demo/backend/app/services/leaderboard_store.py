"""Persist and load per-dataset leaderboards on disk."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.models.schemas import LeaderboardEntry

LEADERBOARDS_DIR = Path(__file__).resolve().parents[3] / "storage" / "leaderboards"


@dataclass
class LeaderboardRecord:
    display_name: str
    leaderboard_score: float
    mean_iou: float
    scored_count: int
    image_count: int
    submitted_at: datetime


@dataclass
class DatasetLeaderboard:
    dataset_id: str
    dataset_label: str
    stems: list[str]
    entries: list[LeaderboardRecord]


def _record_to_json(record: LeaderboardRecord) -> dict:
    return {
        "display_name": record.display_name,
        "leaderboard_score": record.leaderboard_score,
        "mean_iou": record.mean_iou,
        "scored_count": record.scored_count,
        "image_count": record.image_count,
        "submitted_at": record.submitted_at.isoformat(),
    }


def _record_from_json(data: dict) -> LeaderboardRecord:
    submitted = data["submitted_at"]
    if isinstance(submitted, str):
        submitted = datetime.fromisoformat(submitted)
    return LeaderboardRecord(
        display_name=data["display_name"],
        leaderboard_score=float(data["leaderboard_score"]),
        mean_iou=float(data["mean_iou"]),
        scored_count=int(data["scored_count"]),
        image_count=int(data["image_count"]),
        submitted_at=submitted,
    )


def _board_path(dataset_id: str) -> Path:
    return LEADERBOARDS_DIR / f"{dataset_id}.json"


def load_all_leaderboards() -> dict[str, DatasetLeaderboard]:
    """Load every saved leaderboard from disk."""
    LEADERBOARDS_DIR.mkdir(parents=True, exist_ok=True)
    boards: dict[str, DatasetLeaderboard] = {}
    for path in LEADERBOARDS_DIR.glob("*.json"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            dataset_id = raw["dataset_id"]
            entries = [_record_from_json(e) for e in raw.get("entries", [])]
            boards[dataset_id] = DatasetLeaderboard(
                dataset_id=dataset_id,
                dataset_label=raw.get("dataset_label", dataset_id),
                stems=raw.get("stems", []),
                entries=entries,
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return boards


def save_leaderboard(board: DatasetLeaderboard) -> None:
    """Write one dataset leaderboard to disk."""
    LEADERBOARDS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset_id": board.dataset_id,
        "dataset_label": board.dataset_label,
        "stems": board.stems,
        "entries": [_record_to_json(r) for r in board.entries],
    }
    _board_path(board.dataset_id).write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def entries_to_response(
    records: list[LeaderboardRecord],
) -> list[LeaderboardEntry]:
    sorted_board = sorted(records, key=lambda r: r.leaderboard_score, reverse=True)
    return [
        LeaderboardEntry(
            rank=i + 1,
            display_name=r.display_name,
            leaderboard_score=r.leaderboard_score,
            mean_iou=r.mean_iou,
            scored_count=r.scored_count,
            image_count=r.image_count,
            submitted_at=r.submitted_at.isoformat(),
        )
        for i, r in enumerate(sorted_board)
    ]

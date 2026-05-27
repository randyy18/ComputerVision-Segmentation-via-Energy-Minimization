"""Per-dataset leaderboard routes (persisted while the upload set stays the same)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    DatasetListResponse,
    LeaderboardEntry,
    LeaderboardResponse,
    LeaderboardSubmitBody,
)
from app.services.session_store import store

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


@router.get("/datasets", response_model=DatasetListResponse)
def list_datasets() -> DatasetListResponse:
    return DatasetListResponse(datasets=store.list_datasets())


@router.get("", response_model=LeaderboardResponse)
def get_leaderboard(
    dataset_id: str = Query(..., min_length=8, max_length=32),
) -> LeaderboardResponse:
    label, entries = store.get_leaderboard(dataset_id)
    return LeaderboardResponse(
        dataset_id=dataset_id,
        dataset_label=label,
        entries=entries,
    )


@router.post("", response_model=LeaderboardEntry)
def submit_to_leaderboard(body: LeaderboardSubmitBody) -> LeaderboardEntry:
    try:
        return store.submit_leaderboard(body.session_id, body.display_name.strip())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

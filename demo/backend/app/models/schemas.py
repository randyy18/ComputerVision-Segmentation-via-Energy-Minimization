"""Pydantic request/response models for the demo API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BboxBody(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int


class SessionCreateResponse(BaseModel):
    session_id: str
    display_name: str
    image_count: int
    time_limit_sec: int
    stems: list[str]
    dataset_id: str
    dataset_label: str


class ImageInfo(BaseModel):
    index: int
    stem: str
    has_bbox: bool


class SessionResponse(BaseModel):
    session_id: str
    display_name: str
    image_count: int
    time_limit_sec: int
    phase: Literal["game", "processing", "done"]
    images: list[ImageInfo]
    bbox_count: int


class ImageMetrics(BaseModel):
    index: int
    stem: str
    iou: float
    dice: float
    pixel_error: float
    mask_url: str
    overlay_url: str
    skipped: bool = False


class AggregateMetrics(BaseModel):
    mean_iou: float
    mean_dice: float
    mean_pixel_error: float
    scored_count: int
    image_count: int
    leaderboard_score: float


class ResultsResponse(BaseModel):
    session_id: str
    status: Literal["processing", "done", "idle"]
    images: list[ImageMetrics]
    aggregate: AggregateMetrics | None = None


class FinishResponse(BaseModel):
    session_id: str
    status: Literal["processing", "done"]


class LeaderboardSubmitBody(BaseModel):
    session_id: str
    display_name: str = Field(min_length=1, max_length=32)


class LeaderboardEntry(BaseModel):
    rank: int
    display_name: str
    leaderboard_score: float
    mean_iou: float
    scored_count: int
    image_count: int
    submitted_at: str


class LeaderboardResponse(BaseModel):
    dataset_id: str
    dataset_label: str
    entries: list[LeaderboardEntry]


class DatasetSummary(BaseModel):
    dataset_id: str
    dataset_label: str
    image_count: int
    entry_count: int


class DatasetListResponse(BaseModel):
    datasets: list[DatasetSummary]


class RetryResponse(BaseModel):
    session_id: str
    time_limit_sec: int
    phase: Literal["game"]

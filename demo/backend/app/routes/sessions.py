"""Session upload, game, segmentation, and download routes."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from app.models.schemas import (
    BboxBody,
    FinishResponse,
    ResultsResponse,
    RetryResponse,
    SessionCreateResponse,
    SessionResponse,
)
from app.services.session_store import store
from app.services.upload_parser import parse_upload_pairs

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


async def _read_uploads(files: list[UploadFile]) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    for f in files:
        if not f.filename:
            continue
        data = await f.read()
        out.append((f.filename, data))
    return out


@router.post("", response_model=SessionCreateResponse)
async def create_session(
    display_name: str = Form(...),
    images: list[UploadFile] = File(...),
    gt: list[UploadFile] = File(...),
) -> SessionCreateResponse:
    name = display_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Display name is required.")

    try:
        image_files = await _read_uploads(images)
        gt_files = await _read_uploads(gt)
        pairs = parse_upload_pairs(image_files, gt_files)
        session = store.create_session(name, pairs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SessionCreateResponse(
        session_id=session.session_id,
        display_name=session.display_name,
        image_count=len(session.images),
        time_limit_sec=len(session.images),
        stems=[img.stem for img in session.images],
        dataset_id=session.dataset_id,
        dataset_label=session.dataset_label,
    )


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: str) -> SessionResponse:
    try:
        session = store.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return store.build_session_response(session)


@router.get("/{session_id}/images/{index}")
def get_image(session_id: str, index: int) -> FileResponse:
    try:
        session = store.get_session(session_id)
        img = session.images[index]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IndexError as exc:
        raise HTTPException(status_code=404, detail="Image not found.") from exc
    return FileResponse(img.image_path)


@router.put("/{session_id}/bboxes/{index}")
def set_bbox(session_id: str, index: int, body: BboxBody) -> dict[str, bool]:
    try:
        store.set_bbox(session_id, index, (body.x1, body.y1, body.x2, body.y2))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (IndexError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@router.post("/{session_id}/finish", response_model=FinishResponse)
def finish_session(session_id: str) -> FinishResponse:
    try:
        session = store.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if session.phase == "done":
        return FinishResponse(session_id=session_id, status="done")

    store.run_batch_segmentation(session_id)
    return FinishResponse(session_id=session_id, status="done")


@router.get("/{session_id}/results", response_model=ResultsResponse)
def get_results(session_id: str) -> ResultsResponse:
    try:
        return store.build_results_response(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{session_id}/results/{index}/mask")
def get_result_mask(session_id: str, index: int) -> FileResponse:
    try:
        session = store.get_session(session_id)
        img = session.images[index]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IndexError as exc:
        raise HTTPException(status_code=404, detail="Image not found.") from exc
    if img.mask_path is None or not img.mask_path.is_file():
        raise HTTPException(status_code=404, detail="Mask not available.")
    return FileResponse(img.mask_path, media_type="image/png")


@router.get("/{session_id}/results/{index}/overlay")
def get_result_overlay(session_id: str, index: int) -> FileResponse:
    try:
        session = store.get_session(session_id)
        img = session.images[index]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IndexError as exc:
        raise HTTPException(status_code=404, detail="Image not found.") from exc
    if img.overlay_path is None or not img.overlay_path.is_file():
        raise HTTPException(status_code=404, detail="Overlay not available.")
    return FileResponse(img.overlay_path, media_type="image/png")


@router.get("/{session_id}/download")
def download_masks(session_id: str) -> Response:
    try:
        data = store.build_masks_zip(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{session_id}_masks.zip"'},
    )


@router.post("/{session_id}/retry", response_model=RetryResponse)
def retry_session(session_id: str) -> RetryResponse:
    try:
        session = store.retry_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RetryResponse(
        session_id=session.session_id,
        time_limit_sec=len(session.images),
        phase="game",
    )

"""Match uploaded images to ground-truth masks by filename stem."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
GT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
MAX_IMAGES = 30
MAX_FILE_BYTES = 10 * 1024 * 1024


@dataclass
class MatchedPair:
    stem: str
    image_bytes: bytes
    image_ext: str
    gt_bytes: bytes
    gt_ext: str


def _stem_from_filename(filename: str) -> str:
    return Path(filename).stem.lower()


def _validate_file_size(data: bytes, filename: str) -> None:
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"File too large (max 10 MB): {filename}")


def parse_upload_pairs(
    image_files: list[tuple[str, bytes]],
    gt_files: list[tuple[str, bytes]],
) -> list[MatchedPair]:
    """
    Pair images with GT masks by matching filename stems.

    Parameters
    ----------
    image_files : list of (filename, bytes)
    gt_files : list of (filename, bytes)

    Returns
    -------
    list[MatchedPair]
        Sorted by stem; raises ValueError on validation failure.
    """
    images: dict[str, tuple[str, bytes]] = {}
    for filename, data in image_files:
        ext = Path(filename).suffix.lower()
        if ext not in IMAGE_EXTENSIONS:
            continue
        _validate_file_size(data, filename)
        stem = _stem_from_filename(filename)
        images[stem] = (ext, data)

    gts: dict[str, tuple[str, bytes]] = {}
    for filename, data in gt_files:
        ext = Path(filename).suffix.lower()
        if ext not in GT_EXTENSIONS:
            continue
        _validate_file_size(data, filename)
        stem = _stem_from_filename(filename)
        gts[stem] = (ext, data)

    common = sorted(set(images) & set(gts))
    if not common:
        raise ValueError(
            "No matching image/GT pairs found. Use the same filename stem "
            "(e.g. cat.jpg + cat.png)."
        )
    if len(common) > MAX_IMAGES:
        raise ValueError(f"Too many pairs (max {MAX_IMAGES}). Got {len(common)}.")

    pairs: list[MatchedPair] = []
    for stem in common:
        img_ext, img_data = images[stem]
        gt_ext, gt_data = gts[stem]
        pairs.append(
            MatchedPair(
                stem=stem,
                image_bytes=img_data,
                image_ext=img_ext,
                gt_bytes=gt_data,
                gt_ext=gt_ext,
            )
        )
    return pairs

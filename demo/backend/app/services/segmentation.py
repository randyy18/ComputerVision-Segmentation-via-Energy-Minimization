"""Wrap grabcut_classical segmentation and evaluation for the web demo."""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[4]
_GRABCUT_DIR = _REPO_ROOT / "grabcut_classical"
if str(_GRABCUT_DIR) not in sys.path:
    sys.path.insert(0, str(_GRABCUT_DIR))

import config  # noqa: E402
from evaluation import compute_metrics  # noqa: E402
from segmentation import segment_iterative  # noqa: E402
from visualization import apply_mask_overlay  # noqa: E402

N_ITERATIONS = 3


def load_gt_mask(gt_bytes: bytes, target_shape: tuple[int, int]) -> np.ndarray:
    """Decode GT bytes to binary uint8 mask (255=fg), resize if needed."""
    arr = np.frombuffer(gt_bytes, dtype=np.uint8)
    gt = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if gt is None:
        raise ValueError("Cannot decode ground-truth mask.")
    h, w = target_shape
    if gt.shape[:2] != (h, w):
        gt = cv2.resize(gt, (w, h), interpolation=cv2.INTER_NEAREST)
    return (gt > 127).astype(np.uint8) * 255


def run_segmentation(
    image_bytes: bytes,
    gt_bytes: bytes,
    bbox: tuple[int, int, int, int],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, float]]:
    """
    Run iterative graph-cut segmentation and compute metrics.

    Returns
    -------
    mask, overlay_bgr, image_bgr, metrics dict
    """
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    image_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image_bgr is None:
        raise ValueError("Cannot decode image.")

    gt_mask = load_gt_mask(gt_bytes, image_bgr.shape[:2])
    mask, _, _ = segment_iterative(
        image_bgr,
        bbox,
        config,
        n_iterations=N_ITERATIONS,
    )
    metrics = compute_metrics(mask, gt_mask)
    overlay = apply_mask_overlay(image_bgr, mask)
    return mask, overlay, image_bgr, metrics

"""Segmentation quality metrics: IoU, Dice, pixel error rate."""

from __future__ import annotations

import cv2
import numpy as np


def compute_metrics(pred_mask: np.ndarray, gt_mask: np.ndarray) -> dict[str, float]:
    """
    Compare predicted and ground-truth binary masks.

    Parameters
    ----------
    pred_mask : np.ndarray
        (H, W) uint8, 255=foreground.
    gt_mask : np.ndarray
        (H, W) uint8, 255=foreground.

    Returns
    -------
    dict
        Keys: 'iou', 'dice', 'pixel_error'.
    """
    pred_binary = pred_mask > 0
    gt_binary = gt_mask > 0

    intersection = np.logical_and(pred_binary, gt_binary).sum()
    union = np.logical_or(pred_binary, gt_binary).sum()
    pred_sum = pred_binary.sum()
    gt_sum = gt_binary.sum()
    total = pred_binary.size

    iou = intersection / (union + 1e-6)
    dice = 2 * intersection / (pred_sum + gt_sum + 1e-6)
    pixel_error = np.logical_xor(pred_binary, gt_binary).sum() / total

    return {"iou": float(iou), "dice": float(dice), "pixel_error": float(pixel_error)}


def compute_boundary_interior_metrics(
    pred_mask: np.ndarray,
    gt_mask: np.ndarray,
    boundary_width: int = 5,
) -> dict[str, float | int]:
    """
    Split pixel error into boundary band vs interior regions on GT foreground.

    The boundary band is GT foreground pixels within ``boundary_width`` pixels of
    the FG/BG transition (GT fg minus eroded GT fg). Interior is the eroded core.

    Parameters
    ----------
    pred_mask : np.ndarray
        (H, W) uint8, 255=foreground.
    gt_mask : np.ndarray
        (H, W) uint8, 255=foreground.
    boundary_width : int
        Erosion radius in pixels for interior definition.

    Returns
    -------
    dict
        boundary_error, interior_error, boundary_pixels, interior_pixels.
    """
    pred_binary = pred_mask > 0
    gt_binary = gt_mask > 0

    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (2 * boundary_width + 1, 2 * boundary_width + 1),
    )

    gt_uint8 = gt_binary.astype(np.uint8) * 255
    gt_eroded = cv2.erode(gt_uint8, kernel, iterations=1)
    interior_mask = gt_eroded > 0
    boundary_mask = gt_binary & ~interior_mask

    if interior_mask.sum() == 0:
        boundary_mask = gt_binary
        interior_mask = np.zeros_like(gt_binary)

    errors = pred_binary != gt_binary

    boundary_pixels = int(boundary_mask.sum())
    interior_pixels = int(interior_mask.sum())

    boundary_error = float((errors & boundary_mask).sum() / (boundary_pixels + 1e-9))
    interior_error = float((errors & interior_mask).sum() / (interior_pixels + 1e-9))

    return {
        "boundary_error": boundary_error,
        "interior_error": interior_error,
        "boundary_pixels": boundary_pixels,
        "interior_pixels": interior_pixels,
    }

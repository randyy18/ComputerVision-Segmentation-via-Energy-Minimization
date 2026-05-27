"""Mask overlay, contour drawing, and result display."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def draw_bbox(
    image: np.ndarray,
    bbox: tuple[int, int, int, int],
    color: tuple[int, int, int] = (0, 255, 0),
    thickness: int = 2,
) -> np.ndarray:
    """
    Draw bounding box rectangle on a copy of the image.

    Parameters
    ----------
    image : np.ndarray
        BGR uint8 image.
    bbox : tuple
        (x1, y1, x2, y2).
    color, thickness : drawing style for cv2.rectangle.

    Returns
    -------
    np.ndarray
        Copy of image with rectangle drawn.
    """
    out = image.copy()
    x1, y1, x2, y2 = bbox
    cv2.rectangle(out, (x1, y1), (x2, y2), color, thickness)
    return out


def apply_mask_overlay(
    image_bgr: np.ndarray,
    mask: np.ndarray,
    fg_color: tuple[int, int, int] = (0, 120, 255),
    alpha: float = 0.4,
) -> np.ndarray:
    """
    Blend semi-transparent foreground color over masked pixels.

    Parameters
    ----------
    image_bgr : np.ndarray
        (H, W, 3) uint8 BGR.
    mask : np.ndarray
        (H, W) uint8, 255=foreground.
    fg_color : tuple
        BGR overlay color.
    alpha : float
        Overlay weight in [0, 1].

    Returns
    -------
    np.ndarray
        Blended BGR uint8 image.
    """
    result = image_bgr.copy().astype(np.float32)
    overlay = np.full_like(result, fg_color, dtype=np.float32)
    fg = mask > 0
    result[fg] = alpha * overlay[fg] + (1.0 - alpha) * result[fg]
    return result.astype(np.uint8)


def draw_contours(
    image_bgr: np.ndarray,
    mask: np.ndarray,
    color: tuple[int, int, int] = (0, 255, 0),
    thickness: int = 2,
) -> np.ndarray:
    """
    Draw external contours of the binary mask on a copy of the image.

    Parameters
    ----------
    image_bgr : np.ndarray
        BGR uint8 image.
    mask : np.ndarray
        Binary mask, 255=foreground.

    Returns
    -------
    np.ndarray
        Image with contours drawn.
    """
    out = image_bgr.copy()
    contours, _ = cv2.findContours(
        (mask > 0).astype(np.uint8),
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    cv2.drawContours(out, contours, -1, color, thickness)
    return out


def _label_panel(panel: np.ndarray, text: str) -> np.ndarray:
    """Add a text label above a panel."""
    labeled = cv2.copyMakeBorder(panel, 30, 0, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    cv2.putText(
        labeled,
        text,
        (10, 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )
    return labeled


def _align_panel_heights(panels: list[np.ndarray]) -> list[np.ndarray]:
    """Pad panels vertically so they share the same height for horizontal concat."""
    max_h = max(p.shape[0] for p in panels)
    aligned: list[np.ndarray] = []
    for panel in panels:
        if panel.shape[0] < max_h:
            pad = max_h - panel.shape[0]
            panel = cv2.copyMakeBorder(
                panel, 0, pad, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255)
            )
        aligned.append(panel)
    return aligned


def render_segmentation_view(
    image_bgr: np.ndarray,
    mask: np.ndarray,
    mode: str,
) -> np.ndarray:
    """
    Render a segmentation result as a BGR image for display or saving.

    Parameters
    ----------
    image_bgr : np.ndarray
        Source BGR image (used for overlay mode).
    mask : np.ndarray
        Binary mask, 255=foreground.
    mode : str
        ``overlay`` — colored overlay with contours; ``mask`` — grayscale as BGR.

    Returns
    -------
    np.ndarray
        BGR uint8 panel image.
    """
    if mode == "overlay":
        return draw_contours(apply_mask_overlay(image_bgr, mask), mask)
    if mode == "mask":
        return cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    raise ValueError(f"mode must be 'overlay' or 'mask', got {mode!r}")


def make_comparison_panel(
    panels: list[np.ndarray],
    labels: list[str],
) -> np.ndarray:
    """
    Build a horizontal comparison image with text labels above each panel.

    Parameters
    ----------
    panels : list[np.ndarray]
        BGR images to concatenate left-to-right.
    labels : list[str]
        Label per panel (same length as ``panels``).

    Returns
    -------
    np.ndarray
        Combined BGR image.
    """
    if len(panels) != len(labels):
        raise ValueError("panels and labels must have the same length")
    labeled = [_label_panel(p, text) for p, text in zip(panels, labels)]
    return cv2.hconcat(_align_panel_heights(labeled))


def save_comparison_panel(path: str | Path, panel: np.ndarray) -> None:
    """Write a comparison panel image to disk."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), panel):
        raise IOError(f"Failed to write image: {path}")


def show_results(
    original: np.ndarray,
    mask: np.ndarray,
    overlay: np.ndarray,
) -> None:
    """
    Display a 1x3 panel: original | binary mask | overlay with contours.

    Parameters
    ----------
    original : np.ndarray
        BGR uint8 source image.
    mask : np.ndarray
        Binary mask (H, W).
    overlay : np.ndarray
        BGR overlay image (often with contours).
    """
    mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    combined = make_comparison_panel(
        [original, mask_bgr, overlay],
        ["Original", "Mask", "Overlay"],
    )
    cv2.imshow("Graph Cut Segmentation - Results", combined)
    cv2.waitKey(0)
    cv2.destroyWindow("Graph Cut Segmentation - Results")

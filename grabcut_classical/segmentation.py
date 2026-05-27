"""Full segmentation pipeline: histogram -> graph -> min-cut -> mask."""

from __future__ import annotations

from types import ModuleType

import cv2
import numpy as np

from graph_builder import build_graph, compute_sigma_sq
from histogram import build_histogram, compute_data_term


def bgr_to_lab(image_bgr: np.ndarray) -> np.ndarray:
    """
    Convert BGR uint8 image to standard-range float32 Lab.

    OpenCV Lab uses L,a,b in 0..255; rescale to L in [0,100], a,b in [-128,127].
    """
    image_lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2Lab).astype(np.float32)
    image_lab[:, :, 0] = image_lab[:, :, 0] * 100.0 / 255.0
    image_lab[:, :, 1] = image_lab[:, :, 1] - 128.0
    image_lab[:, :, 2] = image_lab[:, :, 2] - 128.0
    return image_lab


def _clip_bbox(
    bbox: tuple[int, int, int, int],
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    """Clip bbox to image bounds; raise if smaller than 2x2."""
    x1, y1, x2, y2 = bbox
    x1 = max(0, min(int(x1), width))
    x2 = max(0, min(int(x2), width))
    y1 = max(0, min(int(y1), height))
    y2 = max(0, min(int(y2), height))
    if x2 - x1 < 2 or y2 - y1 < 2:
        raise ValueError(
            f"Bounding box must be at least 2x2 pixels after clipping; got ({x1},{y1},{x2},{y2})"
        )
    return x1, y1, x2, y2


def segment(
    image_bgr: np.ndarray,
    bbox: tuple[int, int, int, int],
    config: ModuleType,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Segment foreground from background using graph cuts and color histograms.

    Parameters
    ----------
    image_bgr : np.ndarray
        (H, W, 3) uint8 BGR image.
    bbox : tuple
        (x1, y1, x2, y2) pixel coordinates, x=column, y=row.
    config : module
        config.py module with NUM_BINS, EPSILON, BLUR_SIGMA, CONNECTIVITY.

    Returns
    -------
    mask : np.ndarray
        (H, W) uint8, 255=foreground, 0=background.
    d_fg, d_bg : np.ndarray
        (H, W) float64 data terms for debugging.
    """
    if config.BLUR_SIGMA > 0:
        ksize = int(6 * config.BLUR_SIGMA + 1) | 1
        image_bgr = cv2.GaussianBlur(image_bgr, (ksize, ksize), config.BLUR_SIGMA)

    h, w = image_bgr.shape[:2]
    x1, y1, x2, y2 = _clip_bbox(bbox, w, h)

    image_lab = bgr_to_lab(image_bgr)

    fg_pixels = image_lab[y1:y2, x1:x2].reshape(-1, 3)
    outside_mask = np.ones((h, w), dtype=bool)
    outside_mask[y1:y2, x1:x2] = False
    bg_pixels = image_lab[outside_mask]

    if fg_pixels.size == 0 or bg_pixels.size == 0:
        raise ValueError("Degenerate bbox: foreground or background seed set is empty.")

    hist_fg = build_histogram(fg_pixels, config.NUM_BINS, config.EPSILON)
    hist_bg = build_histogram(bg_pixels, config.NUM_BINS, config.EPSILON)

    d_fg, d_bg = compute_data_term(image_lab, hist_fg, hist_bg, config.NUM_BINS)
    sigma_sq = compute_sigma_sq(image_lab, config.CONNECTIVITY)
    lambda_weight = float(np.max(d_fg + d_bg))

    graph, nodes = build_graph(
        image_lab,
        d_fg,
        d_bg,
        (x1, y1, x2, y2),
        lambda_weight,
        config.CONNECTIVITY,
        sigma_sq,
    )
    graph.maxflow()

    # get_grid_segments returns SOURCE-side membership; invert so 255 = foreground.
    segments = graph.get_grid_segments(nodes)
    mask = np.logical_not(segments).reshape(h, w).astype(np.uint8) * 255

    return mask, d_fg, d_bg


# Minimum predicted FG/BG pixels to continue iterative refinement.
_MIN_ITER_SEED_PIXELS = 10


def _solve_mask_from_graph(
    graph,
    nodes: np.ndarray,
    height: int,
    width: int,
) -> np.ndarray:
    """Run maxflow and extract foreground mask (255=fg) from graph segments."""
    graph.maxflow()
    segments = graph.get_grid_segments(nodes)
    return np.logical_not(segments).reshape(height, width).astype(np.uint8) * 255


def segment_iterative(
    image_bgr: np.ndarray,
    bbox: tuple[int, int, int, int],
    config: ModuleType,
    n_iterations: int = 3,
) -> tuple[np.ndarray, np.ndarray, list[np.ndarray]]:
    """
    Iterative histogram refinement without statistical learning.

    Iteration 0 uses bbox seeds (baseline). Later iterations re-bin histograms from
    the current mask while bbox hard background constraints stay in build_graph().

    Parameters
    ----------
    image_bgr : np.ndarray
        (H, W, 3) uint8 BGR image.
    bbox : tuple
        (x1, y1, x2, y2).
    config : module
        config.py module.
    n_iterations : int
        Refinement passes after the initial cut (total solves = n_iterations + 1).

    Returns
    -------
    mask_final : np.ndarray
        Final mask after all iterations.
    mask_baseline : np.ndarray
        Mask from iteration 0.
    masks_per_iter : list[np.ndarray]
        Mask after each solve; [0]=baseline, [-1]=final.
    """
    if config.BLUR_SIGMA > 0:
        ksize = int(6 * config.BLUR_SIGMA + 1) | 1
        img_blurred = cv2.GaussianBlur(image_bgr, (ksize, ksize), config.BLUR_SIGMA)
    else:
        img_blurred = image_bgr

    h, w = image_bgr.shape[:2]
    x1, y1, x2, y2 = _clip_bbox(bbox, w, h)

    image_lab = bgr_to_lab(img_blurred)

    outside_mask = np.ones((h, w), dtype=bool)
    outside_mask[y1:y2, x1:x2] = False

    fg_pixels = image_lab[y1:y2, x1:x2].reshape(-1, 3)
    bg_pixels = image_lab[outside_mask]

    if fg_pixels.size == 0 or bg_pixels.size == 0:
        raise ValueError("Degenerate bounding box: no FG or BG seed pixels.")

    sigma_sq = compute_sigma_sq(image_lab, config.CONNECTIVITY)
    clipped_bbox = (x1, y1, x2, y2)
    masks_per_iter: list[np.ndarray] = []

    hist_fg = build_histogram(fg_pixels, config.NUM_BINS, config.EPSILON)
    hist_bg = build_histogram(bg_pixels, config.NUM_BINS, config.EPSILON)
    d_fg, d_bg = compute_data_term(image_lab, hist_fg, hist_bg, config.NUM_BINS)
    lambda_weight = float(np.max(d_fg + d_bg))
    graph, nodes = build_graph(
        image_lab,
        d_fg,
        d_bg,
        clipped_bbox,
        lambda_weight,
        config.CONNECTIVITY,
        sigma_sq,
    )
    mask = _solve_mask_from_graph(graph, nodes, h, w)
    masks_per_iter.append(mask.copy())
    mask_baseline = mask.copy()

    for it in range(1, n_iterations + 1):
        pred_fg = image_lab[mask == 255].reshape(-1, 3)
        pred_bg = image_lab[mask == 0].reshape(-1, 3)

        if len(pred_fg) < _MIN_ITER_SEED_PIXELS or len(pred_bg) < _MIN_ITER_SEED_PIXELS:
            print(f"  [iterative] Early stop at iteration {it}: degenerate mask.")
            break

        combined_bg = np.vstack([bg_pixels, pred_bg])
        hist_fg = build_histogram(pred_fg, config.NUM_BINS, config.EPSILON)
        hist_bg = build_histogram(combined_bg, config.NUM_BINS, config.EPSILON)
        d_fg, d_bg = compute_data_term(image_lab, hist_fg, hist_bg, config.NUM_BINS)
        lambda_weight = float(np.max(d_fg + d_bg))
        graph, nodes = build_graph(
            image_lab,
            d_fg,
            d_bg,
            clipped_bbox,
            lambda_weight,
            config.CONNECTIVITY,
            sigma_sq,
        )
        mask = _solve_mask_from_graph(graph, nodes, h, w)
        masks_per_iter.append(mask.copy())

    return mask, mask_baseline, masks_per_iter

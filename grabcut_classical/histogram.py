"""Color histogram construction and data term computation for graph-cut segmentation."""

from __future__ import annotations

import numpy as np


def build_histogram(
    pixels: np.ndarray,
    num_bins: int,
    epsilon: float,
) -> np.ndarray:
    """
    Build a normalized 3D Lab color histogram from seed pixels.

    Parameters
    ----------
    pixels : np.ndarray
        Shape (N, 3), float32, CIE Lab (L in [0,100], a,b in [-128,127]).
    num_bins : int
        Bins per channel (histogram shape is (B, B, B)).
    epsilon : float
        Small constant added to every bin after first normalization.

    Returns
    -------
    np.ndarray
        Shape (num_bins, num_bins, num_bins), float64, sums to 1.
    """
    # Standard Lab ranges for histogramdd (matches segmentation rescaling).
    lab_ranges = [(0.0, 100.0), (-128.0, 127.0), (-128.0, 127.0)]
    hist, _ = np.histogramdd(
        pixels,
        bins=num_bins,
        range=lab_ranges,
    )
    hist = hist.astype(np.float64)
    total = hist.sum()
    if total > 0:
        hist /= total
    # Epsilon on every bin so -log never hits zero during data term lookup.
    hist += epsilon
    hist /= hist.sum()
    return hist


def _lab_to_bin_indices(image_lab: np.ndarray, num_bins: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Map each pixel's Lab channels to discrete histogram bin indices."""
    # L: 0..100 -> bins 0..num_bins-1
    l_bins = (image_lab[..., 0] / 100.0 * num_bins).astype(np.int32)
    # a, b: -128..127 -> bins via (x+128)/255 scaling per spec
    a_bins = ((image_lab[..., 1] + 128.0) / 255.0 * num_bins).astype(np.int32)
    b_bins = ((image_lab[..., 2] + 128.0) / 255.0 * num_bins).astype(np.int32)
    max_bin = num_bins - 1
    l_bins = np.clip(l_bins, 0, max_bin)
    a_bins = np.clip(a_bins, 0, max_bin)
    b_bins = np.clip(b_bins, 0, max_bin)
    return l_bins, a_bins, b_bins


def compute_data_term(
    image_lab: np.ndarray,
    hist_fg: np.ndarray,
    hist_bg: np.ndarray,
    num_bins: int,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute per-pixel unary costs from foreground and background histograms.

    Parameters
    ----------
    image_lab : np.ndarray
        Shape (H, W, 3), float32, standard Lab ranges.
    hist_fg, hist_bg : np.ndarray
        Shape (B, B, B), normalized histograms with epsilon.
    num_bins : int
        Bins per channel.

    Returns
    -------
    D_fg, D_bg : np.ndarray
        Shape (H, W), float64. Cost of labeling pixel as fg or bg (-log prob).
    """
    l_bins, a_bins, b_bins = _lab_to_bin_indices(image_lab, num_bins)
    prob_fg = hist_fg[l_bins, a_bins, b_bins]
    prob_bg = hist_bg[l_bins, a_bins, b_bins]
    # Higher histogram probability -> lower unary cost.
    d_fg = -np.log(prob_fg)
    d_bg = -np.log(prob_bg)
    return d_fg, d_bg

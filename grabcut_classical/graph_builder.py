"""Graph construction for Boykov-Jolly style min-cut segmentation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import maxflow
import numpy as np

if TYPE_CHECKING:
    pass

# Capacity representing infinity for hard background seeds outside the bbox.
HARD_BG_CAPACITY = 1e9
# Avoid division by zero in Gaussian edge weights on uniform regions.
SIGMA_EPSILON = 1e-6

# Forward-only neighbour offsets (avoid duplicate undirected edges).
FORWARD_OFFSETS_4 = [(0, 1), (1, 0)]
FORWARD_OFFSETS_8 = [(0, 1), (1, 0), (1, 1), (1, -1)]


def compute_sigma_sq(image_lab: np.ndarray, connectivity: int) -> float:
    """
    Mean squared Lab distance over neighbouring pixel pairs (data-adaptive scale).

    Parameters
    ----------
    image_lab : np.ndarray
        Shape (H, W, 3), float32.
    connectivity : int
        4 or 8.

    Returns
    -------
    float
        Mean of ||Lab_i - Lab_j||^2 over valid forward neighbours.
    """
    h, w = image_lab.shape[:2]
    offsets = FORWARD_OFFSETS_4 if connectivity == 4 else FORWARD_OFFSETS_8
    sum_sq = 0.0
    count = 0
    for di, dj in offsets:
        # Overlap region where both pixels exist for this shift.
        if di >= 0:
            r_src = slice(0, h - di)
            r_dst = slice(di, h)
        else:
            r_src = slice(-di, h)
            r_dst = slice(0, h + di)
        if dj >= 0:
            c_src = slice(0, w - dj)
            c_dst = slice(dj, w)
        else:
            c_src = slice(-dj, w)
            c_dst = slice(0, w + dj)
        diff = image_lab[r_src, c_src] - image_lab[r_dst, c_dst]
        sq = np.sum(diff ** 2, axis=-1)
        sum_sq += float(sq.sum())
        count += int(sq.size)
    mean_sq = sum_sq / max(count, 1)
    if mean_sq <= 0.0:
        mean_sq = SIGMA_EPSILON
    return mean_sq


def _forward_offsets(connectivity: int) -> list[tuple[int, int]]:
    if connectivity == 4:
        return FORWARD_OFFSETS_4
    if connectivity == 8:
        return FORWARD_OFFSETS_8
    raise ValueError(f"connectivity must be 4 or 8, got {connectivity}")


def build_graph(
    image_lab: np.ndarray,
    d_fg: np.ndarray,
    d_bg: np.ndarray,
    bbox: tuple[int, int, int, int],
    lambda_weight: float,
    connectivity: int,
    sigma_sq: float,
) -> tuple[maxflow.Graph[float], np.ndarray]:
    """
    Build a PyMaxflow graph with T-links and N-links ready for maxflow().

    Parameters
    ----------
    image_lab : np.ndarray
        (H, W, 3) float32 Lab image.
    d_fg, d_bg : np.ndarray
        (H, W) float64 unary costs.
    bbox : tuple
        (x1, y1, x2, y2) column/row, top-left to bottom-right (exclusive end optional).
    lambda_weight : float
        Scales smoothness edges; should be max(D_fg + D_bg).
    connectivity : int
        4 or 8.
    sigma_sq : float
        Variance for Gaussian edge weights.

    Returns
    -------
    graph : maxflow.Graph[float]
        Fully constructed graph.
    nodes : np.ndarray
        Node id array from add_nodes (length H*W).
    """
    h, w = image_lab.shape[:2]
    n_nodes = h * w
    offsets = _forward_offsets(connectivity)
    edge_estimate = n_nodes * len(offsets)

    graph = maxflow.Graph[float](n_nodes, edge_estimate)
    nodes = graph.add_nodes(n_nodes)

    x1, y1, x2, y2 = bbox
    x1 = int(np.clip(x1, 0, w))
    x2 = int(np.clip(x2, 0, w))
    y1 = int(np.clip(y1, 0, h))
    y2 = int(np.clip(y2, 0, h))
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"Invalid bbox after clipping: ({x1},{y1},{x2},{y2})")

    inside = np.zeros((h, w), dtype=bool)
    inside[y1:y2, x1:x2] = True

    # PyMaxflow: source_cap = SOURCE->node, sink_cap = node->SINK (see library docs).
    # Map unary costs per project spec: high D_bg keeps node on source (foreground).
    source_cap = d_bg.copy()
    sink_cap = d_fg.copy()
    outside = ~inside
    # Hard background outside bbox: cheap to leave source, expensive to leave sink.
    source_cap[outside] = 0.0
    sink_cap[outside] = HARD_BG_CAPACITY

    source_flat = source_cap.ravel()
    sink_flat = sink_cap.ravel()
    for node_id in range(n_nodes):
        graph.add_tedge(node_id, float(source_flat[node_id]), float(sink_flat[node_id]))

    # N-links: vectorized weights, batch add_edge over flattened valid pairs.
    inv_two_sigma = 1.0 / (2.0 * sigma_sq)
    for di, dj in offsets:
        if di >= 0:
            r_src = slice(0, h - di)
            r_dst = slice(di, h)
        else:
            r_src = slice(-di, h)
            r_dst = slice(0, h + di)
        if dj >= 0:
            c_src = slice(0, w - dj)
            c_dst = slice(dj, w)
        else:
            c_src = slice(-dj, w)
            c_dst = slice(0, w + dj)

        lab_src = image_lab[r_src, c_src]
        lab_dst = image_lab[r_dst, c_dst]
        sq_dist = np.sum((lab_src - lab_dst) ** 2, axis=-1)
        weights = lambda_weight * np.exp(-sq_dist * inv_two_sigma)

        rows = np.arange(lab_src.shape[0])
        cols = np.arange(lab_src.shape[1])
        rr, cc = np.meshgrid(rows, cols, indexing="ij")
        # Global row/col in full image for flat node ids.
        row_global = rr + (0 if di >= 0 else -di)
        col_global = cc + (0 if dj >= 0 else -dj)
        src_ids = (row_global * w + col_global).ravel()
        dst_ids = ((row_global + di) * w + (col_global + dj)).ravel()
        w_flat = weights.ravel()
        for s, d, cap in zip(src_ids, dst_ids, w_flat):
            graph.add_edge(int(s), int(d), float(cap), float(cap))

    return graph, nodes

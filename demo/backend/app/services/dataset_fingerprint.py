"""Fingerprint uploaded image/GT pairs so the same dataset shares one leaderboard."""

from __future__ import annotations

import hashlib

from app.services.upload_parser import MatchedPair


def compute_dataset_id(pairs: list[MatchedPair]) -> str:
    """
    Stable ID for an upload set.

    Same stems + same file bytes → same ID. Any change → new leaderboard.
    """
    parts: list[str] = []
    for pair in sorted(pairs, key=lambda p: p.stem):
        img_hash = hashlib.sha256(pair.image_bytes).hexdigest()[:12]
        gt_hash = hashlib.sha256(pair.gt_bytes).hexdigest()[:12]
        parts.append(f"{pair.stem}:{img_hash}:{gt_hash}")
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


def dataset_label(pairs: list[MatchedPair]) -> str:
    """Short human-readable label for UI."""
    stems = sorted(p.stem for p in pairs)
    n = len(stems)
    if n <= 3:
        return ", ".join(stems)
    return f"{stems[0]}, {stems[1]}, … +{n - 2} more ({n} images)"

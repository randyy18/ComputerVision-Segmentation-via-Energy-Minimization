"""Leaderboard scoring: rewards quality and how many images were boxed."""


def compute_leaderboard_score(
    mean_iou: float,
    scored_count: int,
    image_count: int,
) -> float:
    """
    Composite score ranked on the leaderboard.

    Formula: mean IoU × images scored × completion bonus.

    - More scored images increases the score directly.
    - Finishing a higher share of the upload gives a small extra boost (up to 2×
      when every image is scored).
    """
    if scored_count <= 0 or image_count <= 0:
        return 0.0
    completion = scored_count / image_count
    completion_bonus = 0.5 + 0.5 * completion
    return float(mean_iou * scored_count * completion_bonus)

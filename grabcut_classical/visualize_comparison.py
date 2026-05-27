"""Save side-by-side comparison images: original vs segmentation result."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import ModuleType

import cv2
import numpy as np

import config
from evaluate_dataset import find_image, load_bbox, load_gt_mask
from evaluation import compute_metrics
from segmentation import segment, segment_iterative
from visualization import (
    draw_bbox,
    make_comparison_panel,
    render_segmentation_view,
    save_comparison_panel,
)


def _resolve_gt_path(data_dir: Path, stem: str) -> Path | None:
    """Return ground-truth path for stem if it exists."""
    gt_dir = data_dir / "gt"
    for ext in (".png", ".jpg", ".jpeg", ".bmp"):
        path = gt_dir / f"{stem}{ext}"
        if path.is_file():
            return path
    return None


def _iter_bbox_samples(data_dir: Path) -> list[tuple[str, Path, Path]]:
    """Collect (stem, image_path, bbox_path) for every bbox file with a matching image."""
    bboxes_dir = data_dir / "bboxes"
    images_dir = data_dir / "images"
    samples: list[tuple[str, Path, Path]] = []
    for bbox_path in sorted(bboxes_dir.glob("*.txt")):
        stem = bbox_path.stem
        try:
            image_path = find_image(images_dir, stem)
        except FileNotFoundError:
            print(f"Skipping {stem}: image not found.", file=sys.stderr)
            continue
        samples.append((stem, image_path, bbox_path))
    return samples


def _resolve_single_sample(data_dir: Path, image_arg: str) -> tuple[str, Path, Path]:
    """Resolve --image as stem name or filesystem path to (stem, image_path, bbox_path)."""
    arg_path = Path(image_arg)
    if arg_path.is_file():
        stem = arg_path.stem
        image_path = arg_path
        bbox_path = data_dir / "bboxes" / f"{stem}.txt"
        if not bbox_path.is_file():
            raise FileNotFoundError(f"No bbox file for stem '{stem}': {bbox_path}")
        return stem, image_path, bbox_path

    stem = arg_path.stem if arg_path.suffix else image_arg
    image_path = find_image(data_dir / "images", stem)
    bbox_path = data_dir / "bboxes" / f"{stem}.txt"
    if not bbox_path.is_file():
        raise FileNotFoundError(f"No bbox file for stem '{stem}': {bbox_path}")
    return stem, image_path, bbox_path


def _run_segmentation(
    image: np.ndarray,
    bbox: tuple[int, int, int, int],
    cfg: ModuleType,
    method: str,
    n_iters: int,
) -> np.ndarray:
    """Return predicted mask for baseline or iterative segmentation."""
    if method == "baseline":
        mask, _, _ = segment(image, bbox, cfg)
        return mask
    if method == "iterative":
        mask, _, _ = segment_iterative(image, bbox, cfg, n_iterations=n_iters)
        return mask
    raise ValueError(f"Unknown method: {method!r}")


def _build_panel(
    original: np.ndarray,
    mask: np.ndarray,
    right_mode: str,
    with_gt: bool,
    gt_mask: np.ndarray | None,
) -> np.ndarray:
    """Assemble labeled comparison panel(s) from original and prediction."""
    panels: list[np.ndarray] = [original]
    labels: list[str] = ["Original"]

    if right_mode == "both":
        panels.append(render_segmentation_view(original, mask, "mask"))
        labels.append("Mask")
        panels.append(render_segmentation_view(original, mask, "overlay"))
        labels.append("Overlay")
    else:
        panels.append(render_segmentation_view(original, mask, right_mode))
        labels.append("Segmentation" if right_mode == "overlay" else "Mask")

    if with_gt and gt_mask is not None:
        panels.append(cv2.cvtColor(gt_mask, cv2.COLOR_GRAY2BGR))
        labels.append("Ground truth")

    return make_comparison_panel(panels, labels)


def process_one(
    stem: str,
    image_path: Path,
    bbox_path: Path,
    data_dir: Path,
    output_dir: Path,
    cfg: ModuleType,
    method: str,
    n_iters: int,
    right_mode: str,
    draw_bbox_flag: bool,
    with_gt: bool,
) -> None:
    """Segment one image and save a comparison PNG."""
    image = cv2.imread(str(image_path))
    if image is None:
        print(f"Skipping {stem}: cannot read {image_path}", file=sys.stderr)
        return

    bbox = load_bbox(bbox_path)
    mask = _run_segmentation(image, bbox, cfg, method, n_iters)

    original = draw_bbox(image, bbox) if draw_bbox_flag else image.copy()

    gt_mask: np.ndarray | None = None
    if with_gt:
        gt_path = _resolve_gt_path(data_dir, stem)
        if gt_path is not None:
            gt_mask = load_gt_mask(gt_path, image.shape[:2])

    panel = _build_panel(original, mask, right_mode, with_gt, gt_mask)
    out_path = output_dir / f"{stem}_compare.png"
    save_comparison_panel(out_path, panel)

    msg = f"Saved {out_path}"
    if gt_mask is not None:
        metrics = compute_metrics(mask, gt_mask)
        msg += f"  (IoU={metrics['iou']:.4f})"
    print(msg)


def _default_output_dir(data_dir: Path, method: str, n_iters: int) -> Path:
    """Return method-specific comparison output folder under data-dir/outputs/."""
    base = data_dir / "outputs" / "comparisons"
    if method == "baseline":
        return base / "baseline"
    return base / f"iterative_n{n_iters}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Save original vs segmentation comparison PNGs.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "grabcut",
        help="Dataset root with images/ and bboxes/",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output folder (default: outputs/comparisons/baseline or iterative_n{N})",
    )
    parser.add_argument(
        "--image",
        type=str,
        default=None,
        help="Single image stem (e.g. banana2) or path to an image file",
    )
    parser.add_argument(
        "--method",
        choices=["baseline", "iterative"],
        default="baseline",
        help="Segmentation method",
    )
    parser.add_argument(
        "--n-iters",
        type=int,
        default=3,
        help="Refinement iterations when --method iterative",
    )
    parser.add_argument(
        "--right",
        choices=["overlay", "mask", "both"],
        default="overlay",
        help="Right panel: overlay, mask, or 3-panel original|mask|overlay",
    )
    parser.add_argument(
        "--draw-bbox",
        action="store_true",
        help="Draw the initialization bbox on the original panel",
    )
    parser.add_argument(
        "--with-gt",
        action="store_true",
        help="Append ground-truth mask panel when gt/ exists",
    )
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    output_dir = args.output_dir or _default_output_dir(data_dir, args.method, args.n_iters)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")

    if args.image is not None:
        samples = [_resolve_single_sample(data_dir, args.image)]
    else:
        samples = _iter_bbox_samples(data_dir)

    if not samples:
        print("No samples to process.", file=sys.stderr)
        sys.exit(1)

    for stem, image_path, bbox_path in samples:
        try:
            process_one(
                stem,
                image_path,
                bbox_path,
                data_dir,
                output_dir,
                config,
                args.method,
                args.n_iters,
                args.right,
                args.draw_bbox,
                args.with_gt,
            )
        except (ValueError, FileNotFoundError) as exc:
            print(f"Skipping {stem}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()

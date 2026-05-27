"""Batch evaluation on GrabCut-style dataset with per-file bboxes and GT masks."""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from types import ModuleType

import cv2
import numpy as np

import config
from evaluation import (
    compute_boundary_interior_metrics,
    compute_metrics,
)
from segmentation import segment, segment_iterative
from visualization import apply_mask_overlay, draw_contours

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp")

# IoU change below this is treated as "unchanged" in iterative comparison.
_IOU_UNCHANGED_EPS = 0.001
# Baseline IoU threshold for failure-case convergence report.
_FAILURE_IOU_THRESHOLD = 0.65
# Last-two-iteration IoU stability for "Converged?".
_CONVERGED_IOU_DELTA = 0.005

EVAL_CSV_FIELDS = [
    "image",
    "iou",
    "dice",
    "pixel_error",
    "boundary_error",
    "interior_error",
    "boundary_pixels",
    "interior_pixels",
]


def _results_dir() -> Path:
    """Create and return grabcut_classical/results/ for CSV metric outputs."""
    path = Path(__file__).resolve().parent / "results"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_bbox(bbox_path: Path) -> tuple[int, int, int, int]:
    """Load x1 y1 x2 y2 from a one-line bbox file."""
    text = bbox_path.read_text(encoding="utf-8").strip()
    parts = text.split()
    if len(parts) != 4:
        raise ValueError(f"Expected 4 values in {bbox_path}, got: {text!r}")
    return tuple(int(v) for v in parts)


def find_image(images_dir: Path, stem: str) -> Path:
    """Resolve image path by stem and common extensions."""
    for ext in IMAGE_EXTENSIONS:
        path = images_dir / f"{stem}{ext}"
        if path.is_file():
            return path
    raise FileNotFoundError(f"No image found for stem '{stem}' in {images_dir}")


def load_gt_mask(gt_path: Path, expected_shape: tuple[int, int]) -> np.ndarray:
    """
    Load ground-truth mask as uint8 0/255.

    Raises ValueError if spatial dimensions do not match the image.
    """
    mask = cv2.imread(str(gt_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        raise FileNotFoundError(f"Cannot load ground truth: {gt_path}")
    h, w = expected_shape
    if mask.shape[:2] != (h, w):
        raise ValueError(
            f"GT shape {mask.shape[:2]} does not match image shape {(h, w)} for {gt_path.name}"
        )
    return ((mask > 127).astype(np.uint8)) * 255


def _iter_samples(data_dir: Path) -> list[tuple[str, Path, Path, Path]]:
    """Collect (stem, image_path, bbox_path, gt_path) for all bbox files with GT."""
    bboxes_dir = data_dir / "bboxes"
    images_dir = data_dir / "images"
    gt_dir = data_dir / "gt"
    if not gt_dir.is_dir():
        raise FileNotFoundError(f"Ground truth directory not found: {gt_dir}")

    samples: list[tuple[str, Path, Path, Path]] = []
    for bbox_path in sorted(bboxes_dir.glob("*.txt")):
        stem = bbox_path.stem
        try:
            image_path = find_image(images_dir, stem)
        except FileNotFoundError:
            print(f"Skipping {stem}: image not found.", file=sys.stderr)
            continue
        gt_path = gt_dir / f"{stem}.png"
        if not gt_path.is_file():
            for ext in (".jpg", ".jpeg", ".bmp"):
                alt = gt_dir / f"{stem}{ext}"
                if alt.is_file():
                    gt_path = alt
                    break
        if not gt_path.is_file():
            print(f"Skipping {stem}: ground truth not found.", file=sys.stderr)
            continue
        samples.append((stem, image_path, bbox_path, gt_path))
    return samples


def _print_dataset_summary(results: list[dict], boundary_width: int) -> None:
    """Print mean metrics including boundary vs interior analysis."""
    n = len(results)
    mean_iou = float(np.mean([r["iou"] for r in results]))
    mean_dice = float(np.mean([r["dice"] for r in results]))
    mean_error = float(np.mean([r["pixel_error"] for r in results]))
    mean_bnd = float(np.mean([r["boundary_error"] for r in results]))
    mean_int = float(np.mean([r["interior_error"] for r in results]))

    print()
    print("=" * 60)
    print(f"DATASET SUMMARY (N={n})")
    print("=" * 60)
    print(f"Mean IoU:              {mean_iou:.4f}")
    print(f"Mean Dice:             {mean_dice:.4f}")
    print(f"Mean Pixel Error:      {mean_error:.4f}  (flat, whole image)")
    print()
    print(f"Boundary vs Interior Error Analysis (boundary_width={boundary_width}px):")
    print(f"  Mean Boundary Error: {mean_bnd:.4f}  (error rate in {boundary_width}px band around GT edges)")
    print(f"  Mean Interior Error: {mean_int:.4f}  (error rate in object interior)")
    if mean_int < 1e-6:
        cleaner = "N/A"
    else:
        cleaner = f"{mean_bnd / mean_int:.1f}x cleaner than boundary"
    print(f"  -> Interior is {cleaner}")
    print("=" * 60)


def run_evaluation(
    data_dir: Path,
    cfg: ModuleType,
    output_dir: Path | None = None,
    save_outputs: bool = False,
    boundary_width: int = 5,
) -> list[dict[str, float | str | int]]:
    """
    Run segmentation on all dataset samples and compute metrics vs GT.

    Returns
    -------
    list of dicts with image, iou, dice, pixel_error, boundary/interior fields.
    """
    samples = _iter_samples(data_dir)
    if not samples:
        raise RuntimeError(f"No valid samples found under {data_dir}")

    if save_outputs and output_dir is not None:
        (output_dir / "masks").mkdir(parents=True, exist_ok=True)
        (output_dir / "overlays").mkdir(parents=True, exist_ok=True)

    results: list[dict[str, float | str | int]] = []
    for stem, image_path, bbox_path, gt_path in samples:
        image = cv2.imread(str(image_path))
        if image is None:
            print(f"Skipping {stem}: cannot read {image_path}", file=sys.stderr)
            continue
        bbox = load_bbox(bbox_path)
        gt_mask = load_gt_mask(gt_path, image.shape[:2])
        pred_mask, _, _ = segment(image, bbox, cfg)
        metrics = compute_metrics(pred_mask, gt_mask)
        bi = compute_boundary_interior_metrics(pred_mask, gt_mask, boundary_width=boundary_width)
        row: dict[str, float | str | int] = {
            "image": stem,
            "iou": metrics["iou"],
            "dice": metrics["dice"],
            "pixel_error": metrics["pixel_error"],
            "boundary_error": bi["boundary_error"],
            "interior_error": bi["interior_error"],
            "boundary_pixels": bi["boundary_pixels"],
            "interior_pixels": bi["interior_pixels"],
        }
        results.append(row)
        print(f"{stem}: IoU={metrics['iou']:.4f} Dice={metrics['dice']:.4f}")

        if save_outputs and output_dir is not None:
            cv2.imwrite(str(output_dir / "masks" / f"{stem}.png"), pred_mask)
            overlay = draw_contours(apply_mask_overlay(image, pred_mask), pred_mask)
            cv2.imwrite(str(output_dir / "overlays" / f"{stem}.png"), overlay)

    if results:
        _print_dataset_summary(results, boundary_width)
        csv_path = _results_dir() / "results.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=EVAL_CSV_FIELDS)
            writer.writeheader()
            writer.writerows(results)
        print(f"Wrote {csv_path}")

    return results


def run_ablation(data_dir: Path, base_cfg: ModuleType) -> None:
    """Evaluate all NUM_BINS × CONNECTIVITY combinations with formatted output."""
    orig_bins = base_cfg.NUM_BINS
    orig_conn = base_cfg.CONNECTIVITY
    bin_values = [4, 8, 16]
    conn_values = [4, 8]
    ablation_rows: list[dict[str, float | int]] = []
    total_skipped = 0

    print()
    print("=" * 60)
    print("ABLATION STUDY - NUM_BINS x CONNECTIVITY")
    print("=" * 60)
    print(
        f"{'NUM_BINS':>8}  {'CONNECTIVITY':>12}  {'Mean_IoU':>8}  "
        f"{'Mean_Dice':>9}  {'Mean_PixErr':>11}  {'N':>3}"
    )
    print(
        f"{'--------':>8}  {'------------':>12}  {'--------':>8}  "
        f"{'---------':>9}  {'-----------':>11}  {'--':>3}"
    )

    try:
        for num_bins in bin_values:
            for conn in conn_values:
                print(f"Running NUM_BINS={num_bins}, CONNECTIVITY={conn}...")
                t0 = time.perf_counter()
                base_cfg.NUM_BINS = num_bins
                base_cfg.CONNECTIVITY = conn

                samples = _iter_samples(data_dir)
                ious: list[float] = []
                dices: list[float] = []
                pix_errs: list[float] = []
                skipped = 0

                for stem, image_path, bbox_path, gt_path in samples:
                    image = cv2.imread(str(image_path))
                    if image is None:
                        skipped += 1
                        continue
                    try:
                        bbox = load_bbox(bbox_path)
                        gt_mask = load_gt_mask(gt_path, image.shape[:2])
                        pred_mask, _, _ = segment(image, bbox, base_cfg)
                        m = compute_metrics(pred_mask, gt_mask)
                        ious.append(m["iou"])
                        dices.append(m["dice"])
                        pix_errs.append(m["pixel_error"])
                    except (ValueError, FileNotFoundError) as exc:
                        print(f"  Skip {stem}: {exc}", file=sys.stderr)
                        skipped += 1

                total_skipped += skipped
                n_ok = len(ious)
                mean_iou = float(np.mean(ious)) if ious else 0.0
                mean_dice = float(np.mean(dices)) if dices else 0.0
                mean_pix = float(np.mean(pix_errs)) if pix_errs else 0.0
                elapsed = time.perf_counter() - t0

                ablation_rows.append({
                    "num_bins": num_bins,
                    "connectivity": conn,
                    "mean_iou": mean_iou,
                    "mean_dice": mean_dice,
                    "mean_pixel_error": mean_pix,
                    "n_images": n_ok,
                })

                print(
                    f"{num_bins:8d}  {conn:12d}  {mean_iou:8.4f}  "
                    f"{mean_dice:9.4f}  {mean_pix:11.4f}  {n_ok:3d}  "
                    f"({elapsed:.1f}s)"
                )
    finally:
        base_cfg.NUM_BINS = orig_bins
        base_cfg.CONNECTIVITY = orig_conn

    print("=" * 60)
    if ablation_rows:
        best = max(ablation_rows, key=lambda r: r["mean_iou"])
        print(
            f"Best IoU:  NUM_BINS={best['num_bins']}  CONNECTIVITY={best['connectivity']}  "
            f"->  IoU={best['mean_iou']:.4f}"
        )
    print("=" * 60)
    if total_skipped > 0:
        print(f"Total images skipped (errors or unreadable): {total_skipped}")

    csv_path = _results_dir() / "ablation_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "num_bins",
                "connectivity",
                "mean_iou",
                "mean_dice",
                "mean_pixel_error",
                "n_images",
            ],
        )
        writer.writeheader()
        writer.writerows(ablation_rows)
    print(f"Wrote {csv_path}")


def run_boundary_analysis(
    data_dir: Path,
    cfg: ModuleType,
    boundary_width: int = 5,
) -> None:
    """Per-image boundary vs interior error table sorted by boundary_error."""
    samples = _iter_samples(data_dir)
    rows: list[dict[str, float | str | int]] = []

    for stem, image_path, bbox_path, gt_path in samples:
        image = cv2.imread(str(image_path))
        if image is None:
            continue
        bbox = load_bbox(bbox_path)
        gt_mask = load_gt_mask(gt_path, image.shape[:2])
        pred_mask, _, _ = segment(image, bbox, cfg)
        bi = compute_boundary_interior_metrics(pred_mask, gt_mask, boundary_width=boundary_width)
        rows.append({
            "image": stem,
            "boundary_error": bi["boundary_error"],
            "interior_error": bi["interior_error"],
            "boundary_pixels": bi["boundary_pixels"],
            "interior_pixels": bi["interior_pixels"],
        })

    rows.sort(key=lambda r: r["boundary_error"], reverse=True)

    print()
    print("=" * 60)
    print(f"BOUNDARY vs INTERIOR ERROR ANALYSIS  (boundary_width={boundary_width}px)")
    print("=" * 60)
    print(f"{'Image':<13}  {'BndryErr':>8}  {'IntErr':>7}  {'BndryPx':>7}  {'IntPx':>6}")
    print(f"{'-' * 13}  {'-' * 8}  {'-' * 7}  {'-' * 7}  {'-' * 6}")
    for r in rows:
        print(
            f"{r['image']:<13}  {r['boundary_error']:8.4f}  "
            f"{r['interior_error']:7.4f}  {r['boundary_pixels']:7d}  {r['interior_pixels']:6d}"
        )
    print("=" * 60)
    if rows:
        print("Dataset mean:")
        print(f"  Boundary error: {np.mean([r['boundary_error'] for r in rows]):.4f}")
        print(f"  Interior error: {np.mean([r['interior_error'] for r in rows]):.4f}")
    print("=" * 60)


def _iterative_better_label(delta: float) -> str:
    if abs(delta) < _IOU_UNCHANGED_EPS:
        return "~"
    return "iter" if delta > 0 else "base"


def _check_converged(iou_per_iter: list[float]) -> str:
    if len(iou_per_iter) < 2:
        return "No"
    if abs(iou_per_iter[-1] - iou_per_iter[-2]) < _CONVERGED_IOU_DELTA:
        return "Yes"
    return "No"


def run_iterative_comparison(
    data_dir: Path,
    cfg: ModuleType,
    n_iterations: int = 3,
    output_dir: Path | None = None,
    save_outputs: bool = False,
) -> None:
    """Compare baseline segment() vs segment_iterative() on the full dataset."""
    samples = _iter_samples(data_dir)
    if not samples:
        raise RuntimeError(f"No valid samples found under {data_dir}")

    iter_out: Path | None = None
    if save_outputs:
        iter_out = (output_dir or data_dir / "outputs") / "iterative"
        iter_out.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    failure_tracking: list[tuple[str, list[float]]] = []

    for stem, image_path, bbox_path, gt_path in samples:
        image = cv2.imread(str(image_path))
        if image is None:
            continue
        bbox = load_bbox(bbox_path)
        gt_mask = load_gt_mask(gt_path, image.shape[:2])

        base_mask, _, _ = segment(image, bbox, cfg)
        base_m = compute_metrics(base_mask, gt_mask)

        final_mask, _, masks_per_iter = segment_iterative(image, bbox, cfg, n_iterations=n_iterations)
        iter_m = compute_metrics(final_mask, gt_mask)

        delta = iter_m["iou"] - base_m["iou"]
        improved = delta > _IOU_UNCHANGED_EPS

        rows.append({
            "image": stem,
            "baseline_iou": base_m["iou"],
            "baseline_dice": base_m["dice"],
            "baseline_pixel_error": base_m["pixel_error"],
            "iter_iou": iter_m["iou"],
            "iter_dice": iter_m["dice"],
            "iter_pixel_error": iter_m["pixel_error"],
            "iou_delta": delta,
            "improved": improved,
        })

        if base_m["iou"] < _FAILURE_IOU_THRESHOLD:
            ious_iter = [
                compute_metrics(m, gt_mask)["iou"] for m in masks_per_iter
            ]
            failure_tracking.append((stem, ious_iter))

        if save_outputs and iter_out is not None:
            cv2.imwrite(str(iter_out / f"{stem}_baseline.png"), base_mask)
            cv2.imwrite(str(iter_out / f"{stem}_iter{n_iterations}.png"), final_mask)
            base_ov = draw_contours(apply_mask_overlay(image, base_mask), base_mask)
            iter_ov = draw_contours(apply_mask_overlay(image, final_mask), final_mask)
            panel = cv2.hconcat([base_ov, iter_ov])
            cv2.imwrite(str(iter_out / f"{stem}_compare.png"), panel)

    print()
    print("=" * 60)
    print(f"ITERATIVE vs BASELINE COMPARISON  (n_iterations={n_iterations})")
    print("=" * 60)
    print(
        f"{'Image':<13}  {'Base_IoU':>8}  {'Iter_IoU':>8}  {'Delta':>7}  {'Better?':>7}"
    )
    print(f"{'-' * 13}  {'-' * 8}  {'-' * 8}  {'-' * 7}  {'-' * 7}")
    for r in rows:
        sign = "+" if r["iou_delta"] >= 0 else ""
        print(
            f"{r['image']:<13}  {r['baseline_iou']:8.4f}  {r['iter_iou']:8.4f}  "
            f"{sign}{r['iou_delta']:6.4f}  {_iterative_better_label(r['iou_delta']):>7}"
        )

    n = len(rows)
    if n:
        mean_base_iou = float(np.mean([r["baseline_iou"] for r in rows]))
        mean_iter_iou = float(np.mean([r["iter_iou"] for r in rows]))
        mean_base_dice = float(np.mean([r["baseline_dice"] for r in rows]))
        mean_iter_dice = float(np.mean([r["iter_dice"] for r in rows]))
        mean_base_pe = float(np.mean([r["baseline_pixel_error"] for r in rows]))
        mean_iter_pe = float(np.mean([r["iter_pixel_error"] for r in rows]))
        n_improved = sum(1 for r in rows if r["iou_delta"] > _IOU_UNCHANGED_EPS)
        n_unchanged = sum(1 for r in rows if abs(r["iou_delta"]) < _IOU_UNCHANGED_EPS)
        n_degraded = sum(1 for r in rows if r["iou_delta"] < -_IOU_UNCHANGED_EPS)

        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"{'':18}  {'Baseline':>10}  {'Iterative':>10}  {'Delta':>10}")
        print(
            f"{'Mean IoU:':<18}  {mean_base_iou:10.4f}  {mean_iter_iou:10.4f}  "
            f"{mean_iter_iou - mean_base_iou:+10.4f}"
        )
        print(
            f"{'Mean Dice:':<18}  {mean_base_dice:10.4f}  {mean_iter_dice:10.4f}  "
            f"{mean_iter_dice - mean_base_dice:+10.4f}"
        )
        print(
            f"{'Mean Pixel Error:':<18}  {mean_base_pe:10.4f}  {mean_iter_pe:10.4f}  "
            f"{mean_iter_pe - mean_base_pe:+10.4f}"
        )
        print()
        print(f"Images improved:   {n_improved} / {n}")
        print(f"Images unchanged:  {n_unchanged} / {n}  (|delta IoU| < {_IOU_UNCHANGED_EPS})")
        print(f"Images degraded:   {n_degraded} / {n}")
        print("=" * 60)

    if failure_tracking:
        print()
        print("=" * 60)
        print(f"CONVERGENCE ON FAILURE CASES (baseline IoU < {_FAILURE_IOU_THRESHOLD})")
        print("=" * 60)
        header_iters = "".join(f"  {'Iter' + str(i):>6}" for i in range(n_iterations + 1))
        print(f"{'Image':<9}{header_iters}  {'Converged?':>10}")
        print(f"{'-' * 9}{'  ------' * (n_iterations + 1)}  {'-' * 10}")
        for stem, ious_iter in sorted(failure_tracking, key=lambda x: x[1][0]):
            cols = "".join(f"  {v:8.4f}" for v in ious_iter)
            pad = "  ------" * (n_iterations + 1 - len(ious_iter))
            print(f"{stem:<9}{cols}{pad}  {_check_converged(ious_iter):>10}")
        print("=" * 60)

    csv_path = _results_dir() / "iterative_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "image",
                "baseline_iou",
                "baseline_dice",
                "baseline_pixel_error",
                "iter_iou",
                "iter_dice",
                "iter_pixel_error",
                "iou_delta",
                "improved",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {csv_path}")

    if save_outputs and iter_out is not None:
        print(f"Saved iterative outputs to {iter_out}")


def run_batch_segmentation(
    data_dir: Path,
    cfg: ModuleType,
    output_dir: Path,
) -> None:
    """Segment all images and save masks/overlays without metric computation."""
    bboxes_dir = data_dir / "bboxes"
    images_dir = data_dir / "images"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "masks").mkdir(exist_ok=True)
    (output_dir / "overlays").mkdir(exist_ok=True)

    rows: list[dict[str, float | str]] = []
    for bbox_path in sorted(bboxes_dir.glob("*.txt")):
        stem = bbox_path.stem
        try:
            image_path = find_image(images_dir, stem)
        except FileNotFoundError:
            continue
        image = cv2.imread(str(image_path))
        if image is None:
            continue
        bbox = load_bbox(bbox_path)
        pred_mask, _, _ = segment(image, bbox, cfg)
        fg_pixels = int((pred_mask > 0).sum())
        fg_fraction = fg_pixels / pred_mask.size
        rows.append({
            "image": stem,
            "fg_pixels": fg_pixels,
            "fg_fraction": fg_fraction,
        })
        cv2.imwrite(str(output_dir / "masks" / f"{stem}.png"), pred_mask)
        overlay = draw_contours(apply_mask_overlay(image, pred_mask), pred_mask)
        cv2.imwrite(str(output_dir / "overlays" / f"{stem}.png"), overlay)
        print(f"Saved {stem}")

    if rows:
        csv_path = _results_dir() / "batch_results.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["image", "fg_pixels", "fg_fraction"])
            writer.writeheader()
            writer.writerows(rows)
        print(f"Wrote {csv_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate graph-cut segmentation on a dataset.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "grabcut",
        help="Dataset root with images/, bboxes/, gt/",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for saved masks/overlays",
    )
    parser.add_argument(
        "--save-outputs",
        action="store_true",
        help="Save predicted masks and overlays",
    )
    parser.add_argument(
        "--mode",
        choices=["eval", "ablation", "batch", "boundary", "iterative"],
        default="eval",
        help="eval | ablation | batch | boundary | iterative",
    )
    parser.add_argument(
        "--boundary-width",
        type=int,
        default=5,
        help="Erosion radius for boundary/interior analysis (default: 5)",
    )
    parser.add_argument(
        "--n-iters",
        type=int,
        default=3,
        help="Refinement iterations for iterative mode (default: 3)",
    )
    args = parser.parse_args()
    data_dir = args.data_dir.resolve()
    out_dir = args.output_dir
    if out_dir is None and args.save_outputs:
        out_dir = data_dir / "outputs"

    if args.mode == "eval":
        run_evaluation(
            data_dir,
            config,
            out_dir,
            save_outputs=args.save_outputs,
            boundary_width=args.boundary_width,
        )
    elif args.mode == "ablation":
        run_ablation(data_dir, config)
    elif args.mode == "boundary":
        run_boundary_analysis(data_dir, config, boundary_width=args.boundary_width)
    elif args.mode == "iterative":
        run_iterative_comparison(
            data_dir,
            config,
            n_iterations=args.n_iters,
            output_dir=out_dir,
            save_outputs=args.save_outputs,
        )
    else:
        batch_out = out_dir or (data_dir / "outputs")
        run_batch_segmentation(data_dir, config, batch_out)


if __name__ == "__main__":
    main()

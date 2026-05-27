"""Interactive graph-cut segmentation with bounding-box selection."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

import config
from segmentation import segment
from visualization import apply_mask_overlay, draw_contours, show_results

# Mouse callback state (module-level, as specified).
drawing = False
bbox_start: tuple[int, int] | None = None
bbox_end: tuple[int, int] | None = None
bbox_confirmed: tuple[int, int, int, int] | None = None
_clone: np.ndarray | None = None
_image: np.ndarray | None = None


def _normalize_bbox(
    start: tuple[int, int],
    end: tuple[int, int],
) -> tuple[int, int, int, int]:
    """Convert two corner points to (x1, y1, x2, y2) top-left / bottom-right."""
    x1 = min(start[0], end[0])
    y1 = min(start[1], end[1])
    x2 = max(start[0], end[0])
    y2 = max(start[1], end[1])
    return x1, y1, x2, y2


def _mouse_callback(event: int, x: int, y: int, flags: int, param: object) -> None:
    global drawing, bbox_start, bbox_end, bbox_confirmed
    if _clone is None:
        return
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        bbox_start = (x, y)
        bbox_end = (x, y)
        bbox_confirmed = None
    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        bbox_end = (x, y)
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        if bbox_start is not None:
            bbox_end = (x, y)
            bbox_confirmed = _normalize_bbox(bbox_start, bbox_end)


def main(image_path: str) -> None:
    """Run interactive segmentation GUI for one image."""
    global _clone, _image, bbox_confirmed, drawing, bbox_start, bbox_end

    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Cannot load image: {image_path}")

    _image = image
    _clone = image.copy()
    bbox_confirmed = None
    drawing = False
    bbox_start = None
    bbox_end = None

    print("Draw a bounding box around the foreground object.")
    print("SPACE: run segmentation | R: reset | Q: quit")

    window = "Graph Cut Segmentation"
    cv2.namedWindow(window)
    cv2.setMouseCallback(window, _mouse_callback)

    while True:
        display = _clone.copy()
        if drawing and bbox_start is not None and bbox_end is not None:
            cv2.rectangle(display, bbox_start, bbox_end, (0, 255, 0), 2)
        elif bbox_confirmed is not None:
            x1, y1, x2, y2 = bbox_confirmed
            cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)

        cv2.imshow(window, display)
        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break
        if key == ord("r"):
            _clone = _image.copy()
            bbox_confirmed = None
            bbox_start = None
            bbox_end = None
        if key == ord(" ") and bbox_confirmed is not None:
            print("Running segmentation...")
            mask, _, _ = segment(_image, bbox_confirmed, config)
            overlay = apply_mask_overlay(_image, mask)
            overlay = draw_contours(overlay, mask)
            show_results(_image, mask, overlay)
            print("Done. Press Q to quit or R to reset.")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Interactive graph-cut image segmentation.")
    parser.add_argument("image", help="Path to input image")
    args = parser.parse_args()
    try:
        main(args.image)
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

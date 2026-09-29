#!/usr/bin/env python3
"""
Crop one wide Duty master image into overlapping LEFT / RIGHT action images.

Default workflow for the current Pilgrim action art:
- master: 2048 x 682 px
- output crop: 1120 x 560 px
- vertical crop: centered
- LEFT crop: anchored to the left edge
- RIGHT crop: anchored to the right edge
- resulting horizontal overlap on a 2048 px master: 192 px

Requires:
    pip install pillow

Example:
    python crop_duty_master.py clerical_master.png --out-dir crops

Optional:
    python crop_duty_master.py clerical_master.png \
        --left-name clerical_gain_piety_v01.png \
        --right-name clerical_gain_coins_v01.png
"""

from __future__ import annotations

import argparse
from pathlib import Path
from PIL import Image


DEFAULT_CROP_W = 1120
DEFAULT_CROP_H = 560


def crop_duty_master(
    input_path: Path,
    out_dir: Path,
    crop_w: int = DEFAULT_CROP_W,
    crop_h: int = DEFAULT_CROP_H,
    left_name: str | None = None,
    right_name: str | None = None,
) -> tuple[Path, Path]:
    img = Image.open(input_path).convert("RGBA")
    master_w, master_h = img.size

    if crop_w > master_w:
        raise ValueError(
            f"Crop width {crop_w}px exceeds master width {master_w}px."
        )
    if crop_h > master_h:
        raise ValueError(
            f"Crop height {crop_h}px exceeds master height {master_h}px."
        )

    # Vertically center both crops so they remain perfectly aligned.
    y0 = (master_h - crop_h) // 2
    y1 = y0 + crop_h

    # LEFT uses the left edge of the master.
    left_box = (0, y0, crop_w, y1)

    # RIGHT uses the right edge of the master.
    right_x0 = master_w - crop_w
    right_box = (right_x0, y0, master_w, y1)

    overlap = max(0, crop_w * 2 - master_w)

    out_dir.mkdir(parents=True, exist_ok=True)

    stem = input_path.stem
    left_name = left_name or f"{stem}_left.png"
    right_name = right_name or f"{stem}_right.png"

    left_path = out_dir / left_name
    right_path = out_dir / right_name

    img.crop(left_box).save(left_path)
    img.crop(right_box).save(right_path)

    print(f"Master:       {master_w} x {master_h}")
    print(f"Crop size:    {crop_w} x {crop_h}")
    print(f"Vertical:     y={y0}:{y1}")
    print(f"LEFT box:     {left_box}")
    print(f"RIGHT box:    {right_box}")
    print(f"Overlap:      {overlap}px")
    print(f"Saved LEFT:   {left_path}")
    print(f"Saved RIGHT:  {right_path}")

    return left_path, right_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crop a wide Duty master into overlapping left/right action images."
    )
    parser.add_argument("input", type=Path, help="Path to the wide master image.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("crops"),
        help="Output directory (default: ./crops).",
    )
    parser.add_argument(
        "--crop-width",
        type=int,
        default=DEFAULT_CROP_W,
        help=f"Output crop width (default: {DEFAULT_CROP_W}).",
    )
    parser.add_argument(
        "--crop-height",
        type=int,
        default=DEFAULT_CROP_H,
        help=f"Output crop height (default: {DEFAULT_CROP_H}).",
    )
    parser.add_argument(
        "--left-name",
        type=str,
        default=None,
        help="Optional filename for the left crop.",
    )
    parser.add_argument(
        "--right-name",
        type=str,
        default=None,
        help="Optional filename for the right crop.",
    )

    args = parser.parse_args()

    crop_duty_master(
        input_path=args.input,
        out_dir=args.out_dir,
        crop_w=args.crop_width,
        crop_h=args.crop_height,
        left_name=args.left_name,
        right_name=args.right_name,
    )


if __name__ == "__main__":
    main()

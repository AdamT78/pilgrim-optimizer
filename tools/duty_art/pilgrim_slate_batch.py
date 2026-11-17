#!/usr/bin/env python3
"""Convert Pilgrim duty-action PNGs to deterministic Cold Slate inactive PNGs.

The defaults exactly reproduce the approved gamma-0.88 preview.
Only pixel RGB values change; original dimensions and alpha are preserved.
No generative models, image resizing, sharpening or spatial filters are used.

Requirements:
    python -m pip install Pillow numpy

Examples:
    python pilgrim_slate_batch.py duty_actions_active.zip
    python pilgrim_slate_batch.py ./active_images --out-dir ./inactive_images
    python pilgrim_slate_batch.py duty_actions_active.zip --gamma 0.88

Every filename ending in _active.png becomes _inactive.png.
"""

import argparse
import io
import zipfile
from pathlib import Path, PurePosixPath
from typing import Iterator

import numpy as np
from PIL import Image


# Original sRGB luminance (0..255) -> Cool Slate R, G, B.
# These stops are identical to those used for the previous Pilgrim tests.
SLATE_STOPS = np.array(
    [
        (0, 8, 14, 19),
        (24, 20, 31, 40),
        (48, 33, 48, 61),
        (72, 48, 65, 80),
        (96, 64, 82, 96),
        (120, 84, 101, 116),
        (144, 102, 119, 132),
        (168, 123, 140, 151),
        (192, 146, 161, 171),
        (216, 167, 180, 188),
        (240, 186, 197, 204),
        (255, 199, 207, 215),
    ],
    dtype=np.float32,
)


def convert_image(original: Image.Image, gamma: float = 0.88) -> Image.Image:
    """Grade RGB using a 1D tonal palette; keep original pixel/alpha geometry."""
    pixels = np.asarray(original.convert("RGBA"), dtype=np.uint8)
    original_rgb = pixels[:, :, :3].astype(np.float32)

    luminance = (
        0.2126 * original_rgb[:, :, 0]
        + 0.7152 * original_rgb[:, :, 1]
        + 0.0722 * original_rgb[:, :, 2]
    )

    # Interpolate the fixed palette, then round to 8-bit, exactly as in the
    # approved preview. This intermediate rounding matters for reproducibility.
    slate_rgb = np.stack(
        [
            np.interp(luminance, SLATE_STOPS[:, 0], SLATE_STOPS[:, channel])
            for channel in (1, 2, 3)
        ],
        axis=2,
    )
    slate_8bit = np.clip(np.rint(slate_rgb), 0, 255).astype(np.uint8)

    # Gamma < 1 gently lifts dark/middle tones without moving any pixels.
    graded_rgb = np.rint(
        255.0 * np.power(slate_8bit.astype(np.float32) / 255.0, gamma)
    ).astype(np.uint8)
    result = pixels.copy()
    result[:, :, :3] = graded_rgb
    # result[:, :, 3] remains identical to the original alpha channel.
    return Image.fromarray(result, mode="RGBA")


def source_images(source: Path) -> Iterator[tuple[str, Image.Image]]:
    if source.is_dir():
        for path in sorted(source.iterdir()):
            if path.is_file() and path.name.lower().endswith("_active.png"):
                with Image.open(path) as image:
                    image.load()
                    yield path.name, image.copy()
    elif source.is_file() and source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as archive:
            for info in sorted(archive.infolist(), key=lambda i: i.filename):
                if info.is_dir() or not info.filename.lower().endswith("_active.png"):
                    continue
                # Never extract paths from ZIP members; treat only root images.
                if PurePosixPath(info.filename).name != info.filename:
                    raise ValueError(f"Expected root-level images, got {info.filename!r}")
                with Image.open(io.BytesIO(archive.read(info))) as image:
                    image.load()
                    yield info.filename, image.copy()
    else:
        raise ValueError("Input must be a ZIP file or directory of _active.png files")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="ZIP or folder containing *_active.png")
    parser.add_argument(
        "--out-dir", type=Path, default=Path("pilgrim_duty_actions_inactive"),
        help="Where to write the individual inactive PNGs",
    )
    parser.add_argument(
        "--zip", dest="zip_path", type=Path,
        default=Path("pilgrim_duty_actions_inactive_slate_gamma088.zip"),
        help="ZIP file with all converted PNGs (root-level names)",
    )
    parser.add_argument(
        "--gamma", type=float, default=0.88,
        help="Output gamma exponent: 0.88 is the approved brightness",
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Replace existing generated outputs",
    )
    args = parser.parse_args()
    if not 0.1 <= args.gamma <= 3.0:
        parser.error("--gamma must be between 0.1 and 3.0")
    if args.input.resolve() == args.zip_path.resolve():
        parser.error("The output ZIP must differ from the source ZIP")

    inputs = list(source_images(args.input))
    if not inputs:
        parser.error("No files ending in _active.png found")

    pending = []
    for name, original in inputs:
        filename = name[:-len("_active.png")] + "_inactive.png"
        pending.append((args.out_dir / filename, original))
    if len({path.name for path, _ in pending}) != len(pending):
        parser.error("Multiple source images would produce the same filename")
    existing = [p for p, _ in pending if p.exists()]
    if args.zip_path.exists():
        existing.append(args.zip_path)
    if existing and not args.overwrite:
        parser.error("Output already exists; choose new paths or use --overwrite")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.zip_path.parent.mkdir(parents=True, exist_ok=True)
    for target, original in pending:
        graded = convert_image(original, gamma=args.gamma)
        options = {"optimize": True}
        if original.info.get("icc_profile"):
            options["icc_profile"] = original.info["icc_profile"]
        if original.info.get("dpi"):
            options["dpi"] = original.info["dpi"]
        graded.save(target, format="PNG", **options)
        print(f"{target.name}  {graded.width}x{graded.height}  RGBA")

    mode = "w" if args.overwrite else "x"
    with zipfile.ZipFile(args.zip_path, mode, compression=zipfile.ZIP_DEFLATED) as out:
        for target, _ in pending:
            out.write(target, arcname=target.name)
    print(f"Completed: {len(pending)} PNGs, ZIP: {args.zip_path}")


if __name__ == "__main__":
    main()

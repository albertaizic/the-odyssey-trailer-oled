#!/usr/bin/env python3
"""
Convert a legally obtained video into 1-bit 128x64 frames for an ESP32-S3
and SSD1306 OLED.

Recommended for this display:
    --aspect imax190

Available framing:
    source   Keep the complete source frame.
    imax190  Centre-crop to 1.90:1, then fit it on the OLED.
    imax143  Centre-crop to 1.43:1, then fit it on the OLED.
    fill     Centre-crop to the OLED's exact 2.00:1 ratio.

Examples:
    py convert_video.py odyssey_trailer.mp4 --fps 5 --aspect imax190
    py convert_video.py odyssey_trailer.mp4 --fps 5 --aspect imax143
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np


OLED_WIDTH = 128
OLED_HEIGHT = 64
BYTES_PER_FRAME = OLED_WIDTH * OLED_HEIGHT // 8

ASPECT_RATIOS = {
    "source": None,
    "imax190": 1.90,
    "imax143": 1.43,
    "fill": OLED_WIDTH / OLED_HEIGHT,
}

BAYER_4X4 = np.array(
    [
        [0, 8, 2, 10],
        [12, 4, 14, 6],
        [3, 11, 1, 9],
        [15, 7, 13, 5],
    ],
    dtype=np.uint8,
)


def centre_crop_to_aspect(
    frame: np.ndarray,
    target_aspect: float | None,
) -> np.ndarray:
    """Centre-crop a frame to the requested aspect ratio."""
    if target_aspect is None:
        return frame

    height, width = frame.shape[:2]
    source_aspect = width / height

    if abs(source_aspect - target_aspect) < 0.001:
        return frame

    if source_aspect > target_aspect:
        # Source is too wide: remove equal amounts from left and right.
        new_width = max(1, int(round(height * target_aspect)))
        x_start = max(0, (width - new_width) // 2)
        return frame[:, x_start:x_start + new_width]

    # Source is too tall: remove equal amounts from top and bottom.
    new_height = max(1, int(round(width / target_aspect)))
    y_start = max(0, (height - new_height) // 2)
    return frame[y_start:y_start + new_height, :]


def fit_with_letterbox(frame: np.ndarray) -> np.ndarray:
    """Resize without distortion and centre it on the 128x64 OLED canvas."""
    source_height, source_width = frame.shape[:2]

    if source_width <= 0 or source_height <= 0:
        raise ValueError("Invalid source frame dimensions")

    scale = min(OLED_WIDTH / source_width, OLED_HEIGHT / source_height)
    resized_width = max(1, int(round(source_width * scale)))
    resized_height = max(1, int(round(source_height * scale)))

    resized = cv2.resize(
        frame,
        (resized_width, resized_height),
        interpolation=cv2.INTER_AREA,
    )

    canvas = np.zeros((OLED_HEIGHT, OLED_WIDTH, 3), dtype=np.uint8)
    x = (OLED_WIDTH - resized_width) // 2
    y = (OLED_HEIGHT - resized_height) // 2
    canvas[y:y + resized_height, x:x + resized_width] = resized
    return canvas


def prepare_frame(
    frame: np.ndarray,
    aspect_mode: str,
) -> np.ndarray:
    target_aspect = ASPECT_RATIOS[aspect_mode]
    cropped = centre_crop_to_aspect(frame, target_aspect)
    return fit_with_letterbox(cropped)


def make_one_bit_frame(
    frame: np.ndarray,
    aspect_mode: str,
    dither_mode: str,
    threshold: int,
) -> bytes:
    fitted = prepare_frame(frame, aspect_mode)
    gray = cv2.cvtColor(fitted, cv2.COLOR_BGR2GRAY)

    # Increase local visibility on the very small monochrome screen.
    gray = cv2.equalizeHist(gray)

    if dither_mode == "ordered":
        tiled = np.tile(
            BAYER_4X4,
            (OLED_HEIGHT // 4, OLED_WIDTH // 4),
        )
        threshold_map = ((tiled + 0.5) / 16.0) * 255.0
        pixels_on = gray.astype(np.float32) > threshold_map
    else:
        pixels_on = gray > threshold

    raw = np.packbits(pixels_on, axis=1).tobytes()

    if len(raw) != BYTES_PER_FRAME:
        raise RuntimeError(
            f"Packed frame has {len(raw)} bytes, "
            f"expected {BYTES_PER_FRAME}"
        )

    return raw


def write_output(
    frames: list[bytes],
    fps: int,
    output_dir: Path,
) -> None:
    header_path = output_dir / "odyssey_frames.h"
    source_path = output_dir / "odyssey_frames.cpp"

    header_content = f"""#pragma once

#include <Arduino.h>

constexpr uint16_t ODYSSEY_WIDTH = {OLED_WIDTH};
constexpr uint16_t ODYSSEY_HEIGHT = {OLED_HEIGHT};
constexpr uint16_t ODYSSEY_BYTES_PER_FRAME = {BYTES_PER_FRAME};
constexpr uint8_t ODYSSEY_FPS = {fps}
constexpr uint32_t ODYSSEY_FRAME_COUNT = {len(frames)}

extern const uint8_t
ODYSSEY_FRAMES[ODYSSEY_FRAME_COUNT][ODYSSEY_BYTES_PER_FRAME]
"""

    with header_path.open("w") as h:
        h.write(header_content)

    with source_path.open("w") as cpp:
        cpp.write('#include "odyssey_frames.h"\n\n')
        cpp.write(
            f"const uint8_t ODYSSEY_FRAMES[{len(frames)}][{BYTES_PER_FRAME}] = {{\n"
        )

        for frame in frames:
            cpp.write("  {\n")
            for offset in range(0, len(frame), 32):
                chunk = frame[offset:offset + 32]
                values = ", ".join(
                    f"0x{value:02X}" for value in chunk
                )
                cpp.write(f"    {values},\n")

            cpp.write("  },\n")

        cpp.write("};\n")

    total_bytes = len(frames) * BYTES_PER_FRAME
    print()
    print(f"Created: {header_path}")
    print(f"Created: {source_path}")
    print(f"Frames:  {len(frames)}")
    print(f"FPS:     {fps}")
    print(
        f"Flash:   {total_bytes:,} bytes "
        f"({total_bytes / 1024:.1f} KiB)"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert video to ESP32 SSD1306 frame data."
    )
    parser.add_argument(
        "video",
        type=Path,
        help="Input MP4, MKV, or MOV file",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=5,
        choices=range(1, 16),
        help="Output frames per second (1-15, default: 5)",
    )
    parser.add_argument(
        "--start",
        type=float,
        default=0.0,
        help="Start time in seconds (default: 0)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Maximum converted duration in seconds",
    )
    parser.add_argument(
        "--aspect",
        choices=tuple(ASPECT_RATIOS.keys()),
        default="imax190",
        help=(
            "Framing: source, imax190, imax143, or fill "
            "(default: imax190)"
        ),
    )
    parser.add_argument(
        "--dither",
        choices=("ordered", "threshold"),
        default="ordered",
        help="Black/white conversion method (default: ordered)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=128,
        help="Threshold used with --dither threshold (default: 128)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Directory for output files (default: current)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.output_dir.resolve() != Path(".").resolve():
        print("ERROR: Only the current directory is supported", file=sys.stderr)
        return 1

    if not args.video.is_file():
        print(f"ERROR: {args.video} not found", file=sys.stderr)
        return 1

    if not 0 <= args.threshold <= 255:
        print(
            "ERROR: --threshold must be between 0 and 255",
            file=sys.stderr,
        )
        return 1

    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        print(f"ERROR: Could not open {args.video}", file=sys.stderr)
        return 1

    source_fps = capture.get(cv2.CAP_PROP_FPS)
    source_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    source_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    source_frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    source_duration = (
        source_frame_count / source_fps if source_frame_count else 0
    )

    start_frame = int(round(args.start * source_fps))
    capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    frame_step = source_fps / args.fps
    next_sample_frame = float(start_frame)
    stop_frame = None

    if args.duration is not None:
        stop_frame = start_frame + int(
            round(args.duration * source_fps)
        )

    print(f"Source size:     {source_width}x{source_height}")
    print(f"Source FPS:      {source_fps:.3f}")
    if source_duration > 0:
        print(f"Source duration: {source_duration:.1f} seconds")
    print(f"Output FPS:      {args.fps}")
    print(f"Aspect mode:     {args.aspect}")
    print("Converting...")

    frames: list[bytes] = []
    current_frame_number = start_frame

    while True:
        ret, frame = capture.read()
        if not ret:
            break

        if stop_frame is not None and current_frame_number >= stop_frame:
            break

        if current_frame_number + 1e-6 >= next_sample_frame:
            frames.append(
                make_one_bit_frame(
                    frame,
                    args.aspect,
                    args.dither,
                    args.threshold,
                )
            )
            next_sample_frame += frame_step

        current_frame_number += 1

    capture.release()

    if not frames:
        print("ERROR: No frames extracted", file=sys.stderr)
        return 1

    write_output(frames, args.fps, args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
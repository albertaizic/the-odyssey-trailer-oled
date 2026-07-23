#!/usr/bin/env python3
"""
Convert a legally obtained video file into 1-bit 128x64 frames for the
ESP32-S3 OdysseyTrailerOLED Arduino sketch.

Install:
    py -m pip install opencv-python numpy

Example:
    py convert_video.py odyssey_trailer.mp4 --fps 5 --duration 150

The script creates:
    odyssey_frames.h
    odyssey_frames.cpp
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import cv2
import numpy as np


WIDTH = 128
HEIGHT = 64
BYTES_PER_FRAME = WIDTH * HEIGHT // 8

BAYER_4X4 = np.array(
    [
        [0, 8, 2, 10],
        [12, 4, 14, 6],
        [3, 11, 1, 9],
        [15, 7, 13, 5],
    ],
    dtype=np.float32,
)


def fit_with_letterbox(frame: np.ndarray) -> np.ndarray:
    """Resize without distortion and center it on a 128x64 black canvas."""
    source_height, source_width = frame.shape[:2]

    if source_width <= 0 or source_height <= 0:
        raise ValueError("Invalid source frame dimensions")

    scale = min(WIDTH / source_width, HEIGHT / source_height)
    resized_width = max(1, int(round(source_width * scale)))
    resized_height = max(1, int(round(source_height * scale)))

    resized = cv2.resize(
        frame,
        (resized_width, resized_height),
        interpolation=cv2.INTER_AREA,
    )

    canvas = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    x = (WIDTH - resized_width) // 2
    y = (HEIGHT - resized_height) // 2
    canvas[y:y + resized_height, x:x + resized_width] = resized
    return canvas


def make_one_bit_frame(frame: np.ndarray, mode: str, threshold: int) -> bytes:
    fitted = fit_with_letterbox(frame)
    gray = cv2.cvtColor(fitted, cv2.COLOR_BGR2GRAY)

    # Improve readability on a very small monochrome display.
    gray = cv2.equalizeHist(gray)

    if mode == "ordered":
        tiled = np.tile(BAYER_4X4, (HEIGHT // 4, WIDTH // 4))
        threshold_map = ((tiled + 0.5) / 16.0) * 255.0
        pixels_on = gray.astype(np.float32) > threshold_map
    else:
        pixels_on = gray >= threshold

    packed = np.packbits(pixels_on, axis=1, bitorder="big")
    raw = packed.tobytes()

    if len(raw) != BYTES_PER_FRAME:
        raise RuntimeError(
            f"Packed frame has {len(raw)} bytes; expected {BYTES_PER_FRAME}"
        )

    return raw


def write_output(frames: list[bytes], fps: int, output_dir: Path) -> None:
    header_path = output_dir / "odyssey_frames.h"
    source_path = output_dir / "odyssey_frames.cpp"

    header = f"""#pragma once

#include <Arduino.h>

constexpr uint16_t ODYSSEY_WIDTH = {WIDTH};
constexpr uint16_t ODYSSEY_HEIGHT = {HEIGHT};
constexpr uint16_t ODYSSEY_BYTES_PER_FRAME = {BYTES_PER_FRAME};
constexpr uint8_t ODYSSEY_FPS = {fps};
constexpr uint32_t ODYSSEY_FRAME_COUNT = {len(frames)};

extern const uint8_t
ODYSSEY_FRAMES[ODYSSEY_FRAME_COUNT][ODYSSEY_BYTES_PER_FRAME];
"""
    header_path.write_text(header, encoding="utf-8")

    with source_path.open("w", encoding="utf-8", newline="\n") as output:
        output.write('#include <Arduino.h>\n')
        output.write('#include "odyssey_frames.h"\n\n')
        output.write(
            "const uint8_t "
            "ODYSSEY_FRAMES[ODYSSEY_FRAME_COUNT]"
            "[ODYSSEY_BYTES_PER_FRAME] PROGMEM = {\n"
        )

        for frame_number, frame in enumerate(frames):
            output.write(f"  {{ // frame {frame_number}\n")

            for offset in range(0, len(frame), 32):
                chunk = frame[offset:offset + 32]
                values = ", ".join(f"0x{value:02X}" for value in chunk)
                output.write(f"    {values},\n")

            output.write("  },\n")

        output.write("};\n")

    total_bytes = len(frames) * BYTES_PER_FRAME
    print(f"Created: {header_path}")
    print(f"Created: {source_path}")
    print(f"Frames:  {len(frames)}")
    print(f"FPS:     {fps}")
    print(f"Flash:   {total_bytes:,} bytes ({total_bytes / 1024:.1f} KiB)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert video to ESP32 SSD1306 frame data."
    )
    parser.add_argument("video", type=Path, help="Input MP4/MKV/MOV file")
    parser.add_argument(
        "--fps",
        type=int,
        default=5,
        help="Output frame rate, normally 4-8 (default: 5)",
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
        "--mode",
        choices=("ordered", "threshold"),
        default="ordered",
        help="Black/white conversion method (default: ordered)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=128,
        help="Threshold used with --mode threshold (default: 128)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Folder for generated .h and .cpp files",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.video.is_file():
        print(f"ERROR: Video not found: {args.video}", file=sys.stderr)
        return 1

    if not 1 <= args.fps <= 15:
        print("ERROR: --fps must be between 1 and 15", file=sys.stderr)
        return 1

    if args.start < 0:
        print("ERROR: --start cannot be negative", file=sys.stderr)
        return 1

    if args.duration is not None and args.duration <= 0:
        print("ERROR: --duration must be positive", file=sys.stderr)
        return 1

    if not 0 <= args.threshold <= 255:
        print("ERROR: --threshold must be between 0 and 255", file=sys.stderr)
        return 1

    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        print(
            "ERROR: OpenCV could not open the video. "
            "Try converting it to a normal H.264 MP4 first.",
            file=sys.stderr,
        )
        return 1

    source_fps = capture.get(cv2.CAP_PROP_FPS)
    if source_fps <= 0:
        print("ERROR: Could not determine source FPS", file=sys.stderr)
        capture.release()
        return 1

    source_frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    source_duration = source_frame_count / source_fps if source_frame_count else 0

    start_frame = int(round(args.start * source_fps))
    capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    frame_step = source_fps / args.fps
    next_sample_frame = float(start_frame)
    current_frame_number = start_frame
    stop_frame = None

    if args.duration is not None:
        stop_frame = start_frame + int(round(args.duration * source_fps))

    print(f"Source FPS:      {source_fps:.3f}")
    if source_duration > 0:
        print(f"Source duration: {source_duration:.1f} seconds")
    print(f"Output FPS:      {args.fps}")
    print("Converting...")

    frames: list[bytes] = []

    while True:
        ok, frame = capture.read()
        if not ok:
            break

        if stop_frame is not None and current_frame_number >= stop_frame:
            break

        if current_frame_number + 1e-6 >= next_sample_frame:
            frames.append(
                make_one_bit_frame(frame, args.mode, args.threshold)
            )
            next_sample_frame += frame_step

            if len(frames) % 100 == 0:
                print(f"  {len(frames)} frames")

        current_frame_number += 1

    capture.release()

    if not frames:
        print("ERROR: No frames were produced", file=sys.stderr)
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_output(frames, args.fps, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

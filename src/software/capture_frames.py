"""
Collect labelled training images from the Tapo C200.

Shows the live camera feed next to the 32x32 grayscale image the model
actually sees. Frames are saved into a staging folder, NOT the training set,
so they can be reviewed and sorted before being moved into src/data/:

    0  -> src/captured_frames/unsorted/
    1  -> src/captured_frames/irrelevant/
    2  -> src/captured_frames/safe/
    3  -> src/captured_frames/unsafe/
    a  -> toggle auto-capture into the last-used folder
    q  -> quit

After reviewing, move the images you want to keep into the matching
src/data/<class>/ folder and re-run train_cnn.py.

Auto-capture saves one frame every --interval seconds and skips frames that
barely changed since the last save, so leaving it running while someone
moves around the bed does not fill the folder with duplicates.

Examples:

    python src/software/capture_frames.py
    python src/software/capture_frames.py --auto --interval 0.5
    python src/software/capture_frames.py --source 0      # laptop webcam
"""

from datetime import datetime
from pathlib import Path
import argparse
import time

import cv2
import numpy as np

from camera_stream import CameraStream


# Kept outside src/data so unreviewed frames never end up in training, and
# so train_cnn.py's check for exactly three class folders is not affected.
CAPTURE_DIR = Path(__file__).resolve().parent.parent / "captured_frames"
CLASSES = ["unsorted", "irrelevant", "safe", "unsafe"]
KEY_TO_CLASS = {
    ord("0"): "unsorted",
    ord("1"): "irrelevant",
    ord("2"): "safe",
    ord("3"): "unsafe",
}
MODEL_SIZE = 32


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--source", default="tapo",
        help="'tapo' (default), a webcam index like 0, or a video path/URL."
    )
    parser.add_argument(
        "--stream", default="stream1", choices=["stream1", "stream2"],
        help="Tapo stream. stream1 is full quality (default)."
    )
    parser.add_argument(
        "--out", type=Path, default=CAPTURE_DIR,
        help=f"Folder to save captures into (default {CAPTURE_DIR})."
    )
    parser.add_argument(
        "--label", choices=CLASSES, default="unsorted",
        help="Folder used by auto-capture (default unsorted)."
    )
    parser.add_argument(
        "--auto", action="store_true",
        help="Start with auto-capture enabled."
    )
    parser.add_argument(
        "--interval", type=float, default=1.0,
        help="Seconds between auto-captured frames (default 1.0)."
    )
    parser.add_argument(
        "--min-change", type=float, default=3.0,
        help="Skip auto-captures whose 32x32 mean pixel difference from the "
             "last save is below this (0-255, default 3.0, 0 disables)."
    )
    parser.add_argument(
        "--max-width", type=int, default=640,
        help="Downscale saved images to this width to keep the dataset "
             "small (default 640, 0 keeps full resolution)."
    )
    return parser.parse_args()


def model_view(frame):
    """The exact 32x32 grayscale image train_cnn.py / predictfpga.py use."""

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, (MODEL_SIZE, MODEL_SIZE))


def save_frame(frame, label, out_dir, max_width):
    folder = out_dir / label
    folder.mkdir(parents=True, exist_ok=True)

    if max_width and frame.shape[1] > max_width:
        scale = max_width / frame.shape[1]
        frame = cv2.resize(
            frame,
            (max_width, round(frame.shape[0] * scale)),
            interpolation=cv2.INTER_AREA
        )

    name = datetime.now().strftime("tapo_%Y%m%d_%H%M%S_%f.jpg")
    path = folder / name

    if not cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 92]):
        raise IOError(f"Could not write {path}")

    return path


def count_images(out_dir):
    exts = {".jpg", ".jpeg", ".png", ".bmp"}
    return {
        label: sum(
            1 for p in (out_dir / label).glob("*") if p.suffix.lower() in exts
        ) if (out_dir / label).is_dir() else 0
        for label in CLASSES
    }


def draw_overlay(frame, small, label, auto, counts, flash):
    h, w = frame.shape[:2]
    display = frame.copy()

    # Show the model's 32x32 view, upscaled, in the top-right corner.
    preview_size = max(96, h // 4)
    preview = cv2.resize(
        small, (preview_size, preview_size), interpolation=cv2.INTER_NEAREST
    )
    preview = cv2.cvtColor(preview, cv2.COLOR_GRAY2BGR)
    display[10:10 + preview_size, w - preview_size - 10:w - 10] = preview

    lines = [
        "0 unsorted  1 irrelevant  2 safe  3 unsafe  a auto  q quit",
        f"auto: {'ON' if auto else 'off'} -> {label}",
        "  ".join(f"{k}: {v}" for k, v in counts.items()),
    ]

    if flash:
        lines.append(flash)

    for i, text in enumerate(lines):
        y = 30 + i * 28
        cv2.putText(display, text, (12, y), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (0, 0, 0), 4)
        cv2.putText(display, text, (12, y), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (0, 255, 0) if not auto else (0, 165, 255), 2)

    # Fit very large frames on screen.
    if w > 1280:
        scale = 1280 / w
        display = cv2.resize(display, (1280, round(h * scale)))

    return display


def main():
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    label = args.label
    auto = args.auto
    counts = count_images(args.out)
    last_saved_small = None
    last_auto_time = 0.0
    flash, flash_until = "", 0.0

    with CameraStream(args.source, stream=args.stream) as cam:
        print(f"Connected to {cam.display_name}")
        print(f"Saving into {args.out}")

        last_id = None

        while cam.running:
            last_id, frame = cam.read(last_id)

            if frame is None:
                continue

            small = model_view(frame)
            now = time.time()
            to_save = None

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break
            if key == ord("a"):
                auto = not auto
                last_auto_time = 0.0
            elif key in KEY_TO_CLASS:
                label = KEY_TO_CLASS[key]
                to_save = label

            if auto and to_save is None and now - last_auto_time >= args.interval:
                last_auto_time = now
                changed = (
                    last_saved_small is None
                    or args.min_change <= 0
                    or np.mean(cv2.absdiff(small, last_saved_small))
                    >= args.min_change
                )
                if changed:
                    to_save = label

            if to_save:
                path = save_frame(frame, to_save, args.out, args.max_width)
                counts[to_save] += 1
                last_saved_small = small
                flash, flash_until = f"saved {to_save}/{path.name}", now + 1.0
                print(f"[saved] {path}")

            if now > flash_until:
                flash = ""

            cv2.imshow(
                "Capture training frames",
                draw_overlay(frame, small, label, auto, counts, flash)
            )

    cv2.destroyAllWindows()
    print("Images per class:", count_images(args.out))


if __name__ == "__main__":
    main()

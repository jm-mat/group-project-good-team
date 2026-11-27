"""
Live bed-safety detection on the Tapo C200 using the Keras model on the PC.

This is the software counterpart of predictfpga.py --source tapo: it runs
the same 32x32 grayscale model, but on the computer instead of the Basys-3.
Use it to check model quality on the real camera before going to hardware.

Examples:

    python src/software/predictcamera.py
    python src/software/predictcamera.py --notify            # alert phone app
    python src/software/predictcamera.py --source 0          # laptop webcam
"""

import os

os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

from pathlib import Path
import argparse
import time

import cv2
import numpy as np
from tensorflow import keras

from camera_stream import CameraStream
import predictfpga


MODEL_PATH = Path(__file__).resolve().parent / "cnn_bed_fall_detection.h5"
CLASSES = ["IRRELEVANT", "SAFE", "UNSAFE"]
COLORS = {"SAFE": (0, 255, 0), "UNSAFE": (0, 0, 255), "IRRELEVANT": (0, 255, 255)}


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source", default="tapo",
                        help="'tapo' (default), a webcam index, or a path/URL.")
    parser.add_argument("--stream", default="stream2",
                        choices=["stream1", "stream2"],
                        help="Tapo stream. stream2 (low-res) is plenty for a "
                             "32x32 model and has less lag (default).")
    parser.add_argument("--model", type=Path, default=MODEL_PATH)
    parser.add_argument("--notify", action="store_true",
                        help="POST alerts to the mobile-app server.")
    parser.add_argument("--server", default=predictfpga.APP_SERVER_URL,
                        help="Mobile-app server URL "
                             f"(default {predictfpga.APP_SERVER_URL}).")
    return parser.parse_args()


def preprocess(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (32, 32)).astype("float32") / 255.0
    return small[np.newaxis, :, :, np.newaxis]


def softmax(x):
    e = np.exp(x - np.max(x))
    return e / e.sum()


def main():
    args = parse_args()

    print("Loading model...")
    model = keras.models.load_model(args.model, compile=False)

    unsafe_count = 0

    with CameraStream(args.source, stream=args.stream) as cam:
        print(f"Connected to {cam.display_name}. Press q to quit.")
        last_id = None

        while cam.running:
            last_id, frame = cam.read(last_id)

            if frame is None:
                continue

            started = time.time()
            # Call the model directly; model.predict() has large per-call
            # overhead for single frames.
            logits = model(preprocess(frame), training=False).numpy()[0]
            probs = softmax(logits)
            prediction = CLASSES[int(np.argmax(probs))]

            unsafe_count, should_alert = predictfpga.update_unsafe_count(
                prediction, unsafe_count
            )

            if should_alert:
                print(f"[ALERT] {unsafe_count} consecutive UNSAFE frames")

                if args.notify:
                    packet = predictfpga.create_alert_packet(
                        prediction, unsafe_count
                    )
                    try:
                        predictfpga.notify_mobile_app(packet, args.server)
                        print("[Mobile app notified successfully]")
                    except RuntimeError as error:
                        print("[Mobile app notification failed]", error)

                unsafe_count = 0

            infer_ms = (time.time() - started) * 1000
            text = (
                f"{prediction} | Irr:{probs[0]:.2f} Safe:{probs[1]:.2f} "
                f"Unsafe:{probs[2]:.2f} | streak {unsafe_count} | "
                f"{infer_ms:.0f} ms"
            )
            cv2.putText(frame, text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (0, 0, 0), 4)
            cv2.putText(frame, text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, COLORS[prediction], 2)

            if not cam.connected:
                cv2.putText(frame, "RECONNECTING...", (20, 80),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            cv2.imshow("Bed Safety Detection - Live", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

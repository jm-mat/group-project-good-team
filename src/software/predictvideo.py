import os

# Disable TensorFlow CPU optimizations that can produce different numerical
# behavior on different computers.
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

from pathlib import Path
import sys
import time

import tensorflow as tf
from tensorflow import keras
import numpy as np
import cv2
from tkinter import Tk
from tkinter.filedialog import askopenfilename
import serial


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Change this to the serial port connected to the ESP32.
COM_PORT = "COM5"

# This must match Serial.begin(9600) in the ESP32 sketch.
BAUD_RATE = 9600

# The model expects 32x32 grayscale images and produces three classes.
EXPECTED_INPUT_SHAPE = (32, 32, 1)
CLASSES = ["IRRELEVANT", "SAFE", "UNSAFE"]

# The alert is activated after this many unsafe frames.
UNSAFE_FRAME_LIMIT = 5

# The trained model is expected to be in the current working directory.
MODEL_PATH = (
    Path(__file__).resolve().parent
    / "cnn_bed_fall_detection.h5"
)


# ---------------------------------------------------------------------------
# Select a video file
# ---------------------------------------------------------------------------
# Create a hidden Tkinter window so only the file-selection dialog is shown.
root = Tk()
root.withdraw()

video_path = askopenfilename(
    title="Select a video file",
    filetypes=[
        ("MP4 files", "*.mp4"),
        ("Video files", "*.avi *.mov *.mkv"),
        ("All files", "*.*")
    ]
)

# Close the hidden Tkinter window after the dialog finishes.
root.destroy()

# Stop safely if the user cancels the file-selection dialog.
if not video_path:
    print("No file selected. Exiting.")
    raise SystemExit(0)

video_path = Path(video_path)

# Confirm that the selected path refers to a real file.
if not video_path.is_file():
    raise FileNotFoundError(
        f"The selected video does not exist: {video_path}"
    )

print("Selected video:", video_path)


# ---------------------------------------------------------------------------
# Validate serial-port configuration
# ---------------------------------------------------------------------------
# These checks catch configuration mistakes before opening the serial port.
if not COM_PORT:
    raise ValueError("COM_PORT cannot be empty.")

if not isinstance(BAUD_RATE, int) or BAUD_RATE <= 0:
    raise ValueError(
        f"BAUD_RATE must be a positive integer, got {BAUD_RATE}."
    )


# ---------------------------------------------------------------------------
# Load and validate the trained model
# ---------------------------------------------------------------------------
if not MODEL_PATH.is_file():
    raise FileNotFoundError(
        f"Model file was not found: {MODEL_PATH}\n"
        "Place cnn_bed_fall_detection.h5 in the current directory."
    )

print("Loading model...")

try:
    model = keras.models.load_model(
        MODEL_PATH,
        compile=False
    )
except Exception as error:
    raise RuntimeError(
        f"Unable to load model '{MODEL_PATH}': {error}"
    ) from error

print("Model loaded.")

# Confirm that the model input matches the preprocessing function.
actual_input_shape = tuple(model.input_shape[1:])

if actual_input_shape != EXPECTED_INPUT_SHAPE:
    raise ValueError(
        "Model input shape does not match the expected shape.\n"
        f"Expected: {EXPECTED_INPUT_SHAPE}\n"
        f"Found:    {actual_input_shape}"
    )

# Confirm that the model has one output for every classification label.
if model.output_shape[-1] != len(CLASSES):
    raise ValueError(
        "Model output count does not match the class list.\n"
        f"Expected: {len(CLASSES)} outputs\n"
        f"Found:    {model.output_shape[-1]} outputs"
    )


# ---------------------------------------------------------------------------
# Open the ESP32 serial connection
# ---------------------------------------------------------------------------
ser = None

try:
    ser = serial.Serial(
        COM_PORT,
        BAUD_RATE,
        timeout=1,
        dsrdtr=False,  # Prevent DSR/DTR from resetting the ESP32.
        rtscts=False   # Disable hardware RTS/CTS flow control.
    )

    # Explicitly keep these control lines inactive so opening the port does
    # not unintentionally reset the ESP32.
    ser.dtr = False
    ser.rts = False

    # Allow the ESP32 to finish resetting and initialize its serial interface.
    time.sleep(2)

    print(f"Serial connection opened on {COM_PORT} at {BAUD_RATE} baud.")

except serial.SerialException as error:
    raise RuntimeError(
        f"Unable to open serial port '{COM_PORT}'. "
        "Check the port name, USB connection, and whether another program "
        f"is already using the port. Details: {error}"
    ) from error


# ---------------------------------------------------------------------------
# Send an alert command to the ESP32
# ---------------------------------------------------------------------------
def send_alert(state: bool):
    """
    Send one byte to control the ESP32 alert.

    The ESP32 sketch interprets:
        b'1' as alert ON
        b'0' as alert OFF
    """

    if ser is None or not ser.is_open:
        raise RuntimeError(
            "Cannot send an alert because the serial port is not open."
        )

    command = b"1" if state else b"0"

    # Confirm that exactly one command byte is written.
    bytes_written = ser.write(command)

    if bytes_written != 1:
        raise IOError(
            f"Expected to write one alert byte, wrote {bytes_written}."
        )

    # Force the command to leave the host serial buffer immediately.
    ser.flush()

    print(
        f"[Serial] Sent alert {'ON' if state else 'OFF'}"
    )


# ---------------------------------------------------------------------------
# Convert a video frame to the model input format
# ---------------------------------------------------------------------------
def preprocess_frame(frame):
    """
    Convert one OpenCV BGR frame into a validated model input tensor.

    Returned shape:
        (1, 32, 32, 1)

    The tensor contains one grayscale image, one batch dimension, and one
    grayscale channel dimension.
    """

    if frame is None:
        raise ValueError("Received an empty video frame.")

    # A normal OpenCV color frame has height, width, and three BGR channels.
    if frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError(
            f"Expected a BGR frame with shape (height, width, 3), "
            f"got {frame.shape}."
        )

    # Convert the color frame to one grayscale channel.
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Resize to the same resolution used during model training.
    resized = cv2.resize(gray, (32, 32))

    # Convert pixels to floating point values before normalization.
    normalized = resized.astype("float32")

    if not np.all(np.isfinite(normalized)):
        raise ValueError(
            "The frame contains NaN or infinite pixel values."
        )

    if np.min(normalized) < 0 or np.max(normalized) > 255:
        raise ValueError(
            "Frame pixel values are outside the expected range [0, 255]."
        )

    # Match the normalization used by train_cnn.py.
    normalized = normalized / 255.0

    if not np.all(np.isfinite(normalized)):
        raise ValueError(
            "Normalized frame contains NaN or infinite values."
        )

    if np.min(normalized) < 0.0 or np.max(normalized) > 1.0:
        raise ValueError(
            "Normalized frame values are outside the expected range [0, 1]."
        )

    # Add a batch dimension and a grayscale-channel dimension.
    input_tensor = np.expand_dims(normalized, axis=(0, -1))

    if input_tensor.shape != (1, 32, 32, 1):
        raise ValueError(
            "Preprocessed frame has an unexpected shape.\n"
            f"Expected: {(1, 32, 32, 1)}\n"
            f"Found:    {input_tensor.shape}"
        )

    return input_tensor


# ---------------------------------------------------------------------------
# Open the video
# ---------------------------------------------------------------------------
cap = cv2.VideoCapture(str(video_path))

if not cap.isOpened():
    raise RuntimeError(
        f"OpenCV could not open the video file: {video_path}"
    )


# ---------------------------------------------------------------------------
# Process video frames
# ---------------------------------------------------------------------------
print("Starting video processing...")

unsafe_num = 0

try:
    while True:
        # Read one frame from the video.
        ret, frame = cap.read()

        # ret is False when the video ends or a frame cannot be decoded.
        if not ret:
            print("End of video.")
            break

        # Convert the frame into the model's expected tensor format.
        input_tensor = preprocess_frame(frame)

        # The final Dense layer in train_cnn.py produces logits rather than
        # probabilities, so convert the output with softmax.
        logits = model.predict(
            input_tensor,
            verbose=0
        )

        if logits.shape != (1, len(CLASSES)):
            raise ValueError(
                "Model returned an unexpected output shape.\n"
                f"Expected: {(1, len(CLASSES))}\n"
                f"Found:    {logits.shape}"
            )

        if not np.all(np.isfinite(logits)):
            raise ValueError(
                "Model output contains NaN or infinite values."
            )

        # Convert the three logits into probabilities between 0 and 1.
        probabilities = tf.nn.softmax(logits[0]).numpy()

        if not np.isclose(np.sum(probabilities), 1.0, atol=1e-5):
            raise ValueError(
                "Model probabilities do not sum to approximately 1."
            )

        # Select the class with the largest probability.
        prediction_index = int(np.argmax(probabilities))
        prediction = CLASSES[prediction_index]

        irr, safe, unsafe = probabilities

        # Count unsafe frames toward the alert threshold.
        if prediction == "UNSAFE":
            unsafe_num += 1

        text = (
            f"{prediction} | "
            f"Irr:{irr:.2f} "
            f"Safe:{safe:.2f} "
            f"Unsafe:{unsafe:.2f}"
        )

        # Use a different display color for each classification.
        if prediction == "SAFE":
            color = (0, 255, 0)       # Green
        elif prediction == "UNSAFE":
            color = (0, 0, 255)       # Red
        else:
            color = (0, 255, 255)     # Yellow

        # Display the prediction and probabilities on the video frame.
        cv2.putText(
            frame,
            text,
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            color,
            2
        )

        cv2.imshow("Bed Safety Detection", frame)

        # Allow the user to stop processing by pressing q.
        if cv2.waitKey(1) & 0xFF == ord("q"):
            print("Processing stopped by user.")
            break

        # Activate the ESP32 alert after enough unsafe frames are detected.
        if unsafe_num >= UNSAFE_FRAME_LIMIT:
            send_alert(True)
            print(
                f"Alert triggered after {unsafe_num} unsafe frames."
            )

            # Keep the alert active briefly before ending this run.
            time.sleep(0.5)
            break

finally:
    # Always release the video and GUI resources, including when an exception
    # occurs during inference or serial communication.
    cap.release()
    cv2.destroyAllWindows()

    # Close the serial connection if it was successfully opened.
    if ser is not None and ser.is_open:
        ser.close()
        print("Serial connection closed.")


print(f"Unsafe Frames: {unsafe_num}")
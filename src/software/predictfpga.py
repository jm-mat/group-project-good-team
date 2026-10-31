from pathlib import Path
import json
import time

from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import cv2
import numpy as np
import serial
from serial import SerialException


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Serial port connected to the FPGA.
UART_PORT = "COM5"

# Must match the baud rate used by the FPGA UART.
BAUDRATE = 115200

# Each frame is converted into a 32x32 grayscale image.
FRAME_SIZE = 32

# Desired video-processing rate.
TARGET_FPS = 30

# Maximum time to wait for an FPGA response.
TIMEOUT_SEC = 0.2

# Default test video included in the repository.
# Change this path if using a different video.
VIDEO_PATH = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "input_files"
    / "input_video.mp4"
)

# FPGA prediction IDs and their labels:
#
#   0 = IRRELEVANT
#   1 = SAFE
#   2 = UNSAFE
labels = [
    "IRRELEVANT",
    "SAFE",
    "UNSAFE"
]

# Number of consecutive unsafe predictions required before
# notifying the mobile application.
ALERT_THRESHOLD = 5

# The FPGA receives one 8-bit grayscale pixel for every image pixel.
EXPECTED_PACKET_SIZE = FRAME_SIZE * FRAME_SIZE

# IP address of the computer running server.js.
#
# Replace this address if the computer's Wi-Fi IP address changes.
APP_SERVER_URL = "http://192.168.1.72:50222"


# ---------------------------------------------------------------------------
# Configuration validation
# ---------------------------------------------------------------------------

def validate_configuration():
    """
    Validate configuration values before opening files or hardware.

    This function is kept separate so that the mock E2E test can import
    predictfpga.py without opening the video file or serial port.
    """

    if not UART_PORT:
        raise ValueError(
            "UART_PORT cannot be empty."
        )

    if not isinstance(BAUDRATE, int) or BAUDRATE <= 0:
        raise ValueError(
            f"BAUDRATE must be a positive integer, got {BAUDRATE}."
        )

    if not isinstance(FRAME_SIZE, int) or FRAME_SIZE <= 0:
        raise ValueError(
            f"FRAME_SIZE must be a positive integer, got {FRAME_SIZE}."
        )

    if not isinstance(TARGET_FPS, (int, float)) or TARGET_FPS <= 0:
        raise ValueError(
            f"TARGET_FPS must be greater than zero, got {TARGET_FPS}."
        )

    if not isinstance(TIMEOUT_SEC, (int, float)) or TIMEOUT_SEC < 0:
        raise ValueError(
            f"TIMEOUT_SEC cannot be negative, got {TIMEOUT_SEC}."
        )

    if len(labels) != 3:
        raise ValueError(
            "The FPGA protocol expects exactly three prediction labels."
        )

    if not isinstance(APP_SERVER_URL, str):
        raise ValueError(
            "APP_SERVER_URL must be a string."
        )


# ---------------------------------------------------------------------------
# FPGA prediction decoding
# ---------------------------------------------------------------------------

def decode_prediction_byte(result):
    """
    Convert the FPGA's one-byte response into a class label.

    Valid FPGA response bytes are:

        0 -> IRRELEVANT
        1 -> SAFE
        2 -> UNSAFE
    """

    if len(result) != 1:
        raise ValueError(
            "Expected exactly one FPGA response byte, "
            f"got {len(result)}."
        )

    prediction_id = result[0]

    if prediction_id >= len(labels):
        raise ValueError(
            f"Invalid FPGA prediction byte: {prediction_id}."
        )

    return labels[prediction_id]


# ---------------------------------------------------------------------------
# Unsafe-frame tracking
# ---------------------------------------------------------------------------

def update_unsafe_count(prediction, unsafe_count):
    """
    Track consecutive UNSAFE predictions.

    SAFE and IRRELEVANT predictions reset the counter.

    Returns:
        updated_count: current consecutive unsafe-frame count
        should_alert: whether the alert threshold has been reached
    """

    if not isinstance(prediction, str):
        raise ValueError(
            "prediction must be a string."
        )

    if not isinstance(unsafe_count, int) or unsafe_count < 0:
        raise ValueError(
            "unsafe_count must be a non-negative integer."
        )

    if prediction == "UNSAFE":
        unsafe_count += 1
    else:
        unsafe_count = 0

    should_alert = unsafe_count >= ALERT_THRESHOLD

    return unsafe_count, should_alert


# ---------------------------------------------------------------------------
# Mobile-app notification packet creation
# ---------------------------------------------------------------------------

def create_alert_packet(prediction, unsafe_count):
    """
    Create the JSON packet delivered to the mobile-app server.

    The packet is newline-terminated so that a future stream-based receiver
    can recognize the end of one complete message.
    """

    if prediction != "UNSAFE":
        return None

    if unsafe_count < ALERT_THRESHOLD:
        return None

    packet = {
        "type": "BED_ALERT",
        "class_id": 2,
        "label": "UNSAFE",
        "unsafe_count": unsafe_count
    }

    return (
        json.dumps(packet) + "\n"
    ).encode("utf-8")


# ---------------------------------------------------------------------------
# Mobile-app notification
# ---------------------------------------------------------------------------

def notify_mobile_app(
    alert_packet,
    app_server_url=APP_SERVER_URL
):
    """
    Send an unsafe-bed alert to the Node server used by the mobile app.

    The mobile server exposes:

        POST /simulate-fall

    The server changes its internal fall status to true. The mobile app
    periodically requests GET /status and displays the warning when it sees
    that status.
    """

    if not isinstance(
        alert_packet,
        (bytes, bytearray)
    ) or not alert_packet:
        raise ValueError(
            "alert_packet must contain a non-empty byte payload."
        )

    if not isinstance(
        app_server_url,
        str
    ) or not app_server_url.strip():
        raise ValueError(
            "app_server_url must be a non-empty URL string."
        )

    endpoint = (
        app_server_url.rstrip("/")
        + "/simulate-fall"
    )

    request = Request(
        endpoint,
        data=bytes(alert_packet),
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urlopen(
            request,
            timeout=TIMEOUT_SEC
        ) as response:
            response_body = (
                response.read()
                .decode("utf-8")
            )

    except (
        HTTPError,
        URLError,
        TimeoutError
    ) as error:
        raise RuntimeError(
            "Could not notify the mobile-app server at "
            f"{endpoint}: {error}"
        ) from error

    try:
        result = json.loads(response_body)

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "The mobile-app server returned invalid JSON: "
            f"{response_body!r}"
        ) from error

    if result.get("success") is not True:
        raise RuntimeError(
            f"The mobile-app server rejected the alert: {result}"
        )

    return result


# ---------------------------------------------------------------------------
# Frame preprocessing
# ---------------------------------------------------------------------------

def preprocess_frame(frame):
    """
    Convert one BGR video frame into the FPGA's input packet.

    The FPGA expects:

        32 x 32 grayscale pixels
        8 bits per pixel
        1024 total bytes
    """

    if frame is None:
        raise ValueError(
            "Received an empty video frame."
        )

    if frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError(
            "Expected a BGR frame with shape "
            f"(height, width, 3), got {frame.shape}."
        )

    # Convert the color frame to grayscale.
    gray = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2GRAY
    )

    # Resize to the FPGA neural-network input resolution.
    small = cv2.resize(
        gray,
        (FRAME_SIZE, FRAME_SIZE)
    )

    if small.shape != (
        FRAME_SIZE,
        FRAME_SIZE
    ):
        raise ValueError(
            "Unexpected resized frame shape: "
            f"{small.shape}"
        )

    # The FPGA expects raw unsigned 8-bit pixel values.
    # Do not divide by 255 here because the FPGA input interface receives
    # one raw byte per pixel.
    packet = np.ascontiguousarray(
        small.flatten().astype(np.uint8)
    )

    if packet.size != EXPECTED_PACKET_SIZE:
        raise ValueError(
            "Invalid FPGA packet size.\n"
            f"Expected: {EXPECTED_PACKET_SIZE} bytes\n"
            f"Found:    {packet.size} bytes"
        )

    return packet


# ---------------------------------------------------------------------------
# Main FPGA-processing application
# ---------------------------------------------------------------------------

def main():
    """
    Read video frames, send them to the FPGA, and display predictions.

    Processing path:

        video frame
        -> grayscale and resize
        -> 1024-byte UART packet
        -> FPGA inference
        -> one-byte prediction
        -> unsafe-frame threshold
        -> mobile-app notification
    """

    validate_configuration()

    # Validate the video file before opening OpenCV.
    if not VIDEO_PATH.is_file():
        raise FileNotFoundError(
            "Video file was not found:\n"
            f"{VIDEO_PATH}\n\n"
            "Update VIDEO_PATH in predictfpga.py if necessary."
        )

    # Open the video file.
    cap = cv2.VideoCapture(
        str(VIDEO_PATH)
    )

    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open video source: {VIDEO_PATH}"
        )

    ser = None
    unsafe_count = 0

    try:
        # Open the UART connection to the FPGA.
        ser = serial.Serial(
            UART_PORT,
            BAUDRATE,
            timeout=TIMEOUT_SEC
        )

        print(
            f"Serial opened on {UART_PORT} "
            f"at {BAUDRATE} baud."
        )

        frame_interval = 1.0 / TARGET_FPS

        while True:
            loop_start = time.time()

            # Read exactly one video frame.
            ret, frame = cap.read()

            if not ret or frame is None:
                print(
                    "No valid frame from source. Exiting."
                )
                break

            # Convert the frame into the 1024-byte FPGA packet.
            packet = preprocess_frame(frame)

            # Send one complete frame to the FPGA.
            bytes_written = ser.write(
                packet.tobytes()
            )

            if bytes_written != EXPECTED_PACKET_SIZE:
                raise IOError(
                    "Incomplete frame transmission.\n"
                    f"Expected: {EXPECTED_PACKET_SIZE} bytes\n"
                    f"Sent: {bytes_written} bytes"
                )

            # The FPGA should return exactly one prediction byte.
            result = ser.read(1)

            if len(result) == 0:
                overlay_text = (
                    "No response from FPGA"
                )
                overlay_color = (
                    0,
                    0,
                    255
                )

            else:
                try:
                    # Convert the FPGA response into a class label.
                    prediction = decode_prediction_byte(
                        result
                    )

                    # Track consecutive unsafe predictions.
                    unsafe_count, should_alert = (
                        update_unsafe_count(
                            prediction,
                            unsafe_count
                        )
                    )

                    # Select a display color.
                    if prediction == "SAFE":
                        overlay_color = (
                            0,
                            255,
                            0
                        )

                    elif prediction == "UNSAFE":
                        overlay_color = (
                            0,
                            0,
                            255
                        )

                    else:
                        overlay_color = (
                            0,
                            255,
                            255
                        )

                    overlay_text = (
                        f"Prediction: {prediction} "
                        f"| Unsafe count: {unsafe_count}"
                    )

                    # Notify the mobile app once the unsafe threshold is
                    # reached.
                    if should_alert:
                        alert_packet = (
                            create_alert_packet(
                                prediction,
                                unsafe_count
                            )
                        )

                        print(
                            "[Mobile app packet created]",
                            alert_packet.decode(
                                "utf-8"
                            ).strip()
                        )

                        try:
                            notify_mobile_app(
                                alert_packet
                            )

                            print(
                                "[Mobile app notified successfully]"
                            )

                        except RuntimeError as error:
                            # Keep processing if the phone or server is
                            # temporarily unavailable.
                            print(
                                "[Mobile app notification failed]",
                                error
                            )

                        # Reset the counter so one continuous unsafe sequence
                        # does not send unlimited alerts.
                        unsafe_count = 0

                except ValueError as error:
                    print(
                        f"Warning: {error}"
                    )

                    overlay_text = (
                        "Invalid FPGA prediction"
                    )

                    overlay_color = (
                        0,
                        0,
                        255
                    )

            # Draw the result on the original video frame.
            cv2.putText(
                frame,
                overlay_text,
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                overlay_color,
                2
            )

            # Display the video and prediction.
            cv2.imshow(
                "FPGA Inference",
                frame
            )

            # Press q to stop processing.
            if cv2.waitKey(1) & 0xFF == ord("q"):
                print(
                    "Processing stopped by user."
                )
                break

            # Maintain the requested frame rate.
            elapsed = time.time() - loop_start
            remaining = frame_interval - elapsed

            if remaining > 0:
                time.sleep(remaining)

    except SerialException as error:
        raise RuntimeError(
            f"Unable to communicate with FPGA on port "
            f"'{UART_PORT}': {error}"
        ) from error

    finally:
        # Release the video and display resources.
        cap.release()
        cv2.destroyAllWindows()

        # Close the serial connection if it opened successfully.
        if ser is not None and ser.is_open:
            ser.close()
            print(
                "Closed video and serial."
            )


# ---------------------------------------------------------------------------
# Program entry point
# ---------------------------------------------------------------------------

# This guard allows:
#
#   python predictfpga.py
#
# to run the real FPGA application while allowing the mock E2E test to import
# the helper functions without opening the video or serial port.
if __name__ == "__main__":
    main()

"""
Live video input from a TP-Link Tapo C200 (or any RTSP / OpenCV source).

The Tapo C200 exposes two RTSP streams once a "Camera Account" has been
created in the Tapo app (Camera -> Settings -> Advanced Settings ->
Camera Account):

    rtsp://<user>:<password>@<camera-ip>:554/stream1   high quality (1080p)
    rtsp://<user>:<password>@<camera-ip>:554/stream2   low quality (~360p)

Connection settings are read from environment variables, or from a `.env`
file in the repository root (already ignored by git):

    TAPO_IP=192.168.1.50
    TAPO_USERNAME=camera_account_user
    TAPO_PASSWORD=camera_account_password
    TAPO_STREAM=stream1            # optional, stream1 or stream2
    TAPO_RTSP_URL=rtsp://...       # optional, overrides all of the above

CameraStream reads frames on a background thread and keeps only the newest
one. RTSP clients that read slower than the camera sends otherwise fall
further and further behind real time, which is unusable for live detection.
"""

from pathlib import Path
import os
import re
import threading
import time
from urllib.parse import quote

# Force RTSP over TCP. UDP drops packets on Wi-Fi and produces smeared,
# grey frames. Must be set before OpenCV opens the stream.
os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "rtsp_transport;tcp"
)

import cv2


REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"

VALID_STREAMS = ("stream1", "stream2")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def load_env_file(path=ENV_FILE):
    """
    Load KEY=VALUE lines from a .env file into os.environ.

    Variables already set in the real environment take precedence.
    Missing files are ignored.
    """

    path = Path(path)

    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key:
            os.environ.setdefault(key, value)


def build_rtsp_url(stream=None, env=None):
    """
    Build the Tapo RTSP URL from configuration.

    The username and password are percent-encoded so that characters such
    as '@', ':' or '/' in the password do not break the URL.
    """

    if env is None:
        load_env_file()
        env = os.environ

    override = env.get("TAPO_RTSP_URL", "").strip()

    if override:
        return override

    ip = env.get("TAPO_IP", "").strip()
    username = env.get("TAPO_USERNAME", "")
    password = env.get("TAPO_PASSWORD", "")
    stream = stream or env.get("TAPO_STREAM", "stream1").strip()

    missing = [
        name
        for name, value in (
            ("TAPO_IP", ip),
            ("TAPO_USERNAME", username),
            ("TAPO_PASSWORD", password),
        )
        if not value
    ]

    if missing:
        raise ValueError(
            "Missing camera settings: "
            + ", ".join(missing)
            + f"\nSet them as environment variables or in {ENV_FILE}."
            "\nSee .env.example for the format."
        )

    if stream not in VALID_STREAMS:
        raise ValueError(
            f"TAPO_STREAM must be one of {VALID_STREAMS}, got {stream!r}."
        )

    return (
        f"rtsp://{quote(username, safe='')}:{quote(password, safe='')}"
        f"@{ip}:554/{stream}"
    )


def redact_url(url):
    """Hide credentials in a URL so it can be printed safely."""

    return re.sub(r"//[^/@]*@", "//***:***@", str(url))


def resolve_source(source="tapo", stream=None):
    """
    Convert a user-facing source name into something cv2.VideoCapture opens.

        "tapo"         -> RTSP URL from the camera configuration
        "0", "1", ...  -> local webcam index (handy for testing)
        anything else  -> file path or stream URL, used as-is
    """

    if source is None or source == "tapo":
        return build_rtsp_url(stream=stream)

    if isinstance(source, int) or str(source).isdigit():
        return int(source)

    return str(source)


# ---------------------------------------------------------------------------
# Threaded latest-frame reader
# ---------------------------------------------------------------------------

class CameraStream:
    """
    Continuously read a video source and expose only the newest frame.

    Usage:

        with CameraStream("tapo", stream="stream2") as cam:
            frame_id, frame = cam.read()
    """

    def __init__(
        self,
        source="tapo",
        stream=None,
        reconnect_delay=2.0,
        open_timeout=10.0
    ):
        self.source = resolve_source(source, stream=stream)
        self.reconnect_delay = reconnect_delay
        self.open_timeout = open_timeout

        self._cap = None
        self._lock = threading.Lock()
        self._new_frame = threading.Condition(self._lock)
        self._frame = None
        self._frame_id = 0
        self._running = False
        self._thread = None
        self.connected = False

    @property
    def display_name(self):
        return redact_url(self.source)

    # -- lifecycle ---------------------------------------------------------

    def _open(self):
        if isinstance(self.source, int):
            cap = cv2.VideoCapture(self.source)
        else:
            cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)

        # Keep OpenCV's internal queue as small as possible.
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not cap.isOpened():
            cap.release()
            return None

        return cap

    def start(self):
        """Open the source and start the reader thread."""

        self._cap = self._open()

        if self._cap is None:
            raise RuntimeError(
                f"Could not open video source: {self.display_name}\n"
                "Check that the camera is on the same network, the IP is "
                "correct, and the Camera Account username/password in the "
                "Tapo app match your settings."
            )

        self.connected = True
        self._running = True
        self._thread = threading.Thread(
            target=self._reader,
            name="CameraStream",
            daemon=True
        )
        self._thread.start()

        # Wait for the first frame so callers get a working stream.
        frame_id, frame = self.read(timeout=self.open_timeout)

        if frame is None:
            self.stop()
            raise RuntimeError(
                f"Opened {self.display_name} but received no frames "
                f"within {self.open_timeout} seconds."
            )

        return self

    def _reader(self):
        while self._running:
            ok, frame = (False, None)

            if self._cap is not None:
                ok, frame = self._cap.read()

            if ok and frame is not None:
                with self._new_frame:
                    self._frame = frame
                    self._frame_id += 1
                    self._new_frame.notify_all()
                continue

            # Stream dropped (Wi-Fi hiccup, camera reboot, end of file).
            self.connected = False

            if self._cap is not None:
                self._cap.release()
                self._cap = None

            if isinstance(self.source, str) and not self._is_live():
                # A finished video file: stop instead of looping forever.
                self._running = False
                with self._new_frame:
                    self._new_frame.notify_all()
                break

            print(
                f"[camera] Lost stream, reconnecting in "
                f"{self.reconnect_delay:.0f}s..."
            )
            time.sleep(self.reconnect_delay)
            self._cap = self._open()

            if self._cap is not None:
                self.connected = True
                print("[camera] Reconnected.")

    def _is_live(self):
        return str(self.source).lower().startswith(
            ("rtsp://", "rtsps://", "http://", "https://")
        )

    def read(self, last_id=None, timeout=5.0):
        """
        Return (frame_id, frame) for the newest frame.

        If last_id is given, wait until a frame newer than last_id arrives
        so the same frame is never processed twice. Returns (last_id, None)
        on timeout or when the source has ended.
        """

        deadline = time.time() + timeout

        with self._new_frame:
            while True:
                newer = self._frame is not None and (
                    last_id is None or self._frame_id != last_id
                )

                if newer:
                    return self._frame_id, self._frame.copy()

                remaining = deadline - time.time()

                if remaining <= 0 or not self._running:
                    return last_id, None

                self._new_frame.wait(remaining)

    @property
    def running(self):
        return self._running

    def stop(self):
        self._running = False

        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()


# ---------------------------------------------------------------------------
# Quick connection check:  python src/software/camera_stream.py [stream2]
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    stream_name = sys.argv[1] if len(sys.argv) > 1 else None

    with CameraStream("tapo", stream=stream_name) as cam:
        print(f"Connected to {cam.display_name}. Press q to quit.")

        last_id = None
        frames = 0
        started = time.time()

        while cam.running:
            last_id, frame = cam.read(last_id)

            if frame is None:
                continue

            frames += 1
            fps = frames / max(time.time() - started, 1e-6)
            h, w = frame.shape[:2]

            cv2.putText(
                frame,
                f"{w}x{h}  {fps:.1f} fps",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 0),
                2
            )
            cv2.imshow("Tapo C200", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cv2.destroyAllWindows()

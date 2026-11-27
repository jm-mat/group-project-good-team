"""Hardware-free tests for the Tapo camera configuration helpers."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "software"))

from camera_stream import build_rtsp_url, redact_url, resolve_source  # noqa: E402


def test_builds_tapo_rtsp_url():
    env = {"TAPO_IP": "192.168.1.50", "TAPO_USERNAME": "cam", "TAPO_PASSWORD": "pw"}
    assert build_rtsp_url(env=env) == "rtsp://cam:pw@192.168.1.50:554/stream1"
    assert build_rtsp_url("stream2", env=env).endswith("/stream2")


def test_special_characters_in_password_are_encoded():
    env = {"TAPO_IP": "10.0.0.2", "TAPO_USERNAME": "cam", "TAPO_PASSWORD": "p@ss:w/rd"}
    assert build_rtsp_url(env=env) == "rtsp://cam:p%40ss%3Aw%2Frd@10.0.0.2:554/stream1"


def test_full_url_override():
    env = {"TAPO_RTSP_URL": "rtsp://x:y@host/stream2"}
    assert build_rtsp_url(env=env) == "rtsp://x:y@host/stream2"


def test_missing_settings_raise():
    with pytest.raises(ValueError, match="TAPO_PASSWORD"):
        build_rtsp_url(env={"TAPO_IP": "1.2.3.4", "TAPO_USERNAME": "cam"})


def test_invalid_stream_rejected():
    env = {"TAPO_IP": "1.2.3.4", "TAPO_USERNAME": "a", "TAPO_PASSWORD": "b"}
    with pytest.raises(ValueError, match="TAPO_STREAM"):
        build_rtsp_url("stream9", env=env)


def test_redact_hides_credentials():
    assert redact_url("rtsp://cam:secret@1.2.3.4:554/stream1") == (
        "rtsp://***:***@1.2.3.4:554/stream1"
    )


def test_resolve_webcam_index_and_paths():
    assert resolve_source("0") == 0
    assert resolve_source("clip.mp4") == "clip.mp4"

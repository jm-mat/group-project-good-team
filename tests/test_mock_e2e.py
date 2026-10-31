import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = ROOT / "src" / "FPGA_Mobile_App" / "server"


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_mock_fpga_notifies_mobile_server():
    if shutil.which("node") is None:
        pytest.skip("Node.js is not installed.")

    port = free_port()

    server = subprocess.Popen(
        ["node", "server.js"],
        cwd=SERVER_DIR,
        env={
            **os.environ,
            "PORT": str(port),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        status_url = (
            f"http://127.0.0.1:{port}/status"
        )

        deadline = time.time() + 5

        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                    status_url,
                    timeout=0.5
                ):
                    break
            except (
                OSError,
                urllib.error.URLError
            ):
                time.sleep(0.1)
        else:
            pytest.fail("Mobile server did not start.")

        sys.path.insert(0, str(ROOT / "tests"))

        from mock_E2E import run_mock_e2e

        status = run_mock_e2e(
            f"http://127.0.0.1:{port}"
        )

        assert status["isFalling"] is True

    finally:
        server.terminate()

        try:
            server.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server.kill()
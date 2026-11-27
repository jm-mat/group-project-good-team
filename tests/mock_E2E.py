import argparse
import json
import sys
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
SOFTWARE_DIR = ROOT / "src" / "software"

sys.path.insert(0, str(SOFTWARE_DIR))

from predictfpga import (
    ALERT_THRESHOLD,
    create_alert_packet,
    decode_prediction_byte,
    notify_mobile_app,
    update_unsafe_count,
)


def run_mock_e2e(server_url):
    unsafe_count = 0
    alert_packet = None

    # Replace the FPGA with five UNSAFE prediction bytes.
    for _ in range(ALERT_THRESHOLD):
        prediction = decode_prediction_byte(bytes([2]))

        unsafe_count, should_alert = (
            update_unsafe_count(
                prediction,
                unsafe_count
            )
        )

        if should_alert:
            alert_packet = create_alert_packet(
                prediction,
                unsafe_count
            )

    assert alert_packet is not None

    response = notify_mobile_app(
        alert_packet,
        server_url
    )

    assert response["success"] is True

    with urlopen(
        server_url.rstrip("/") + "/status",
        timeout=2
    ) as response:
        status = json.loads(
            response.read().decode("utf-8")
        )

    assert status["isFalling"] is True

    return status


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "server_url",
        nargs="?",
        default="http://localhost:3000"
    )

    args = parser.parse_args()
    print(run_mock_e2e(args.server_url))
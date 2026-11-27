import ast
from pathlib import Path

import cv2
import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src" / "software" / "predictvideo.py"
VIDEO = ROOT / "tests" / "input_files" / "input_video.mp4"


def load_preprocess_function():
    tree = ast.parse(
        SCRIPT.read_text(encoding="utf-8")
    )

    function_node = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "preprocess_frame"
    )

    namespace = {
        "cv2": cv2,
        "np": np,
    }

    exec(
        compile(
            ast.Module(
                body=[function_node],
                type_ignores=[]
            ),
            str(SCRIPT),
            "exec"
        ),
        namespace
    )

    return namespace["preprocess_frame"]


def read_first_frame():
    cap = cv2.VideoCapture(str(VIDEO))
    assert cap.isOpened()

    try:
        success, frame = cap.read()
    finally:
        cap.release()

    assert success
    return frame


def test_video_preprocessing_shape_and_range():
    preprocess_frame = load_preprocess_function()
    tensor = preprocess_frame(read_first_frame())

    assert tensor.shape == (1, 32, 32, 1)
    assert tensor.dtype == np.float32
    assert np.isfinite(tensor).all()
    assert 0.0 <= tensor.min() <= tensor.max() <= 1.0


def test_video_preprocessing_rejects_empty_frame():
    preprocess_frame = load_preprocess_function()

    with pytest.raises(ValueError):
        preprocess_frame(None)


def test_video_tensor_works_with_saved_model():
    tf = pytest.importorskip("tensorflow")

    model = tf.keras.models.load_model(
        ROOT / "src" / "software" / "cnn_bed_fall_detection.h5",
        compile=False
    )

    tensor = load_preprocess_function()(read_first_frame())
    output = model.predict(tensor, verbose=0)

    assert output.shape == (1, 3)
    assert np.isfinite(output).all()
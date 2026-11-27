from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "src" / "data"
MODEL_PATH = ROOT / "src" / "software" / "cnn_bed_fall_detection.h5"


def test_training_dataset_has_three_classes():
    expected = {"irrelevant", "safe", "unsafe"}
    actual = {
        path.name
        for path in DATA_DIR.iterdir()
        if path.is_dir()
    }

    assert actual == expected

    for class_name in expected:
        assert list((DATA_DIR / class_name).glob("*"))


def test_saved_model_has_expected_interface():
    tf = pytest.importorskip("tensorflow")

    assert MODEL_PATH.is_file()

    model = tf.keras.models.load_model(
        MODEL_PATH,
        compile=False
    )

    assert tuple(model.input_shape[1:]) == (32, 32, 1)
    assert model.output_shape[-1] == 3
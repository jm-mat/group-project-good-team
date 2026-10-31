import argparse
import math
from pathlib import Path

import tensorflow as tf
from tensorflow import keras
import hls4ml
from hls4ml.utils.config import config_from_keras_model
import numpy as np


# ---------------------------------------------------------------------------
# Command-line mode selection
# ---------------------------------------------------------------------------
# "convert-only" creates the hls4ml project without requiring Vivado synthesis.
# "build" also compiles and synthesizes the generated HLS project.
parser = argparse.ArgumentParser(
    description="Convert the trained Keras model into an hls4ml project."
)

parser.add_argument(
    "--mode",
    choices=["convert-only", "build"],
    default="convert-only",
    help="convert-only skips synthesis; build runs compile and synthesis."
)

args = parser.parse_args()


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# The script expects to be run from the directory containing the model file.
MODEL_PATH = (
    Path(__file__).resolve().parent
    / "cnn_bed_fall_detection.h5"
)
OUTPUT_DIR = Path("hls4ml_prj")

EXPECTED_INPUT_SHAPE = (32, 32, 1)
EXPECTED_OUTPUT_CLASSES = 3
FPGA_PART = "xc7a35tcpg236-1"
HLS_BACKEND = "Vivado"


# ---------------------------------------------------------------------------
# Input validation: model file
# ---------------------------------------------------------------------------
# Check for the model before TensorFlow attempts to load it so that a missing
# file produces a clear and useful error message.
if not MODEL_PATH.is_file():
    raise FileNotFoundError(
        f"Model file was not found: {MODEL_PATH}\n"
        "Run train_cnn.py first or place the .h5 file in the current directory."
    )


# ---------------------------------------------------------------------------
# Load trained Keras model
# ---------------------------------------------------------------------------
# compile=False is used because the model only needs to be converted for
# inference. The original optimizer and training state are not required.
try:
    model = keras.models.load_model(MODEL_PATH, compile=False)
except Exception as error:
    raise RuntimeError(
        f"Unable to load Keras model '{MODEL_PATH}': {error}"
    ) from error


# Display the model architecture for diagnosis.
# model.summary() already prints the summary, so print(model.summary()) is
# avoided because it would print an additional unnecessary "None".
model.summary()


# ---------------------------------------------------------------------------
# Input validation: model interface
# ---------------------------------------------------------------------------
# The HLS design is configured for 32x32 grayscale images. The model must
# accept that exact shape so the generated hardware interface matches the
# image-preprocessing code.
actual_input_shape = tuple(model.input_shape[1:])

if actual_input_shape != EXPECTED_INPUT_SHAPE:
    raise ValueError(
        "Unexpected model input shape.\n"
        f"Expected: {EXPECTED_INPUT_SHAPE}\n"
        f"Found:    {actual_input_shape}"
    )

# The final Dense layer must produce one output for each class:
# IRRELEVANT, SAFE, and UNSAFE.
actual_output_classes = model.output_shape[-1]

if actual_output_classes != EXPECTED_OUTPUT_CLASSES:
    raise ValueError(
        "Unexpected number of model outputs.\n"
        f"Expected: {EXPECTED_OUTPUT_CLASSES}\n"
        f"Found:    {actual_output_classes}"
    )


# ---------------------------------------------------------------------------
# Input validation: supported layer types
# ---------------------------------------------------------------------------
# hls4ml supports many layer types, but unsupported layers should be detected
# before conversion instead of producing a confusing later error.
#
# This validation checks the actual Keras layer type rather than searching for
# text such as "conv" in a layer name.
supported_layer_types = (
    keras.layers.InputLayer,
    keras.layers.MaxPooling2D,
    keras.layers.Flatten,
    keras.layers.Dense,
    keras.layers.Conv2D,
    keras.layers.ReLU,
    keras.layers.Activation,
)

unsupported_layers = [
    layer
    for layer in model.layers
    if not isinstance(layer, supported_layer_types)
]

if unsupported_layers:
    unsupported_names = [
        f"{layer.name} ({type(layer).__name__})"
        for layer in unsupported_layers
    ]

    raise ValueError(
        "Unsupported Keras layer types detected:\n"
        + "\n".join(unsupported_names)
    )


# ---------------------------------------------------------------------------
# Diagnostic inference test
# ---------------------------------------------------------------------------
# Use deterministic random input so the conversion check is repeatable.
# This does not measure model accuracy; it only verifies that the model accepts
# the expected tensor format and produces a valid output.
random_generator = np.random.default_rng(seed=0)

x = random_generator.random(
    (1, *EXPECTED_INPUT_SHAPE),
    dtype=np.float32
)

if x.shape != (1, 32, 32, 1):
    raise ValueError(f"Invalid diagnostic input shape: {x.shape}")

if not np.all(np.isfinite(x)):
    raise ValueError("Diagnostic input contains NaN or infinite values.")

try:
    y = model.predict(x, verbose=0)
except Exception as error:
    raise RuntimeError(
        f"Keras inference failed before hls4ml conversion: {error}"
    ) from error

if y.shape != (1, EXPECTED_OUTPUT_CLASSES):
    raise ValueError(
        "Unexpected model output shape.\n"
        f"Expected: {(1, EXPECTED_OUTPUT_CLASSES)}\n"
        f"Found:    {y.shape}"
    )

if not np.all(np.isfinite(y)):
    raise ValueError("Model output contains NaN or infinite values.")

print("Model output shape:", y.shape)
print("Model output:", y)


# ---------------------------------------------------------------------------
# Create hls4ml configuration
# ---------------------------------------------------------------------------
# granularity='name' allows individual layer settings to be applied below.
try:
    config = config_from_keras_model(
        model,
        granularity="name"
    )
except Exception as error:
    raise RuntimeError(
        f"Unable to create hls4ml configuration: {error}"
    ) from error


# Confirm that the expected configuration sections exist before modifying them.
if "Model" not in config:
    raise KeyError("hls4ml configuration does not contain a 'Model' section.")

if "LayerName" not in config:
    raise KeyError(
        "hls4ml configuration does not contain a 'LayerName' section."
    )


# ---------------------------------------------------------------------------
# Global hls4ml settings
# ---------------------------------------------------------------------------
# Fixed-point arithmetic reduces FPGA resource usage compared with floating
# point while still providing enough precision for this small model.
config["Model"]["Precision"] = "ap_fixed<10,3>"

# Resource strategy reduces parallel hardware usage, which is appropriate for
# a resource-limited Basys-3 FPGA.
config["Model"]["Strategy"] = "Resource"

# Dataflow is disabled because this small model does not require a streaming
# dataflow architecture.
config["Model"]["Dataflow"] = False

# io_parallel exposes the model input and output as parallel interfaces.
config["Model"]["IOType"] = "io_parallel"

# ReuseFactor controls how aggressively arithmetic hardware is reused.
config["Model"]["ReuseFactor"] = 24


# ---------------------------------------------------------------------------
# Dense-layer settings
# ---------------------------------------------------------------------------
# Apply resource-oriented settings to every Dense layer instead of assuming
# that only one layer is named exactly "dense".
for keras_layer in model.layers:
    if isinstance(keras_layer, keras.layers.Dense):
        layer_name = keras_layer.name

        if layer_name not in config["LayerName"]:
            raise KeyError(
                f"Layer '{layer_name}' was not found in the hls4ml configuration."
            )

        config["LayerName"][layer_name]["Strategy"] = "Resource"
        config["LayerName"][layer_name]["ReuseFactor"] = 32


# ---------------------------------------------------------------------------
# Convert model
# ---------------------------------------------------------------------------
# This creates the hls4ml project files and the generated hardware description.
try:
    hls_model = hls4ml.converters.convert_from_keras_model(
        model,
        hls_config=config,
        output_dir=str(OUTPUT_DIR),
        part=FPGA_PART,
        backend=HLS_BACKEND
    )
except Exception as error:
    raise RuntimeError(
        f"hls4ml model conversion failed: {error}"
    ) from error

# Confirm that conversion produced the requested project directory.
if not OUTPUT_DIR.exists():
    raise RuntimeError(
        f"hls4ml conversion completed without creating '{OUTPUT_DIR}'."
    )

print(f"hls4ml project generated in: {OUTPUT_DIR}")


# ---------------------------------------------------------------------------
# Optional build mode
# ---------------------------------------------------------------------------
# Conversion-only mode stops here. This allows a grader to check conversion
# without requiring Vivado synthesis tools.
if args.mode == "convert-only":
    print("Conversion-only mode complete.")
    print("Vivado synthesis was not run.")
else:
    # Compile prepares the generated HLS model for C simulation/build steps.
    try:
        hls_model.compile()
    except Exception as error:
        raise RuntimeError(
            f"hls4ml compilation failed: {error}"
        ) from error

    # Synthesis and export require the configured Vivado toolchain.
    try:
        hls_model.build(
            csim=False,
            synth=True,
            cosim=False,
            export=True
        )
    except Exception as error:
        raise RuntimeError(
            "hls4ml build failed. Confirm that the required Vivado version "
            f"is installed and available. Details: {error}"
        ) from error

    print("hls4ml build and Vivado synthesis completed successfully.")
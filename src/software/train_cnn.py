import os
import math

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

from pathlib import Path

# The model and training pipeline expect this exact input resolution.
# Keeping the image size small reduces FPGA resource usage.
imageSize = (32, 32)

SOFTWARE_DIR = Path(__file__).resolve().parent
DATA_DIR = SOFTWARE_DIR.parent / "data"
MODEL_PATH = SOFTWARE_DIR / "cnn_bed_fall_detection.h5"

# The model produces three output values, so the dataset must contain
# exactly three class directories.
expectedClasses = {"irrelevant", "safe", "unsafe"}

# Validate that the training-data directory exists before TensorFlow attempts
# to load it. This produces a clearer error than a later file-loading failure.
if not DATA_DIR.is_dir():
    raise FileNotFoundError(
        f"Training-data directory was not found: {DATA_DIR}"
)

# Load training data from subdirectories inside "data".
# Each subdirectory represents one classification label.
train_ds = keras.preprocessing.image_dataset_from_directory(
    str(DATA_DIR),
    image_size=imageSize,
    color_mode="grayscale",
    batch_size=32,
    label_mode="categorical"  # Three classes represented as one-hot labels.
)

# TensorFlow assigns class names from the directory names.
# This validation ensures the folder names match the labels expected by
# the rest of the application.
actualClasses = set(train_ds.class_names)

if actualClasses != expectedClasses:
    raise ValueError(
        "Dataset class folders are incorrect.\n"
        f"Expected: {sorted(expectedClasses)}\n"
        f"Found:    {sorted(actualClasses)}"
    )

# Validate that the dataset contains at least one batch.
# A zero-length dataset cannot produce a trained model.
datasetCardinality = tf.data.experimental.cardinality(train_ds).numpy()

if datasetCardinality == 0:
    raise ValueError("The training dataset is empty.")

# Normalize images
def preprocess(image, label):
    # Image values loaded from standard image files should be finite.
    # NaN or infinite values would make training invalid.
    tf.debugging.assert_all_finite(
        image,
        "Input image contains NaN or infinite values."
    )

    # The input must be grayscale, meaning it must contain one channel.
    tf.debugging.assert_equal(
        tf.shape(image)[-1],
        1,
        message="Input image must contain exactly one grayscale channel."
    )

    # Image data should be in the normal 8-bit image range before scaling.
    tf.debugging.assert_greater_equal(
        image,
        0.0,
        message="Input image contains a pixel value below 0."
    )

    tf.debugging.assert_less_equal(
        image,
        255.0,
        message="Input image contains a pixel value above 255."
    )

    # Convert integer image pixels to floating point values and scale them
    # to the [0, 1] range expected by the trained neural network.
    img = tf.cast(image, tf.float32) / 255.0

    # Confirm that normalization produced valid values.
    tf.debugging.assert_all_finite(
        img,
        "Normalized image contains NaN or infinite values."
    )

    tf.debugging.assert_greater_equal(
        img,
        0.0,
        message="Normalized image contains a value below 0."
    )

    tf.debugging.assert_less_equal(
        img,
        1.0,
        message="Normalized image contains a value above 1."
    )

    # Return the validated image and its categorical label.
    return img, label


# Apply preprocessing to every batch before training.
train_ds = train_ds.map(preprocess)

# Inspect one batch to validate the dataset's final shape and label format.
sampleImages, sampleLabels = next(iter(train_ds.take(1)))

if sampleImages.shape.rank != 4:
    raise ValueError(
        f"Expected image tensors to have rank 4, got {sampleImages.shape}."
    )

if tuple(sampleImages.shape[1:]) != (32, 32, 1):
    raise ValueError(
        "Incorrect image tensor shape. "
        f"Expected (32, 32, 1), got {tuple(sampleImages.shape[1:])}."
    )

if sampleLabels.shape.rank != 2 or sampleLabels.shape[-1] != 3:
    raise ValueError(
        "Labels must use categorical format with three classes. "
        f"Got label shape {sampleLabels.shape}."
    )

# Updated Neural Network Architecture to fit Basys-3 resources
def make_model():
    # The input layer enforces the expected 32x32 grayscale input format.
    return keras.Sequential([
        layers.Input(shape=(32, 32, 1)),

        # Reduce the spatial dimensions before flattening to lower
        # the number of values entering the dense layers.
        layers.MaxPooling2D(pool_size=(2, 2)),

        # Convert the pooled image into a one-dimensional feature vector.
        layers.Flatten(),

        # Small dense layers reduce FPGA memory and logic requirements.
        layers.Dense(4, activation='relu'),
        layers.Dense(8, activation='relu'),

        # Produce one logit for each class:
        # irrelevant, safe, and unsafe.
        layers.Dense(3)
    ])


model = make_model()

# Validate the model interface before training.
if model.input_shape != (None, 32, 32, 1):
    raise ValueError(
        f"Unexpected model input shape: {model.input_shape}"
    )

if model.output_shape[-1] != 3:
    raise ValueError(
        f"Expected three model outputs, got {model.output_shape[-1]}"
    )

# Use categorical crossentropy with logits.
# The final Dense layer does not use softmax, so from_logits=True is required.
model.compile(
    optimizer='adam',
    loss=tf.keras.losses.CategoricalCrossentropy(from_logits=True),
    metrics=['accuracy']
)

# Train
history = model.fit(train_ds, epochs=60)

# Validate the recorded training results.
# Non-finite loss or accuracy usually indicates invalid input data,
# an unstable training configuration, or a numerical failure.
for metricName, metricValues in history.history.items():
    if not metricValues:
        raise ValueError(f"No values were recorded for metric '{metricName}'.")

    if not all(math.isfinite(float(value)) for value in metricValues):
        raise ValueError(
            f"Training metric '{metricName}' contains NaN or infinite values."
        )

# Save model
model.save(MODEL_PATH)

print(
    f"Training complete. Model saved as {MODEL_PATH}"
)
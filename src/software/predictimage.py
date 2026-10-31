import os

# Disable a TensorFlow CPU optimization that can create inconsistent numerical
# behavior across different systems.
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

from pathlib import Path

import tensorflow as tf
from tensorflow import keras
import numpy as np
import cv2
from tkinter import Tk
from tkinter.filedialog import askopenfilename


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# The trained model expects one 32x32 grayscale image.
EXPECTED_INPUT_SHAPE = (32, 32, 1)

# These labels must match the three output neurons of the trained model.
classes = ["IRRELEVANT", "SAFE", "UNSAFE"]

MODEL_PATH = (
    Path(__file__).resolve().parent
    / "cnn_bed_fall_detection.h5"
)

SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp"
}


# ---------------------------------------------------------------------------
# Select an input image
# ---------------------------------------------------------------------------
# Create a hidden Tkinter window so that only the file-selection dialog appears.
root = Tk()
root.withdraw()

# Ask the user to select an image file.
image_path = askopenfilename(
    title="Select an image",
    filetypes=[
        ("Image files", "*.jpg *.jpeg *.png *.bmp"),
        ("All files", "*.*")
    ]
)

# Close the hidden Tkinter window after the dialog is finished.
root.destroy()

# Stop safely if the user cancels the file-selection dialog.
if not image_path:
    print("No file selected. Exiting.")
    raise SystemExit(0)

image_path = Path(image_path)

# Confirm that the selected path points to a regular file.
if not image_path.is_file():
    raise FileNotFoundError(
        f"The selected image does not exist: {image_path}"
    )

# Validate the file extension before sending it to OpenCV.
if image_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
    raise ValueError(
        f"Unsupported image format: {image_path.suffix}\n"
        f"Supported formats: {sorted(SUPPORTED_EXTENSIONS)}"
    )

print("Selected image:", image_path)


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

# Confirm that the model accepts the image shape produced by preprocessing.
actual_input_shape = tuple(model.input_shape[1:])

if actual_input_shape != EXPECTED_INPUT_SHAPE:
    raise ValueError(
        "Model input shape does not match the expected image shape.\n"
        f"Expected: {EXPECTED_INPUT_SHAPE}\n"
        f"Found:    {actual_input_shape}"
    )

# Confirm that the model produces one output for each classification label.
if model.output_shape[-1] != len(classes):
    raise ValueError(
        "Model output count does not match the class list.\n"
        f"Expected: {len(classes)} outputs\n"
        f"Found:    {model.output_shape[-1]} outputs"
    )


# ---------------------------------------------------------------------------
# Image preprocessing
# ---------------------------------------------------------------------------
def preprocess_image(path):
    """
    Load an image and convert it into the tensor format expected by the model.

    The returned tensor has shape:
        (1, 32, 32, 1)

    The first dimension is the batch dimension and the last dimension is the
    single grayscale channel.
    """

    # IMREAD_GRAYSCALE converts color images into one-channel grayscale images.
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)

    # OpenCV returns None when the file cannot be decoded.
    if img is None:
        raise ValueError(
            f"OpenCV could not read the selected image: {path}"
        )

    # A grayscale image should have height and width but no color-channel
    # dimension at this stage.
    if img.ndim != 2:
        raise ValueError(
            f"Expected a grayscale image, but received shape {img.shape}."
        )

    # Resize the input to the fixed resolution used during training.
    img = cv2.resize(img, (32, 32))

    # Convert pixels to floating point values before normalization.
    img = img.astype("float32")

    # Validate raw image pixels before scaling.
    if not np.all(np.isfinite(img)):
        raise ValueError("Image contains NaN or infinite pixel values.")

    if np.min(img) < 0 or np.max(img) > 255:
        raise ValueError(
            "Image pixel values are outside the expected range [0, 255]."
        )

    # Normalize 8-bit pixels from [0, 255] to [0, 1].
    img = img / 255.0

    # Validate the normalized image.
    if not np.all(np.isfinite(img)):
        raise ValueError(
            "Normalized image contains NaN or infinite values."
        )

    if np.min(img) < 0.0 or np.max(img) > 1.0:
        raise ValueError(
            "Normalized image values are outside the expected range [0, 1]."
        )

    # Add a batch dimension and a grayscale-channel dimension.
    input_tensor = np.expand_dims(img, axis=(0, -1))

    # Confirm that the final tensor matches the model input interface.
    if input_tensor.shape != (1, 32, 32, 1):
        raise ValueError(
            "Preprocessed input has an unexpected shape.\n"
            f"Expected: {(1, 32, 32, 1)}\n"
            f"Found:    {input_tensor.shape}"
        )

    return input_tensor


# ---------------------------------------------------------------------------
# Run inference
# ---------------------------------------------------------------------------
input_tensor = preprocess_image(image_path)

# The final Dense layer in the training script does not use softmax, so the
# model returns logits rather than probabilities.
logits = model.predict(
    input_tensor,
    verbose=0
)

# Validate the model output before using it.
if logits.shape != (1, len(classes)):
    raise ValueError(
        "Model returned an unexpected output shape.\n"
        f"Expected: {(1, len(classes))}\n"
        f"Found:    {logits.shape}"
    )

if not np.all(np.isfinite(logits)):
    raise ValueError(
        "Model output contains NaN or infinite values."
    )

# Convert logits into probabilities so the displayed values are meaningful
# percentages between 0 and 1.
probabilities = tf.nn.softmax(logits[0]).numpy()

if not np.all(np.isfinite(probabilities)):
    raise ValueError(
        "Softmax output contains NaN or infinite values."
    )

if not np.isclose(np.sum(probabilities), 1.0, atol=1e-5):
    raise ValueError(
        "Model probabilities do not sum to approximately 1."
    )

# Select the class with the greatest probability.
prediction_index = int(np.argmax(probabilities))
prediction = classes[prediction_index]

irr, safe, unsafe = probabilities


# ---------------------------------------------------------------------------
# Display prediction results
# ---------------------------------------------------------------------------
print("\nPrediction Results:")
print("-------------------")
print("Prediction:", prediction)
print(f"Irrelevant: {irr:.2f}")
print(f"Safe:       {safe:.2f}")
print(f"Unsafe:     {unsafe:.2f}")


# ---------------------------------------------------------------------------
# Display the original image with its predicted label
# ---------------------------------------------------------------------------
# Load the original color image for display so the user sees the input in its
# original appearance rather than the internally resized grayscale version.
img = cv2.imread(str(image_path))

if img is None:
    raise ValueError(
        f"OpenCV could not reload the image for display: {image_path}"
    )

# Draw the predicted class on the displayed image.
cv2.putText(
    img,
    prediction,
    (20, 40),
    cv2.FONT_HERSHEY_SIMPLEX,
    1.0,
    (0, 255, 0),
    2
)

# Show the annotated image until the user presses a key.
cv2.imshow("Prediction", img)
cv2.waitKey(0)
cv2.destroyAllWindows()
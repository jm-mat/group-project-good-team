import os
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

import tensorflow as tf
from tensorflow import keras
import numpy as np
import cv2
from tkinter import Tk
from tkinter.filedialog import askopenfilename

# Hide Tk window
Tk().withdraw()

# Ask user for an image file
image_path = askopenfilename(
    title="Select an image",
    filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")]
)

if not image_path:
    print("No file selected. Exiting.")
    exit()

print("Selected image:", image_path)

print("Loading model...")
model = keras.models.load_model("cnn_bed_fall_detection.h5", compile=False)
print("Model loaded.")

def preprocess_image(path):
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    img = cv2.resize(img, (32, 32))
    img = img.astype("float32") / 255.0
    return np.expand_dims(img, axis=(0, -1))

#3 inference classes
classes = ["IRRELEVANT", "SAFE", "UNSAFE"]

input_tensor = preprocess_image(image_path)
probabilities = model.predict(input_tensor, verbose=0)[0]

prediction = classes[np.argmax(probabilities)]
irr, safe, unsafe = probabilities

print("\nPrediction Results:")
print("-------------------")
print("Prediction:", prediction)
print(f"Irrelevant: {irr:.2f}")
print(f"Safe:       {safe:.2f}")
print(f"Unsafe:     {unsafe:.2f}")

# Show the image with label
img = cv2.imread(image_path)
cv2.putText(img, prediction, (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

cv2.imshow("Prediction", img)
cv2.waitKey(0)
cv2.destroyAllWindows()

import tensorflow as tf
from tensorflow import keras
import numpy as np
from PIL import Image

# load trained model
model = keras.models.load_model("cnn_bed_fall_detection.h5")

# preprocess the image
def load_and_preprocess(image_path):
    img = Image.open(image_path).convert("L") # grayscale
    img = img.resize((96, 96))                # resize
    img = np.array(img) / 255.0               # normalize
    img = np.expand_dims(img, axis=(0, -1))   # shape: (1, 96, 96, 1)
    return img

# run prediction
image_path = "sample_input2.jpg"                 # change path for example image
img = load_and_preprocess(image_path)

prediction = model.predict(img)[0][0]

if prediction >= 0.13:
    print("Prediction: UNSAFE")
else:
    print("Prediction: SAFE")

print("Output:", prediction)

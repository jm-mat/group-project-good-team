import tensorflow as tf
from tensorflow import keras
import numpy as np
import cv2

# load trained model
model = keras.models.load_model("cnn_bed_fall_detection.h5")

# preprocess video frames
def preprocess_frame(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (96, 96))
    normalized = resized / 255.0
    input_tensor = np.expand_dims(normalized, axis=(0, -1))  # shape: (1, 96, 96, 1)
    return input_tensor


# open video file
video_path = "input_video.mp4"   # change path for example video file
cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    print("Error: Could not open video file.")
    exit()

# process video frames
while True:
    ret, frame = cap.read()
    if not ret:
        break  # end of video

    # preprocess
    input_tensor = preprocess_frame(frame)

    # predict
    prediction = model.predict(input_tensor, verbose=0)[0][0]
    label = "UNSAFE" if prediction >= 0.13 else "SAFE"

    # display output on frame
    cv2.putText(frame, f"{label} ({prediction:.2f})",
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX,
                1.0, (0, 0, 255) if label == "UNSAFE" else (0, 255, 0), 2)

    # show frame
    cv2.imshow("Bed Safety Detection", frame)

    # Press 'q' to quit early
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

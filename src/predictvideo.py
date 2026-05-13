import os
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

import tensorflow as tf
from tensorflow import keras
import numpy as np
import cv2
from tkinter import Tk
from tkinter.filedialog import askopenfilename
import serial
import time

COM_PORT = "COM5"       # Windows: "COM3", "COM4" etc.
                        # Linux/Mac: "/dev/ttyUSB0" or "/dev/tty.usbserial-xxx"
BAUD_RATE = 9600

ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=1,
                    dsrdtr=False,      # disable DSR/DTR
                    rtscts=False)      # disable RTS/CTS
ser.dtr = False    # explicitly hold DTR low so it doesn't reset
ser.rts = False
time.sleep(2)
time.sleep(2)  # wait for ESP32 to finish rebooting after serial connect


# Hide the root Tk window
Tk().withdraw()

# Ask user for a video file
video_path = askopenfilename(
    title="Select a video file",
    filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")]
)

if not video_path:
    print("No file selected. Exiting.")
    exit()

print("Selected video:", video_path)

print("Loading model...")
model = keras.models.load_model("cnn_bed_fall_detection.h5", compile=False)
print("Model loaded.")

def send_alert(state: bool):
    cmd = b'1' if state else b'0'
    ser.write(cmd)
    print(f"[Serial] Sent alert {'ON' if state else 'OFF'}")

def preprocess_frame(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (32, 32))
    normalized = resized.astype("float32") / 255.0
    return np.expand_dims(normalized, axis=(0, -1))

classes = ["IRRELEVANT", "SAFE", "UNSAFE"]

cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    print("Error: Could not open video file.")
    exit()

print("Starting video processing...")
unsafe_num = 0
while True:
    ret, frame = cap.read()
    if not ret:
        print("End of video.")
        break

    input_tensor = preprocess_frame(frame)
    probabilities = model.predict(input_tensor, verbose=0)[0]

    prediction = classes[np.argmax(probabilities)]
    irr, safe, unsafe = probabilities
    if prediction == "UNSAFE":
        unsafe_num += 1
    text = f"{prediction} | Irr:{irr:.2f} Safe:{safe:.2f} Unsafe:{unsafe:.2f}"

    color = (0, 255, 0) if prediction == "SAFE" else \
            (0, 0, 255) if prediction == "UNSAFE" else \
            (0, 255, 255)

    cv2.putText(frame, text, (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

    cv2.imshow("Bed Safety Detection", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
    
    if unsafe_num >= 5:
        send_alert(True);
        time.sleep(0.5)
        break

cap.release()
cv2.destroyAllWindows()
print(f'Unsafe Frames: {unsafe_num}\n')



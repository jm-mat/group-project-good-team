from ast import Num
import cv2
import numpy as np
import serial
import time



# Configurations
UART_PORT   = "COM4"      # Check devicemanager for port name
BAUDRATE    = 921600      # FPGA uart_tx BAUDa
FRAME_SIZE  = 32          # 32x32 bitstream
TARGET_FPS  = 30          # desired display frame rate
TIMEOUT_SEC = 0.2         # UART read timeout

labels = ["IRRELEVANT", "SAFE", "UNSAFE"]       # 3 class labels

cap = cv2.VideoCapture("input_video.mp4")       # rename to path of video file

if not cap.isOpened():
    print("Could not open video source")
    exit()

# OPEN SERIAL
ser = serial.Serial(UART_PORT, BAUDRATE, timeout=TIMEOUT_SEC)
print(f"Serial opened on {UART_PORT} @ {BAUDRATE} baud")

frame_interval = 1.0 / TARGET_FPS

ser2 = serial.Serial('COM5', 9600, timeout=1,
                    dsrdtr=False,      # disable DSR/DTR
                    rtscts=False)      # disable RTS/CTS
ser2.dtr = False    # explicitly hold DTR low so it doesn't reset
ser2.rts = False
time.sleep(2)

# sends alert to esp32 over serial
def send_alert(state: bool):
    cmd = b'1' if state else b'0'
    ser2.write(cmd)
    print(f"[Serial] Sent alert {'ON' if state else 'OFF'}")

num_unsafe = 0;
# Main loop (trying to sync with FPGA)
while True:
    loop_start = time.time()

    # Read exactly ONE frame to send to FPGA
    ret, frame = cap.read()
    if not ret:
        print("No frame from source, exiting.")
        break

    # Preprocess frame: grayscale then resize to FRAME_SIZE x FRAME_SIZE
    gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (FRAME_SIZE, FRAME_SIZE))
    packet = small.flatten().astype(np.uint8)


    # Send preprocessed frame to FPGA
    ser.write(packet.tobytes())

    # Wait for inference result from FPGA
    result = ser.read(1)
    
    overlay_text = "No response"

    if len(result) == 1:
        pred = result[0]
        if (pred == 2):
            num_unsafe += 1
        if pred < len(labels):
            overlay_text = f"Prediction: {labels[pred]} ({pred})"
        else:
            overlay_text = f"Prediction: Unknown ({pred})"
    if (num_unsafe >= 5):
        send_alert(True)
        num_unsafe = 0
    # Overlay inference result on the same frame
    cv2.putText(frame, overlay_text, (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0) if "Prediction" in overlay_text else (0, 0, 255), 2)

    cv2.imshow("FPGA Inference (Synced)", frame)

    # Press 'q' to abort this script
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

    # Enforce desired FPS for testing
    elapsed = time.time() - loop_start
    remaining = frame_interval - elapsed
    if remaining > 0:
        time.sleep(remaining)


# Cleanup
cap.release()
cv2.destroyAllWindows()
ser.close()
ser2.close()
print("Closed video and serial.")

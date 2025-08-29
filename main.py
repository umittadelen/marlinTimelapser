import serial
import time
import cv2
import os
from tqdm import tqdm

# ---------------- SETTINGS ----------------
PORT = "COM4"       # Change to your printer's serial port
BAUDRATE = 115200
GCODE_FILE = "a.gcode"
FRAMES_DIR = "./frames"
CAMERA_INDEX = 0
# ------------------------------------------

os.makedirs(FRAMES_DIR, exist_ok=True)

# Connect to printer
ser = serial.Serial(PORT, BAUDRATE, timeout=5)
time.sleep(2)  # wait for connection

# Camera
cap = cv2.VideoCapture(CAMERA_INDEX)

def send_gcode(cmd):
    """Send a command to the printer and wait for 'ok'."""
    print(f"[→] {cmd}")
    ser.write((cmd + "\n").encode())

    while True:
        line = ser.readline().decode(errors="ignore").strip()
        if line:
            print(f"[←] Printer: {line}")
        if "ok" in line.lower():
            break

def take_picture(layer):
    """Take and save a picture with the camera."""
    ret, frame = cap.read()
    if ret:
        path = os.path.join(FRAMES_DIR, f"frame{layer}.png")
        cv2.imwrite(path, frame)
        print(f"[📸] Saved picture: {path}")
    else:
        print("[!] Failed to capture image")

def clean_line(line):
    """Remove comments and spaces."""
    return line.split(";")[0].strip()

def parse_temp(line):
    """Extract target temperature from gcode line safely."""
    line = clean_line(line)
    if "S" in line:
        try:
            return float(line.split("S")[1])
        except:
            return None
    return None

# Count total lines in the G-code file
def count_lines(file_path):
    with open(file_path, "r") as f:
        return sum(1 for _ in f)

total_lines = count_lines(GCODE_FILE)

# Initialize tqdm progress bar
progress_bar = tqdm(total=total_lines, desc="Processing G-code", unit="line")

# -------- Main loop --------
with open(GCODE_FILE, "r") as f:
    layer = 0
    for raw_line in f:
        line = raw_line.strip()
        if not line or line.startswith(";"):
            # Check for layer change
            if ";LAYER_CHANGE" in raw_line:
                layer += 1
                take_picture(layer)
            progress_bar.update(1)  # Update progress bar
            continue

        # Handle heating commands
        if line.startswith("M104"):  # set nozzle temp (no wait)
            target = parse_temp(line)
            if target is not None:
                send_gcode(line)

        elif line.startswith("M109"):  # set nozzle temp (wait)
            target = parse_temp(line)
            if target is not None:
                send_gcode(line)
                print(f"[🔥] Waiting for nozzle to reach {target}°C...")
                while True:
                    ser.write(b"M105\n")
                    resp = ser.readline().decode(errors="ignore").strip()
                    if resp:
                        print(f"[←] {resp}")
                    if "ok" in resp.lower() and f"T:{target}" in resp:
                        break

        elif line.startswith("M190"):  # set bed temp (wait)
            target = parse_temp(line)
            if target is not None:
                send_gcode(line)
                print(f"[🔥] Waiting for bed to reach {target}°C...")
                while True:
                    ser.write(b"M105\n")
                    resp = ser.readline().decode(errors="ignore").strip()
                    if resp:
                        print(f"[←] {resp}")
                    if "ok" in resp.lower() and f"B:{target}" in resp:
                        break

        else:
            send_gcode(line)

        progress_bar.update(1)  # Update progress bar

# Cleanup
progress_bar.close()
cap.release()
ser.close()
print("[✔] Print finished")

import serial
import time
import cv2
import os
from tqdm import tqdm
import argparse
from chromaconsole import *

# ---------------- SETTINGS ----------------
def parse_args():
    parser = argparse.ArgumentParser(description="3D Printer Timelapser")
    parser.add_argument("--port", type=str, default="COM4", help="Printer COM port")
    parser.add_argument("--baudrate", type=int, default=115200, help="Printer baud rate")
    parser.add_argument("--gcode_file", type=str, default="a.gcode", help="Path to the G-code file")
    parser.add_argument("--frames_dir", type=str, default="./frames", help="Directory to save frames")
    parser.add_argument("--camera_index", type=int, default=0, help="Camera index")
    parser.add_argument("--record", action="store_true", help="Enable recording frames")
    return parser.parse_args()

args = parse_args()

PORT = args.port
BAUDRATE = args.baudrate
GCODE_FILE = args.gcode_file
FRAMES_DIR = args.frames_dir
CAMERA_INDEX = args.camera_index
RECORD = args.record
# ------------------------------------------

if RECORD:
    os.makedirs(FRAMES_DIR, exist_ok=True)
    cap = cv2.VideoCapture(CAMERA_INDEX)
else:
    cap = None

# Connect to printer
ser = serial.Serial(PORT, BAUDRATE, timeout=5)
time.sleep(2)  # wait for connection

def send_gcode(cmd):
    """Send a command to the printer and wait for 'ok'."""
    tqdm.write(f"{Color.Text.br_magenta()}[→] {cmd}{Style.reset()}")
    ser.write((cmd + "\n").encode())

    while True:
        line = ser.readline().decode(errors="ignore").strip()
        if line:
            tqdm.write(f"{Color.Text.br_yellow()}[←] Printer: {line}{Style.reset()}")
        if "ok" in line.lower():
            break

def take_picture(layer):
    """Take and save a picture with the camera."""
    if not RECORD or cap is None:
        return
    ret, frame = cap.read()
    if ret:
        path = os.path.join(FRAMES_DIR, f"frame{layer}.png")
        cv2.imwrite(path, frame)
        tqdm.write(f"{Color.Text.br_white()}[📸] Saved picture: {path}{Style.reset()}")
    else:
        tqdm.write(f"{Color.Text.br_red()}[!] Failed to capture image{Style.reset()}")

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

# Count total non-comment lines in the G-code file
def count_non_comment_lines(file_path):
    with open(file_path, "r") as f:
        return sum(1 for line in f if line.strip() and not line.strip().startswith(";"))

total_lines = count_non_comment_lines(GCODE_FILE)

# Initialize tqdm progress bar
# grad = " ⡀⡄⡆⡇⣇⣧⣷⣿"
grad = " ░▒▓█"
progress_bar = tqdm(
    total=total_lines,
    desc=f"{Color.Text.br_cyan()}Processing G-code{Style.reset()}",
    unit="line",
    dynamic_ncols=True,
    leave=True,
    colour="#17fc03",
    ascii=grad
)

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
                tqdm.write(f"{Color.Text.br_blue()}[🔥] Waiting for nozzle to reach {target}°C...{Style.reset()}")
                while True:
                    ser.write(b"M105\n")
                    resp = ser.readline().decode(errors="ignore").strip()
                    if resp:
                        tqdm.write(f"{Color.Text.br_yellow()}[←] {resp}{Style.reset()}")
                    if "ok" in resp.lower() and f"T:{target}" in resp:
                        break

        elif line.startswith("M190"):  # set bed temp (wait)
            target = parse_temp(line)
            if target is not None:
                send_gcode(line)
                tqdm.write(f"{Color.Text.br_blue()}[🔥] Waiting for bed to reach {target}°C...{Style.reset()}")
                while True:
                    ser.write(b"M105\n")  # Request temperature status
                    resp = ser.readline().decode(errors="ignore").strip()
                    if resp:
                        tqdm.write(f"{Color.Text.br_yellow()}[←] {resp}{Style.reset()}")
                        if "ok" in resp.lower():
                            # Extract bed temperature from the response
                            if "B:" in resp:
                                try:
                                    current_temp = float(resp.split("B:")[1].split()[0])
                                    if current_temp >= target:
                                        break
                                except (IndexError, ValueError):
                                    pass

        else:
            send_gcode(line)

        progress_bar.update(1)  # Update progress bar

# Cleanup
progress_bar.close()
if cap:
    cap.release()
ser.close()
print("[✔] Print finished")

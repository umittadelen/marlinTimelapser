import serial
import time
import cv2
import os
from tqdm import tqdm
import argparse
from chromaconsole import *
import datetime

# ---------------- SETTINGS ----------------
def parse_args():
    parser = argparse.ArgumentParser(
        description="📸 3D Printer Timelapser — stream G-code to your printer and capture photos each layer."
    )
    parser.add_argument(
        "--port", "-p",
        type=str,
        default="COM4",
        help="Printer COM port (default: COM4)"
    )
    parser.add_argument(
        "--baudrate", "-br",
        type=int,
        default=115200,
        help="Printer baud rate (default: 115200)"
    )
    parser.add_argument(
        "--gcode_file", "-gf",
        type=str,
        default="a.gcode",
        help="Path to the G-code file (.gcode)"
    )
    parser.add_argument(
        "--frames_dir", "-fd",
        type=str,
        default="./frames",
        help="Directory to save captured frames (default: ./frames)"
    )
    parser.add_argument(
        "--camera_index", "-ci",
        type=int,
        default=0,
        help="Camera index for OpenCV (default: 0)"
    )
    parser.add_argument(
        "--record", "-r",
        action="store_true",
        help="Enable recording frames (saves PNGs for each layer)"
    )
    parser.add_argument(
        "--camera_resolution", "-cr",
        type=str,
        default="640x480",
        help="Camera resolution in WIDTHxHEIGHT format (default: 640x480)"
    )
    parser.add_argument(
        "--camera_brightness", "-cb",
        type=int,
        default=128,
        help="Camera brightness (0–255, default: 128)"
    )
    parser.add_argument(
        "--camera_contrast", "-cc",
        type=int,
        default=128,
        help="Camera contrast (0–255, default: 128)"
    )
    return parser.parse_args()
# ------------------------------------------

args = parse_args()

PORT = args.port
BAUDRATE = args.baudrate
GCODE_FILE = args.gcode_file if args.gcode_file.endswith('.gcode') else args.gcode_file + '.gcode'
FRAMES_DIR = args.frames_dir
CAMERA_INDEX = args.camera_index
RECORD = args.record
CAMERA_RESOLUTION = tuple(map(int, args.camera_resolution.split('x')))
CAMERA_BRIGHTNESS = args.camera_brightness
CAMERA_CONTRAST = args.camera_contrast
# ------------------------------------------

if RECORD:
    os.makedirs(FRAMES_DIR, exist_ok=True)
    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_RESOLUTION[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_RESOLUTION[1])
    cap.set(cv2.CAP_PROP_BRIGHTNESS, CAMERA_BRIGHTNESS)
    cap.set(cv2.CAP_PROP_CONTRAST, CAMERA_CONTRAST)
else:
    cap = None

# Connect to printer
ser = serial.Serial(PORT, BAUDRATE, timeout=5)
time.sleep(2)  # wait for connection

def send_gcode(cmd):
    """Send a command to the printer and wait for 'ok'."""
    tqdm.write(f"{Color.Text.br_magenta()}[←] {cmd}{Style.reset()}")
    ser.write((cmd + "\n").encode())

    while True:
        line = ser.readline().decode(errors="ignore").strip()
        if line:
            tqdm.write(f"{Color.Text.br_yellow()}[→] Printer: {line}{Style.reset()}")
        if "ok" in line.lower():
            break

def take_picture(layer):
    """Take and save a picture with the camera."""
    if not RECORD or cap is None:
        return
    ret, frame = cap.read()
    if ret:
        path = os.path.join(FRAMES_DIR, f"frame{layer}.png")
        # Ensure the frame is properly saved in PNG format
        if not cv2.imwrite(path, frame):
            tqdm.write(f"{Color.Text.br_red()}[!] Failed to save image: {path}{Style.reset()}")
        else:
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

def format_time(seconds):
    """Format seconds into HH:MM:SS."""
    return str(datetime.timedelta(seconds=int(seconds)))

# Count total non-comment lines in the G-code file
def count_non_comment_lines(file_path):
    with open(file_path, "r") as f:
        return sum(1 for line in f if line.strip() and not line.strip().startswith(";"))

total_lines = count_non_comment_lines(GCODE_FILE)

# Initialize tqdm progress bar
grad = " ⡀⡄⡆⡇⣇⣧⣷⣿"
#grad = " ░▒▓█"
progress_bar = tqdm(
    total=total_lines,
    desc=f"{Color.Text.br_cyan()}Processing G-code{Style.reset()}",
    unit="line",
    dynamic_ncols=True,
    leave=True,
    colour="#00ff00",
    ascii=grad
)

# Initialize variables for time calculation
total_time = None
elapsed_time = 0

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

            # Parse ;TIME and ;TIME_ELAPSED comments
            if line.startswith(";TIME:"):
                try:
                    total_time = int(line.split(":")[1])
                except ValueError:
                    tqdm.write(f"{Color.Text.br_red()}[!] Invalid TIME format: {line}{Style.reset()}")

            elif line.startswith(";TIME_ELAPSED:"):
                try:
                    elapsed_time = float(line.split(":")[1])
                except ValueError:
                    tqdm.write(f"{Color.Text.br_red()}[!] Invalid TIME_ELAPSED format: {line}{Style.reset()}")

            # Calculate and display remaining time
            if total_time is not None:
                remaining_time = total_time - elapsed_time
                progress_bar.set_description(f"{Color.Text.br_cyan()}Remaining: {format_time(remaining_time) if remaining_time!=None else "NaN"}{Style.reset()}")

            continue

        if total_time is None:
            tqdm.write(f"{Color.Text.br_red()}[!] Missing ;TIME comment in G-code. Remaining time cannot be calculated.{Style.reset()}")
            total_time = -1

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
print(f"[✔] Print finished")
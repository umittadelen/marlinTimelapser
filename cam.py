import cv2
import tkinter as tk
from threading import Thread
from tkinter import messagebox

class FastLiveCamera:
    def __init__(self, master):
        self.master = master
        self.master.title("Fast Live Camera")

        # --- Variables ---
        self.camera_index = tk.StringVar(value="0")
        self.res_width = tk.StringVar(value="640")
        self.res_height = tk.StringVar(value="480")
        self.brightness = tk.StringVar(value="128")
        self.contrast = tk.StringVar(value="128")

        self.running = False
        self.cap = None

        self.prev_settings = {}  # Track previous values to avoid redundant sets

        # --- GUI ---
        tk.Label(master, text="Camera Index:").grid(row=0, column=0, sticky="e")
        tk.Entry(master, textvariable=self.camera_index, width=8).grid(row=0, column=1)

        tk.Label(master, text="Resolution Width:").grid(row=1, column=0, sticky="e")
        tk.Entry(master, textvariable=self.res_width, width=8).grid(row=1, column=1)

        tk.Label(master, text="Resolution Height:").grid(row=2, column=0, sticky="e")
        tk.Entry(master, textvariable=self.res_height, width=8).grid(row=2, column=1)

        tk.Label(master, text="Brightness:").grid(row=3, column=0, sticky="e")
        tk.Entry(master, textvariable=self.brightness, width=8).grid(row=3, column=1)

        tk.Label(master, text="Contrast:").grid(row=4, column=0, sticky="e")
        tk.Entry(master, textvariable=self.contrast, width=8).grid(row=4, column=1)

        tk.Button(master, text="Start Camera", command=self.start_camera).grid(row=5, column=0, pady=10)
        tk.Button(master, text="Stop Camera", command=self.stop_camera).grid(row=5, column=1, pady=10)

    def start_camera(self):
        if self.running:
            return
        try:
            idx = int(self.camera_index.get())
        except ValueError:
            messagebox.showerror("Error", "Camera index must be an integer")
            return

        # Use DirectShow backend
        self.cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            messagebox.showerror("Error", f"Cannot open camera {idx}")
            return

        self.running = True
        self.prev_settings = {}
        Thread(target=self.update_frame, daemon=True).start()

    def stop_camera(self):
        self.running = False
        if self.cap:
            self.cap.release()
            self.cap = None
        cv2.destroyAllWindows()

    def apply_settings(self):
        # Only apply if changed
        try:
            settings = {
                "width": int(self.res_width.get()),
                "height": int(self.res_height.get()),
                "brightness": int(self.brightness.get()),
                "contrast": int(self.contrast.get())
            }
        except ValueError:
            return  # invalid input, skip

        for key, value in settings.items():
            if self.prev_settings.get(key) != value:
                if key == "width":
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, value)
                elif key == "height":
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, value)
                elif key == "brightness":
                    self.cap.set(cv2.CAP_PROP_BRIGHTNESS, value)
                elif key == "contrast":
                    self.cap.set(cv2.CAP_PROP_CONTRAST, value)
                self.prev_settings[key] = value

    def update_frame(self):
        while self.running and self.cap:
            self.apply_settings()

            ret, frame = self.cap.read()
            if not ret:
                continue

            cv2.imshow("Live Camera", frame)
            if cv2.waitKey(1) == 27:  # ESC
                self.stop_camera()
                break

if __name__ == "__main__":
    root = tk.Tk()
    app = FastLiveCamera(root)
    root.mainloop()

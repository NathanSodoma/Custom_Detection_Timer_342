import tkinter as tk
from tkinter import messagebox
import time
import threading
import subprocess
import os

# === Constants ===
VOLUME_STEP = 5
BRIGHTNESS_PATH = "/sys/class/backlight/rpi_backlight/brightness"
BRIGHTNESS_VALUES = {
    'dim': 50,
    'normal': 125,
    'bright': 255
}

# === Timer Logic ===
class Timer:
    def __init__(self, label, update_buttons_state):
        self.label = label
        self.running = False
        self.remaining = 0
        self.thread = None
        self.lock = threading.Lock()
        self.update_buttons_state = update_buttons_state

    def start(self, seconds):
        with self.lock:
            if self.running:
                return
            self.remaining = seconds
            self.running = True
            self.update_buttons_state(False)
            self.thread = threading.Thread(target=self.run)
            self.thread.start()

    def run(self):
        while self.running and self.remaining > 0:
            mins, secs = divmod(self.remaining, 60)
            self.label.config(text=f"{mins:02d}:{secs:02d}")
            time.sleep(1)
            self.remaining -= 1
        if self.remaining == 0 and self.running:
            self.label.config(text="Time's up!")
        self.running = False
        self.update_buttons_state(True)

    def stop(self):
        with self.lock:
            self.running = False
            self.remaining = 0

    def reset_display(self):
        self.label.config(text="01:00")

# === Brightness Control ===
class BrightnessControl:
    def __init__(self, root):
        self.hardware_available = os.path.exists(BRIGHTNESS_PATH)
        if not self.hardware_available:
            # Simulated brightness overlay fallback
            self.canvas = tk.Canvas(root, bg='black', highlightthickness=0)
            self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
            self.rect = self.canvas.create_rectangle(0, 0, 800, 480, fill='black', stipple='gray12')
            self.set_simulated('normal')

    def set_brightness(self, level):
        if self.hardware_available:
            try:
                brightness_value = BRIGHTNESS_VALUES.get(level, 150)
                with open(BRIGHTNESS_PATH, 'w') as f:
                    f.write(str(brightness_value))
            except Exception as e:
                print(f"[Warning] Hardware brightness failed: {e}")
        else:
            self.set_simulated(level)

    def set_simulated(self, level):
        if level == 'bright':
            self.canvas.place_forget()
        else:
            self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
            stipple_map = {
                'normal': 'gray50',
                'dim': 'gray75'
            }
            self.canvas.itemconfig(self.rect, stipple=stipple_map.get(level, 'gray50'))

# === GUI Setup ===
def main():
    root = tk.Tk()
    root.config(cursor="none")
    root.title("Raspberry Pi Touch Controller")
    root.geometry("800x480")
    root.attributes('-fullscreen', True)
    root.bind("<Escape>", lambda e: root.destroy())

    # === Brightness Controller ===
    brightness_control = BrightnessControl(root)

    # === Timer Display ===
    timer_label = tk.Label(root, text="01:00", font=("Arial", 48))
    timer_label.pack(pady=15)

    timer_minutes = tk.IntVar(value=1)

    def update_timer_label():
        mins = timer_minutes.get()
        timer_label.config(text=f"{mins:02d}:00")

    def update_buttons_state(enable):
        plus_btn.config(state=tk.NORMAL if enable else tk.DISABLED)
        minus_btn.config(state=tk.NORMAL if enable else tk.DISABLED)

    timer = Timer(timer_label, update_buttons_state)

    def increase_time():
        timer_minutes.set(timer_minutes.get() + 1)
        update_timer_label()

    def decrease_time():
        if timer_minutes.get() > 1:
            timer_minutes.set(timer_minutes.get() - 1)
            update_timer_label()

    def start_timer():
        minutes = timer_minutes.get()
        timer.start(minutes * 60)

    def reset_timer():
        timer.stop()
        timer_minutes.set(1)
        timer.reset_display()
        update_buttons_state(True)

    # === Timer Controls ===
    timer_control_frame = tk.Frame(root)
    timer_control_frame.pack(pady=5)

    btn_style = {"font": ("Arial", 22), "width": 6, "height": 2, "padx": 5, "pady": 5}

    plus_btn = tk.Button(timer_control_frame, text="+", command=increase_time, **btn_style)
    minus_btn = tk.Button(timer_control_frame, text="-", command=decrease_time, **btn_style)
    start_btn = tk.Button(timer_control_frame, text="Start", command=start_timer, **btn_style)
    reset_btn = tk.Button(timer_control_frame, text="Reset", command=reset_timer, fg='white', bg='red', **btn_style)

    plus_btn.grid(row=0, column=0, padx=5)
    minus_btn.grid(row=0, column=1, padx=5)
    start_btn.grid(row=0, column=2, padx=5)
    reset_btn.grid(row=0, column=3, padx=5)

    # === Volume Control ===
    vol_frame = tk.LabelFrame(root, text="Volume", font=("Arial", 16))
    vol_frame.pack(pady=10)

    tk.Button(vol_frame, text="Volume +", command=lambda: change_volume("up"),
              font=("Arial", 18), width=10, height=2).pack(side=tk.LEFT, padx=15)
    tk.Button(vol_frame, text="Volume -", command=lambda: change_volume("down"),
              font=("Arial", 18), width=10, height=2).pack(side=tk.RIGHT, padx=15)

    # === Brightness Control Buttons ===
    bright_frame = tk.LabelFrame(root, text="Brightness", font=("Arial", 16))
    bright_frame.pack(pady=10)

    tk.Button(bright_frame, text="Dim", command=lambda: brightness_control.set_brightness('dim'),
              font=("Arial", 18), width=10, height=2).pack(side=tk.LEFT, padx=10)
    tk.Button(bright_frame, text="Normal", command=lambda: brightness_control.set_brightness('normal'),
              font=("Arial", 18), width=10, height=2).pack(side=tk.LEFT, padx=10)
    tk.Button(bright_frame, text="Bright", command=lambda: brightness_control.set_brightness('bright'),
              font=("Arial", 18), width=10, height=2).pack(side=tk.LEFT, padx=10)

    # === Exit Button ===
    exit_frame = tk.Frame(root)
    exit_frame.pack(side='bottom', pady=20, fill='x')

    exit_btn = tk.Button(exit_frame, text="Exit App", command=root.destroy, font=("Arial", 20),
                         bg="gray", fg="white", height=2)
    exit_btn.pack(fill='x', padx=50)

    root.mainloop()

# === Volume Control Logic ===
def change_volume(direction):
    if direction == "up":
        subprocess.run(["amixer", "sset", "Master", f"{VOLUME_STEP}%+"])
    else:
        subprocess.run(["amixer", "sset", "Master", f"{VOLUME_STEP}%-"])

# === Launch ===
if __name__ == "__main__":
    main()

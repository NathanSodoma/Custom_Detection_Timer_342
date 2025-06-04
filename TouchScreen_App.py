import tkinter as tk
from tkinter import messagebox
import time
import threading
import subprocess
import os
import RPi.GPIO as GPIO
import numpy as np
import simpleaudio as sa


# === Constants ===
VOLUME_STEP = 5
BRIGHTNESS_PATH = "/sys/class/backlight/rpi_backlight/brightness"
BRIGHTNESS_VALUES = {
    'dim': 50,
    'normal': 125,
    'bright': 255
}
# === GPIO and Sound Setup ===
SENSOR_PIN = 17



# === Timer Logic ===
class Timer:
    def __init__(self, label, update_buttons_state, wave_obj, play_obj_ref, start_tone_loop):
        self.label = label
        self.running = False
        self.paused = False
        self.remaining = 0
        self.thread = None
        self.lock = threading.Lock()
        self.update_buttons_state = update_buttons_state
        self.wave_obj = wave_obj
        self.play_obj_ref = play_obj_ref
        self.start_tone_loop = start_tone_loop
    
    def start(self, seconds):
        with self.lock:
            if self.running:
                return
            self.remaining = seconds
            self.running = True
            self.paused = False
            self.update_buttons_state(False)
            self.thread = threading.Thread(target=self.run)
            self.thread.start()

    def run(self):
        while self.running and self.remaining > 0:
            with self.lock:
                if self.paused:
                    time.sleep(0.1)
                    continue
                mins, secs = divmod(self.remaining, 60)
                self.label.config(text=f"{mins:02d}:{secs:02d}")
                self.remaining -= 1
            time.sleep(1)
        if self.remaining == 0 and self.running:
            self.label.config(text="Time's up!")
            try:
                if self.play_obj_ref[0] is None or not self.play_obj_ref[0].is_playing():
                    self.start_tone_loop()
            except Exception as e:
                print(f"[Warning] Could not play alert tone: {e}")
            self.update_buttons_state(False)
            
        self.running = False
        self.update_buttons_state(True)



    def stop(self):
        with self.lock:
            self.running = False
            self.remaining = 0

    def reset_display(self):
        self.label.config(text="01:00")

    def pause(self):
        with self.lock:
            self.paused = True

    def resume(self):
        with self.lock:
            self.paused = False

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
    
    subprocess.run(["amixer", "cset", "numid=3", "1"])
    subprocess.run(["amixer", "sset", "Master", "50%"])  # Set volume to 50%

    tone_thread = [None]
    


    # === Brightness Controller ===
    brightness_control = BrightnessControl(root)

    # === Timer Display ===
    timer_label = tk.Label(root, text="01:00", font=("Arial", 48))
    timer_label.pack(pady=15)

    # === Generate 440 Hz Tone ===
    def generate_tone(freq=440, duration=2.0, sample_rate=44100, amplitude=0.5):
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        tone = np.sin(freq * 2 * np.pi * t)
        audio = (tone * (2**15 - 1) * amplitude).astype(np.int16)
        return audio
    
    tone_buffer = generate_tone(duration=10.0)
    wave_obj = sa.WaveObject(tone_buffer, 1, 2, 44100)
    play_obj = None

    
    timer_minutes = tk.IntVar(value=1)
    
    def update_timer_label():
        mins = timer_minutes.get()
        timer_label.config(text=f"{mins:02d}:00")

    def update_buttons_state(enable):
        plus_btn.config(state=tk.NORMAL if enable else tk.DISABLED)
        minus_btn.config(state=tk.NORMAL if enable else tk.DISABLED)

    


    # === Initialize GPIO and Sound ===
    GPIO.setmode(GPIO.BCM)
    

   

    play_obj_ref = [None]  # Mutable container to track current playback

    tone_loop_active = [False]  # Shared flag for controlling playback thread

    def start_tone_loop():
        if tone_loop_active[0]:
            return  # already running

        tone_loop_active[0] = True

        def loop():
            while tone_loop_active[0]:
                play_obj_ref[0] = wave_obj.play()
                while play_obj_ref[0].is_playing():
                    if not tone_loop_active[0]:
                        play_obj_ref[0].stop()
                        break
                    time.sleep(0.05)

        tone_thread[0] = threading.Thread(target=loop, daemon=True)
        tone_thread[0].start()
    
    def stop_tone_loop():
        tone_loop_active[0] = False
        if play_obj_ref[0]:
            play_obj_ref[0].stop()
            play_obj_ref[0] = None
        if tone_thread[0] and tone_thread[0].is_alive():
            tone_thread[0].join(timeout=0.5)  # Ensure thread exits quickly
            tone_thread[0] = None
    
    timer = Timer(timer_label, update_buttons_state, wave_obj, play_obj_ref, start_tone_loop)

    
    def gpio_callback(channel):
        current_state = GPIO.input(SENSOR_PIN)
        if current_state == GPIO.LOW and timer.running:
            print("[GPIO] Object removed - pausing timer and playing tone")
            timer.pause()
            start_tone_loop()
        elif current_state == GPIO.HIGH:
            print("[GPIO] Object returned - resuming timer and stopping tone")
            timer.resume()
            stop_tone_loop()
            
    GPIO.setup(SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(SENSOR_PIN, GPIO.BOTH, callback=gpio_callback, bouncetime=150)
    


    
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
        if play_obj_ref[0]:
            stop_tone_loop()
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

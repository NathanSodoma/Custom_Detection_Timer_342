import numpy as np
import pyaudio
import os
import time

# Force audio output to 3.5mm jack
os.system("amixer cset numid=3 1")  # 0=auto, 1=headphones, 2=HDMI

# Parameters
volume = 0.5      # range [0.0, 1.0]
fs = 44100        # sampling rate, Hz
duration = 5.0    # in seconds
frequency = 440.0 # A4 note (Hz)

# Generate a sine wave
samples = (np.sin(2*np.pi*np.arange(fs*duration)*frequency/fs)).astype(np.float32)

# Initialize PyAudio
p = pyaudio.PyAudio()

# Open stream
stream = p.open(format=pyaudio.paFloat32,
                channels=1,
                rate=fs,
                output=True)

# Play the sound
print("Playing test tone...")
stream.write(volume*samples)

# Clean up
stream.stop_stream()
stream.close()
p.terminate()

print("Test complete.")

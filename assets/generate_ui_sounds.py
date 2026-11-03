"""Generate the short, original UI sound effects shipped with the app."""
import math
import random
import struct
import wave
from pathlib import Path

RATE = 24000
ROOT = Path(__file__).resolve().parent


def write(name, samples):
    with wave.open(str(ROOT / name), 'wb') as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(b''.join(struct.pack('<h', round(max(-1, min(1, x)) * 32767)) for x in samples))


def rolling():
    rng = random.Random(72)
    values = []
    for i in range(RATE):
        t = (i / RATE) % 0.125
        envelope = math.exp(-t * 130) if t < 0.04 else 0
        values.append(0.18 * envelope * (0.55 * rng.uniform(-1, 1) + 0.45 * math.sin(2 * math.pi * 1450 * t)))
    return values


def complete():
    values = []
    for i in range(int(RATE * 1.05)):
        t = i / RATE
        sample = 0
        for delay, frequency in [(0, 523.25), (0.10, 659.25), (0.20, 783.99)]:
            local = t - delay
            if local >= 0:
                attack = min(1.0, local / 0.015)
                sample += 0.15 * attack * math.exp(-local * 4.4) * (math.sin(2 * math.pi * frequency * local) + 0.3 * math.sin(4 * math.pi * frequency * local))
        values.append(sample)
    return values


if __name__ == '__main__':
    write('rolling.wav', rolling())
    write('complete.wav', complete())

from __future__ import annotations

import argparse
import hashlib
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 44_100
AMPLITUDE = 10_485
EXPECTED_SHA256 = "5c175336ed360d80e37d06ad219e3ce6d28f564279b5a21d5af1a229e906ec29"
PATTERN = (
    (880, 180),
    (0, 80),
    (660, 180),
    (0, 200),
) * 3


def generate_alarm_wave(output: Path) -> str:
    frames = bytearray()
    for frequency, duration_ms in PATTERN:
        sample_count = SAMPLE_RATE * duration_ms // 1000
        for sample_index in range(sample_count):
            if frequency == 0.0:
                value = 0
            else:
                half_cycle = (2 * sample_index * frequency) // SAMPLE_RATE
                value = AMPLITUDE if half_cycle % 2 == 0 else -AMPLITUDE
            frames.extend(struct.pack("<h", value))

    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(SAMPLE_RATE)
        stream.writeframes(frames)
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the original AI Presence Monitor alarm WAV."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("assets/ai-presence-alarm.wav"),
    )
    args = parser.parse_args()
    digest = generate_alarm_wave(args.output)
    print(f"{digest}  {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

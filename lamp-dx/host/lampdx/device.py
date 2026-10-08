"""Talk to the LAMP-Dx ESP32 over USB serial (protocol documented in firmware/lamp_dx/lamp_dx.ino)."""
from __future__ import annotations

import json
import re
import time


def parse_line(line: str) -> dict | None:
    line = line.strip()
    if not line.startswith("{"):
        return None
    # Firmware prints a failed sensor as nan/inf, which isn't valid JSON.
    line = re.sub(r"(?<=[:,])\s*-?(nan|inf)\b", "null", line)
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


class SerialDevice:
    def __init__(self, port: str, baud: int = 115200):
        import serial  # pip install pyserial
        self.ser = serial.Serial(port, baud, timeout=0.2)
        time.sleep(2.0)                  # ESP32 resets when the port opens
        self.ser.reset_input_buffer()
        self.last: dict = {}

    def send(self, cmd: str) -> None:
        self.ser.write((cmd.strip() + "\n").encode())

    def poll(self) -> dict:
        """Drain pending lines; return the latest telemetry."""
        while self.ser.in_waiting:
            msg = parse_line(self.ser.readline().decode(errors="replace"))
            if msg and "state" in msg:
                self.last = msg
            elif msg and "error" in msg:
                raise RuntimeError(f"device error: {msg['error']}")
        return self.last

    def wait(self, seconds: float) -> None:
        time.sleep(seconds)

    def close(self) -> None:
        self.send("STOP")
        self.ser.close()

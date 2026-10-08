# KJG-2026-002 LAMP-Dx

A portable, autonomous diagnostic platform. It runs **LAMP** (loop-mediated isothermal amplification) at 65 °C, images the reactions as they run, and uses software to call each sample **DETECTED / NOT DETECTED / RETEST / INVALID**, checked against built-in controls.

> **Status: research prototype. For research use only.** It is not a medical device and not cleared by any regulator. See [docs/business-and-regulatory.md](docs/business-and-regulatory.md) for the path to clinical use.

## How it works

```
 sample → lysis/inactivation → tube with LAMP mix (8-tube strip)
                                      │
   ESP32 firmware ── PID heater ──► aluminium block 65 °C ±0.5, heated lid 75 °C
         ▲   safety: over-temp, sensor fault, runaway, thermal fuse
         │ USB serial
   Host app (laptop / Raspberry Pi)
         ├─ camera frame every 30 s (blue LED + amber filter, or white light for colour change)
         ├─ per-well signal → threshold time (Tt) + sigmoid-shape check
         ├─ controls: NTC must stay negative, positive control must amplify, internal control per sample
         └─ HTML + JSON report
```

## What's here

| Path | What |
|---|---|
| `firmware/lamp_dx/lamp_dx.ino` | ESP32 firmware: heaters, LED, serial protocol, 1 Hz telemetry |
| `firmware/lamp_dx/control.h` | PID and safety state machine. Plain C++, unit-tested on a PC |
| `firmware/test/test_control.cpp` | Thermal-model tests: reaches 65 °C in about 90 s, peaks at 65.1 °C, holds ±0.03 °C, and trips each fault |
| `host/lampdx/` | Python app: run orchestration, imaging, analysis, report, simulator, model training |
| `host/tests/` | 14 end-to-end tests over simulated runs (normal, contaminated NTC, inhibited sample, late non-specific product, heater failure, drift) |
| `docs/hardware.md` | Bill of materials, wiring, block and optics build |
| `docs/assay-protocol.md` | How to run a test, controls, contamination control, biosafety |
| `docs/business-and-regulatory.md` | Market, unit economics, regulatory path, 90-day plan |

## Quick start (no hardware needed)

```bash
cd lamp-dx/host
pip install numpy pytest
python -m lampdx.run --simulate normal            # also: contaminated_ntc, inhibited_sample, late_nonspecific
python -m lampdx.run --simulate normal --mode colorimetric
python -m pytest -q
```

Each run writes `runs/run-<id>.html` (the report) and `runs/run-<id>.json` (raw data).

Firmware logic tests:

```bash
cd lamp-dx/firmware/test
g++ -std=c++17 -O2 -I../lamp_dx test_control.cpp -o test_control && ./test_control
```

## With hardware

1. Build the device as described in [docs/hardware.md](docs/hardware.md). Flash `firmware/lamp_dx/lamp_dx.ino` using Arduino IDE with **esp32 core 3.x**.
2. Get well pixel positions from one camera frame and save them as a layout JSON (same shape as `strip_layout()` in `host/lampdx/simulate.py`).
3. Install `pyserial` and `opencv-python-headless`, then run:
   `python -m lampdx.run --port /dev/ttyUSB0 --camera 0 --layout layout.json`

## The "AI", honestly

- **The calls come from explicit rules:** threshold time, cutoff time, sigmoid fit quality, rise steepness, and controls. This keeps every call explainable and auditable, which regulators need.
- **The confidence score is a logistic model.** `python -m lampdx.train labels.csv` retrains it on runs you have labelled with a reference method (lab qPCR). It stays advisory until it has been validated on held-out real samples.
- **A known limit:** a late non-specific product that crosses before the cutoff looks exactly like a weak true positive. The cutoff must be validated for each assay. A second target or melt-curve confirmation is the long-term fix.

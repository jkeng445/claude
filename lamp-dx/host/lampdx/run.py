"""Run an assay end to end: heat → image every N seconds → analyse → report.

    # no hardware: simulated device + camera
    python -m lampdx.run --simulate normal

    # real device
    python -m lampdx.run --port /dev/ttyUSB0 --camera 0 --layout layout.json
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import analysis, report
from .imaging import well_signals


def run_assay(dev, cam, layout, minutes=35.0, block_c=65.0, lid_c=75.0, interval_s=30.0,
              model=None, log=print) -> dict:
    mode = layout.get("mode", "fluorescence")
    t_min, signals = [], {w["name"]: [] for w in layout["wells"]}
    dev.send(f"RUN {block_c} {lid_c} {minutes}")
    fault = None
    while True:
        dev.wait(interval_s)
        tel = dev.poll()
        state = tel.get("state")
        if state == "FAULT":
            fault = tel.get("fault")
            log(f"DEVICE FAULT: {fault}, heaters off, run aborted")
            break
        if state in ("HOLD", "DONE"):
            dev.send("LED 1"); dev.wait(1)
            frame = cam.capture()
            if mode == "fluorescence":
                dev.send("LED 0")          # limit dye photobleaching between reads
            t_min.append(round(tel.get("hold_s", 0) / 60.0, 3))
            for k, v in well_signals(frame, layout).items():
                signals[k].append(v)
            log(f"  t={t_min[-1]:5.1f} min  block={tel.get('block')} °C")
        elif state:
            log(f"  {state}: block={tel.get('block')} °C")
        if state == "DONE":
            break
    dev.send("LED 0")

    params = analysis.CallParams.for_mode(mode)
    model = model or analysis.DEFAULT_MODEL
    if fault or len(t_min) < 6:
        result = {"run_valid": False, "issues": [f"device fault: {fault}" if fault else "too few reads"],
                  "samples": {}, "wells": {}}
    else:
        wells = {w["name"]: analysis.call_well(w["name"], t_min, signals[w["name"]], params, model)
                 for w in layout["wells"]}
        result = analysis.interpret_run(layout["wells"], wells)
    return {"run_id": uuid.uuid4().hex[:8], "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "block_c": block_c, "mode": mode, "cutoff_min": params.cutoff_min,
            "model_trained_on": model.get("trained_on", 0), "layout": layout,
            "t_min": t_min, "signals": signals, "fault": fault, "result": result}


def main(argv=None):
    ap = argparse.ArgumentParser(description="KJG-2026-002 LAMP-Dx assay runner")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--simulate", metavar="SCENARIO", help="normal | contaminated_ntc | inhibited_sample | late_nonspecific")
    src.add_argument("--port", help="serial port of the ESP32, e.g. /dev/ttyUSB0 or COM3")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--layout", help="plate layout JSON (default: 8-tube strip)")
    ap.add_argument("--mode", choices=["fluorescence", "colorimetric"], default="fluorescence")
    ap.add_argument("--minutes", type=float, default=35)
    ap.add_argument("--block", type=float, default=65)
    ap.add_argument("--lid", type=float, default=75)
    ap.add_argument("--interval", type=float, default=30)
    ap.add_argument("--model", help="trained model JSON from train.py")
    ap.add_argument("--out", default="runs")
    a = ap.parse_args(argv)

    from .simulate import SCENARIOS, SimulatedCamera, SimulatedDevice, strip_layout
    layout = json.loads(Path(a.layout).read_text()) if a.layout else strip_layout(a.mode)
    if a.simulate:
        if a.simulate not in SCENARIOS:
            ap.error(f"unknown scenario; pick one of {', '.join(SCENARIOS)}")
        dev = SimulatedDevice()
        cam = SimulatedCamera(dev, layout, SCENARIOS[a.simulate])
    else:
        from .device import SerialDevice
        from .imaging import OpenCVCamera
        dev, cam = SerialDevice(a.port), OpenCVCamera(a.camera)

    try:
        run = run_assay(dev, cam, layout, a.minutes, a.block, a.lid, a.interval, analysis.load_model(a.model))
    finally:
        dev.close()

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    stem = out / f"run-{run['run_id']}"
    stem.with_suffix(".json").write_text(json.dumps(run, indent=1))
    stem.with_suffix(".html").write_text(report.render(run))
    res = run["result"]
    print(f"\nRun {'VALID' if res['run_valid'] else 'INVALID'}")
    for i in res["issues"]:
        print(f"  ! {i}")
    for sid, s in res["samples"].items():
        tt = "" if s["tt_min"] is None else f"  Tt {s['tt_min']:.1f} min"
        print(f"  {sid}: {s['verdict']}{tt}")
    print(f"Report: {stem.with_suffix('.html')}")
    return 0 if res["run_valid"] else 2


if __name__ == "__main__":
    sys.exit(main())

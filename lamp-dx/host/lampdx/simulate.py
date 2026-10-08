"""Hardware-free simulator: a virtual LAMP-Dx and camera with realistic curves.

Lets you develop and demo the full pipeline (heating → imaging → AI calls →
report) before any hardware exists. It also generates labelled data for tests.
Time is virtual, so a 35-minute run finishes in about a second.
"""
from __future__ import annotations

import math

import numpy as np

# Typical LAMP kinetics: ~10 min at 1e5 copies, ~24 min at 10 copies.
def lamp_t0(copies: float) -> float:
    return 27.0 - 3.2 * math.log10(max(copies, 1.0))


class SimulatedDevice:
    """Same interface as SerialDevice. Thermal model ≈ the firmware test plant."""

    def __init__(self, ambient: float = 25.0, fault: str | None = None):
        self.t = 0.0
        self.block = self.lid = ambient
        self.amb = ambient
        self.state, self.fault_name = "IDLE", "NONE"
        self.sp, self.lid_sp, self.hold_total, self.hold_s = 65.0, 75.0, 0.0, 0.0
        self.led = 0
        self.fault = fault                # e.g. "heater" → simulated runaway

    def send(self, cmd: str) -> None:
        parts = cmd.split()
        if parts[0] == "RUN":
            self.sp, self.lid_sp, minutes = map(float, parts[1:4])
            self.hold_total, self.hold_s, self.state = minutes * 60, 0.0, "RAMP"
        elif parts[0] == "STOP":
            self.state = "IDLE" if self.state != "FAULT" else "FAULT"
        elif parts[0] == "LED":
            self.led = int(parts[1])

    def wait(self, seconds: float) -> None:
        dt = 0.5
        for _ in range(int(seconds / dt)):
            self.t += dt
            heating = self.state in ("RAMP", "HOLD")
            if heating and self.fault == "heater":
                if self.t > 90:
                    self.state, self.fault_name = "FAULT", "THERMAL_RUNAWAY"
                continue
            tgt_b = self.sp if heating else self.amb
            tgt_l = self.lid_sp if heating else self.amb
            self.block += (tgt_b - self.block) * min(1.0, dt / (25 if heating else 120))
            self.lid += (tgt_l - self.lid) * min(1.0, dt / 30)
            if self.state == "RAMP" and abs(self.block - self.sp) <= 0.5:
                self.state = "HOLD"
            if self.state == "HOLD":
                self.hold_s += dt
                if self.hold_s >= self.hold_total:
                    self.state = "DONE"

    def poll(self) -> dict:
        return {"ms": int(self.t * 1000), "state": self.state, "fault": self.fault_name,
                "block": round(self.block + np.random.normal(0, 0.03), 2), "lid": round(self.lid, 2),
                "hold_s": self.hold_s, "led": self.led}

    def close(self) -> None:
        self.state = "IDLE"


def well_rise(truth: dict, t_min: float, mode: str, rng: np.random.Generator) -> float:
    """Fractional rise over baseline for one well at time t (minutes into the hold)."""
    amp = 1.2 if mode == "fluorescence" else 1.6
    rise = 0.0
    copies = truth.get("copies", 0)
    if copies > 0 and not truth.get("inhibited"):
        t0 = truth.get("t0") or lamp_t0(copies)
        rise += amp / (1 + math.exp(-(t_min - t0) / truth.get("k", 1.0)))
    if truth.get("nonspecific_at"):
        rise += 0.8 * amp / (1 + math.exp(-(t_min - truth["nonspecific_at"]) / 1.5))
    rise += truth.get("drift", 0.0) * t_min
    return rise + rng.normal(0, 0.006)


class SimulatedCamera:
    """Renders an 8-well strip as the camera would see it, driven by the device's virtual clock."""

    def __init__(self, device: SimulatedDevice, layout: dict, truth: dict[str, dict], seed: int = 1):
        self.dev, self.layout, self.truth = device, layout, truth
        self.rng = np.random.default_rng(seed)
        self.h, self.w = layout.get("height", 240), layout.get("width", 640)
        yy, xx = np.mgrid[: self.h, : self.w]
        self.masks = {w["name"]: (xx - w["x"]) ** 2 + (yy - w["y"]) ** 2 <= w["r"] ** 2 for w in layout["wells"]}

    def capture(self) -> np.ndarray:
        mode = self.layout.get("mode", "fluorescence")
        t_min = self.dev.hold_s / 60.0
        if mode == "fluorescence":
            img = np.full((self.h, self.w, 3), (8.0, 12.0, 10.0))
        else:
            img = np.full((self.h, self.w, 3), (200.0, 200.0, 195.0))
        for w in self.layout["wells"]:
            r = well_rise(self.truth.get(w["name"], {}), t_min, mode, self.rng)
            if mode == "fluorescence":
                g = 45.0 * (1 + r)
                img[self.masks[w["name"]]] = (6 + 0.05 * g, 12 + g, 9 + 0.1 * g)
            else:
                f = max(0.0, min(1.0, r / 1.6))
                pink, yellow = np.array((225, 80, 140.0)), np.array((232, 205, 70.0))
                img[self.masks[w["name"]]] = pink + f * (yellow - pink)
        img += self.rng.normal(0, 1.5, img.shape)
        return np.clip(img, 0, 255).astype(np.uint8)


def strip_layout(mode: str = "fluorescence") -> dict:
    """Default 8-tube strip: S1, IC1, S2, IC2, S3, IC3, NTC, PC."""
    roles = [("S1", "sample", "P1"), ("IC1", "ic", "P1"), ("S2", "sample", "P2"), ("IC2", "ic", "P2"),
             ("S3", "sample", "P3"), ("IC3", "ic", "P3"), ("NTC", "ntc", None), ("PC", "pc", None)]
    wells = []
    for i, (name, role, sid) in enumerate(roles):
        w = {"name": name, "role": role, "x": 60 + i * 74, "y": 120, "r": 22}
        if sid:
            w["sample_id"] = sid
        if role == "sample":
            w["target"] = "target"
        wells.append(w)
    return {"mode": mode, "width": 640, "height": 240, "wells": wells, "background": {"x": 320, "y": 30, "r": 15}}


SCENARIOS = {
    # P1 high positive, P2 low positive, P3 negative with a good internal control.
    "normal": {"S1": {"copies": 1e5}, "IC1": {"copies": 1e4}, "S2": {"copies": 30}, "IC2": {"copies": 1e4},
               "S3": {}, "IC3": {"copies": 1e4}, "NTC": {}, "PC": {"copies": 1e4}},
    # Amplicon contamination: NTC goes positive, so the whole run must be rejected.
    "contaminated_ntc": {"S1": {"copies": 1e5}, "IC1": {"copies": 1e4}, "S2": {}, "IC2": {"copies": 1e4},
                         "S3": {}, "IC3": {"copies": 1e4}, "NTC": {"copies": 1e3}, "PC": {"copies": 1e4}},
    # P2 sample is inhibited (blood/soil), so its internal control fails and the result is invalid, not negative.
    "inhibited_sample": {"S1": {"copies": 1e5}, "IC1": {"copies": 1e4}, "S2": {"copies": 1e3, "inhibited": True},
                         "IC2": {"copies": 1e4, "inhibited": True}, "S3": {}, "IC3": {"copies": 1e4},
                         "NTC": {}, "PC": {"copies": 1e4}},
    # Non-specific product crossing after the 30 min cutoff must not be called positive.
    "late_nonspecific": {"S1": {"copies": 1e5}, "IC1": {"copies": 1e4}, "S2": {}, "IC2": {"copies": 1e4},
                         "S3": {"nonspecific_at": 37}, "IC3": {"copies": 1e4}, "NTC": {}, "PC": {"copies": 1e4}},
}

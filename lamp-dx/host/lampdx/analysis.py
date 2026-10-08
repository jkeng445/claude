"""Amplification-curve analysis for LAMP-Dx (KJG-2026-002).

Turns per-well signal-vs-time curves into calls:

1. Baseline: median of the early window (after the block has equilibrated).
2. Threshold time (Tt): first time the baseline-normalised rise stays above
   threshold for 3 consecutive reads. In LAMP, Tt falls as target load rises,
   so it is the primary quantitative output.
3. Shape check: a 4-parameter logistic (sigmoid) is fitted to the curve. Real
   amplification is sigmoidal. Drift, bubbles and condensation usually are not.
4. Call: POSITIVE / NEGATIVE / INDETERMINATE by explicit rules, plus an
   advisory confidence score from a logistic model that can be retrained on
   labelled runs (see train.py). The rules make the call. The model is a second
   opinion until it has been validated on real clinical/field data.

Then run-level logic applies the controls (NTC, positive control, internal control).
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

POSITIVE, NEGATIVE, INDETERMINATE = "POSITIVE", "NEGATIVE", "INDETERMINATE"


@dataclass
class CallParams:
    baseline_start_min: float = 1.0     # ignore the first minute (thermal equilibration)
    baseline_end_min: float = 5.0
    min_rise: float = 0.10              # fractional rise over baseline that counts as signal
    noise_sigmas: float = 10.0
    cutoff_min: float = 30.0            # later amplification is treated as likely non-specific
    min_fit_r2: float = 0.95
    max_k_min: float = 5.0              # real LAMP rises in minutes; slower "sigmoids" are drift
    consecutive: int = 3

    @classmethod
    def for_mode(cls, mode: str) -> "CallParams":
        # Colorimetric (phenol red G/R ratio) moves far more than fluorescence.
        return cls(min_rise=0.25) if mode == "colorimetric" else cls()


@dataclass
class WellResult:
    name: str
    call: str
    tt_min: float | None
    amplitude: float
    slope_k: float | None
    fit_r2: float | None
    confidence: float
    reasons: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- curve fitting
def _logistic(t, p):
    a, t0, k, c = p
    return c + a / (1.0 + np.exp(-(t - t0) / k))


def fit_sigmoid(t: np.ndarray, y: np.ndarray, t0_guess: float) -> tuple[np.ndarray, float]:
    """Levenberg–Marquardt fit of y = c + a / (1 + exp(-(t - t0)/k)). Returns (params, R²)."""
    p = np.array([max(y.max() - y.min(), 1e-6), t0_guess, 1.5, float(np.median(y[:3]))])
    lam = 1e-2
    def sse(q):
        return float(np.sum((y - _logistic(t, q)) ** 2))
    cost = sse(p)
    for _ in range(200):
        a, t0, k, c = p
        e = np.exp(-(t - t0) / k)
        s = 1.0 / (1.0 + e)
        ds = s * s * e                              # d s / d((t - t0)/k)
        J = np.column_stack([s, -a * ds / k, -a * ds * (t - t0) / k**2, np.ones_like(t)])
        r = y - _logistic(t, p)
        H = J.T @ J
        step = np.linalg.solve(H + lam * np.diag(np.diag(H) + 1e-12), J.T @ r)
        cand = p + step
        cand[2] = float(np.clip(cand[2], 0.05, 20.0))
        new_cost = sse(cand)
        if new_cost < cost:
            p, lam = cand, lam * 0.3
            if cost - new_cost < 1e-12 * max(cost, 1e-12):
                cost = new_cost
                break
            cost = new_cost
        else:
            lam *= 10
            if lam > 1e8:
                break
    ss_tot = float(np.sum((y - y.mean()) ** 2)) or 1e-12
    return p, 1.0 - cost / ss_tot


# ---------------------------------------------------------------- confidence model
DEFAULT_MODEL = {
    # Hand-set starting weights. Replace by running train.py on labelled runs.
    "features": ["tt_margin", "log_amp", "fit_r2", "late_slope"],
    "weights": [0.6, 2.5, 6.0, 1.5],
    "bias": -4.0,
    "trained_on": 0,
}


def features(res: WellResult, params: CallParams) -> list[float]:
    tt_margin = (params.cutoff_min - res.tt_min) / 5.0 if res.tt_min is not None else -3.0
    log_amp = math.log10(max(res.amplitude, 1e-3) / params.min_rise)
    r2 = res.fit_r2 if res.fit_r2 is not None else 0.0
    late = 1.0 if (res.slope_k is not None and 0.1 < res.slope_k < 6) else 0.0
    return [tt_margin, log_amp, r2, late]


def load_model(path: str | Path | None) -> dict:
    if path and Path(path).exists():
        return json.loads(Path(path).read_text())
    return DEFAULT_MODEL


def model_prob(x: list[float], model: dict) -> float:
    z = model["bias"] + sum(w * v for w, v in zip(model["weights"], x))
    return 1.0 / (1.0 + math.exp(-max(-50.0, min(50.0, z))))


# ---------------------------------------------------------------- per-well call
def call_well(name: str, t_min, signal, params: CallParams | None = None, model: dict | None = None) -> WellResult:
    params = params or CallParams()
    model = model or DEFAULT_MODEL
    t = np.asarray(t_min, float)
    f = np.asarray(signal, float)
    reasons: list[str] = []

    win = (t >= params.baseline_start_min) & (t <= params.baseline_end_min)
    if win.sum() < 3:
        win = np.zeros_like(t, bool); win[:3] = True
    base = float(np.median(f[win]))
    if abs(base) < 1e-9:
        return WellResult(name, INDETERMINATE, None, 0.0, None, None, 0.0, ["no baseline signal (empty well / camera fault?)"])
    rise = (f - base) / abs(base)
    noise = 1.4826 * float(np.median(np.abs(rise[win] - np.median(rise[win]))))
    thr = max(params.min_rise, params.noise_sigmas * noise)

    tt = None
    above = rise >= thr
    for i in range(len(t) - params.consecutive + 1):
        if t[i] > params.baseline_end_min * 0.5 and above[i:i + params.consecutive].all():
            if i > 0 and rise[i] != rise[i - 1]:
                tt = float(t[i - 1] + (thr - rise[i - 1]) * (t[i] - t[i - 1]) / (rise[i] - rise[i - 1]))
            else:
                tt = float(t[i])
            break

    amplitude = float(rise[-max(3, len(rise) // 10):].mean())
    k = r2 = None
    if tt is not None:
        p, r2 = fit_sigmoid(t, rise, tt)
        amplitude, k = float(p[0]), float(p[2])

    if tt is None:
        call = NEGATIVE
        if amplitude > thr * 0.5:
            call = INDETERMINATE
            reasons.append(f"signal drifted to {amplitude:.0%} without a clean crossing")
    else:
        call = POSITIVE
        if tt > params.cutoff_min:
            call = INDETERMINATE
            reasons.append(f"late amplification (Tt {tt:.1f} > {params.cutoff_min:.0f} min) – possible non-specific product")
        if r2 is not None and r2 < params.min_fit_r2:
            call = INDETERMINATE
            reasons.append(f"curve is not sigmoidal (R² {r2:.2f})")
        if k is not None and k > params.max_k_min:
            call = INDETERMINATE
            reasons.append(f"rise is too gradual for amplification (k {k:.1f} min): drift or evaporation")
        if amplitude < 2 * params.min_rise:
            call = INDETERMINATE
            reasons.append(f"weak plateau ({amplitude:.0%} rise)")

    res = WellResult(name, call, tt, amplitude, k, r2, 0.0, reasons)
    p_pos = model_prob(features(res, params), model)
    res.confidence = round(p_pos if call == POSITIVE else (1 - p_pos if call == NEGATIVE else 0.5), 3)
    return res


# ---------------------------------------------------------------- run interpretation
def interpret_run(wells: list[dict], results: dict[str, WellResult]) -> dict:
    """Apply controls. `wells` entries: {name, role: sample|ntc|pc|ic, sample_id?, target?}."""
    issues = []
    for w in wells:
        r = results[w["name"]]
        if w["role"] == "ntc" and r.call != NEGATIVE:
            issues.append(f"NTC {w['name']} is {r.call}: contamination or primer-dimer; decontaminate and repeat")
        if w["role"] == "pc" and r.call != POSITIVE:
            issues.append(f"Positive control {w['name']} is {r.call}: reagent, heating or optics failure")
    run_valid = not issues

    samples: dict[str, dict] = {}
    for w in wells:
        if w["role"] in ("sample", "ic"):
            s = samples.setdefault(w["sample_id"], {"target": None, "ic": None, "target_name": None})
            if w["role"] == "sample":
                s["target"], s["target_name"] = results[w["name"]], w.get("target", "target")
            else:
                s["ic"] = results[w["name"]]

    out = {}
    for sid, s in samples.items():
        tgt, ic = s["target"], s["ic"]
        if tgt is None:
            continue
        if not run_valid:
            verdict = "INVALID RUN"
        elif tgt.call == POSITIVE:
            verdict = "DETECTED"
        elif tgt.call == INDETERMINATE:
            verdict = "RETEST"
        elif ic is None:
            verdict = "NOT DETECTED (no internal control, unverified)"
        elif ic.call == POSITIVE:
            verdict = "NOT DETECTED"
        else:
            verdict = "INVALID (internal control failed: bad sample or inhibition)"
        out[sid] = {"target": s["target_name"], "verdict": verdict,
                    "tt_min": tgt.tt_min, "confidence": tgt.confidence}
    return {"run_valid": run_valid, "issues": issues, "samples": out,
            "wells": {k: asdict(v) for k, v in results.items()}}

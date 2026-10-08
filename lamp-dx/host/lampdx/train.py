"""Retrain the advisory confidence model from labelled runs.

Label file (CSV): run_json,well,truth   with truth = 1 (target present) or 0.
Truth must come from a reference method (lab qPCR or culture), never from this device's own calls.

    python -m lampdx.train labels.csv --out model.json
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from . import analysis


def fit_logistic(X: np.ndarray, y: np.ndarray, l2: float = 0.1, iters: int = 2000, lr: float = 0.1):
    Xb = np.column_stack([X, np.ones(len(X))])
    w = np.zeros(Xb.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(Xb @ w, -50, 50)))
        grad = Xb.T @ (p - y) / len(y) + l2 * np.r_[w[:-1], 0] / len(y)
        w -= lr * grad
    return w[:-1], w[-1]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("labels")
    ap.add_argument("--out", default="model.json")
    a = ap.parse_args(argv)

    X, y, runs = [], [], {}
    for row in csv.DictReader(open(a.labels)):
        run = runs.setdefault(row["run_json"], json.loads(Path(row["run_json"]).read_text()))
        params = analysis.CallParams.for_mode(run["mode"])
        res = analysis.call_well(row["well"], run["t_min"], run["signals"][row["well"]], params)
        X.append(analysis.features(res, params)); y.append(int(row["truth"]))
    X, y = np.array(X), np.array(y, float)
    if len(set(y)) < 2 or len(y) < 20:
        raise SystemExit(f"need ≥20 labelled wells with both outcomes (have {len(y)})")
    w, b = fit_logistic(X, y)
    pred = (1 / (1 + np.exp(-(X @ w + b)))) >= 0.5
    model = {"features": analysis.DEFAULT_MODEL["features"], "weights": w.round(4).tolist(),
             "bias": round(float(b), 4), "trained_on": int(len(y)),
             "train_accuracy": round(float((pred == y).mean()), 4)}
    Path(a.out).write_text(json.dumps(model, indent=1))
    print(f"trained on {len(y)} wells, train accuracy {model['train_accuracy']:.1%} → {a.out}")
    print("Training accuracy is optimistic. Validate on held-out runs before trusting it.")


if __name__ == "__main__":
    main()

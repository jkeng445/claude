import json

import numpy as np
import pytest

from lampdx import analysis
from lampdx.device import parse_line
from lampdx.run import run_assay
from lampdx.simulate import SCENARIOS, SimulatedCamera, SimulatedDevice, strip_layout


def simulate(scenario, mode="fluorescence", minutes=35, fault=None, seed=1):
    layout = strip_layout(mode)
    dev = SimulatedDevice(fault=fault)
    cam = SimulatedCamera(dev, layout, SCENARIOS[scenario], seed=seed)
    return run_assay(dev, cam, layout, minutes=minutes, log=lambda *_: None)


@pytest.mark.parametrize("mode", ["fluorescence", "colorimetric"])
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_normal_run(mode, seed):
    res = simulate("normal", mode, seed=seed)["result"]
    assert res["run_valid"], res["issues"]
    s = res["samples"]
    assert s["P1"]["verdict"] == "DETECTED"
    assert s["P2"]["verdict"] == "DETECTED"
    assert s["P3"]["verdict"] == "NOT DETECTED"
    assert s["P1"]["tt_min"] < s["P2"]["tt_min"]   # more target → earlier Tt


def test_tt_tracks_copy_number():
    t = np.arange(0, 35, 0.5)
    tts = []
    for copies in (1e2, 1e3, 1e4, 1e5):
        t0 = 27 - 3.2 * np.log10(copies)
        y = 100 * (1 + 1.2 / (1 + np.exp(-(t - t0))))
        tts.append(analysis.call_well("w", t, y).tt_min)
    assert all(a > b for a, b in zip(tts, tts[1:]))
    assert np.allclose(np.diff(tts), -3.2, atol=0.3)  # log-linear standard curve


def test_contaminated_ntc_invalidates_run():
    res = simulate("contaminated_ntc")["result"]
    assert not res["run_valid"]
    assert all(s["verdict"] == "INVALID RUN" for s in res["samples"].values())


def test_inhibited_sample_is_invalid_not_negative():
    res = simulate("inhibited_sample")["result"]
    assert res["run_valid"]
    assert res["samples"]["P2"]["verdict"].startswith("INVALID")


def test_late_nonspecific_is_retest_not_positive():
    res = simulate("late_nonspecific", minutes=45)["result"]
    assert res["samples"]["P3"]["verdict"] == "RETEST"


def test_heater_fault_aborts_run():
    run = simulate("normal", fault="heater")
    assert run["fault"] == "THERMAL_RUNAWAY"
    assert not run["result"]["run_valid"]


def test_linear_drift_is_not_positive():
    t = np.arange(0, 35, 0.5)
    y = 100 * (1 + 0.004 * t) + np.random.default_rng(0).normal(0, 0.3, t.size)
    assert analysis.call_well("w", t, y).call != analysis.POSITIVE


def test_firmware_nan_telemetry_parses():
    msg = parse_line('{"ms":1,"state":"FAULT","fault":"SENSOR_BLOCK","block":nan,"lid":25.0}')
    assert msg["block"] is None and msg["state"] == "FAULT"


def test_report_renders(tmp_path):
    from lampdx import report
    html = report.render(simulate("normal"))
    assert "research use only" in html.lower() and "DETECTED" in html
    json.dumps(simulate("normal"))   # run record is serialisable

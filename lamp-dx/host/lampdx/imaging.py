"""Read per-well signal out of a camera frame.

Fluorescence mode: blue (~470 nm) excitation, amber long-pass filter in front of
the camera. Signal = mean green inside the well minus the background patch.

Colorimetric mode: white light, phenol-red master mix goes pink → yellow as
LAMP acidifies the reaction. Signal = mean G / mean R inside the well.
"""
from __future__ import annotations

import numpy as np


def _disc_mask(shape, x, y, r):
    yy, xx = np.ogrid[: shape[0], : shape[1]]
    return (xx - x) ** 2 + (yy - y) ** 2 <= r * r


def well_signals(frame: np.ndarray, layout: dict) -> dict[str, float]:
    """frame: H×W×3 RGB uint8/float. layout: {"mode", "wells": [{name,x,y,r}], "background": {x,y,r}}."""
    img = frame.astype(float)
    mode = layout.get("mode", "fluorescence")
    bg = layout.get("background")
    bg_g = 0.0
    if mode == "fluorescence" and bg:
        bg_g = float(img[_disc_mask(img.shape, bg["x"], bg["y"], bg["r"])][:, 1].mean())
    out = {}
    for w in layout["wells"]:
        # Inner 70% of the well avoids the tube wall reflections.
        px = img[_disc_mask(img.shape, w["x"], w["y"], w["r"] * 0.7)]
        if mode == "colorimetric":
            out[w["name"]] = float(px[:, 1].mean() / max(px[:, 0].mean(), 1.0))
        else:
            out[w["name"]] = max(float(px[:, 1].mean()) - bg_g, 0.0)
    return out


class OpenCVCamera:
    """USB / Pi camera via OpenCV. Fix exposure and white balance. Auto modes ruin quantitation."""

    def __init__(self, index: int = 0, exposure: float | None = -6):
        import cv2  # optional dependency: pip install opencv-python-headless
        self.cv2 = cv2
        self.cap = cv2.VideoCapture(index)
        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        if exposure is not None:
            self.cap.set(cv2.CAP_PROP_EXPOSURE, exposure)
        self.cap.set(cv2.CAP_PROP_AUTO_WB, 0)

    def capture(self) -> np.ndarray:
        for _ in range(3):           # drop buffered frames so the image is current
            self.cap.read()
        ok, bgr = self.cap.read()
        if not ok:
            raise RuntimeError("camera read failed")
        return self.cv2.cvtColor(bgr, self.cv2.COLOR_BGR2RGB)

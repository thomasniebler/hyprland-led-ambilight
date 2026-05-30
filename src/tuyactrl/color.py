"""Color extraction and temporal smoothing."""
from __future__ import annotations

import colorsys

import numpy as np
from PIL import Image


def extract_color(
    img: Image.Image,
    sample_size: int = 64,
    min_saturation: float = 0.15,
    saturation_boost: float = 1.4,
    max_saturation: float = 1.0,
) -> tuple[int, int, int]:
    """Return the dominant colorful RGB from *img*.

    Strategy
    --------
    1. Downsample for speed.
    2. Build a saturation-and-brightness weight for every pixel so that vivid,
       well-lit pixels dominate the average (mimicking how the eye perceives
       scene color).
    3. Fall back to an unweighted average when the frame is nearly monochrome
       (desktop background, terminal, etc.).
    4. Optionally boost output saturation so dim scenes still produce a
       noticeable LED color.
    """
    img = img.resize((sample_size, sample_size), Image.BILINEAR).convert("RGB")
    pixels = np.asarray(img, dtype=np.float32) / 255.0  # (H, W, 3)
    flat = pixels.reshape(-1, 3)

    r, g, b = flat[:, 0], flat[:, 1], flat[:, 2]
    cmax = np.maximum(np.maximum(r, g), b)
    cmin = np.minimum(np.minimum(r, g), b)
    delta = cmax - cmin

    # Vectorised saturation (HSV style) — suppress divide-by-zero for black pixels
    with np.errstate(invalid="ignore", divide="ignore"):
        sat = np.where(cmax > 1e-6, delta / cmax, 0.0)
    val = cmax

    colorful = sat >= min_saturation
    if colorful.sum() >= 10:
        weights = sat[colorful] * val[colorful]
        weights_sum = weights.sum()
        if weights_sum > 1e-9:
            avg = np.average(flat[colorful], axis=0, weights=weights)
        else:
            avg = flat[colorful].mean(axis=0)
    else:
        # Monochrome frame – just use a simple average
        avg = flat.mean(axis=0)

    # Boost saturation in HSV space
    h, s, v = colorsys.rgb_to_hsv(float(avg[0]), float(avg[1]), float(avg[2]))
    s = min(max_saturation, s * saturation_boost)
    r_out, g_out, b_out = colorsys.hsv_to_rgb(h, s, v)

    return (round(r_out * 255), round(g_out * 255), round(b_out * 255))


class ColorSmoother:
    """Exponential moving average in HSV space.

    Smoothing in HSV avoids the grey desaturated transients you get when
    interpolating between two vivid hues in RGB.  Hue wraps correctly around
    the 0/1 boundary.
    """

    def __init__(self, alpha: float = 0.18) -> None:
        self.alpha = alpha
        self._h: float | None = None
        self._s: float = 0.0
        self._v: float = 0.0

    def reset(self) -> None:
        self._h = None

    def smooth(self, r: int, g: int, b: int) -> tuple[int, int, int]:
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)

        if self._h is None:
            self._h, self._s, self._v = h, s, v
        else:
            # Shortest-path hue interpolation
            dh = h - self._h
            if dh > 0.5:
                dh -= 1.0
            elif dh < -0.5:
                dh += 1.0
            self._h = (self._h + self.alpha * dh) % 1.0
            self._s += self.alpha * (s - self._s)
            self._v += self.alpha * (v - self._v)

        r_out, g_out, b_out = colorsys.hsv_to_rgb(self._h, self._s, self._v)
        return (round(r_out * 255), round(g_out * 255), round(b_out * 255))

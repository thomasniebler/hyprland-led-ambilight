"""Tests for colour extraction and smoothing."""
import colorsys

import numpy as np
import pytest
from PIL import Image

from tuyactrl.color import ColorSmoother, extract_color


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def solid_image(r: int, g: int, b: int, size: int = 50) -> Image.Image:
    """Return a solid-colour PIL Image."""
    arr = np.full((size, size, 3), [r, g, b], dtype=np.uint8)
    return Image.fromarray(arr)


def assert_dominant_channel(rgb: tuple[int, int, int], channel: int) -> None:
    """Assert that *channel* (0=R, 1=G, 2=B) is the largest value in *rgb*."""
    assert rgb[channel] == max(rgb), (
        f"Expected channel {channel} to dominate in {rgb}"
    )


# ---------------------------------------------------------------------------
# extract_color
# ---------------------------------------------------------------------------

class TestExtractColor:
    def test_vivid_red_dominates(self):
        img = solid_image(220, 40, 30)
        r, g, b = extract_color(img, sample_size=32, saturation_boost=1.0)
        assert_dominant_channel((r, g, b), 0)
        assert r > 150

    def test_vivid_green_dominates(self):
        img = solid_image(30, 200, 40)
        r, g, b = extract_color(img, sample_size=32, saturation_boost=1.0)
        assert_dominant_channel((r, g, b), 1)

    def test_vivid_blue_dominates(self):
        img = solid_image(30, 50, 210)
        r, g, b = extract_color(img, sample_size=32, saturation_boost=1.0)
        assert_dominant_channel((r, g, b), 2)

    def test_grey_falls_back_to_average(self):
        """A fully desaturated image should produce a near-grey output."""
        img = solid_image(128, 128, 128)
        r, g, b = extract_color(img, sample_size=32, saturation_boost=1.0)
        # All channels should be close to 128
        assert abs(r - 128) < 10
        assert abs(g - 128) < 10
        assert abs(b - 128) < 10

    def test_saturation_boost_increases_saturation(self):
        """Boosted output saturation should be >= unboosted."""
        img = solid_image(180, 160, 140)  # slightly warm, low saturation
        r1, g1, b1 = extract_color(img, sample_size=32, saturation_boost=1.0)
        r2, g2, b2 = extract_color(img, sample_size=32, saturation_boost=2.0)
        _, s1, _ = colorsys.rgb_to_hsv(r1/255, g1/255, b1/255)
        _, s2, _ = colorsys.rgb_to_hsv(r2/255, g2/255, b2/255)
        assert s2 >= s1

    def test_output_channels_in_range(self):
        """RGB values must always be 0–255."""
        for color in [(255, 0, 0), (0, 255, 0), (0, 0, 255), (0, 0, 0), (255, 255, 255)]:
            img = solid_image(*color)
            r, g, b = extract_color(img, sample_size=16, saturation_boost=2.0)
            assert 0 <= r <= 255
            assert 0 <= g <= 255
            assert 0 <= b <= 255

    def test_high_min_saturation_falls_back_for_grey(self):
        """When min_saturation is very high, grey scenes fall back to average."""
        img = solid_image(128, 128, 128)
        # Should not crash even with extreme filter
        r, g, b = extract_color(img, sample_size=16, min_saturation=0.99, saturation_boost=1.0)
        assert 0 <= r <= 255

    def test_mixed_image_colorful_pixels_win(self):
        """Half vivid red, half neutral grey — red should dominate."""
        arr = np.zeros((50, 50, 3), dtype=np.uint8)
        arr[:25, :] = [220, 30, 30]   # top half: vivid red
        arr[25:, :] = [128, 128, 128] # bottom half: grey
        img = Image.fromarray(arr)
        r, g, b = extract_color(img, sample_size=32, saturation_boost=1.0)
        assert_dominant_channel((r, g, b), 0)


# ---------------------------------------------------------------------------
# ColorSmoother
# ---------------------------------------------------------------------------

class TestColorSmoother:
    def test_instant_alpha_converges_immediately(self):
        s = ColorSmoother(alpha=1.0)
        r, g, b = s.smooth(255, 0, 0)
        assert r == 255
        assert g == 0
        assert b == 0

    def test_zero_alpha_stays_frozen_after_init(self):
        s = ColorSmoother(alpha=0.0)
        s.smooth(255, 0, 0)   # first call initialises
        r, g, b = s.smooth(0, 0, 255)  # should not move
        # Still at red (within rounding)
        assert r > 200
        assert b < 50

    def test_partial_alpha_interpolates(self):
        s = ColorSmoother(alpha=0.5)
        s.smooth(0, 0, 255)  # initialise to blue
        for _ in range(20):  # many steps toward red
            r, g, b = s.smooth(255, 0, 0)
        # Should be close to red after many iterations
        assert r > 200

    def test_hue_wrap_red_to_magenta(self):
        """Interpolating from red (hue≈0) to magenta (hue≈300°) should not
        go through green/cyan — it should take the short path."""
        s = ColorSmoother(alpha=1.0)
        s.smooth(255, 0, 0)       # hue = 0 (red)
        r, g, b = s.smooth(255, 0, 200)  # hue ≈ 0.86 (magenta)
        # Green channel must stay very low — no green detour
        assert g < 50

    def test_reset_reinitialises(self):
        s = ColorSmoother(alpha=0.0)
        s.smooth(255, 0, 0)   # initialise to red
        s.reset()
        r, g, b = s.smooth(0, 0, 255)  # after reset, should snap to blue
        assert b == 255
        assert r == 0

    def test_output_always_in_range(self):
        s = ColorSmoother(alpha=0.3)
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (128, 128, 0), (0, 0, 0)]
        for color in colors * 5:
            r, g, b = s.smooth(*color)
            assert 0 <= r <= 255
            assert 0 <= g <= 255
            assert 0 <= b <= 255

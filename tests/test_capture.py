"""Tests for capture helpers (no real Hyprland/grim required)."""
import asyncio
import json

import pytest

from tuyactrl.capture import (
    WindowGeometry,
    active_window_geometry,
    capture_window,
    grab_active_window,
)
from tuyactrl.config import CaptureConfig


# ---------------------------------------------------------------------------
# WindowGeometry
# ---------------------------------------------------------------------------

class TestWindowGeometry:
    def test_grim_arg_format(self):
        geo = WindowGeometry(x=0, y=0, w=1920, h=1080)
        assert geo.grim_arg == "0,0 1920x1080"

    def test_grim_arg_with_offset(self):
        geo = WindowGeometry(x=100, y=200, w=800, h=600)
        assert geo.grim_arg == "100,200 800x600"

    def test_grim_arg_negative_offset(self):
        # Multi-monitor setups can have negative co-ordinates
        geo = WindowGeometry(x=-1920, y=0, w=1920, h=1080)
        assert geo.grim_arg == "-1920,0 1920x1080"


# ---------------------------------------------------------------------------
# active_window_geometry — mock hyprctl via monkeypatch
# ---------------------------------------------------------------------------

def _fake_hyprctl(response: dict):
    """Return an async function that simulates hyprctl output."""
    async def _fake(*args, **kwargs):
        class FakeProc:
            async def communicate(self):
                return json.dumps(response).encode(), b""
        return FakeProc()
    return _fake


class TestActiveWindowGeometry:
    def test_normal_window(self, monkeypatch):
        payload = {"at": [100, 200], "size": [1280, 720], "class": "firefox"}
        monkeypatch.setattr(
            "tuyactrl.capture.asyncio.create_subprocess_exec",
            _fake_hyprctl(payload),
        )
        geo = asyncio.run(active_window_geometry())
        assert geo is not None
        assert geo.x == 100
        assert geo.y == 200
        assert geo.w == 1280
        assert geo.h == 720

    def test_zero_size_returns_none(self, monkeypatch):
        payload = {"at": [0, 0], "size": [0, 0]}
        monkeypatch.setattr(
            "tuyactrl.capture.asyncio.create_subprocess_exec",
            _fake_hyprctl(payload),
        )
        geo = asyncio.run(active_window_geometry())
        assert geo is None

    def test_missing_size_returns_none(self, monkeypatch):
        payload = {"at": [0, 0]}  # no "size" key
        monkeypatch.setattr(
            "tuyactrl.capture.asyncio.create_subprocess_exec",
            _fake_hyprctl(payload),
        )
        geo = asyncio.run(active_window_geometry())
        assert geo is None

    def test_subprocess_error_returns_none(self, monkeypatch):
        async def _broken(*args, **kwargs):
            raise OSError("hyprctl not found")
        monkeypatch.setattr("tuyactrl.capture.asyncio.create_subprocess_exec", _broken)
        geo = asyncio.run(active_window_geometry())
        assert geo is None

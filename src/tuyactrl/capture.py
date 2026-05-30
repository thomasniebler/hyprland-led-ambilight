"""Capture the active Hyprland window as a PIL Image using grim."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from io import BytesIO

from PIL import Image

from tuyactrl.config import CaptureConfig

log = logging.getLogger(__name__)


@dataclass
class WindowGeometry:
    x: int
    y: int
    w: int
    h: int

    @property
    def grim_arg(self) -> str:
        return f"{self.x},{self.y} {self.w}x{self.h}"


async def _run_subprocess_with_timeout(
    args: list[str], timeout: float
) -> bytes | None:
    """Run a subprocess, kill it if it exceeds *timeout*, return stdout or None."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return stdout
    except (asyncio.TimeoutError, Exception):
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        await proc.wait()
        raise


async def active_window_geometry() -> WindowGeometry | None:
    """Return geometry of the currently focused Hyprland window."""
    try:
        stdout = await _run_subprocess_with_timeout(
            ["hyprctl", "-j", "activewindow"], timeout=1.0
        )
        data = json.loads(stdout)
        at = data.get("at", [0, 0])
        size = data.get("size", [0, 0])
        if size[0] <= 0 or size[1] <= 0:
            return None
        return WindowGeometry(x=at[0], y=at[1], w=size[0], h=size[1])
    except Exception as exc:
        log.debug("hyprctl error: %s", exc)
        return None


async def capture_window(geo: WindowGeometry) -> Image.Image | None:
    """Capture a screen region via grim and return it as a PIL Image."""
    try:
        stdout = await _run_subprocess_with_timeout(
            ["grim", "-g", geo.grim_arg, "-"], timeout=2.0
        )
        if not stdout:
            return None
        return Image.open(BytesIO(stdout))
    except Exception as exc:
        log.debug("grim error: %s", exc)
        return None


async def grab_active_window(cfg: CaptureConfig) -> Image.Image | None:
    """High-level: get active window geometry, then capture it."""
    geo = await active_window_geometry()
    if geo is None:
        return None
    img = await capture_window(geo)
    return img

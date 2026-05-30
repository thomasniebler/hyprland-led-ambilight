"""Tuya LED strip controller wrapper around tinytuya."""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

import tinytuya

from tuyactrl.config import TuyaConfig

log = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tuya")


class LedController:
    """Manages a persistent connection to a Tuya BulbDevice.

    Commands are sent in a dedicated thread so they never block the asyncio
    event loop.  Only sends when the colour has changed by at least
    ``cfg.min_change`` across all channels combined.
    """

    def __init__(self, cfg: TuyaConfig) -> None:
        self._cfg = cfg
        self._dev: tinytuya.BulbDevice | None = None
        self._last: tuple[int, int, int] | None = None

    # ------------------------------------------------------------------
    # Internal helpers (called from the thread executor)
    # ------------------------------------------------------------------

    def _get_device(self) -> tinytuya.BulbDevice:
        if self._dev is None:
            dev = tinytuya.BulbDevice(
                self._cfg.device_id,
                self._cfg.ip,
                self._cfg.local_key,
                version=self._cfg.version,
                persist=True,   # keep TCP socket open between commands
            )
            dev.set_socketTimeout(2.0)
            dev.set_socketRetryLimit(2)
            if self._cfg.bulb_type:
                # Skip auto-detection status fetch — use explicit bulb type.
                # Type B covers most modern RGB LED strips (DPS 20-28).
                dev.set_bulb_type(self._cfg.bulb_type)
            self._dev = dev
        return self._dev

    def _send_sync(self, r: int, g: int, b: int) -> None:
        dev = self._get_device()
        try:
            # nowait=True: fire-and-forget — no blocking response wait.
            # For ambilight we care about throughput, not ACK confirmation.
            dev.set_colour(r, g, b, nowait=True)
        except Exception as exc:
            log.warning("Tuya send failed, reconnecting: %s", exc)
            self._dev = None  # Force reconnect on next call
            raise

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def send(self, r: int, g: int, b: int) -> None:
        """Send colour to the device if it has changed enough."""
        if self._last is not None:
            lr, lg, lb = self._last
            if abs(r - lr) + abs(g - lg) + abs(b - lb) < self._cfg.min_change:
                return

        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(_executor, self._send_sync, r, g, b)
            self._last = (r, g, b)
        except Exception:
            pass  # Already logged in _send_sync

    async def turn_off(self) -> None:
        """Turn the LED strip off (best-effort; errors are logged, not raised)."""
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(_executor, self._do_turn_off)
        except Exception as exc:
            log.warning("Could not turn off device: %s", exc)

    def _do_turn_off(self) -> None:
        dev = self._get_device()
        dev.turn_off()

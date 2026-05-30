"""Main async loop: capture → analyse → smooth → send."""
from __future__ import annotations

import asyncio
import logging
import signal

from tuyactrl.capture import grab_active_window
from tuyactrl.color import ColorSmoother, extract_color
from tuyactrl.config import Config
from tuyactrl.tuya import LedController

log = logging.getLogger(__name__)


async def run(cfg: Config) -> None:
    led = LedController(cfg.tuya)
    smoother = ColorSmoother(cfg.color.smoothing_alpha)
    interval = cfg.capture.interval_ms / 1000.0

    stop = asyncio.Event()

    def _handle_signal() -> None:
        log.info("Shutting down…")
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    log.info(
        "Started — device %s @ %s, interval %dms",
        cfg.tuya.device_id,
        cfg.tuya.ip,
        cfg.capture.interval_ms,
    )

    while not stop.is_set():
        tick_start = loop.time()

        try:
            img = await grab_active_window(cfg.capture)
            if img is not None:
                raw = extract_color(
                    img,
                    sample_size=cfg.capture.sample_size,
                    min_saturation=cfg.capture.min_saturation,
                    saturation_boost=cfg.color.saturation_boost,
                    max_saturation=cfg.color.max_saturation,
                )
                smooth = smoother.smooth(*raw)
                log.debug("raw=%s  smooth=%s", raw, smooth)
                await led.send(*smooth)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.warning("Frame error: %s", exc)

        elapsed = loop.time() - tick_start
        sleep_time = max(0.0, interval - elapsed)
        try:
            await asyncio.wait_for(stop.wait(), timeout=sleep_time)
        except asyncio.TimeoutError:
            pass

    await led.turn_off()
    log.info("LED off, bye.")

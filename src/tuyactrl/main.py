"""Main async loop: capture → analyse → smooth → send."""
from __future__ import annotations

import asyncio
import logging
import signal
from datetime import UTC, datetime

from tuyactrl.capture import grab_active_window
from tuyactrl.color import ColorSmoother, extract_color
from tuyactrl.context import collect_context_snapshot, evaluate_context_policy
from tuyactrl.config import Config
from tuyactrl.status import RuntimeStatus, new_status, write_status
from tuyactrl.tuya import LedController

log = logging.getLogger(__name__)


async def run(cfg: Config) -> None:
    led = LedController(cfg.tuya)
    smoother = ColorSmoother(cfg.color.smoothing_alpha) if cfg.color.enable_smoothing else None
    interval = cfg.capture.interval_ms / 1000.0
    context_interval = cfg.context.poll_interval_ms / 1000.0
    context_active = True
    context_reasons: list[str] = []
    context_next_check = 0.0
    turned_off_for_context = False
    snapshot_wifi: str | None = None
    snapshot_ac: bool | None = None
    snapshot_ext: bool | None = None
    last_color: tuple[int, int, int] | None = None
    status = new_status()
    status.running = True
    status.reason = "starting"
    try:
        write_status(status)
    except Exception as exc:
        log.debug("Failed to write initial status: %s", exc)

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
            if cfg.context.enabled and tick_start >= context_next_check:
                snapshot = await collect_context_snapshot()
                snapshot_wifi = snapshot.wifi_ssid
                snapshot_ac = snapshot.ac_power
                snapshot_ext = snapshot.external_monitor
                context_active, new_reasons = evaluate_context_policy(cfg.context, snapshot)
                if context_active != (len(context_reasons) == 0) or new_reasons != context_reasons:
                    if context_active:
                        turned_off_for_context = False
                        log.info(
                            "Context became active (wifi=%s ac=%s ext-monitor=%s)",
                            snapshot.wifi_ssid,
                            snapshot.ac_power,
                            snapshot.external_monitor,
                        )
                    else:
                        log.info(
                            "Context inactive (%s) (wifi=%s ac=%s ext-monitor=%s)",
                            ", ".join(new_reasons),
                            snapshot.wifi_ssid,
                            snapshot.ac_power,
                            snapshot.external_monitor,
                        )
                context_reasons = new_reasons
                context_next_check = tick_start + context_interval

            if cfg.context.enabled and not context_active:
                if cfg.context.turn_off_when_inactive and not turned_off_for_context:
                    await led.turn_off()
                    if smoother is not None:
                        smoother.reset()
                    turned_off_for_context = True
            else:
                img = await grab_active_window(cfg.capture)
                if img is not None:
                    raw = extract_color(
                        img,
                        sample_size=cfg.capture.sample_size,
                        min_saturation=cfg.capture.min_saturation,
                        saturation_boost=cfg.color.saturation_boost,
                        max_saturation=cfg.color.max_saturation,
                    )
                    out = smoother.smooth(*raw) if smoother is not None else raw
                    log.debug("raw=%s  out=%s", raw, out)
                    await led.send(*out)
                    last_color = out
        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.warning("Frame error: %s", exc)

        reason = "running"
        if cfg.context.enabled and not context_active:
            reason = ",".join(context_reasons) if context_reasons else "context-inactive"
        status = RuntimeStatus(
            running=True,
            active=context_active,
            reason=reason,
            wifi_ssid=snapshot_wifi,
            ac_power=snapshot_ac,
            external_monitor=snapshot_ext,
            last_color=last_color,
            updated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        try:
            write_status(status)
        except Exception as exc:
            log.debug("Failed to write status: %s", exc)

        elapsed = loop.time() - tick_start
        sleep_time = max(0.0, interval - elapsed)
        try:
            await asyncio.wait_for(stop.wait(), timeout=sleep_time)
        except asyncio.TimeoutError:
            pass

    await led.turn_off()
    status.running = False
    status.active = False
    status.reason = "stopped"
    status.updated_at = datetime.now(UTC).isoformat(timespec="seconds")
    try:
        write_status(status)
    except Exception as exc:
        log.debug("Failed to write final status: %s", exc)
    log.info("LED off, bye.")

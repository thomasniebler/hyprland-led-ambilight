"""Context-aware activation (power, Wi-Fi, monitor topology)."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from tuyactrl.config import ContextConfig

log = logging.getLogger(__name__)


@dataclass
class ContextSnapshot:
    ac_power: bool | None
    wifi_ssid: str | None
    external_monitor: bool | None


def evaluate_context_policy(
    cfg: ContextConfig,
    snapshot: ContextSnapshot,
) -> tuple[bool, list[str]]:
    """Return (active, reasons) for the given runtime snapshot."""
    if not cfg.enabled:
        return True, []

    reasons: list[str] = []

    if cfg.require_ac_power and snapshot.ac_power is not True:
        reasons.append("ac-power-required")

    if cfg.require_external_monitor and snapshot.external_monitor is not True:
        reasons.append("external-monitor-required")

    if cfg.allowed_ssids:
        if snapshot.wifi_ssid is None:
            reasons.append("wifi-unknown")
        elif snapshot.wifi_ssid not in cfg.allowed_ssids:
            reasons.append(f"wifi-not-allowed:{snapshot.wifi_ssid}")

    if cfg.blocked_ssids and snapshot.wifi_ssid in cfg.blocked_ssids:
        reasons.append(f"wifi-blocked:{snapshot.wifi_ssid}")

    return (len(reasons) == 0, reasons)


async def collect_context_snapshot(timeout_s: float = 1.5) -> ContextSnapshot:
    """Probe local system state used for context-aware activation."""
    ac_power, wifi_ssid, external_monitor = await asyncio.gather(
        _detect_ac_power(),
        _detect_wifi_ssid(timeout_s),
        _detect_external_monitor(timeout_s),
    )
    return ContextSnapshot(
        ac_power=ac_power,
        wifi_ssid=wifi_ssid,
        external_monitor=external_monitor,
    )


async def _detect_wifi_ssid(timeout_s: float) -> str | None:
    # Prefer nmcli (widely available when NetworkManager is used).
    out = await _run_command(
        ("nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"),
        timeout_s=timeout_s,
    )
    if out:
        for line in out.splitlines():
            if line.startswith("yes:"):
                ssid = line[4:].strip()
                if ssid:
                    return ssid

    # Fallback for systems without nmcli.
    out = await _run_command(("iwgetid", "-r"), timeout_s=timeout_s)
    if out:
        ssid = out.strip()
        return ssid or None
    return None


async def _detect_external_monitor(timeout_s: float) -> bool | None:
    out = await _run_command(("hyprctl", "-j", "monitors"), timeout_s=timeout_s)
    if not out:
        return None
    try:
        monitors = json.loads(out)
    except json.JSONDecodeError:
        return None
    if not isinstance(monitors, list):
        return None
    return len(monitors) > 1


async def _detect_ac_power() -> bool | None:
    """Return whether a line-power source is currently online."""
    base = Path("/sys/class/power_supply")
    if not base.exists():
        return None

    candidates = list(base.glob("*/type"))
    mains_dirs: list[Path] = []
    for type_file in candidates:
        try:
            type_name = type_file.read_text(encoding="utf-8").strip().lower()
        except OSError:
            continue
        if type_name in {"mains", "usb"}:
            mains_dirs.append(type_file.parent)

    if not mains_dirs:
        return None

    seen_offline = False
    for dev_dir in mains_dirs:
        online_file = dev_dir / "online"
        if not online_file.exists():
            continue
        try:
            online = online_file.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if online == "1":
            return True
        seen_offline = True

    if seen_offline:
        return False
    return None


async def _run_command(cmd: tuple[str, ...], timeout_s: float) -> str | None:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return None
    except Exception as exc:
        log.debug("Context command start failed %s: %s", cmd[0], exc)
        return None

    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return None
    except Exception as exc:
        log.debug("Context command failed %s: %s", cmd[0], exc)
        return None

    if proc.returncode != 0:
        return None
    return stdout.decode("utf-8", errors="ignore").strip()

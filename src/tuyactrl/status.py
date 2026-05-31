"""Runtime status persistence and Waybar-friendly formatting."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_STATUS_FILE = Path.home() / ".cache" / "tuyactrl" / "status.json"


@dataclass
class RuntimeStatus:
    running: bool
    active: bool
    reason: str
    wifi_ssid: str | None
    ac_power: bool | None
    external_monitor: bool | None
    last_color: tuple[int, int, int] | None
    updated_at: str


def new_status() -> RuntimeStatus:
    return RuntimeStatus(
        running=False,
        active=False,
        reason="starting",
        wifi_ssid=None,
        ac_power=None,
        external_monitor=None,
        last_color=None,
        updated_at=_now_iso(),
    )


def write_status(status: RuntimeStatus, path: Path = DEFAULT_STATUS_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(asdict(status), ensure_ascii=True, separators=(",", ":")),
        encoding="utf-8",
    )
    tmp_path.replace(path)


def read_status(path: Path = DEFAULT_STATUS_FILE) -> RuntimeStatus | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return RuntimeStatus(
        running=bool(payload.get("running", False)),
        active=bool(payload.get("active", False)),
        reason=str(payload.get("reason", "unknown")),
        wifi_ssid=payload.get("wifi_ssid"),
        ac_power=payload.get("ac_power"),
        external_monitor=payload.get("external_monitor"),
        last_color=tuple(payload["last_color"]) if payload.get("last_color") else None,
        updated_at=str(payload.get("updated_at", _now_iso())),
    )


def waybar_json(status: RuntimeStatus) -> str:
    if status.running and status.active:
        icon = "🟢"
        cls = "active"
        text = f"{icon} ambi"
    elif status.running:
        icon = "🟡"
        cls = "paused"
        text = f"{icon} ambi"
    else:
        icon = "⚪"
        cls = "stopped"
        text = f"{icon} ambi"

    tooltip = (
        f"reason: {status.reason}\\n"
        f"wifi: {status.wifi_ssid}\\n"
        f"ac: {status.ac_power}\\n"
        f"ext-monitor: {status.external_monitor}\\n"
        f"updated: {status.updated_at}"
    )

    payload = {
        "text": text,
        "class": cls,
        "tooltip": tooltip,
    }
    return json.dumps(payload, ensure_ascii=False)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")

"""Tests for runtime status persistence and waybar formatting."""

import json

from tuyactrl.status import RuntimeStatus, read_status, waybar_json, write_status


def test_write_and_read_status_roundtrip(tmp_path):
    status_file = tmp_path / "status.json"
    status = RuntimeStatus(
        running=True,
        active=False,
        reason="wifi-not-allowed:Office",
        wifi_ssid="Office",
        ac_power=True,
        external_monitor=False,
        last_color=(10, 20, 30),
        updated_at="2026-01-01T00:00:00+00:00",
    )
    write_status(status, status_file)
    loaded = read_status(status_file)
    assert loaded == status


def test_waybar_json_classes():
    active = RuntimeStatus(
        running=True,
        active=True,
        reason="running",
        wifi_ssid="Home",
        ac_power=True,
        external_monitor=True,
        last_color=(1, 2, 3),
        updated_at="2026-01-01T00:00:00+00:00",
    )
    payload = json.loads(waybar_json(active))
    assert payload["class"] == "active"
    assert "ambi" in payload["text"]

    paused = RuntimeStatus(
        running=True,
        active=False,
        reason="context-inactive",
        wifi_ssid="Corp",
        ac_power=False,
        external_monitor=False,
        last_color=None,
        updated_at="2026-01-01T00:00:00+00:00",
    )
    payload = json.loads(waybar_json(paused))
    assert payload["class"] == "paused"

    stopped = RuntimeStatus(
        running=False,
        active=False,
        reason="stopped",
        wifi_ssid=None,
        ac_power=None,
        external_monitor=None,
        last_color=None,
        updated_at="2026-01-01T00:00:00+00:00",
    )
    payload = json.loads(waybar_json(stopped))
    assert payload["class"] == "stopped"

"""Tests for context-aware activation policy."""

from tuyactrl.config import ContextConfig
from tuyactrl.context import ContextSnapshot, evaluate_context_policy


def test_policy_disabled_always_active():
    cfg = ContextConfig(enabled=False)
    active, reasons = evaluate_context_policy(
        cfg,
        ContextSnapshot(ac_power=None, wifi_ssid=None, external_monitor=None),
    )
    assert active is True
    assert reasons == []


def test_policy_requires_ac_power():
    cfg = ContextConfig(enabled=True, require_ac_power=True)
    active, reasons = evaluate_context_policy(
        cfg,
        ContextSnapshot(ac_power=False, wifi_ssid="Home", external_monitor=True),
    )
    assert active is False
    assert "ac-power-required" in reasons


def test_policy_enforces_allowed_ssids():
    cfg = ContextConfig(enabled=True, allowed_ssids=["HomeWiFi", "BackupWiFi"])
    active, reasons = evaluate_context_policy(
        cfg,
        ContextSnapshot(ac_power=True, wifi_ssid="OfficeWiFi", external_monitor=True),
    )
    assert active is False
    assert reasons == ["wifi-not-allowed:OfficeWiFi"]


def test_policy_enforces_blocked_ssids():
    cfg = ContextConfig(enabled=True, blocked_ssids=["CorpWiFi"])
    active, reasons = evaluate_context_policy(
        cfg,
        ContextSnapshot(ac_power=True, wifi_ssid="CorpWiFi", external_monitor=True),
    )
    assert active is False
    assert reasons == ["wifi-blocked:CorpWiFi"]


def test_policy_combines_multiple_reasons():
    cfg = ContextConfig(
        enabled=True,
        require_ac_power=True,
        require_external_monitor=True,
        allowed_ssids=["HomeWiFi"],
    )
    active, reasons = evaluate_context_policy(
        cfg,
        ContextSnapshot(ac_power=False, wifi_ssid=None, external_monitor=False),
    )
    assert active is False
    assert set(reasons) == {
        "ac-power-required",
        "external-monitor-required",
        "wifi-unknown",
    }


def test_policy_active_when_all_constraints_met():
    cfg = ContextConfig(
        enabled=True,
        require_ac_power=True,
        require_external_monitor=True,
        allowed_ssids=["HomeWiFi"],
        blocked_ssids=["CorpWiFi"],
    )
    active, reasons = evaluate_context_policy(
        cfg,
        ContextSnapshot(ac_power=True, wifi_ssid="HomeWiFi", external_monitor=True),
    )
    assert active is True
    assert reasons == []

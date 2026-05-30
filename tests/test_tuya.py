"""Tests for Tuya LED controller reconnect behavior."""

import pytest

from tuyactrl.config import TuyaConfig
from tuyactrl.tuya import LedController


class _FakeBulbRetryOnce:
    instances = []

    def __init__(self, *_args, **_kwargs):
        self.idx = len(self.__class__.instances)
        self.calls = 0
        self.last = None
        self.__class__.instances.append(self)

    def set_socketTimeout(self, _timeout):
        return None

    def set_socketRetryLimit(self, _limit):
        return None

    def set_bulb_type(self, _type):
        return None

    def set_colour(self, r, g, b, nowait):
        self.calls += 1
        if self.idx == 0:
            raise RuntimeError("simulated dropped socket")
        self.last = (r, g, b, nowait)


class _FakeBulbAlwaysFails:
    instances = []

    def __init__(self, *_args, **_kwargs):
        self.__class__.instances.append(self)

    def set_socketTimeout(self, _timeout):
        return None

    def set_socketRetryLimit(self, _limit):
        return None

    def set_bulb_type(self, _type):
        return None

    def set_colour(self, *_args, **_kwargs):
        raise RuntimeError("simulated persistent failure")


class _FakeBulbTurnOffRetry:
    instances = []

    def __init__(self, *_args, **_kwargs):
        self.idx = len(self.__class__.instances)
        self.turn_off_calls = 0
        self.__class__.instances.append(self)

    def set_socketTimeout(self, _timeout):
        return None

    def set_socketRetryLimit(self, _limit):
        return None

    def set_bulb_type(self, _type):
        return None

    def turn_off(self):
        self.turn_off_calls += 1
        if self.idx == 0:
            raise RuntimeError("stale socket")


def _cfg() -> TuyaConfig:
    return TuyaConfig(
        device_id="dev",
        local_key="localkey12345678",
        ip="192.168.1.42",
        bulb_type="B",
    )


def test_send_sync_reconnects_and_retries_once(monkeypatch):
    _FakeBulbRetryOnce.instances.clear()
    monkeypatch.setattr("tuyactrl.tuya.tinytuya.BulbDevice", _FakeBulbRetryOnce)

    led = LedController(_cfg())
    led._send_sync(10, 20, 30)

    assert len(_FakeBulbRetryOnce.instances) == 2
    assert _FakeBulbRetryOnce.instances[0].calls == 1
    assert _FakeBulbRetryOnce.instances[1].last == (10, 20, 30, True)


def test_send_sync_resets_cached_device_after_failed_retry(monkeypatch):
    _FakeBulbAlwaysFails.instances.clear()
    monkeypatch.setattr("tuyactrl.tuya.tinytuya.BulbDevice", _FakeBulbAlwaysFails)

    led = LedController(_cfg())
    with pytest.raises(RuntimeError, match="persistent failure"):
        led._send_sync(1, 2, 3)

    assert len(_FakeBulbAlwaysFails.instances) == 2
    assert led._dev is None


def test_failure_backoff_state_and_reset(monkeypatch):
    led = LedController(_cfg())

    monkeypatch.setattr("tuyactrl.tuya.time.monotonic", lambda: 100.0)
    first = led._mark_send_failure()
    assert first == pytest.approx(0.25)
    assert led._consecutive_failures == 1
    assert led._suspend_until == pytest.approx(100.25)

    second = led._mark_send_failure()
    assert second == pytest.approx(0.5)
    assert led._consecutive_failures == 2
    assert led._suspend_until == pytest.approx(100.5)

    led._mark_send_success()
    assert led._consecutive_failures == 0
    assert led._suspend_until == 0.0


def test_turn_off_retries_once_with_fresh_connection(monkeypatch):
    _FakeBulbTurnOffRetry.instances.clear()
    monkeypatch.setattr("tuyactrl.tuya.tinytuya.BulbDevice", _FakeBulbTurnOffRetry)

    led = LedController(_cfg())
    led._do_turn_off()

    assert len(_FakeBulbTurnOffRetry.instances) == 2
    assert _FakeBulbTurnOffRetry.instances[0].turn_off_calls == 1
    assert _FakeBulbTurnOffRetry.instances[1].turn_off_calls == 1

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

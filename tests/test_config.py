"""Tests for config loading and validation."""
import dataclasses
import tempfile
from pathlib import Path

import pytest

from tuyactrl.config import (
    CaptureConfig,
    ColorConfig,
    Config,
    TuyaConfig,
    load,
)


def _write(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(suffix=".toml", delete=False, mode="w")
    f.write(content)
    f.close()
    return Path(f.name)


MINIMAL = """\
[tuya]
device_id = "abc123"
local_key  = "key1234567890123"
ip         = "192.168.1.42"
"""


def test_minimal_config_loads():
    cfg = load(_write(MINIMAL))
    assert isinstance(cfg, Config)
    assert cfg.tuya.device_id == "abc123"
    assert cfg.tuya.ip == "192.168.1.42"
    # Defaults should be populated
    assert cfg.capture.interval_ms == 100
    assert cfg.color.enable_smoothing is False
    assert cfg.color.smoothing_alpha == 0.18


def test_full_config_overrides_defaults():
    toml = MINIMAL + """\
[capture]
interval_ms = 200
sample_size = 32
min_saturation = 0.25

[color]
enable_smoothing = true
smoothing_alpha = 0.5
saturation_boost = 2.0
max_saturation = 0.9
"""
    cfg = load(_write(toml))
    assert cfg.capture.interval_ms == 200
    assert cfg.capture.sample_size == 32
    assert cfg.capture.min_saturation == 0.25
    assert cfg.color.enable_smoothing is True
    assert cfg.color.smoothing_alpha == 0.5
    assert cfg.color.saturation_boost == 2.0
    assert cfg.color.max_saturation == 0.9


def test_missing_tuya_section_raises():
    with pytest.raises(ValueError, match=r"\[tuya\]"):
        load(_write("[capture]\ninterval_ms = 100\n"))


@pytest.mark.parametrize("missing_key", ["device_id", "local_key", "ip"])
def test_missing_required_tuya_key_raises(missing_key):
    keys = {"device_id": "x", "local_key": "y", "ip": "1.2.3.4"}
    del keys[missing_key]
    lines = "\n".join(f'{k} = "{v}"' for k, v in keys.items())
    with pytest.raises(ValueError, match=missing_key):
        load(_write(f"[tuya]\n{lines}\n"))


def test_unknown_tuya_key_raises():
    toml = """\
[tuya]
device_id = "x"
local_key  = "y"
ip         = "1.2.3.4"
bogus      = 1
"""
    with pytest.raises(ValueError, match="Unknown keys"):
        load(_write(toml))


def test_unknown_capture_key_raises():
    with pytest.raises(ValueError, match="Unknown keys"):
        load(_write(MINIMAL + "[capture]\nfake_key = 99\n"))


def test_unknown_color_key_raises():
    with pytest.raises(ValueError, match="Unknown keys"):
        load(_write(MINIMAL + "[color]\nfake_key = 99\n"))


def test_invalid_interval_ms_raises():
    with pytest.raises(ValueError, match="interval_ms"):
        load(_write(MINIMAL + "[capture]\ninterval_ms = 0\n"))


def test_invalid_sample_size_raises():
    with pytest.raises(ValueError, match="sample_size"):
        load(_write(MINIMAL + "[capture]\nsample_size = -1\n"))


@pytest.mark.parametrize("alpha", [-0.1, 1.1])
def test_invalid_smoothing_alpha_raises(alpha):
    with pytest.raises(ValueError, match="smoothing_alpha"):
        load(_write(MINIMAL + f"[color]\nsmoothing_alpha = {alpha}\n"))


def test_invalid_enable_smoothing_type_raises():
    with pytest.raises(ValueError, match="enable_smoothing"):
        load(_write(MINIMAL + '[color]\nenable_smoothing = "no"\n'))


def test_negative_min_change_raises():
    with pytest.raises(ValueError, match="min_change"):
        toml = """\
[tuya]
device_id = "x"
local_key  = "y"
ip         = "1.2.3.4"
min_change = -1
"""
        load(_write(toml))


def test_tuya_version_override():
    toml = """\
[tuya]
device_id = "x"
local_key  = "y"
ip         = "1.2.3.4"
version    = "3.4"
"""
    cfg = load(_write(toml))
    assert cfg.tuya.version == "3.4"

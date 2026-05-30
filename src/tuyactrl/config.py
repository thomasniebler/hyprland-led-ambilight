"""Configuration dataclasses and TOML loader."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib  # type: ignore[no-redef]
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]


@dataclass
class TuyaConfig:
    device_id: str
    local_key: str
    ip: str
    version: str = "3.3"
    # Minimum summed RGB-channel delta to bother sending a new command.
    min_change: int = 4
    # Pre-configure bulb type to skip the auto-detection status fetch on first
    # use.  Set to "B" for most modern RGB LED strips (DPS 20-28).
    # Leave empty to let tinytuya detect automatically.
    bulb_type: str = ""


@dataclass
class CaptureConfig:
    # How often to sample the screen (milliseconds).
    interval_ms: int = 100
    # Downsample captured image to this size before color analysis.
    sample_size: int = 64
    # Minimum saturation (0-1) for a pixel to be considered "colorful".
    min_saturation: float = 0.15


@dataclass
class ColorConfig:
    # Exponential-moving-average factor per frame (0 = frozen, 1 = instant).
    smoothing_alpha: float = 0.18
    # Multiply saturation of the output color by this factor.
    saturation_boost: float = 1.4
    # Clamp saturation boost ceiling.
    max_saturation: float = 1.0


@dataclass
class Config:
    tuya: TuyaConfig
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    color: ColorConfig = field(default_factory=ColorConfig)


def _filter_keys(raw: dict, cls: type) -> dict:
    """Return only the keys that match dataclass fields; raise on unknowns."""
    import dataclasses
    valid = {f.name for f in dataclasses.fields(cls)}
    unknown = set(raw) - valid
    if unknown:
        raise ValueError(f"Unknown keys in [{cls.__name__}]: {sorted(unknown)}")
    return {k: v for k, v in raw.items() if k in valid}


def load(path: Path) -> Config:
    with path.open("rb") as f:
        raw = tomllib.load(f)

    tuya_raw = raw.get("tuya", {})
    if not tuya_raw:
        raise ValueError("Missing [tuya] section in config")
    for key in ("device_id", "local_key", "ip"):
        if key not in tuya_raw:
            raise ValueError(f"Missing required tuya.{key} in config")

    tuya = TuyaConfig(**_filter_keys(tuya_raw, TuyaConfig))

    capture_raw = raw.get("capture", {})
    capture = CaptureConfig(**_filter_keys(capture_raw, CaptureConfig)) if capture_raw else CaptureConfig()

    color_raw = raw.get("color", {})
    color = ColorConfig(**_filter_keys(color_raw, ColorConfig)) if color_raw else ColorConfig()

    # Basic range validation
    if capture.interval_ms <= 0:
        raise ValueError("capture.interval_ms must be > 0")
    if capture.sample_size <= 0:
        raise ValueError("capture.sample_size must be > 0")
    if not (0.0 <= color.smoothing_alpha <= 1.0):
        raise ValueError("color.smoothing_alpha must be in [0.0, 1.0]")
    if tuya.min_change < 0:
        raise ValueError("tuya.min_change must be >= 0")
    if tuya.bulb_type and tuya.bulb_type not in ("A", "B", "C"):
        raise ValueError("tuya.bulb_type must be 'A', 'B', 'C', or omitted")

    return Config(tuya=tuya, capture=capture, color=color)

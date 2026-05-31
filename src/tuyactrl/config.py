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
    # Toggle HSV smoothing on/off.
    enable_smoothing: bool = False
    # Exponential-moving-average factor per frame (0 = frozen, 1 = instant).
    smoothing_alpha: float = 0.18
    # Multiply saturation of the output color by this factor.
    saturation_boost: float = 1.4
    # Clamp saturation boost ceiling.
    max_saturation: float = 1.0


@dataclass
class ContextConfig:
    # Enable context-aware auto start/stop behavior.
    enabled: bool = False
    # Poll context probes (wifi/power/monitor) every N milliseconds.
    poll_interval_ms: int = 3000
    # Require AC/USB-C external power to run ambilight.
    require_ac_power: bool = False
    # Require an external monitor (more than one connected monitor in Hyprland).
    require_external_monitor: bool = False
    # If non-empty, ambilight only runs on these SSIDs.
    allowed_ssids: list[str] = field(default_factory=list)
    # Ambilight is always disabled on these SSIDs.
    blocked_ssids: list[str] = field(default_factory=list)
    # Turn strip off when context becomes inactive.
    turn_off_when_inactive: bool = True


@dataclass
class Config:
    tuya: TuyaConfig
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    color: ColorConfig = field(default_factory=ColorConfig)
    context: ContextConfig = field(default_factory=ContextConfig)


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
    context_raw = raw.get("context", {})
    context = ContextConfig(**_filter_keys(context_raw, ContextConfig)) if context_raw else ContextConfig()

    # Basic range validation
    if capture.interval_ms <= 0:
        raise ValueError("capture.interval_ms must be > 0")
    if capture.sample_size <= 0:
        raise ValueError("capture.sample_size must be > 0")
    if not (0.0 <= color.smoothing_alpha <= 1.0):
        raise ValueError("color.smoothing_alpha must be in [0.0, 1.0]")
    if not isinstance(color.enable_smoothing, bool):
        raise ValueError("color.enable_smoothing must be true or false")
    if tuya.min_change < 0:
        raise ValueError("tuya.min_change must be >= 0")
    if tuya.bulb_type and tuya.bulb_type not in ("A", "B", "C"):
        raise ValueError("tuya.bulb_type must be 'A', 'B', 'C', or omitted")
    if context.poll_interval_ms <= 0:
        raise ValueError("context.poll_interval_ms must be > 0")
    if not isinstance(context.enabled, bool):
        raise ValueError("context.enabled must be true or false")
    if not isinstance(context.require_ac_power, bool):
        raise ValueError("context.require_ac_power must be true or false")
    if not isinstance(context.require_external_monitor, bool):
        raise ValueError("context.require_external_monitor must be true or false")
    if not isinstance(context.turn_off_when_inactive, bool):
        raise ValueError("context.turn_off_when_inactive must be true or false")
    if not all(isinstance(ssid, str) and ssid.strip() for ssid in context.allowed_ssids):
        raise ValueError("context.allowed_ssids must be a list of non-empty strings")
    if not all(isinstance(ssid, str) and ssid.strip() for ssid in context.blocked_ssids):
        raise ValueError("context.blocked_ssids must be a list of non-empty strings")

    return Config(tuya=tuya, capture=capture, color=color, context=context)

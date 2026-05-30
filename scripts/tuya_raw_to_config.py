#!/usr/bin/env python3
"""Convert tuya-raw style JSON dumps into a ready-to-run config.toml."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ID_KEYS = ("id", "devId", "gwId", "device_id")
KEY_KEYS = ("key", "local_key", "localKey")
IP_KEYS = ("ip", "ip_address", "local_ip")
VERSION_KEYS = ("version", "ver", "protocol_version")
NAME_KEYS = ("name", "device_name", "product_name")


def _first_value(data: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _iter_dicts(payload: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    stack = [payload]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            out.append(current)
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return out


def _extract_candidates(payload: Any) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for item in _iter_dicts(payload):
        device_id = _first_value(item, ID_KEYS)
        local_key = _first_value(item, KEY_KEYS)
        ip = _first_value(item, IP_KEYS)
        if not (device_id and local_key and ip):
            continue
        version = _first_value(item, VERSION_KEYS) or "3.3"
        name = _first_value(item, NAME_KEYS)
        candidates.append(
            {
                "name": name,
                "device_id": device_id,
                "local_key": local_key,
                "ip": ip,
                "version": version,
            }
        )
    return candidates


def _pick_candidate(candidates: list[dict[str, str]], selector: str) -> dict[str, str]:
    if not candidates:
        raise ValueError("No Tuya device entries with id/key/ip found in input JSON")
    if selector:
        selector_lower = selector.lower()
        for item in candidates:
            if item["device_id"] == selector:
                return item
            if item["name"] and item["name"].lower() == selector_lower:
                return item
        raise ValueError(f"No matching device found for selector: {selector}")
    return candidates[0]


def _render_config(device: dict[str, str]) -> str:
    return f"""[tuya]
device_id = "{device["device_id"]}"
local_key = "{device["local_key"]}"
ip        = "{device["ip"]}"
version   = "{device["version"]}"
bulb_type = "B"
min_change = 4

[capture]
interval_ms = 100
sample_size = 64
min_saturation = 0.15

[color]
enable_smoothing = true
smoothing_alpha = 0.18
saturation_boost = 1.4
max_saturation = 1.0
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse tuya-raw/devices JSON and generate config.toml for tuyactrl",
    )
    parser.add_argument("--input", "-i", type=Path, default=Path("tuya-raw.json"))
    parser.add_argument("--output", "-o", type=Path, default=Path("config.toml"))
    parser.add_argument(
        "--device",
        "-d",
        default="",
        help="Device selector: exact device id or exact device name (optional)",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input file not found: {args.input}")

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    candidates = _extract_candidates(payload)
    chosen = _pick_candidate(candidates, args.device.strip())

    args.output.write_text(_render_config(chosen), encoding="utf-8")

    print(f"Wrote {args.output} for device_id={chosen['device_id']} ip={chosen['ip']}")
    if len(candidates) > 1 and not args.device:
        print(
            f"Note: found {len(candidates)} matching entries; "
            f"used the first one. Pass --device to select explicitly."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""CLI entry point."""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from tuyactrl.config import load as load_config


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Silence noisy tinytuya internals unless verbose
    if not verbose:
        logging.getLogger("tinytuya").setLevel(logging.WARNING)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="tuyactrl",
        description="Hyprland ambilight for Tuya LED strips",
    )
    parser.add_argument(
        "-c", "--config",
        type=Path,
        default=Path("config.toml"),
        metavar="FILE",
        help="Path to config.toml (default: ./config.toml)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Run tinytuya's LAN device scanner and exit",
    )
    args = parser.parse_args()

    _setup_logging(args.verbose)
    log = logging.getLogger(__name__)

    if args.scan:
        import tinytuya
        print("Scanning for Tuya devices on the local network (≈18 s)…")
        devices = tinytuya.deviceScan(verbose=False, maxretry=3)
        if not devices:
            print("No devices found.")
        else:
            for dev_id, info in devices.items():
                print(f"\n  ID   : {dev_id}")
                for k, v in info.items():
                    print(f"  {k:<5}: {v}")
        sys.exit(0)

    if not args.config.exists():
        log.error("Config file not found: %s", args.config)
        log.error("Copy config.example.toml to config.toml and fill in your device details.")
        sys.exit(1)

    try:
        cfg = load_config(args.config)
    except Exception as exc:
        log.error("Failed to load config: %s", exc)
        sys.exit(1)

    from tuyactrl.main import run
    asyncio.run(run(cfg))

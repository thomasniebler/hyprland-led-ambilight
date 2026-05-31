# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Taskfile-based workflows for local install, systemd service install, and generating `config.toml` from Tuya JSON dumps.
- Automatic reconnect safeguard for Tuya send failures.
- Optional color smoothing via `color.enable_smoothing`.
- Context-aware auto activation via `[context]` config (AC power, Wi-Fi allow/deny lists, external monitor requirement).
- Runtime context policy evaluator with automatic pause/resume and optional LED shutdown while inactive.
- Runtime status file at `~/.cache/tuyactrl/status.json` for integrations.
- CLI status outputs: `--status-json` and Waybar-friendly `--waybar`.
- Added Taskfile target `start-service` to start/enable an already-installed user service.

### Changed
- Default for `color.enable_smoothing` is now `false`.
- `config.example.toml` and generated configs now include context policy settings.

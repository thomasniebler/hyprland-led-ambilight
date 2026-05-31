# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Taskfile-based workflows for local install, systemd service install, and generating `config.toml` from Tuya JSON dumps.
- Automatic reconnect safeguard for Tuya send failures.
- Optional color smoothing via `color.enable_smoothing`.

### Changed
- Default for `color.enable_smoothing` is now `false`.


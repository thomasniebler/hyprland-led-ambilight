# tuyactrl

**Hyprland ambilight for Tuya LED strips.**  
Continuously samples the colour distribution of the focused Hyprland window
and mirrors it on a local Tuya LED strip — much like Philips TV Ambilight.

---

## Requirements

| Dependency | Purpose |
|---|---|
| [uv](https://github.com/astral-sh/uv) | Python env & packaging |
| [grim](https://sr.ht/~emersion/grim/) | Wayland screen capture |
| `hyprctl` | Active window geometry (bundled with Hyprland) |
| Tuya LED strip | On the same LAN, local-control enabled |

Install `grim` via your distro package manager, e.g.:
```bash
# Arch
sudo pacman -S grim
# Ubuntu/Debian (Wayland PPA)
sudo apt install grim
```

## Cloud-Free / Local Operation

> **tuyactrl communicates directly with your LED strip over LAN using the
> Tuya local-control protocol — no traffic goes to Tuya's cloud servers
> during normal operation.**

tinytuya opens a plain TCP socket to the device's IP address and encrypts
commands with the local key.  The only time the internet is needed is the
**one-time step** of retrieving the local key from the Tuya IoT Platform
(see *Getting Tuya Device Credentials* below).  After that, the device can
be firewalled from the internet entirely.

Performance notes:
- A **persistent TCP socket** is kept open between commands (`persist=True`),
  avoiding reconnect overhead on every ~100 ms frame.
- Commands are sent **fire-and-forget** (`nowait=True`) — no blocking ACK
  wait, maximising throughput.
- Setting `bulb_type = "B"` in config skips the auto-detection status request
  on first use (recommended for modern RGB LED strips).

---

```bash
# Clone the repo (or copy the folder)
git clone <repo-url> tuyactrl
cd tuyactrl

# Install Python dependencies (creates .venv automatically)
uv sync
```

---

## Getting Tuya Device Credentials

Tuya devices require three values: **device_id**, **local_key**, and **IP
address**.  The tinytuya wizard automates credential retrieval:

### 1. Create a Tuya IoT Platform account

1. Go to <https://iot.tuya.com> and sign up / log in.
2. Click **Cloud → Development → Create Cloud Project**.  
   Choose region, name it anything, enable *Smart Home* as the data source.
3. Under **Devices → Link Tuya App Account**, scan the QR code with the
   **Tuya Smart** or **Smart Life** mobile app (the same app used to pair
   your LED strip).

### 2. Pair your LED strip

Make sure the strip is already paired in the Tuya app and visible in the
app before proceeding.

### 3. Run the wizard

```bash
uv run python -m tinytuya wizard
```

The wizard asks for your Tuya IoT Platform **Access ID** and **Access
Secret** (found on the project's API page), then downloads credentials for
all linked devices and writes them to `snapshot.json` / `devices.json`.

Copy the values for your LED strip into `config.toml`:

```toml
[tuya]
device_id = "abc123..."   # "id" field in devices.json
local_key  = "xyz..."     # "key" field
ip         = "192.168.1.x"
```

> **Tip:** If the wizard hangs on discovery, specify the IP manually in the
> wizard prompt or just read it from your router's DHCP table.

---

## Setup

```bash
# Copy the example config and fill in your credentials
cp config.example.toml config.toml
$EDITOR config.toml

# (Optional) Scan to verify the device is reachable
uv run tuyactrl --scan

# Run
uv run tuyactrl

# Run with verbose debug output
uv run tuyactrl -v

# Use a custom config path
uv run tuyactrl -c /path/to/my.toml
```

---

## Configuration

See [`config.example.toml`](config.example.toml) for all options with
inline documentation.  Key knobs:

| Setting | Default | Effect |
|---|---|---|
| `tuya.version` | `"3.3"` | Tuya protocol version (3.1, 3.3, 3.4, 3.5) |
| `tuya.bulb_type` | `""` | Pre-set bulb type (`A`/`B`/`C`) — skips auto-detection; `B` suits most RGB strips |
| `capture.interval_ms` | 100 | Poll interval — lower = faster reaction, more CPU/network |
| `capture.sample_size` | 64 | Resize dimension before colour analysis |
| `capture.min_saturation` | 0.15 | Ignore grey/white pixels (terminals, blank desktops) |
| `color.smoothing_alpha` | 0.3 | EMA factor — lower = slower cinematic fades |
| `color.saturation_boost` | 1.5 | Multiply saturation — punch up dull content |
| `color.min_change` | 4 | Skip Tuya send if Euclidean RGB change < this value |

---

## Autostart with Hyprland

Add to `~/.config/hypr/hyprland.conf`:

```conf
exec-once = /path/to/tuyactrl/.venv/bin/tuyactrl -c /path/to/tuyactrl/config.toml
```

Or, if you installed via `uv tool install`:

```conf
exec-once = tuyactrl -c ~/.config/tuyactrl/config.toml
```

---

## Running as a systemd User Service

Create `~/.config/systemd/user/tuyactrl.service`:

```ini
[Unit]
Description=Tuya ambilight (Hyprland)
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=/path/to/tuyactrl/.venv/bin/tuyactrl -c /path/to/tuyactrl/config.toml
Restart=on-failure
RestartSec=5s
# Hyprland socket path — needed for hyprctl
Environment=HYPRLAND_INSTANCE_SIGNATURE=%i

[Install]
WantedBy=graphical-session.target
```

Enable and start:

```bash
systemctl --user daemon-reload
systemctl --user enable --now tuyactrl
journalctl --user -u tuyactrl -f   # follow logs
```

> **Note:** `HYPRLAND_INSTANCE_SIGNATURE` is set automatically in your
> Hyprland session.  If the service starts before Hyprland is fully up,
> add `ExecStartPre=/bin/sleep 3`.

---

## How It Works

```
┌─────────────────────────────────────────────────────┐
│  asyncio loop  (~100 ms tick)                       │
│                                                      │
│  hyprctl -j activewindow                             │
│       ↓  (x, y, w, h)                               │
│  grim -g "x,y WxH" -   →  PNG bytes (stdout)        │
│       ↓                                              │
│  Resize to sample_size×sample_size                   │
│  Vectorised HSV analysis (numpy)                     │
│  Saturation-weighted average → dominant RGB          │
│       ↓                                              │
│  ColorSmoother  (EMA in HSV space, shortest hue arc) │
│       ↓  smooth RGB                                  │
│  tinytuya BulbDevice.set_colour(r, g, b)             │
│  (thread executor — skipped if Δ < min_change)       │
└─────────────────────────────────────────────────────┘
```

Smoothing is done in HSV space to avoid grey midpoints when interpolating
between two vivid hues (e.g. red → blue).

---

## Running Tests

```bash
uv run pytest -v
```

36 tests across config loading, colour extraction, HSV smoothing, and
window geometry / capture mocking.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "No devices found" on `--scan` | Device must be on same LAN; open UDP 6666/6667 in firewall |
| Device refuses commands | Try `version = "3.1"` or `"3.4"` in `[tuya]` section |
| Wrong device responds | Double-check `ip` and `device_id` in config |
| Flickers | Raise `min_change` (e.g. 8–12), lower `smoothing_alpha` |
| Always grey/white output | Lower `min_saturation` or raise `saturation_boost` |
| High CPU usage | Raise `interval_ms` (e.g. 200) or lower `sample_size` (e.g. 32) |
| `grim` not found | Install grim; ensure it is in PATH |
| `hyprctl` not found | Only works inside a running Hyprland session |
| Subprocess timeout | Raise `capture.timeout_s` in config (default 2 s) |

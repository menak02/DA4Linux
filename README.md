# DA4Linux

Dolby Audio-like processing for Linux via PipeWire filter-chain.

DA4Linux parses Dolby DAX3 XML tuning files (from Windows DriverStore) and
generates a PipeWire filter-chain configuration that applies speaker
correction FIR, parametric EQ, multiband compression, stereo enhancement,
bass enhancement, dialogue enhancement, loudness compensation, virtual
surround, and a brickwall limiter to your laptop's built-in speakers.

Currently supports **Lenovo ThinkPad T14s Gen 2 Intel** (Realtek ALC3287
and ALC257). The profile system is extensible — add your own device.

DA4Linux is a **config generator, not a daemon**. It runs once, writes a
PipeWire `.conf` file, and exits. The DSP runs inside PipeWire itself.
This means no persistent background process to manage and no init system
coupling.

## Installation

### pip (recommended)

```bash
pip install da4linux
```

### Makefile (any Linux)

```bash
git clone https://github.com/da4linux/da4linux
cd da4linux
sudo make install
```

Custom prefix:

```bash
sudo make install PREFIX=/usr
```

Staging install for packaging:

```bash
make install DESTDIR=/tmp/staging PREFIX=/usr
```

### Debian/Devuan .deb

```bash
sudo apt install ./da4linux_0.1.0-1_all.deb
```

### From source (editable)

```bash
git clone https://github.com/da4linux/da4linux
cd da4linux
pip install -e .
```

## Auto-Start on Login

DA4Linux installs an XDG autostart entry that runs `da4linux generate`
when you log in. This works on ALL desktop environments regardless of
init system (runit, openrc, s6, systemd, etc.).

If you use a window manager without XDG autostart support (i3, dwm, etc.),
add this to your `~/.xinitrc` or `~/.profile`:

```bash
da4linux generate
```

## Requirements

- PipeWire >= 1.0
- LSP Plugins (LV2) — for limiter, multiband compressor, loudness compensation
- CALF Plugins (LV2) — for bass enhancer and stereo tools
- Python >= 3.9 (stdlib only — no pip dependencies)
- numpy (optional — needed for impulse response generation from DAX3 data)
- libmysofa-utils (optional — needed for virtual surround with HRTF SOFA files)

On Debian/Devuan:

```bash
sudo apt install pipewire wireplumber lsp-plugins-lv2 calf-plugins
```

## Quick Start

```bash
# Detect your audio hardware
da4linux detect

# Parse a DAX3 XML tuning file (from Windows DriverStore)
da4linux parse /path/to/dax3_ext_speaker.xml

# Generate PipeWire filter-chain config and install it
da4linux generate --xml /path/to/dax3_ext_speaker.xml

# Or use a built-in profile (no DAX3 XML needed)
da4linux generate

# Restart PipeWire to load the new config
# The command depends on your init system:
#   runit:     sv restart pipewire         (or killall -HUP pipewire)
#   systemd:   systemctl --user restart pipewire
#   openrc:    rc-service pipewire restart
#   generic:   killall pipewire && pipewire &
```

## Finding DAX3 XML Files

If you dual-boot Windows, the DAX3 XML tuning files live in:

```
C:\Windows\System32\DriverStore\FileRepository\*dax3*\dax3_ext_*.xml
```

Or look in your EFI partition under `Drivers/` on some OEM installs.

Mount your Windows partition and copy the files to a Linux-accessible
location. You only need to do this once.

## How It Works

1. **Hardware detection** — reads DMI and ALSA sysfs to identify your laptop
   model and audio codec
2. **DAX3 XML parsing** — extracts speaker PEQ filters, audio optimizer
   bands, and multiband compressor settings from Dolby's tuning data
3. **Config generation** — produces a PipeWire `filter-chain` SPA-JSON config
   with a virtual sink that processes audio through:
   - Speaker correction convolver (FIR)
   - Parametric EQ (IIR biquad chain)
   - Multiband compressor (LSP LV2, 4-band)
   - Stereo enhancement (CALF StereoTools or M/S matrix)
   - Bass enhancement (CALF BassEnhancer or low-shelf biquad)
   - Dialogue enhancement (M/S center extraction + voice EQ)
   - Loudness compensation (LSP LV2 or ebur128 gain riding)
   - Virtual surround (PipeWire spatializer with SOFA HRTF)
   - Output gain stage
   - Brickwall limiter (LSP LV2, LADSPA, ZaMaximX2, or built-in clamp)

## Built-in Profiles

When no DAX3 XML is available, DA4Linux falls back to safe built-in profiles:

| Profile Key | Device |
|-------------|--------|
| `LENOVO_T14SG2_ALC3287` | ThinkPad T14s Gen 2 (Intel) |
| `LENOVO_20WNS73J00_RealtekALC257` | ThinkPad T14s Gen 2i (ALC257) |
| `GENERIC_LAPTOP` | Any unknown laptop (safe defaults) |

## Configuration Files

Generated configs are written to:

```
~/.config/pipewire/pipewire.conf.d/50-da4linux.conf
```

Impulse response files (when generated from DAX3 data):

```
~/.local/share/da4linux/ir/
```

HRTF files for virtual surround:

```
~/.local/share/da4linux/hrir/
```

## Restarting PipeWire

The command depends on your init system:

| Init System | Command |
|-------------|---------|
| runit       | `sv restart pipewire` or `killall -HUP pipewire` |
| systemd     | `systemctl --user restart pipewire` |
| openrc      | `rc-service pipewire restart` |
| s6          | `s6-svc -r /run/service/pipewire` |
| generic     | `killall pipewire && pipewire &` |

## License

GNU General Public License v3. See [LICENSE](LICENSE).

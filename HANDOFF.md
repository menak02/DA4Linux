# DA4Linux — Developer Handoff Document

> **Last Updated:** 2026-08-09  
> **Current Version:** 0.1.0  
> **Status:** Working. GUI compiles and installs. Python sidecar crash fixed (see Known Issues → Resolved).

---

## 1. Project Overview

DA4Linux applies Dolby Audio-like DSP (Dolby DAX3 tuning data) to Linux laptop speakers through PipeWire's filter-chain plugin. It is **not a daemon** — it runs once, generates a `pipewire.conf.d/` file, and exits. The DSP runs entirely inside PipeWire itself, with no background process to manage.

**What it provides:**
- Speaker correction FIR convolver (from real DAX3 XML)
- Parametric EQ (IIR biquad chain)
- Multiband compressor (LSP LV2, 4-band)
- Stereo enhancement (CALF StereoTools / M/S matrix)
- Bass enhancement (CALF BassEnhancer / low-shelf biquad)
- Dialogue enhancement (M/S center extraction + voice EQ)
- Loudness maximizer — currently tuned to +13 dB / +14 dB pre-gain
- Virtual surround (PipeWire spatializer, optional)
- Brickwall limiter (LSP LV2) as the final output stage

**Supported hardware:** ThinkPad T14s Gen 2 (ALC3287 and ALC257). Extensible profile system for other devices.

---

## 2. Architecture

```
DA4Linux
├── Python CLI Engine (src/da4linux/)       ← pure Python, stdlib only
│   ├── cli.py                              ← argparse CLI, all subcommands
│   ├── generator.py                        ← core DSP config generator
│   ├── detect.py                           ← DMI/ALSA hardware detection
│   ├── parser.py                           ← DAX3 XML tuning file parser
│   ├── plugin_db.py                        ← LV2/LADSPA plugin discovery
│   ├── constants.py                        ← DSP constants and defaults
│   ├── ir_generator.py                     ← FIR impulse response generator
│   └── profiles/                           ← built-in hardware profiles
│       └── __init__.py                     ← LENOVO_T14SG2_ALC3287, ALC257, GENERIC
│
├── Tauri GUI (ui/)                         ← React + Vite + Tailwind CSS v4
│   ├── src/                                ← React frontend
│   │   ├── App.tsx                         ← main application shell
│   │   └── components/
│   │       ├── BentoTile.tsx              ← bento-box card component
│   │       └── AICommandPalette.tsx       ← Ctrl+K command palette
│   └── src-tauri/                          ← Rust/Tauri wrapper
│       ├── src/main.rs + lib.rs           ← Tauri app entry
│       ├── tauri.conf.json                ← app config, sidecar registration
│       ├── capabilities/default.json      ← shell plugin permissions
│       ├── bin/                           ← compiled Python sidecar lives here
│       │   ├── da4linux-cli-x86_64-unknown-linux-gnu   ← for deb/appimage
│       │   └── da4linux-x86_64-unknown-linux-gnu       ← GUI placeholder
│       └── icons/                         ← app icons (all sizes, generated)
│
├── build_sidecar.sh                        ← compiles cli.py → da4linux-cli binary
├── sidecar_entry.py                        ← PyInstaller entry (CRITICAL, see §5)
└── .github/workflows/build.yml            ← CI/CD: builds deb + AppImage
```

### Communication Model

```
[User] → [da4linux GUI (Tauri/WebKit)] ──Sidecar IPC──▶ [da4linux-cli (PyInstaller binary)]
                                                                  │
                                                                  ▼
                                              ~/.config/pipewire/pipewire.conf.d/50-da4linux.conf
                                                                  │
                                                                  ▼
                                                     [PipeWire filter-chain DSP]
```

The GUI invokes the sidecar using `@tauri-apps/plugin-shell`:
```typescript
const command = Command.sidecar("bin/da4linux-cli", args);
const output = await command.execute();
```

---

## 3. Build & Toolchain

### Prerequisites

| Tool | Purpose | Version |
|------|---------|---------|
| Python ≥ 3.9 | CLI engine | any |
| PyInstaller (via pipx) | Bundle Python to binary | 6.x |
| Rust + Cargo | Compile Tauri app | stable |
| Node.js + npm | React frontend | 20+ |
| `libwebkit2gtk-4.1-dev` | Tauri WebKit runtime | (apt) |
| `libgtk-3-dev` | GTK3 window system | (apt) |
| `libayatana-appindicator3-dev` | System tray support | (apt) |

### Full Build From Source

```bash
# 1. Install apt deps
sudo apt install libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev build-essential -y

# 2. Install PyInstaller (user-level, via pipx)
pipx install pyinstaller     # or: pip install pyinstaller

# 3. Compile Python sidecar → ui/src-tauri/bin/da4linux-cli-<triple>
./build_sidecar.sh

# 4. Build the Tauri app (produces .deb, .rpm, .AppImage)
cd ui && npm install && npm run tauri build
```

Artifacts land at:
- `.deb` → `ui/src-tauri/target/release/bundle/deb/da4linux_0.1.0_amd64.deb`
- `.AppImage` → `ui/src-tauri/target/release/bundle/appimage/da4linux_0.1.0_amd64.AppImage`
- `.rpm` → `ui/src-tauri/target/release/bundle/rpm/`

### Development Mode (hot-reload)

```bash
# Terminal 1 – keep Python sidecar up to date whenever you change cli.py
./build_sidecar.sh

# Terminal 2 – Tauri dev server with React hot-reload
cd ui && npm run tauri dev
```

---

## 4. Installation Methods

### A. Debian Package
```bash
sudo dpkg -i da4linux_0.1.0_amd64.deb
```
Installs:
- `/usr/bin/da4linux` — the Tauri GUI (opens a window)
- `/usr/bin/da4linux-cli` — the standalone Python CLI engine

### B. AppImage (no root needed)
```bash
chmod +x da4linux_0.1.0_amd64.AppImage
./da4linux_0.1.0_amd64.AppImage
```

### C. CLI only (Python install)
```bash
pip install .
# or: pip install -e .   (editable, for development)
da4linux-cli generate
```

---

## 5. Critical Known Issues & Resolutions

### ✅ RESOLVED — PyInstaller Sidecar Crash (Relative Import Error)

**Symptom:** The GUI opens, hangs a few seconds, then closes/crashes silently.  
**Root cause:** `build_sidecar.sh` was pointing PyInstaller directly at `cli.py`. Because `cli.py` uses `from . import __version__` (a relative import), PyInstaller couldn't resolve the package context at runtime, producing:
```
ImportError: attempted relative import with no known parent package
[PYI-4734:ERROR] Failed to execute script 'cli' due to unhandled exception!
```

**Fix (commit `a66f64e`):**
- Created `sidecar_entry.py` — a top-level script that uses **absolute imports** (`from da4linux.cli import main`) and sets up `sys._MEIPASS` path handling.
- Updated `build_sidecar.sh` to use `sidecar_entry.py` as the PyInstaller entrypoint with `--collect-all da4linux --paths src`.

> ⚠️ **IMPORTANT:** If you ever need to rebuild the sidecar, always run `./build_sidecar.sh`. Do **not** point PyInstaller directly at `cli.py` or any file with relative imports.

---

### ✅ RESOLVED — Debian Package Name Collision

**Symptom:** `dpkg -i tauri-app_0.1.0_amd64.deb` failed with:
```
trying to overwrite '/usr/bin/da4linux', which is also in package da4linux (0.1.0-1)
```

**Fix (commit `4a85154`):**  
Renamed the Tauri app's Cargo crate from `tauri-app` to `da4linux`, so the new `.deb` package upgrades the old one cleanly rather than conflicting with it. The Python sidecar was simultaneously renamed from `da4linux` to `da4linux-cli` to keep the two binaries distinct.

---

### ⚠️ OPEN — GUI Shows Static Data

The current UI (`ui/src/App.tsx`) displays **hardcoded values** (e.g., `+13.0 dB`, `LENOVO_20WNS73J00` profile badge). The sidecar integration is wired up correctly for actions (Regenerate DSP, Restart PipeWire, Check Status) — those call the real binary and show `alert()` output. However, status tiles don't yet dynamically query the sidecar on load.

**Next step:** On `App` mount, call `da4linux-cli status` and `da4linux-cli detect`, parse the stdout, and populate state into React. Use the existing `runCommand()` helper pattern.

---

### ⚠️ OPEN — GTK Module Warning (non-fatal)

When running `da4linux` from terminal, you may see:
```
Gtk-Message: Failed to load module "appmenu-gtk-module": undefined symbol: gtk_module_display_init
```
This is a cosmetic warning from Devuan's GTK3 module. The app runs fine regardless. It's caused by a broken `libwindow-decorations-gtk-module.so` and is not a DA4Linux bug.

---

## 6. DSP Configuration (Loudness Tuning)

The loudness maximizer was tuned in two passes. Key values in [`src/da4linux/profiles/__init__.py`](src/da4linux/profiles/__init__.py):

| Profile | `volmax_boost` | Effective Gain |
|---------|---------------|----------------|
| `LENOVO_T14SG2_ALC3287` | `208.0` | +13 dB |
| `LENOVO_20WNS73J00_RealtekALC257` | `224.0` | +14 dB |

In [`src/da4linux/generator.py`](src/da4linux/generator.py), the headroom threshold was raised from `14.0` → `24.0` (line ~654) to prevent the limiter from squashing the pre-gain boost.

The final limiter stage (LSP LV2 `limiter_stereo`) catches any peaks above 0 dBFS, so distortion/clipping is not a concern even at these boost levels.

---

## 7. CI/CD

**GitHub Actions workflow:** [`.github/workflows/build.yml`](.github/workflows/build.yml)

Triggers on every push/PR to `master`. Steps:
1. Checkout + setup Node 20, Rust stable, Python 3.11
2. Install apt and pip dependencies
3. Run `./build_sidecar.sh` to compile the Python sidecar
4. `npm install && npm run tauri build` in `ui/`
5. Upload `.deb` and `.AppImage` as GitHub Actions artifacts

> **Note:** The CI workflow uploads build artifacts but does not yet create GitHub Releases automatically. To publish a release, manually draft one on GitHub and attach the artifacts, or add a `release` job triggered on `v*` tags.

---

## 8. File Map Quick Reference

| File | Purpose |
|------|---------|
| `src/da4linux/cli.py` | All CLI subcommands (`generate`, `detect`, `status`, etc.) |
| `src/da4linux/generator.py` | PipeWire SPA-JSON config generation logic |
| `src/da4linux/profiles/__init__.py` | Built-in hardware profiles + DSP tuning values |
| `src/da4linux/detect.py` | DMI + ALSA hardware detection |
| `sidecar_entry.py` | **PyInstaller entry point** — do not remove |
| `build_sidecar.sh` | Compiles `da4linux-cli` binary for Tauri bundling |
| `ui/src/App.tsx` | Main React UI shell |
| `ui/src/components/BentoTile.tsx` | Card component (Bento Box layout) |
| `ui/src/components/AICommandPalette.tsx` | Ctrl+K command palette |
| `ui/src-tauri/tauri.conf.json` | Tauri app config (window, sidecar, icons) |
| `ui/src-tauri/capabilities/default.json` | Shell plugin permissions for sidecar |
| `ui/src-tauri/bin/` | Compiled sidecar binaries live here |
| `.github/workflows/build.yml` | CI/CD pipeline |
| `app_icon.jpg` | Source icon (generated, used by `tauri icon`) |

---

## 9. Roadmap / Suggested Next Steps

1. **Dynamic UI data** — Query `da4linux-cli status` and `detect` on app launch; parse and display live hardware/config info in the Bento tiles instead of hardcoded strings.
2. **Real-time DSP controls** — Add sliders for bass enhancement level, stereo width, loudness gain. Pass values as `--flag` args to the sidecar.
3. **Headphone mode toggle** — The CLI already supports `--headphone` flag. Wire a toggle in the UI.
4. **GitHub Releases automation** — Add a release workflow triggered by `v*` tags that publishes the `.deb` and `.AppImage` as release assets.
5. **Multi-device profile selector** — UI dropdown to select from `da4linux-cli profiles` output.
6. **Autostart toggle** — Show/hide the XDG autostart entry from within the GUI.
7. **EasyEffects conflict detection** — Surface the EasyEffects warning in the UI (currently only printed to CLI stdout).
8. **Additional hardware profiles** — Community-contributed profiles for other ThinkPad/Lenovo/Dell models.

---

## 10. Repository

- **GitHub:** https://github.com/menak02/DA4Linux
- **License:** GNU GPL v3
- **Latest commit:** `a66f64e` — fix: resolve PyInstaller relative import crash in da4linux-cli sidecar

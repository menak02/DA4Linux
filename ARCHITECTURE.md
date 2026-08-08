# DA4Linux — Architecture Document

**Project:** DA4Linux — Dolby Audio Processing for Linux via PipeWire filter-chain
**License:** GNU GPL v3
**Date:** 2026-08-06
**Status:** Design phase — Phase 1 implemented, Phase 2+3 designed

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Processing Pipeline Design](#2-processing-pipeline-design)
3. [Configuration & Tuning](#3-configuration--tuning)
4. [Implementation Plan](#4-implementation-plan)
5. [Deployment Architecture](#5-deployment-architecture)
6. [Gaps vs Real Dolby Atmos](#6-gaps-vs-real-dolby-atmos)
7. [Phase 2+3 Architecture: Dynamics, Enhancement & Spatial](#7-phase-23-architecture-dynamics-enhancement--spatial)
   - 7.1 [Updated Processing Chain](#71-updated-processing-chain)
   - 7.2 [Stage 4: Multiband Compressor](#72-stage-4-multiband-compressor--full-specification)
   - 7.3 [Stage 5: Stereo Enhancement](#73-stage-5-stereo-enhancement--ms-width-control)
   - 7.4 [Stage 6: Bass Enhancer (C SPA Plugin)](#74-stage-6-bass-enhancer--custom-c-spa-plugin)
   - 7.5 [Stage 7: Loudness Compensation](#75-stage-7-loudness-compensation--ebu-r128--iso-226)
   - 7.6 [Stage 8: Dialogue Enhancement](#76-stage-8-dialogue-enhancement--center-channel-extraction)
   - 7.7 [Stage 9: Virtual Surround](#77-stage-9-virtual-surround--sofa-hrtf-spatialization)
   - 7.8 [Stage Bypass Strategy](#78-stage-bypass-strategy)
   - 7.9 [Profile Format Extensions](#79-profile-format--phase-23-extensions)
   - 7.10 [Implementation Plan (Tasks)](#710-implementation-plan--phase-23-tasks)
   - 7.11 [Risks & Mitigations](#711-risks--mitigations)
   - 7.12 [Open Questions](#712-open-questions-for-stakeholders)
   - 7.13 [Appendix D: LSP Limiter Port Symbols](#713-appendix-d-lsp-limiter-stereo-port-symbols-verified)
   - 7.14 [Appendix E: CALF Bass Enhancer Ports](#714-appendix-e-calf-bass-enhancer-lv2-port-symbols-reference)
   - 7.15 [Appendix F: ISO 226 Curve Data](#715-appendix-f-iso-226-reference-curve-data)

---

## 1. Architecture Overview

### 1.1 High-Level Layered Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                     USER-SPACE APPLICATIONS                   │
│  (Firefox, VLC, Spotify, games, DAWs, system sounds, etc.)   │
└───────────────────────────┬──────────────────────────────────┘
                            │ audio streams
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                     PIPEWIRE SERVER (daemon)                  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              libpipewire-module-filter-chain           │   │
│  │                                                       │   │
│  │   Virtual Sink ──► [DSP Processing Graph] ──► Output  │   │
│  │   (capture stream)        │              (playback)    │   │
│  │                           │                            │   │
│  │   ┌───────┐  ┌──────┐  ┌──┴───┐  ┌───────┐  ┌─────┐ │   │
│  │   │ Gain  │→ │ PEQ  │→ │ Dyn  │→ │Stereo│→ │Bass │ │   │
│  │   │ Stage │  │ (IIR)│  │(MB)  │  │Widen │  │Enh. │ │   │
│  │   └───────┘  └──────┘  └──┬───┘  └───────┘  └──┬──┘ │   │
│  │                           │                     │     │   │
│  │   ┌───────┐  ┌──────┐  ┌──┴───┐  ┌───────┐  ┌─┴───┐ │   │
│  │   │Limit. │← │Dial. │← │Loudn │← │Virtual│← │     │ │   │
│  │   │(brick)│  │Enh.  │  │Comp. │  │Surr.  │  │     │ │   │
│  │   └───┬───┘  └──────┘  └──────┘  └───┬───┘  └─────┘ │   │
│  │       │                               │              │   │
│  └───────┼───────────────────────────────┼──────────────┘   │
│          │                               │                   │
└──────────┼───────────────────────────────┼───────────────────┘
           │                               │
           ▼                               ▼
┌──────────────────────────────────────────────────────────────┐
│                    ALSA / KERNEL LAYER                        │
│  ┌─────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │ HDA Intel       │  │ Bluetooth      │  │ USB Audio    │  │
│  │ (snd_hda_intel) │  │ (bluez5)       │  │              │  │
│  └────────┬────────┘  └───────┬────────┘  └──────┬───────┘  │
│           │                   │                    │          │
│           ▼                   ▼                    ▼          │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              PHYSICAL HARDWARE                          │  │
│  │   Realtek ALC3287 speakers / Headphone jack / BT       │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 Module Breakdown

| Module | Language | Responsibility | Dependencies |
|--------|----------|----------------|--------------|
| **`da4linux.cli`** | Python 3.9+ | CLI entry point; DMI auto-detection; status reporting; multi-init restart management | Python stdlib (`argparse`, `shutil`, `subprocess`) |
| **`da4linux.parser`** | Python 3.9+ | DAX3 XML parser; namespace-insensitive ElementTree processing; tuning data model | Python stdlib (`xml.etree.ElementTree`, `dataclasses`) |
| **`da4linux.generator`** | Python 3.9+ | Dynamic LV2/LADSPA path search; 9-stage SPA-JSON filter graph generator; headroom pre-gain calculation | Python stdlib (`pathlib`, `math`) |
| **`da4linux.profiles`** | Python 3.9+ | Built-in hardware profiles & custom user JSON profile loader (`~/.config/da4linux/profiles/`) | Python stdlib (`json`, `pathlib`) |
| **`da4linux-service`** | Agnostic | systemd user units, runit services, OpenRC, Dinit, s6, and XDG autostart integration | XDG Autostart / Active Session Supervisor |

### 1.3 Data Flow

```
Application audio
       │
       ▼
┌─────────────────────┐
│ PipeWire decides     │  WirePlumber policy routes apps to DA4Linux virtual sink
│ routing              │  when speakers are active, bypasses for headphones/BT
└────────┬────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│              PIPEWIRE FILTER-CHAIN GRAPH                     │
│                                                             │
│  capture.stream ──► [In L] ────┐                            │
│  (stereo f32le,     [In R] ────┤                            │
│   48 kHz)                       │                            │
│                                 ▼                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Stage 1: input_gain      (builtin:linear)            │   │
│  │   Pre-gain: -6.0 dB (headroom for EQ boosts)         │   │
│  │   Out L, Out R                                        │   │
│  └──────────────────────────┬───────────────────────────┘   │
│                             │                                │
│  ┌──────────────────────────▼───────────────────────────┐   │
│  │ Stage 2: speaker_eq      (builtin:convolver)         │   │
│  │   FIR impulse response from DAX3 speaker correction   │   │
│  │   File: ~/.config/da4linux/irs/thinkpad-t14sg2.irs   │   │
│  └──────────────────────────┬───────────────────────────┘   │
│                             │                                │
│  ┌──────────────────────────▼───────────────────────────┐   │
│  │ Stage 3: param_eq        (builtin:param_eq)          │   │
│  │   Filters array from DAX3 Intelligent EQ bands       │   │
│  │   Per-channel: L and R have independent filters       │   │
│  └──────────────────────────┬───────────────────────────┘   │
│                             │                                │
│  ┌──────────────────────────▼───────────────────────────┐   │
│  │ Stage 4: multiband_dyn   (lv2:lsp-mb-compressor)     │   │
│  │   LSP Multiband Compressor x8 Stereo                  │   │
│  │   URI: http://lsp-plug.in/plugins/lv2/mb_compressor_stereo │
│  │   4 bands: <120, 120-500, 500-3k, >3k Hz              │   │
│  │   Modern mode, soft knee, no lookahead (latency)      │   │
│  └──────────────────────────┬───────────────────────────┘   │
│                             │                                │
│  ┌──────────────────────────▼───────────────────────────┐   │
│  │ Stage 5: stereo_enhance  (lv2:lsp-*) OR custom C     │   │
│  │   Option A: LSP cross/balance + M/S matrix            │   │
│  │   Option B: custom M/S width control (C code)         │   │
│  └──────────────────────────┬───────────────────────────┘   │
│                             │                                │
│  ┌──────────────────────────▼───────────────────────────┐   │
│  │ Stage 6: bass_enhance   (custom C builtin plugin)     │   │
│  │   MaxxBass-style psychoacoustic bass:                 │   │
│  │   - Low-pass filter below 120 Hz                       │   │
│  │   - Waveshaping to generate harmonics                  │   │
│  │   - Band-pass 120-300 Hz harmonic signal               │   │
│  │   - Mix with dry signal at controllable ratio          │   │
│  └──────────────────────────┬───────────────────────────┘   │
│                             │                                │
│  ┌──────────────────────────▼───────────────────────────┐   │
│  │ Stage 7: loudness_comp  (ebur128 + builtin:linear)    │   │
│  │   EBU R128 loudness meter → lufs2gain → linear gain   │   │
│  │   Target: -14 LUFS integrated                          │   │
│  │   OR: ISO 226 equal-loudness dynamic EQ (custom C)    │   │
│  └──────────────────────────┬───────────────────────────┘   │
│                             │                                │
│  ┌──────────────────────────▼───────────────────────────┐   │
│  │ Stage 8: dialogue_enh   (builtin:bq_peaking)          │   │
│  │   M/S decode → bandpass 300-6000 Hz boost → M/S encode│   │
│  │   +3 to +6 dB center channel emphasis                  │   │
│  └──────────────────────────┬───────────────────────────┘   │
│                             │                                │
│  ┌──────────────────────────▼───────────────────────────┐   │
│  │ Stage 9: virtual_surround (optional, user toggle)     │   │
│  │   Option A: builtin:sofa/spatializer (SOFA HRTF)     │   │
│  │   Option B: builtin:convolver (pre-baked IR)          │   │
│  └──────────────────────────┬───────────────────────────┘   │
│                             │                                │
│  ┌──────────────────────────▼───────────────────────────┐   │
│  │ Stage 10: output_limiter  (lv2:lsp-limiter)           │   │
│  │   LSP Limiter Stereo                                   │   │
│  │   URI: http://lsp-plug.in/plugins/lv2/limiter_stereo  │   │
│  │   Threshold: -1.0 dBFS, 4× oversampling               │   │
│  │   Herm Thin mode, lookahead 2.5 ms                     │   │
│  └──────────────────────────┬───────────────────────────┘   │
│                             │                                │
│  [Out L] ────────┘          │          └──────── [Out R]     │
│                             ▼                                │
│  playback.stream ──► ALSA device (speakers)                  │
│  (stereo f32le, 48 kHz)                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Processing Pipeline Design

### 2.1 Stage-by-Stage Technology Selection

| # | Stage | Technology | Why Not LV2 | Why Not Builtin | Status |
|---|-------|------------|-------------|-----------------|--------|
| 1 | Input Gain | **builtin:linear** | Overkill for a simple multiply | — | Available |
| 2 | Speaker Correction (FIR) | **builtin:convolver** | LV2 convolvers add unnecessary latency; builtin uses FFT and is pipewire-optimized | — | Available |
| 3 | Parametric EQ (IIR) | **builtin:param_eq** | LV2 EQ has GUI-oriented overhead; builtin is zero-copy biquad chain | — | Available |
| 4 | Multiband Dynamics | **LV2: LSP MB Compressor** | Builtin has no multiband compressor; LSP is the most mature open-source MB comp with per-band SC, modern mode, stereo split | builtin has no dynamics processor | Available (LSP 1.2.x) |
| 5 | Stereo Enhancer | **builtin (biquad + mixer) OR custom C** | LV2 stereo wideners are designed for music production, add latency | M/S processing with builtin biquads + mixer works but is unwieldy; custom C is cleaner | Builtin: available now; Custom C: Phase 2 |
| 6 | Bass Enhancement | **custom C (libspa plugin)** | No LV2 plugin implements psychoacoustic bass enhancement (MaxxBass is patented but patent EXPIRED 2020) | builtin has no waveshaper | Phase 2 custom C |
| 7 | Loudness Compensation | **ebur128 + builtin:linear** for simple; **custom C** for ISO 226 | — | ebur128 is available; ISO 226 dynamic EQ needs custom C | ebur128: available; Dynamic: Phase 3 |
| 8 | Dialogue Enhancement | **builtin biquads (M/S decode → EQ → encode)** | — | M/S matrix is trivial with builtin copy/mixer + biquads | Available |
| 9 | Virtual Surround | **builtin:sofa/spatializer** or **builtin:convolver** | LV2 spatializers exist (LSP Room Builder) but heavier; builtin sofa is pipewire-native | — | Available (needs SOFA file) |
| 10 | Speaker Protection Limiter | **LV2: LSP Limiter** | Builtin clamp is too crude; LSP Limiter has lookahead, oversampling, true-peak detection | builtin clamp has no lookahead/oversampling | Available (LSP 1.2.x) |

### 2.2 Detailed Stage Specifications

#### Stage 1: Input Gain

```
Type: builtin:linear
Purpose: Provide headroom for subsequent EQ boosts; user-accessible preamp
Controls:
  Mult: 1.0 (passthrough by default, configurable via capture.volumes)
Ports: In L, In R → Out L, Out R
Stream mapping: capture.volumes maps to hardware volume keys
```

#### Stage 2: Speaker Correction (FIR Convolution)

```
Type: builtin:convolver
Purpose: Apply Lenovo/Dolby's measured speaker impulse response correction
Config:
  filename: ~/.config/da4linux/irs/{model_id}_speaker_correction.irs
  blocksize: 128 (for 48 kHz, this gives ~2.7 ms block)
  gain: 0.0 (unity, attenuation is baked into IR)
  channel: 0 (stereo IR file, channels 0+1)
Note: IR is minimum-phase to minimize latency. Extracted from DAX3 
      <audio_optimizer> filter banks as FIR coefficients.
Ports: In → Out (mono-per-channel; instantiated twice for L+R)
```

#### Stage 3: Parametric EQ

```
Type: builtin:param_eq
Purpose: Dolby "Intelligent EQ" — per-mode tonal shaping
Config (in filters array):
  filters = [
    { type = bq_peaking,  freq = 100, gain = 2.0, q = 0.7 },
    { type = bq_highshelf, freq = 8000, gain = -1.5, q = 0.7 },
    ...  # up to 32 bands, read from DAX3 XML <ieq_bands>
  ]
Ports: In 1, In 2 → Out 1, Out 2 (L and R independent)
Channel-specific: filters1 (L) and filters2 (R) are separate arrays
```

#### Stage 4: Multiband Dynamics

```
Type: LV2
Plugin URI: http://lsp-plug.in/plugins/lv2/mb_compressor_stereo
Purpose: Dolby "Volume Leveler" + multiband DRC
Configuration per band:
  Band 1 (sub-bass):  freq_start = 20,  freq_end = 120
    ratio = 2.0, attack = 20ms, release = 80ms, makeup = +3dB
  Band 2 (bass):      freq_start = 120, freq_end = 500
    ratio = 1.5, attack = 15ms, release = 60ms
  Band 3 (mid):        freq_start = 500, freq_end = 3000
    ratio = 1.2, attack = 10ms, release = 40ms
  Band 4 (treble):     freq_start = 3000, freq_end = 20000
    ratio = 1.5, attack = 5ms,  release = 30ms
Mode: Classic (IIR crossover, allpass phase-compensated)
Stereo Split: OFF (linked stereo)
Lookahead: 0 (to keep latency under 5 ms)
SC Boost: Pink BT (+3 dB/oct, matches typical music spectral tilt)
Note: DAX3's multiband compressor is "content-classifier driven" and 
      cannot be reproduced; these are sensible defaults for music.
```

#### Stage 5: Stereo Enhancement

```
Type: builtin (using mixer + copy + biquads for M/S processing)
Purpose: Dolby "Surround Virtualizer" width enhancement
Implementation via M/S matrix:
  
  ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌─────────┐
  │ Input L ├───►│ Mid =    ├───►│ Mid gain │───►│ L = M+S │───► Output L
  │         │    │ (L+R)/2  │    │ (1.0)    │    │         │
  │ Input R ├───►│ Side =   ├───►│ Side gain├───►│ R = M-S │───► Output R
  └─────────┘    │ (L-R)/2  │    │ (1.0-2.0)│    └─────────┘
                 └──────────┘    └──────────┘
  
  In filter-chain config, this uses:
  - Two builtin:copy nodes to tee L and R
  - Two builtin:mixer nodes for M = 0.5*(L+R) and S = 0.5*(L-R)
  - Two builtin:linear nodes for M gain and S gain
  - Two builtin:mixer nodes for L_out = M + S*gain, R_out = M - S*gain
  - S gain controlled by user preference (1.0 = passthrough, 2.0 = wide)

User control: "Stereo Width" slider (0.0 to 2.0, default 1.0)
```

#### Stage 6: Bass Enhancement (Psychoacoustic)

```
Type: custom C (libspa plugin)
Purpose: Generate harmonics of missing low frequencies so small speakers 
         sound fuller (MaxxBass principle, patent expired 2020)
Implementation:
  - Split signal: low-pass 120 Hz → waveshaper → band-pass 120-300 Hz → mix
  - Waveshaper: soft-clipping polynomial (x - x^3/3, normalized)
  - Dry/wet mix control (0% to 100%, default 30%)
  - Optional: second harmonic emphasis (2x frequency via full-wave rectifier)
Controls:
  - "Bass Amount" (0.0 to 1.0): dry/wet mix
  - "Crossover Freq" (60 to 200 Hz): frequency below which to generate harmonics
  - "Harmonics" (2 to 4): which harmonics to generate
Ports: In → Out (mono, instantiated per channel)
SPA plugin: da4linux/libspa-bass-enhancer.so
```

#### Stage 7: Loudness Compensation

```
Type: ebur128 + builtin:linear (Phase 1) / custom C ISO 226 (Phase 3)
Purpose: Normalize volume and compensate for Fletcher-Munson at low levels
Phase 1 (simple):
  - ebur128 node measures momentary LUFS
  - lufs2gain node converts to gain
  - builtin:linear applies gain
  - Target: -14 LUFS integrated (configurable)
Phase 3 (dynamic):
  - Custom C plugin implements ISO 226:2023 equal-loudness contours
  - At low system volume → bass and treble boost
  - At high system volume → flat response
  - Smooth interpolation between 20 phon and 80 phon curves
  - Reference: system volume reported by PipeWire metadata or ALSA mixer
```

#### Stage 8: Dialogue Enhancement

```
Type: builtin (biquad chain in M/S domain)
Purpose: Boost center-panned content (dialogue) relative to stereo content
Implementation:
  - Same M/S matrix as Stage 5, but:
  - Apply bandpass biquad (bq_peaking, freq=2000, gain=+3.0 dB, q=1.0) on Mid channel
  - OR: apply high-shelf cut on Side channel
  - Mid gain: 1.0 to 2.0 (user controllable)
Ports: In L, In R → Out L, Out R (M/S encode → EQ → M/S decode)
User toggle: Enable/disable with intensity slider
```

#### Stage 9: Virtual Surround (Optional)

```
Type: builtin:sofa/spatializer
Purpose: HRTF-based spatial audio for headphones; bypassed on speakers
Config:
  filename: ~/.config/da4linux/sofa/HRTF.sofa  (user-provided or bundled)
  blocksize: 128
  gain: -3.0 (prevent clipping from HRTF peaks)
  normalize: true
  Azimuth: 0 (can be made user-adjustable)
  Elevation: 0
Note: Only applies to headphone output path. On speakers, this stage is bypassed.
      SOFA files are NOT bundled (licensing concerns). User provides or 
      downloads from https://sofacoustics.org/.
```

#### Stage 10: Output Limiter

```
Type: LV2
Plugin URI: http://lsp-plug.in/plugins/lv2/limiter_stereo
Purpose: Speaker protection and preventing digital clipping
Config:
  Mode: Herm Thin (clean, transparent limiting)
  Oversampling: 4x/24bit
  Threshold: -1.0 dBFS
  Boost: OFF (no makeup gain, total output should be level-matched)
  Attack: 1.0 ms
  Release: 10.0 ms
  Lookahead: 2.5 ms
  ALR: ON (smooth automated level regulation before peak limiting)
  ALR Attack: 5.0 ms, ALR Release: 50.0 ms, ALR Knee: -3.0 dB
Ports: In L, In R → Out L, Out R
Note: This adds ~2.5 ms latency. Total pipeline latency target: <10 ms.
```

### 2.3 Complete PipeWire Filter-Chain Configuration (Generated)

Below is what `da4linux-config` generates into `~/.config/pipewire/pipewire.conf.d/50-da4linux.conf`:

```json
context.modules = [
  {
    name = libpipewire-module-filter-chain
    args = {
      node.description = "DA4Linux Audio Enhancement"
      media.name = "DA4Linux Output"
      filter.graph = {
        nodes = [
          # Stage 1: Input Gain
          { type = builtin name = input_gain_L  label = linear control = { Mult = 0.5 Add = 0.0 } }
          { type = builtin name = input_gain_R  label = linear control = { Mult = 0.5 Add = 0.0 } }

          # Stage 2: Speaker FIR Correction (per channel)
          { type = builtin name = fir_corr_L  label = convolver config = {
            filename = "/home/user/.config/da4linux/irs/t14sg2_correction_L.irs"
            blocksize = 128 gain = 0.0 } }
          { type = builtin name = fir_corr_R  label = convolver config = {
            filename = "/home/user/.config/da4linux/irs/t14sg2_correction_R.irs"
            blocksize = 128 gain = 0.0 } }

          # Stage 3: Parametric EQ (Intelligent EQ)
          { type = builtin name = ieq  label = param_eq config = {
            filters1 = [
              { type = bq_peaking freq = 100 gain = 2.0 q = 0.7 }
              { type = bq_highshelf freq = 8000 gain = -1.5 q = 0.7 }
            ]
            filters2 = [
              { type = bq_peaking freq = 100 gain = 2.0 q = 0.7 }
              { type = bq_highshelf freq = 8000 gain = -1.5 q = 0.7 }
            ]
          }}

          # Stage 4: Multiband Compressor (LV2)
          { type = lv2 name = mb_comp
            plugin = "http://lsp-plug.in/plugins/lv2/mb_compressor_stereo"
            control = {
              mode = 0           # Classic mode
              sc_boost = 1       # Pink BT (+3dB/oct)
              stereo_split = 0   # Linked stereo
              bl_0 = 1           # Band 0 ON
              mode_0 = 0         # Downward
              fstart_0 = 20.0
              fend_0 = 120.0
              ratio_0 = 2.0
              at_0 = 20.0
              rt_0 = 80.0
              mk_0 = 3.0
              bl_1 = 1           # Band 1 ON
              fstart_1 = 120.0
              fend_1 = 500.0
              ratio_1 = 1.5
              at_1 = 15.0
              rt_1 = 60.0
              bl_2 = 1           # Band 2 ON
              fstart_2 = 500.0
              fend_2 = 3000.0
              ratio_2 = 1.2
              at_2 = 10.0
              rt_2 = 40.0
              bl_3 = 1           # Band 3 ON
              fstart_3 = 3000.0
              fend_3 = 20000.0
              ratio_3 = 1.5
              at_3 = 5.0
              rt_3 = 30.0
            }
          }

          # Stage 5: Stereo Enhancement (M/S processing)
          # Split L and R to feed M/S matrix
          { type = builtin name = copy_L1  label = copy }
          { type = builtin name = copy_L2  label = copy }
          { type = builtin name = copy_R1  label = copy }
          { type = builtin name = copy_R2  label = copy }
          # M = (L+R)/2, S = (L-R)/2
          { type = builtin name = mix_M  label = mixer control = { "Gain 1" = 0.5 "Gain 2" = 0.5 } }
          { type = builtin name = mix_S  label = mixer control = { "Gain 1" = 0.5 "Gain 2" = -0.5 } }
          # Side gain
          { type = builtin name = side_gain_L  label = linear control = { Mult = 1.5 Add = 0.0 } }
          { type = builtin name = side_gain_R  label = linear control = { Mult = 1.5 Add = 0.0 } }
          # L_out = M + S*gain, R_out = M - S*gain
          { type = builtin name = mix_Lout  label = mixer control = { "Gain 1" = 1.0 "Gain 2" = 1.0 } }
          { type = builtin name = mix_Rout  label = mixer control = { "Gain 1" = 1.0 "Gain 2" = -1.0 } }

          # Stage 6: Bass Enhancement (custom C — Phase 2)
          # Stub: passthrough for Phase 1
          { type = builtin name = bass_L  label = linear control = { Mult = 1.0 Add = 0.0 } }
          { type = builtin name = bass_R  label = linear control = { Mult = 1.0 Add = 0.0 } }
          # Future: { type = ladspa name = bass_L plugin = da4linux/libspa-bass-enhancer label = bass_enhancer ... }

          # Stage 7: Loudness (EBU R128)
          { type = ebur128 name = loudness_meter label = ebur128
            config = { max-history = 10.0 max-window = 3.0 } }
          { type = ebur128 name = lufs_to_gain label = lufs2gain
            control = { "Target LUFS" = -14.0 } }
          { type = builtin name = loudness_gain_L label = linear }
          { type = builtin name = loudness_gain_R label = linear }

          # Stage 8: Dialogue Enhancement (M/S center boost)
          { type = builtin name = dialog_boost label = bq_peaking
            control = { Freq = 2000.0 Gain = 3.0 Q = 1.0 } }
          # M/S decode for dialog: reuse M/S from stage 5 if in chain,
          # but simpler: just apply mid-side EQ on stereo signal.
          # Actually, we do M/S decode → EQ mid → M/S encode:
          # This requires splitting L/R again (or reusing stage 5 topology)
          # For simplicity in Phase 1: use bq_peaking on L+R mixed signal
          # Phase 2: proper M/S center extraction

          # Stage 9: Virtual Surround (optional, SOFA spatializer)
          # Only enabled when profile specifies headphones
          # { type = sofa name = hrtf label = spatializer config = {
          #   filename = "/home/user/.config/da4linux/sofa/HRTF.sofa"
          #   blocksize = 128 gain = -3.0 normalize = true } }

          # Stage 10: Output Limiter (LV2)
          { type = lv2 name = limiter
            plugin = "http://lsp-plug.in/plugins/lv2/limiter_stereo"
            control = {
              mode = 0            # Herm Thin
              ovs = 6            # 4x/24bit oversampling
              alr = 1            # ALR ON
              alr_at = 5.0
              alr_rt = 50.0
              alr_knee = -3.0
              lk_a = 2.5         # Lookahead 2.5ms
              thr = -1.0         # Threshold -1.0 dBFS
              at = 1.0           # Attack 1.0ms
              rt = 10.0          # Release 10.0ms
              sc_mode = 0        # Internal sidechain
            }
          }
        ]
        links = [
          # Capture → Input Gain
          { output = "input_gain_L:In"  input = "input_gain_L:In" }
          { output = "input_gain_R:In"  input = "input_gain_R:In" }

          # Input Gain → FIR Correction
          { output = "input_gain_L:Out" input = "fir_corr_L:In" }
          { output = "input_gain_R:Out" input = "fir_corr_R:In" }

          # FIR → Parametric EQ
          { output = "fir_corr_L:Out"   input = "ieq:In 1" }
          { output = "fir_corr_R:Out"   input = "ieq:In 2" }

          # Parametric EQ → Multiband Compressor
          { output = "ieq:Out 1"        input = "mb_comp:in_l" }
          { output = "ieq:Out 2"        input = "mb_comp:in_r" }

          # Multiband Compressor → Stereo Enhancer (M/S)
          { output = "mb_comp:out_l"    input = "copy_L1:In" }
          { output = "mb_comp:out_r"    input = "copy_R1:In" }
          { output = "copy_L1:Out"      input = "mix_M:In 1" }
          { output = "copy_R1:Out"      input = "mix_M:In 2" }
          { output = "copy_L1:Out"      input = "mix_S:In 1" }
          { output = "copy_R1:Out"      input = "mix_S:In 2" }
          { output = "mix_S:Out"        input = "side_gain_L:In" }
          { output = "side_gain_L:Out"  input = "mix_Lout:In 2" }
          { output = "mix_M:Out"        input = "mix_Lout:In 1" }
          { output = "mix_M:Out"        input = "mix_Rout:In 1" }
          { output = "side_gain_L:Out"  input = "mix_Rout:In 2" }

          # M/S → Bass Enhancer
          { output = "mix_Lout:Out"     input = "bass_L:In" }
          { output = "mix_Rout:Out"     input = "bass_R:In" }

          # Bass → Loudness Meter (EBU R128)
          { output = "bass_L:Out"       input = "loudness_meter:In FL" }
          { output = "bass_R:Out"       input = "loudness_meter:In FR" }

          # Loudness Meter → Gain
          { output = "loudness_meter:Shortterm LUFS" input = "lufs_to_gain:LUFS" }
          { output = "lufs_to_gain:Gain"  input = "loudness_gain_L:Control" }
          { output = "loudness_meter:Out FL" input = "loudness_gain_L:In" }
          { output = "loudness_meter:Out FR" input = "loudness_gain_R:In" }
          # Copy control from L to R
          { output = "lufs_to_gain:Gain"  input = "loudness_gain_R:Control" }
          # Note: lufs2gain produces a single control output. We need to 
          # tee it to both L and R linear nodes. Use copy for control signals.
          # Builtin:copy works for audio; for control signals use builtin:linear 
          # with Mult=1.0 as a control passthrough.

          # Loudness Gain → Dialog Enhancement → Limiter
          { output = "loudness_gain_L:Out"  input = "limiter:in_l" }
          { output = "loudness_gain_R:Out"  input = "limiter:in_r" }

          # Limiter → Playback
          { output = "limiter:out_l" input = "output_L" }
          { output = "limiter:out_r" input = "output_R" }
        ]
        inputs  = [ "input_gain_L:In" "input_gain_R:In" ]
        outputs = [ "output_L" "output_R" ]
        capture.volumes = [
          { control = "input_gain_L:Mult" min = 0.0 max = 1.0 scale = cubic }
          { control = "input_gain_R:Mult" min = 0.0 max = 1.0 scale = cubic }
        ]
      }
      capture.props = {
        node.name      = "da4linux.capture"
        media.class    = Audio/Sink
        audio.channels = 2
        audio.position = [ FL FR ]
        node.description = "DA4Linux Sink"
        priority.session = 900
      }
      playback.props = {
        node.name       = "da4linux.playback"
        media.class     = Audio/Sink
        audio.channels  = 2
        audio.position  = [ FL FR ]
        node.passive    = true
        node.description = "DA4Linux Output"
        target.object   = "alsa_output.pci-XXXX"
      }
    }
  }
]
```

**IMPORTANT CAVEAT about the links section above:**
The links in a filter-chain graph follow the rule that each input port can only be linked from ONE output, and each output can link to ONE input (unless teed via builtin:copy). The above links section needs to be verified for correctness — particularly:

- The `capture.volumes` control signal path to `input_gain_L:Mult` must route through the filter-chain's internal volume system, not through explicit links.
- Control-output to control-input links like `lufs_to_gain:Gain → loudness_gain_L:Control` need to be verified against PipeWire >= 1.0 behavior.
- The M/S matrix using copy/mixer nodes needs careful port routing. An alternative is to use a single LV2 M/S plugin or a custom C node.

**Recommendation for Phase 1:** Simplify. Use the builtin convolver for the FIR speaker correction and a single-stage parametric EQ. Skip the complex M/S matrix, multiband compression, and EBU loudness. Build the full chain incrementally and test each stage.

---

## 3. Configuration & Tuning

### 3.1 Hardware Auto-Detection

```python
# da4linux/core/detector.py
import subprocess
import re
from pathlib import Path

def detect_hardware() -> dict:
    """Detect hardware via DMI/sysfs. Returns device profile key."""
    # Read DMI product name and SKU
    dmi_dir = Path("/sys/class/dmi/id")
    product_name = (dmi_dir / "product_name").read_text().strip()
    product_sku = (dmi_dir / "product_sku").read_text().strip()
    
    # Read ALSA card info for codec identification
    proc_asound = Path("/proc/asound")
    cards = [d for d in proc_asound.iterdir() if d.name.startswith("card")]
    
    codecs = []
    for card in cards:
        codec_path = card / "codec#0"
        if codec_path.exists():
            content = codec_path.read_text()
            # Extract codec name: e.g., "Realtek ALC3287"
            m = re.search(r'Codec: (.+)', content)
            if m:
                codecs.append(m.group(1).strip())
    
    # Detect subsystem PCI ID for precise match
    # e.g., /sys/class/sound/card0/device/subsystem_vendor
    #       /sys/class/sound/card0/device/subsystem_device
    
    return {
        "vendor": "Lenovo",
        "model": product_name,        # "ThinkPad T14s Gen 2i"
        "sku": product_sku,           # "LENOVO_MT_20WN_BU_Think_FM_ThinkPad T14s Gen 2i"
        "codec": codecs[0] if codecs else None,  # "Realtek ALC3287"
        "subsystem_vendor": "17AA",   # Lenovo
        "subsystem_device": "22F2",   # T14s Gen 2 specific
    }

def get_profile_key(hw: dict) -> str:
    """Generate profile lookup key matching DAX3 XML naming convention."""
    # Format: VENDOR_MODEL_CODEC_SUBSYS
    # e.g., "LENOVO_T14SG2_ALC3287_17AA22F2"
    model_short = re.sub(r'[^A-Za-z0-9]', '', hw["model"]).upper()
    return f"{hw['vendor'].upper()}_{model_short}_{hw['codec'].replace(' ','')}_{hw['subsystem_vendor']}{hw['subsystem_device']}"
```

### 3.2 DAX3 XML Integration

The project leverages the extraction pipeline from `mister2d/thinkpad-linux-audio` and `antoinecellerier/speaker-tuning-to-easyeffects`.

**DAX3 XML structure (relevant sections):**

```xml
<dax3_config>
  <tuning>
    <speaker_correction>
      <!-- FIR filter banks for speaker correction -->
      <filter_bank channel="L" sample_rate="48000">
        <filter index="0" b0="0.123" b1="0.456" ... />
      </filter_bank>
    </speaker_correction>
    <intelligent_eq>
      <!-- Per-mode EQ curves -->
      <mode name="Music">
        <band freq="100" gain="2.0" q="0.7" type="peaking" />
        <band freq="8000" gain="-1.5" q="0.7" type="highshelf" />
      </mode>
      <mode name="Movie"> ... </mode>
      <mode name="Voice"> ... </mode>
    </intelligent_eq>
    <audio_optimizer>
      <!-- Per-channel gains for spatial balance -->
      <channel name="L" gain="-3.0" />
      <channel name="R" gain="-3.0" />
    </audio_optimizer>
    <virtualizer>
      <!-- Surround widening coefficients -->
      <width amount="0.3" />
    </virtualizer>
  </tuning>
</dax3_config>
```

**DA4Linux profile format (JSON):**

```json
{
  "version": 1,
  "hardware": {
    "vendor": "Lenovo",
    "model": "ThinkPad T14s Gen 2i",
    "codec": "Realtek ALC3287",
    "profile_key": "LENOVO_T14SG2_ALC3287_17AA22F2",
    "channels": 2,
    "has_subwoofer": false,
    "max_power_watts": 4
  },
  "modes": {
    "music": {
      "stage_config": {
        "input_gain": -6.0,
        "speaker_eq": { "irs_file": "t14sg2_speaker_correction.irs" },
        "param_eq": {
          "filters_l": [
            { "type": "peaking", "freq": 100, "gain": 2.0, "q": 0.7 },
            { "type": "highshelf", "freq": 8000, "gain": -1.5, "q": 0.7 }
          ],
          "filters_r": [
            { "type": "peaking", "freq": 100, "gain": 2.0, "q": 0.7 },
            { "type": "highshelf", "freq": 8000, "gain": -1.5, "q": 0.7 }
          ]
        },
        "multiband_dynamics": {
          "bands": [
            { "start": 20, "end": 120, "ratio": 2.0, "attack_ms": 20, "release_ms": 80, "makeup_db": 3.0 },
            { "start": 120, "end": 500, "ratio": 1.5, "attack_ms": 15, "release_ms": 60, "makeup_db": 0.0 },
            { "start": 500, "end": 3000, "ratio": 1.2, "attack_ms": 10, "release_ms": 40, "makeup_db": 0.0 },
            { "start": 3000, "end": 20000, "ratio": 1.5, "attack_ms": 5, "release_ms": 30, "makeup_db": 0.0 }
          ]
        },
        "stereo_width": 1.0,
        "bass_enhance": { "amount": 0.3, "crossover_hz": 120 },
        "loudness_target_lufs": -14.0,
        "dialogue_enhance": { "enabled": false, "gain_db": 0.0 },
        "virtual_surround": { "enabled": false },
        "limiter": { "threshold_dbfs": -1.0, "lookahead_ms": 2.5 }
      }
    },
    "movie": { "...": "..." },
    "voice": { "...": "..." }
  },
  "user_overrides": {
    "bass_enhance_amount": 0.5,
    "stereo_width": 1.3,
    "loudness_target_lufs": -16.0
  }
}
```

### 3.3 Configuration File Layout

```
~/.config/da4linux/
├── config.yaml              # Global user settings (preferred mode, volume key behavior, etc.)
├── profiles/
│   ├── LENOVO_T14SG2_ALC3287_17AA22F2.json   # Auto-detected device profile
│   └── default.json                           # Fallback profile (generic laptop)
├── irs/                                      # Impulse response files (FIR convolution)
│   ├── t14sg2_speaker_correction_L.irs       # Per-channel IR (WAV format, 48 kHz mono)
│   └── t14sg2_speaker_correction_R.irs
├── sofa/                                     # SOFA HRTF files (user-provided)
│   └── HRTF.sofa
└── generated/                                # Generated PipeWire config (auto-regenerated)
    └── da4linux_music.conf                   # Per-mode config drop-in
```

### 3.4 User-Configurable vs Fixed Parameters

| Parameter | Fixed (from DAX3) | User-Adjustable | Range |
|-----------|-------------------|-----------------|-------|
| Speaker correction FIR | ✓ | ✗ | — |
| IEQ filter bands | ✓ | ✗ | — |
| Input gain (preamp) | — | ✓ | -20 to +6 dB |
| Multiband comp thresholds | ✓ (default) | ✓ (advanced) | per band |
| Stereo width | — | ✓ | 0.0 to 2.0 |
| Bass enhancement amount | — | ✓ | 0.0 to 1.0 |
| Loudness target LUFS | — | ✓ | -24 to -10 |
| Dialogue enhancement | — | ✓ | 0 to +6 dB |
| Virtual surround toggle | — | ✓ | ON/OFF |
| Limiter threshold | — | ✓ | -6 to 0 dBFS |

---

## 4. Implementation Plan

### 4.1 Directory Structure

```
DA4Linux/
├── README.md
├── ARCHITECTURE.md          # This document
├── LICENSE                  # GNU GPL v3
├── pyproject.toml           # Python package metadata (PEP 621)
├── uv.lock                  # Dependency lockfile
├── meson.build              # Top-level Meson build for C components
├── meson_options.txt
│
├── src/
│   ├── da4linux/                    # Python package root
│   │   ├── __init__.py
│   │   ├── cli/
│   │   │   ├── __init__.py
│   │   │   ├── main.py              # Typer CLI entry point
│   │   │   ├── commands.py          # Subcommands: init, detect, apply, status, disable
│   │   │   └── output.py            # Rich output formatting
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── detector.py          # Hardware detection (DMI, ALSA, sysfs)
│   │   │   ├── profile.py           # Profile data model (Pydantic)
│   │   │   ├── dax3_parser.py       # DAX3 XML parser (lxml)
│   │   │   └── ir_extractor.py      # FIR coefficient → WAV IR conversion
│   │   ├── config/
│   │   │   ├── __init__.py
│   │   │   ├── generator.py         # PipeWire config JSON generator
│   │   │   ├── templates.py         # Configuration templates
│   │   │   └── validator.py         # Config validation
│   │   └── service/
│   │       ├── __init__.py
│   │       └── manager.py           # DBus service for runtime control
│   │
│   ├── dsp/                          # C DSP components
│   │   ├── meson.build
│   │   ├── include/
│   │   │   └── da4linux/
│   │   │       ├── bass_enhancer.h
│   │   │       └── common.h
│   │   ├── bass_enhancer.c           # MaxxBass-style psychoacoustic bass
│   │   ├── loudness_iso226.c         # ISO 226 equal-loudness dynamic EQ
│   │   ├── spa_plugin.c              # SPA plugin boilerplate/wrapper
│   │   └── test/
│   │       ├── test_bass_enhancer.c
│   │       └── test_loudness.c
│   │
│   └── service/                      # Systemd + WirePlumber integration
│       ├── da4linux.service          # systemd user service unit
│       └── wireplumber/
│           └── 50-da4linux.lua       # WirePlumber Lua policy script
│
├── profiles/                         # Bundled device profiles
│   ├── index.json                    # Profile registry (model → profile file)
│   └── lenovo/
│       └── thinkpad-t14s-gen2.json
│
├── tests/                            # Python test suite
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_detector.py
│   ├── test_dax3_parser.py
│   ├── test_profile.py
│   ├── test_generator.py
│   └── fixtures/
│       ├── sample_dax3.xml
│       ├── dmi_mock/
│       └── expected_configs/
│
├── docs/
│   ├── user-guide.md
│   ├── developer-guide.md
│   ├── contributing.md
│   └── profiles/
│       └── adding-new-device.md
│
├── scripts/
│   ├── install.sh                    # One-shot installer
│   ├── uninstall.sh
│   └── generate_profile.py          # Profile extraction utility
│
└── .github/
    └── workflows/
        ├── test.yml
        └── lint.yml
```

### 4.2 Build System

**Python:** `uv` (PEP 621 pyproject.toml, uv.lock)

```toml
# pyproject.toml
[project]
name = "da4linux"
version = "0.1.0"
description = "Dolby Audio processing for Linux via PipeWire filter-chain"
license = { text = "GPL-3.0-only" }
requires-python = ">=3.11"
dependencies = [
    "typer>=0.12",
    "rich>=13.0",
    "pydantic>=2.0",
    "lxml>=5.0",
    "pyyaml>=6.0",
    "numpy>=1.26",
    "scipy>=1.12",
]

[project.scripts]
da4linux = "da4linux.cli.main:app"

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "pytest-xdist>=3.6",
    "ruff>=0.5",
    "mypy>=1.10",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
target-version = "py311"
line-length = 100
[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM"]
[tool.ruff.format]
quote-style = "double"

[tool.mypy]
strict = true
python_version = "3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = ["-v", "--tb=short", "--strict-markers"]
```

**C:** Meson

```meson
# src/dsp/meson.build
project('da4linux-dsp', 'c',
  version: '0.1.0',
  license: 'GPL-3.0-only',
  default_options: [
    'c_std=c11',
    'warning_level=3',
    'werror=true',
    'buildtype=debugoptimized',
  ]
)

cc = meson.get_compiler('c')

# Dependencies
m_dep = cc.find_library('m', required: true)
spa_dep = dependency('libspa-0.2', required: true)
pipewire_dep = dependency('libpipewire-0.3', required: true)

# SPA plugin library
spa_plugin = shared_library('spa-bass-enhancer',
  sources: ['bass_enhancer.c', 'spa_plugin.c'],
  include_directories: include_directories('include'),
  dependencies: [m_dep, spa_dep, pipewire_dep],
  install: true,
  install_dir: get_option('libdir') / 'spa-0.2' / 'da4linux',
  c_args: ['-D_GNU_SOURCE'],
)

# Tests
test_bass = executable('test_bass_enhancer',
  'test/test_bass_enhancer.c',
  link_with: spa_plugin,
  dependencies: [m_dep],
)
test('bass_enhancer', test_bass)
```

### 4.3 Dependencies

**Runtime (must be installed):**

| Package | Version | Purpose | Distro Package |
|---------|---------|---------|----------------|
| PipeWire | >= 1.0 | Audio server, filter-chain module | `pipewire` |
| WirePlumber | >= 0.5 | Session manager | `wireplumber` |
| LSP Plugins (LV2) | >= 1.2.x | Multiband compressor, limiter | `lsp-plugins-lv2` |
| libmysofa | >= 1.3 | SOFA HRTF loading (spatializer) | `libmysofa1` |
| libebur128 | >= 1.2 | EBU R128 loudness metering | `libebur128-1` |
| Python | >= 3.11 | CLI and config generation | `python3` |

**Build-only:**

| Package | Purpose |
|---------|---------|
| meson | C build system |
| ninja | C build backend |
| gcc / clang | C compiler |
| libspa-0.2-dev | SPA plugin headers |
| libpipewire-0.3-dev | PipeWire headers |

### 4.4 Phased Development Plan

| Phase | Deliverable | Owner | Effort |
|-------|------------|-------|--------|
| **Phase 1: Core Pipeline** | Hardware detection (Python), FIR speaker correction via builtin:convolver, parametric EQ via builtin:param_eq, output limiter via LV2 LSP Limiter. CLI tool: `da4linux init`, `da4linux apply`. Working end-to-end chain. | @coder (Python), @scout (testing) | 2-3 weeks |
| **Phase 2: Dynamics & Enhancement** | Multiband compressor integration (LSP LV2), stereo M/S enhancement, custom C bass enhancer SPA plugin. EBU R128 loudness normalization. | @coder (Python+C), @researcher (tuning parameters) | 3-4 weeks |
| **Phase 3: Advanced Features** | ISO 226 dynamic loudness EQ (C), dialogue enhancement (M/S center extraction), virtual surround via SOFA, DE/ONNX neural models, per-app mode switching. | @coder (C), @researcher (psychoacoustics) | 4-6 weeks |
| **Phase 4: Deployment & Polish** | Systemd user service, WirePlumber integration, output switching logic, GUI (optional), Flatpak packaging, AUR package. | @coder, @reviewer, @security-auditor | 2-3 weeks |

---

## 5. Deployment Architecture

### 5.1 Systemd User Service

```ini
# src/service/da4linux.service
[Unit]
Description=DA4Linux Audio Enhancement Service
Documentation=https://github.com/user/da4linux
After=pipewire.service wireplumber.service
Requires=pipewire.service wireplumber.service
PartOf=graphical-session.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/da4linux apply --auto-detect
ExecStop=/usr/bin/da4linux disable
Restart=no
Environment=XDG_RUNTIME_DIR=/run/user/%U

[Install]
WantedBy=graphical-session.target
```

Install: `systemctl --user enable --now da4linux.service`

### 5.2 WirePlumber Integration for Device Hotplug

**Problem:** When user plugs in headphones, the processing chain should either:
- **Option A:** Follow the output device (reconfigure and re-attach to headphone sink)
- **Option B:** Bypass entirely for headphones (speaker correction is only for speakers)
- **Option C:** Switch to a different profile (headphone EQ + virtual surround)

**Solution:** Option C — WirePlumber Lua policy script that:
1. Detects which output device (speaker/headphone/BT) is the default
2. Sets a PipeWire metadata key `da4linux.profile = "speakers" | "headphones" | "bypass"`
3. The filter-chain module reads this metadata and reconfigures itself

```lua
-- src/service/wireplumber/50-da4linux.lua
-- WirePlumber Lua policy: manage DA4Linux profile switching

rule = {
  matches = {
    {
      { "device.name", "matches", "alsa_card.pci-*" },
    },
  },
  apply_properties = {
    ["device.profile-set"] = "da4linux-profiles",
  },
}

-- Monitor default audio sink changes
default_sink_monitor = SimpleEventHook {
  name = "da4linux-default-sink-monitor",
  interests = {
    EventHook.DefaultNodesChanged,
  },
  execute = function(event)
    local default_sink = getDefaultSink()
    local sink_props = default_sink:get_properties()
    local device_class = sink_props["device.class"]
    
    if device_class == "sound" then
      -- Internal speakers
      setMetadata("da4linux.profile", "speakers")
    elseif device_class == "headphones" then
      setMetadata("da4linux.profile", "headphones")
    elseif device_class == "bluetooth" then
      setMetadata("da4linux.profile", "bypass")
    end
  end,
}

default_sink_monitor:register()
```

**Alternative (simpler for Phase 1):** Create a `node.link-group` on the filter-chain so PipeWire automatically reconnects it when the default sink changes. The filter-chain playback stream uses `node.target` = the default audio sink.

### 5.3 Output Switching Strategy

```
                           ┌──────────────┐
                           │ WirePlumber  │
                           │ detects      │
                           │ default sink │
                           └──────┬───────┘
                                  │
                ┌─────────────────┼──────────────────┐
                ▼                 ▼                    ▼
        ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
        │ Speakers      │  │ Headphones   │  │ Bluetooth    │
        │ (ALSA HDA)    │  │ (ALSA HDA)   │  │ (bluez5)     │
        └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
               │                 │                   │
               ▼                 ▼                   ▼
        ┌──────────────────────────────────────────────────┐
        │          DA4Linux filter-chain reconfigures:      │
        │                                                  │
        │  Speakers:    Full chain (all 10 stages)         │
        │  Headphones:  Virtual surround replaces speaker   │
        │               correction; user EQ profile loaded  │
        │  Bluetooth:   Bypass all processing (codec does   │
        │               its own DSP)                        │
        └──────────────────────────────────────────────────┘
```

### 5.4 Conflict Resolution

**Problem:** Multiple audio processors (EasyEffects, JamesDSP, PulseEffects, etc.) try to insert themselves into the PipeWire graph simultaneously, creating cascading filter-chains with excessive latency and potential feedback loops.

**Detection and resolution strategy:**

1. **Detection:** On startup, `da4linux init` queries PipeWire for:
   - Active filter-chain modules
   - Running EasyEffects/JamesDSP instances
   - Any node with `media.class = Audio/Sink` that is not a hardware device

2. **Conflict reporting:**
   ```
   $ da4linux status
   ⚠ Conflict detected: EasyEffects is running on the speaker output.
     Only one audio processor should be active at a time.
     Suggested action: da4linux disable-easyeffects
   ```

3. **Automatic resolution (opt-in):**
   - `da4linux apply --force` — disables competing processors via their DBus API or by unloading their PipeWire modules
   - `da4linux disable` — removes DA4Linux filter-chain and restores previous state

4. **Graceful coexistence (future):**
   - If EasyEffects is using the `output` (speaker) pipeline, DA4Linux could use the `input` (microphone) pipeline instead, or vice versa.
   - A `da4linux.mode = cooperative` flag that only applies speaker correction, letting EasyEffects handle dynamics/EQ.

---

## 6. Gaps vs Real Dolby Atmos

### 6.1 What CAN Be Achieved

| Dolby Feature | DA4Linux Equivalent | Fidelity |
|---------------|-------------------|----------|
| Speaker correction (FIR) | builtin:convolver with DAX3 IR | **100%** — same coefficients |
| Intelligent EQ | builtin:param_eq with DAX3 bands | **100%** — same filters |
| Volume Leveler (DRC) | LSP Multiband Compressor | **80%** — no content classifier, but functional |
| Surround Virtualizer (width) | M/S stereo processing | **70%** — stereo widening, no true surround decode |
| Dialogue Enhancer | M/S center channel boost | **60%** — boosts center, but no neural voice extraction |
| Bass Enhancement | Custom C psychoacoustic bass | **80%** — same principle as MaxxBass (patent expired) |
| Loudness Compensation | EBU R128 or ISO 226 dynamic EQ | **90%** — EBU R128 is standard; ISO 226 is the physical model Dolby uses |
| Speaker Protection | LSP Limiter with lookahead | **95%** — professional-grade brickwall limiting |

### 6.2 What CANNOT Be Achieved

| Dolby Feature | Why Unavailable | Workaround |
|---------------|----------------|------------|
| **Atmos object-based audio** | Requires Dolby AC-4/TrueHD decoder with JOC (Joint Object Coding); decoder is proprietary and patent-encumbered | None. This is the core gap. |
| **Height virtualization** | Requires metadata about height objects (not present in stereo streams) | Approximate with SOFA HRTF headphone virtualization (no height metadata, but spatial widening) |
| **Dolby Atmos decode (TrueHD/DD+)** | Bitstream decoder is closed-source; implementing it violates Dolby patents | Use Cavern for .NET-based decode (separate project, Windows/Linux via Mono) |
| **DAX3 content classifier** | Proprietary neural network that classifies content type (music/movie/voice/game) for mode switching | Manual mode switching via CLI or audio stream metadata (application.name) |
| **Dolby Headphone / Dolby Virtual Speaker** | Proprietary HRTF database; specific DSP algorithms | Generic SOFA HRTF; similar perceptual result but different spatialization |
| **Dialogue Intelligence** | Neural voice extraction model trained on proprietary data | M/S center extraction works for center-panned content but fails on panned dialogue |

### 6.3 Migration Path

```
Phase 1: Static speaker correction (FIR + PEQ) — TODAY
         │
Phase 2: Full dynamics chain (MB comp, bass enh, loudness, limiter) — MONTHS 1-3
         │
Phase 3: Virtual surround (SOFA HRTF), dialogue enh. — MONTHS 4-6
         │
Phase 4: Neural enhancement via ONNX (PipeWire filter-chain ONNX nodes) — MONTHS 7-12
         │  PipeWire >= 1.2 supports ONNX runtime as a filter-chain node type.
         │  Potential models: voice extraction, content classification,
         │  neural upmixing (e.g., Facebook Demucs for source separation)
         │
Phase 5: Object audio decode — IF legal landscape changes
         │  Cavern (C# .NET) already does TrueHD/DD+ JOC decode.
         │  A pipewire-sink → Cavern → pipewire-source bridge is possible
         │  but adds significant complexity and depends on Cavern's license.
         │
         ▼
      Full Dolby Atmos replacement? — NOT POSSIBLE without Dolby license.
      DA4Linux provides "Dolby-quality audio enhancement" but NOT
      "Dolby Atmos certification" or object-based audio rendering.
```

---

## Open Questions for Stakeholders

1. **DAX3 XML redistribution legality:** The DAX3 XML files are extracted from Lenovo's signed driver packages. Can we:
   - Bundle them in the repo? (risk of copyright claim)
   - Provide a downloader script that fetches from Lenovo's site? (safer)
   - Require users to extract themselves? (worst UX)
   
   **Recommendation:** Ship an extraction script and clear documentation. Do NOT bundle DAX3 XML in the repo. The `mister2d/thinkpad-linux-audio` project follows this pattern.

2. **SOFA HRTF file bundling:** Many SOFA files have restrictive licenses (CC BY-NC, proprietary). Recommendation: bundle no SOFA files. Provide a script to download MIT-licensed alternatives (e.g., from SADIE II database, which is CC0).

3. **EasyEffects coexistence:** Should DA4Linux integrate with EasyEffects (import/export presets, share IRS files) or remain independent? Recommendation: share the IRS file format and profile JSON; document interop; remain independent for core functionality.

4. **GUI vs CLI-first:** Phase 1 is CLI-only (da4linux CLI tool). Is a GTK/QT GUI needed? Recommendation: CLI-first for v0.1; GUI as a separate package (`da4linux-gui`) using GTK4/libadwaita in Phase 4.

5. **Snap/Flatpak packaging:** PipeWire filter-chain runs inside the PipeWire daemon. A Flatpak'd da4linux can only write config files and call `pw-cli` or DBus. The actual DSP runs in the host PipeWire process. This is feasible. Recommendation: support both native packages (AUR, apt, rpm) and Flatpak for sandboxed installs.

6. **Target latency:** The full 10-stage pipeline with limiter lookahead adds ~5-8 ms latency. For real-time applications (DAWs, games), this may be noticeable. Should we provide a "low-latency mode" that strips multiband compression and limiter lookahead? Recommendation: yes, add `--latency low|medium|high` flag that selects different processing chains.

---

## Appendix A: LV2 Plugin URIs Reference

| Plugin | LV2 URI | Category |
|--------|---------|----------|
| LSP Parametric EQ x32 Stereo | `http://lsp-plug.in/plugins/lv2/para_equalizer_x32_stereo` | EQ |
| LSP Multiband Compressor x8 Stereo | `http://lsp-plug.in/plugins/lv2/mb_compressor_stereo` | Dynamics |
| LSP Limiter Stereo | `http://lsp-plug.in/plugins/lv2/limiter_stereo` | Dynamics |
| LSP Compressor Stereo | `http://lsp-plug.in/plugins/lv2/compressor_stereo` | Dynamics |
| LSP Surge Filter Stereo | `http://lsp-plug.in/plugins/lv2/surge_filter_stereo` | Utility |
| LSP Delay Compensator x2 Stereo | `http://lsp-plug.in/plugins/lv2/comp_delay_x2_stereo` | Delay |
| CALF Bass Enhancer | `http://calf.sourceforge.net/plugins/BassEnhancer` | Enhancement |

## Appendix B: PipeWire Filter-Chain Debugging

```bash
# View active filter-chain modules
pw-cli list-objects | grep -A 20 filter-chain

# Monitor PipeWire log for filter-chain errors
PIPEWIRE_DEBUG=4 pipewire 2>&1 | grep filter-chain

# Test a filter-chain config without restarting PipeWire
pipewire -c /path/to/test-filter-chain.conf

# List available LV2 plugins
lv2ls

# Inspect LV2 plugin port names and control symbols
lv2info http://lsp-plug.in/plugins/lv2/mb_compressor_stereo

# List available LADSPA plugins
listplugins

# Inspect LADSPA plugin port names
analyseplugin <ladspa_plugin_name>

# Check ALSA devices
aplay -l
cat /proc/asound/card*/codec#*
```

## Appendix C: Typical DAX3 XML to IRS Conversion Pipeline

```bash
# 1. Extract DAX3 XML from Lenovo driver package
python -m da4linux.core.dax3_parser \
  --input DEV_0287_SUBSYS_17AA22F2.xml \
  --output-dir ~/.config/da4linux/irs/ \
  --sample-rate 48000

# 2. This produces:
#   t14sg2_correction_L.irs   (WAV, mono, float32, 48 kHz, FIR coefficients)
#   t14sg2_correction_R.irs
#   t14sg2_profile.json       (DAX3-derived EQ and dynamics parameters)

# 3. Validate IR files
python -m da4linux.core.ir_extractor --validate t14sg2_correction_L.irs

# 4. Generate PipeWire config from profile
python -m da4linux.config.generator \
  --profile ~/.config/da4linux/profiles/t14sg2_profile.json \
  --mode music \
  --output ~/.config/pipewire/pipewire.conf.d/50-da4linux.conf
```

## 7. Phase 2+3 Architecture: Dynamics, Enhancement & Spatial

**Authoritative design.** This section extends and supersedes the Phase 1 sketches
for stages 4–9. All decisions are based on verified system state:
- LSP 1.2.33 LV2 plugins confirmed installed (`/usr/lib/lv2/lsp-plugins.lv2/`)
- CALF Bass Enhancer confirmed NOT installed
- PipeWire >=1.0 with `ebur128`, `sofa`, and `builtin` node types available

### 7.1 Updated Processing Chain

```
capture.stream (stereo f32le, 48 kHz)
 |
 +-[1] Input Gain         builtin:linear              Pre-amp, headroom
 +-[2] Speaker FIR        builtin:convolver           DAX3 speaker correction (Phase 1)
 +-[3] Parametric EQ      builtin:param_eq            DAX3 Intelligent EQ (Phase 1)
 +-[4] Multiband Comp     lv2:mb_compressor_stereo    Per-band DRC (Phase 2)
 +-[5] Stereo Enhancer    builtin M/S matrix          Width control (Phase 2)
 +-[6] Bass Enhancer      custom C SPA plugin         MaxxBass harmonics (Phase 2)
 +-[7] Loudness Comp      ebur128 + linear            EBU R128 + ISO 226 (Phase 2/3)
 +-[8] Dialogue Enhancer  builtin M/S + biquads       Center channel boost (Phase 3)
 +-[9] Virtual Surround   builtin:sofa/spatializer    HRTF headphones (Phase 3)
 +-[10] Output Limiter    lv2:limiter_stereo          Speaker protection (Phase 1)
 |
 v
playback.stream (-> ALSA device)
```

**Processing order justification:**
Dynamics (compression) before spatial (stereo/surround) is the industry standard:
widening a compressed signal is transparent; compressing a widened signal alters
the stereo image. Bass enhancement after stereo widening preserves harmonic phase
relationships. Loudness compensation near the end ensures the final perceived
loudness takes all upstream processing into account. Virtual surround is
second-to-last so HRTF filters are the last tonal shaping before the brickwall
limiter. Dialogue enhancement precedes VR so center extraction works on the
un-spatialized stereo field.

---

### 7.2 Stage 4: Multiband Compressor — Full Specification

#### 7.2.1 Technology Decision

| Factor | Decision |
|--------|----------|
| Primary plugin | `http://lsp-plug.in/plugins/lv2/mb_compressor_stereo` |
| Version | LSP 1.2.33 (installed at `/usr/lib/lv2/lsp-plugins.lv2/`) |
| Fallback | `http://lsp-plug.in/plugins/lv2/compressor_stereo` (single-band, single set of params) |
| Why LSP | Most mature open-source multiband compressor: per-band SC, Classic/Modern modes, linked stereo, Pink BT spectral tilt |
| Latency | 0 samples in Classic (IIR) mode; ~256–512 samples in Modern/Linear Phase |

#### 7.2.2 Verified LV2 Port Symbols (from .ttl file)

**Audio ports (indices 0–3):**

| Index | Symbol | Direction | Name |
|-------|--------|-----------|------|
| 0 | `in_l` | Input | Input L |
| 1 | `in_r` | Input | Input R |
| 2 | `out_l` | Output | Output L |
| 3 | `out_r` | Output | Output R |

**Key global control ports (indices 4–29):**

| Index | Symbol | Type | Range | Default | Notes |
|-------|--------|------|-------|---------|-------|
| 8 | `enabled` | toggle | 0/1 | 1 | Master bypass |
| 9 | `mode` | enum | 0=Classic,1=Modern,2=Linear Phase | 1 | Use 0 for zero latency |
| 10 | `g_in` | log gain | 0.0–10.0 | 1.0 | Input gain |
| 11 | `g_out` | log gain | 0.0–10.0 | 1.0 | Output gain |
| 12 | `g_dry` | log gain | 0.0–10.0 | 0.0 | Dry mix |
| 13 | `g_wet` | log gain | 0.0–10.0 | 1.0 | Wet mix |
| 18 | `envb` | enum | 0=None,1=Pink BT,2=Pink MT,3=Brown BT,4=Brown MT | 1 | Spectral tilt |
| 21 | `ssplit` | toggle | 0/1 | 0 | Stereo split (0=linked) |

**Band split ports (indices 30–43):**

For N active bands, enable splits `cbe_1` through `cbe_(N-1)`.

| Index | Symbol | Name | Default |
|-------|--------|------|---------|
| 30 | `cbe_1` | Split enable 2 | 0 |
| 31 | `sf_1` | Split freq 2 (Hz) | 40 |
| 32 | `cbe_2` | Split enable 3 | 1 |
| 33 | `sf_2` | Split freq 3 (Hz) | 100 |
| 34 | `cbe_3` | Split enable 4 | 0 |
| 35 | `sf_3` | Split freq 4 (Hz) | 252 |
| 36 | `cbe_4` | Split enable 5 | 1 |
| 37 | `sf_4` | Split freq 5 (Hz) | 632 |
| 38 | `cbe_5` | Split enable 6 | 0 |
| 39 | `sf_5` | Split freq 6 (Hz) | 1587 |
| 40 | `cbe_6` | Split enable 7 | 1 |
| 41 | `sf_6` | Split freq 7 (Hz) | 3984 |
| 42 | `cbe_7` | Split enable 8 | 0 |
| 43 | `sf_7` | Split freq 8 (Hz) | 10000 |

**CRITICAL — LSP split-frequency model:**
To get 4 bands at 120 Hz, 500 Hz, 3 kHz splits:
- `cbe_1=1, sf_1=120` (split band 1/2)
- `cbe_2=1, sf_2=500` (split band 2/3)
- `cbe_3=1, sf_3=3000` (split band 3/4)
- `cbe_4=0` (disable remaining splits)

Band 1 is below sf_1, Band N is between sf_(N-1) and sf_N, Band 8 is above sf_7.

**Per-band control ports — Band N (N = 0–7):**

Each band has 28 ports. Base port index for band N = 44 + N*28.

| Offset | Symbol | Range | Default | Notes |
|--------|--------|-------|---------|-------|
| +0–+10 | `sce_N`…`schf_N` | — | — | SC source/cut settings (leave at defaults) |
| +11 | `cm_N` | 0=Down,1=Up,2=Boost | 0 | Compression mode |
| +12 | `ce_N` | 0/1 | 1 | Per-band enable |
| +13 | `bs_N` | 0/1 | 0 | Solo |
| +14 | `bm_N` | 0/1 | 0 | Mute |
| +15 | `al_N` | 0.001–1.0 | 0.251 (~-12dB) | Attack threshold (LINEAR GAIN, not dB!) |
| +16 | `at_N` | 0–2000 ms | 20 | Attack time |
| +17 | `rrl_N` | 0–63.1 | 0 | Release threshold |
| +18 | `rt_N` | 0–5000 ms | 100 | Release time |
| +19 | `ht_N` | 0–1000 ms | 0 | Hold time |
| +20 | `cr_N` | 1.0–100.0 | 1.0 | Ratio (linear) |
| +21 | `kn_N` | 0.063–1.0 | 0.501 (~6dB) | Knee (linear gain) |
| +22–+23 | `bth_N`,`bsa_N` | — | — | Boost params (leave default) |
| +24 | `mk_N` | 0.001–1000 | 1.0 | Makeup gain (linear) |

**Threshold conversion formula:**
`al = 10^(threshold_dB/20)`. Default `al=0.251` => ~-12 dB. `al=0.1` => -20 dB.

#### 7.2.3 Fallback Logic (in generator.py)

```python
def resolve_mb_compressor() -> tuple[str | None, str | None]:
    mb_ttl = Path("/usr/lib/lv2/lsp-plugins.lv2/mb_compressor_stereo.ttl")
    sc_ttl = Path("/usr/lib/lv2/lsp-plugins.lv2/compressor_stereo.ttl")
    if mb_ttl.exists():
        return ("mb_compressor_stereo", "LSP Multiband Compressor x8")
    elif sc_ttl.exists():
        return ("compressor_stereo", "LSP Compressor (single-band fallback)")
    else:
        return (None, None)  # Skip stage entirely
```

When single-band fallback is used, apply mid-band (band 2, 500–3000 Hz) parameters.

#### 7.2.4 DAX3 XML Integration

The existing `parser.py` already parses `<mb-compressor-tuning>` `<band_group_N>` into
`MBCompressorBand` objects. Mapping to LSP port symbols:

| DAX3 field | LSP symbol | Conversion |
|-----------|-----------|------------|
| `threshold` | `al` | `10^(threshold/20)` — dB to linear gain |
| `ratio` | `cr` | Pass-through (already linear) |
| `attack` | `at` | Pass-through (both ms) |
| `release` | `rt` | Pass-through (both ms) |
| `knee` | `kn` | `10^(knee/20)` — dB to linear gain |
| `makeup_gain` | `mk` | `10^(makeup_gain/20)` — dB to linear gain |

#### 7.2.5 PipeWire Filter-Chain Node (SPA-JSON)

```json
{
    type = lv2
    name = mb_comp
    plugin = "http://lsp-plug.in/plugins/lv2/mb_compressor_stereo"
    control = {
        "enabled" = 1
        "mode"    = 0       # Classic (IIR, zero latency)
        "g_in"    = 1.0
        "g_out"   = 1.0
        "g_dry"   = 0.0
        "g_wet"   = 1.0
        "envb"    = 1       # Pink BT (+3dB/oct)
        "ssplit"  = 0       # Linked stereo
        # 4-band splits: <120, 120-500, 500-3000, >3000 Hz
        "cbe_1"   = 1
        "sf_1"    = 120.0
        "cbe_2"   = 1
        "sf_2"    = 500.0
        "cbe_3"   = 1
        "sf_3"    = 3000.0
        "cbe_4"   = 0
        "cbe_5"   = 0
        "cbe_6"   = 0
        "cbe_7"   = 0
        # Band 0 (sub-bass, <120 Hz)
        "ce_0"    = 1
        "al_0"    = 0.100   # ~-20 dB
        "at_0"    = 20.0
        "rt_0"    = 80.0
        "cr_0"    = 2.0
        "kn_0"    = 0.501   # ~6 dB knee
        "mk_0"    = 1.413   # +3 dB makeup
        # Band 1 (bass, 120-500 Hz)
        "ce_1"    = 1
        "al_1"    = 0.178
        "at_1"    = 15.0
        "rt_1"    = 60.0
        "cr_1"    = 1.5
        "kn_1"    = 0.630
        "mk_1"    = 1.0
        # Band 2 (mid, 500-3000 Hz)
        "ce_2"    = 1
        "al_2"    = 0.251
        "at_2"    = 10.0
        "rt_2"    = 40.0
        "cr_2"    = 1.2
        "kn_2"    = 0.794
        "mk_2"    = 1.0
        # Band 3 (treble, >3000 Hz)
        "ce_3"    = 1
        "al_3"    = 0.178
        "at_3"    = 5.0
        "rt_3"    = 30.0
        "cr_3"    = 1.5
        "kn_3"    = 0.630
        "mk_3"    = 1.0
    }
}
```


### 7.3 Stage 5: Stereo Enhancement — M/S Width Control

#### 7.3.1 Decision: PipeWire Builtins Over LV2

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| LSP Stereo Tools LV2 | Purpose-built, one node | Not installed; adds LV2 overhead | NO |
| Custom C SPA plugin | Efficient, single node | Dev effort; maintenance burden | Future |
| **PipeWire builtin M/S** | Zero latency, no deps, proven | 8 nodes; unwieldy config | **YES** |

M/S matrix is six multiply-adds per sample — simpler than any LV2 plugin.
The 8-node approach adds zero measurable latency. Can replace with C plugin later.

#### 7.3.2 M/S Matrix Topology

```
                    [copy_L]
  L_in ------------>|     |---+
                    [-----]   |       [mix_M:G1=0.5(L),G2=0.5(R)]
                              +------>| M = (L+R)/2 |---+
                              |       [-------------]   |
                    [copy_R]  |                          |
  R_in ------------>|     |---+                          |
                    [-----]  |       [mix_S:G1=0.5(L),G2=-0.5(R)]  [side_gain:Mult=width]
                              +------>| S = (L-R)/2 |--------------->|                |---+
                                      [-------------]                [----------------]   |
                                                                                          |
  +---------------------------------------------------------------------------------------+
  |                              [mix_Lout:G1=1.0(M),G2=1.0(S*gain)]
  +----------------------------->| L_out = M + S*w |---> L_out
  |  +-------------------------->| R_out = M - S*w |---> R_out
  |  |                           [mix_Rout:G1=1.0(M),G2=-1.0(S*gain)]
  |  |
  |  +-- (side_gain output fan-out to both mixers)
  |
  +-- (mix_M output fan-out to both mixers)
```

**Width control:** `side_gain.Mult` = stereo width:
- 0.0 -> mono (L=R=M)
- 1.0 -> passthrough (original stereo)
- 2.0 -> double width (aggressive)

#### 7.3.3 Filter-Chain Node Definitions

```json
{ type = builtin  name = st_copy_L   label = copy }
{ type = builtin  name = st_copy_R   label = copy }
{ type = builtin  name = st_mix_M    label = mixer  control = { "Gain 1" = 0.5  "Gain 2" = 0.5 } }
{ type = builtin  name = st_mix_S    label = mixer  control = { "Gain 1" = 0.5  "Gain 2" = -0.5 } }
{ type = builtin  name = st_side_gain  label = linear  control = { "Mult" = 1.2  "Add" = 0.0 } }
{ type = builtin  name = st_mix_Lout label = mixer  control = { "Gain 1" = 1.0  "Gain 2" = 1.0 } }
{ type = builtin  name = st_mix_Rout label = mixer  control = { "Gain 1" = 1.0  "Gain 2" = -1.0 } }
```

#### 7.3.4 Links

```
{ output = "mb_comp:out_l"       input = "st_copy_L:In" }
{ output = "mb_comp:out_r"       input = "st_copy_R:In" }
{ output = "st_copy_L:Out"       input = "st_mix_M:In 1" }
{ output = "st_copy_R:Out"       input = "st_mix_M:In 2" }
{ output = "st_copy_L:Out"       input = "st_mix_S:In 1" }
{ output = "st_copy_R:Out"       input = "st_mix_S:In 2" }
{ output = "st_mix_S:Out"        input = "st_side_gain:In" }
{ output = "st_mix_M:Out"        input = "st_mix_Lout:In 1" }
{ output = "st_mix_M:Out"        input = "st_mix_Rout:In 1" }
{ output = "st_side_gain:Out"    input = "st_mix_Lout:In 2" }
{ output = "st_side_gain:Out"    input = "st_mix_Rout:In 2" }
```

Fan-out (one output -> multiple inputs) is supported by PipeWire filter-chain.

#### 7.3.5 DAX3 Surround Boost Mapping

```python
width = 1.0 + surround_boost * 1.0  # 1.0 at boost=0, 2.0 at boost=1.0
width = max(0.0, min(3.0, width))   # Clamp to prevent over-widening
```

---

### 7.4 Stage 6: Bass Enhancer — Custom C SPA Plugin

#### 7.4.1 Technology Decision

| Option | Feasibility | Quality | Latency | Verdict |
|--------|------------|---------|---------|---------|
| **Custom C SPA plugin** | Best | High | 0 samples | **PRIMARY** |
| CALF Bass Enhancer LV2 | Not installed | Medium | ~256 samples | Fallback |
| Pre-baked IR convolver | Always works | Low | 128+ samples | Last resort |

MaxxBass patent (US 5,930,373) expired 2020. Algorithm is now public domain:
LPF -> waveshape -> HPF -> mix with dry. ~200 lines of C. SPA plugin runs
directly in PipeWire RT graph with zero context switches.

#### 7.4.2 Source Layout

```
src/dsp/
|-- meson.build
|-- include/
|   `-- da4linux/
|       `-- bass_enhancer.h
|-- bass_enhancer.c           # Core DSP: filtering + waveshaping
|-- spa_bass_enhancer.c       # SPA plugin boilerplate
`-- test/
    `-- test_bass_enhancer.c
```

#### 7.4.3 SPA Plugin API Surface (Minimum)

```c
// spa_bass_enhancer.c — Entry points
#include <spa/support/plugin.h>
#include <spa/node/node.h>
#include <spa/node/utils.h>
#include <spa/node/io.h>
#include <spa/param/audio/format-utils.h>

// Per-instance data (RT-safe: no alloc in process())
struct bass_enhancer_data {
    struct spa_handle  handle;
    struct spa_node    node;
    struct spa_hook_list hooks;

    // Parameters (updated from non-RT thread via set_param)
    float crossover_freq;     // Hz, default 150
    float harmonic_amount;    // 0.0–1.0, default 0.3
    int   harmonic_order;     // 2,3,4

    // RT filter states (2nd-order Butterworth biquads)
    float lp_b0, lp_b1, lp_b2, lp_a1, lp_a2; // Lowpass coeffs
    float hp_b0, hp_b1, hp_b2, hp_a1, hp_a2; // Highpass coeffs
    float lp_z[2][2];  // L/R channel, 2 delay states
    float hp_z[2][2];

    float dry_level;
    float wet_level;
};

// Exported factory descriptor
extern const struct spa_handle_factory spa_bass_enhancer_factory;

// Required methods:
//   spa_node_init      — allocate resources
//   spa_node_process   — THE REAL-TIME AUDIO CALLBACK
//   spa_node_port_enum_params  — describe parameters
//   spa_node_port_set_param    — update parameters (non-RT)
//   spa_node_get_io_flags      — declare RT-safe, no alloc
```

#### 7.4.4 Core DSP Algorithm

```c
static inline float
bass_enhance_sample(float dry, float lp_z[2], float hp_z[2],
                    const float *lp_c, const float *hp_c,
                    float amount)
{
    // 1. Butterworth 2nd-order lowpass (transposed DF-II)
    float bass = lp_c[0]*dry + lp_c[1]*lp_z[0] + lp_c[2]*lp_z[1]
               - lp_c[3]*lp_z[0] - lp_c[4]*lp_z[1];
    lp_z[1] = lp_z[0];
    lp_z[0] = bass;

    // 2. Cubic soft-clipper -> odd harmonics
    float shaped = bass - (amount * bass * bass * bass / 3.0f);

    // 3. Butterworth 2nd-order highpass -> keep only harmonics
    float harm = hp_c[0]*shaped + hp_c[1]*hp_z[0] + hp_c[2]*hp_z[1]
               - hp_c[3]*hp_z[0] - hp_c[4]*hp_z[1];
    hp_z[1] = hp_z[0];
    hp_z[0] = harm;

    // 4. Mix dry + harmonics
    return dry + amount * harm;
}
```

#### 7.4.5 Coefficients Calculation

```c
// Precompute biquad coefficients from crossover frequency
// Called from set_param (non-RT), not from process()
void compute_coeffs(float freq_hz, float sample_rate, float *lp, float *hp) {
    float w0 = 2.0f * M_PI * freq_hz / sample_rate;
    float alpha = sinf(w0) / sqrtf(2.0f); // Q = 0.7071 (Butterworth)

    // Lowpass
    float cosw = cosf(w0);
    float a0_inv = 1.0f / (1.0f + alpha);
    lp[0] = (1.0f - cosw) * 0.5f * a0_inv;   // b0
    lp[1] = (1.0f - cosw) * a0_inv;           // b1 (= 2*b0 for bilinear)
    lp[2] = lp[0];                             // b2
    lp[3] = 2.0f * cosw * a0_inv;              // -a1 (negated for DF-II)
    lp[4] = (alpha - 1.0f) * a0_inv;           // -a2

    // Highpass
    float a0_inv_hp = 1.0f / (1.0f + alpha);
    hp[0] = (1.0f + cosw) * 0.5f * a0_inv_hp;
    hp[1] = -(1.0f + cosw) * a0_inv_hp;
    hp[2] = hp[0];
    hp[3] = 2.0f * cosw * a0_inv_hp;
    hp[4] = (alpha - 1.0f) * a0_inv_hp;
}
```

#### 7.4.6 Meson Build

```meson
# src/dsp/meson.build
project('da4linux-dsp', 'c',
  version: '0.2.0',
  license: 'GPL-3.0-only',
  default_options: ['c_std=c11', 'warning_level=3', 'buildtype=debugoptimized']
)

cc = meson.get_compiler('c')
m_dep = cc.find_library('m', required: true)
spa_dep = dependency('libspa-0.2', required: true, version: '>=0.2')

spa_bass = shared_module('spa-bass-enhancer',
  sources: ['bass_enhancer.c', 'spa_bass_enhancer.c'],
  include_directories: include_directories('include'),
  dependencies: [m_dep, spa_dep],
  install: true,
  install_dir: get_option('libdir') / 'spa-0.2' / 'da4linux',
  name_prefix: '',
)

test_bass = executable('test_bass_enhancer',
  'test/test_bass_enhancer.c',
  link_with: spa_bass,
  dependencies: [m_dep],
)
test('bass_enhancer', test_bass)
```

Install path: `/usr/lib/x86_64-linux-gnu/spa-0.2/da4linux/spa-bass-enhancer.so`

#### 7.4.7 Filter-Chain Integration

SPA plugins in filter-chain: Use `type = adapter` with `factory.name = "adapter"`
and `node.library` pointing to the SPA plugin. The exact config format may vary
between PipeWire 1.0 and 1.2 — verify at implementation time.

Fallback chain:
1. Try SPA plugin: check `spa-bass-enhancer.so` in SPA plugin path
2. Try CALF LV2: check for `http://calf.sourceforge.net/plugins/BassEnhancer`
3. Passthrough: `builtin:linear` with `Mult=1.0`

---

### 7.5 Stage 7: Loudness Compensation — EBU R128 + ISO 226

#### 7.5.1 Architecture

Two sub-components, independently operable:

```
                   [ebur128 meter]  -> Shortterm LUFS
                          |
                   [lufs2gain]      -> Gain (target: -14 LUFS)
                          |
                   [linear node]    -> Apply gain to L/R audio
                          |
              [ISO 226 Dynamic EQ]  -> Phase 3: Fletcher-Munson curves
              (custom C SPA plugin)    Reads system volume metadata
                                       Bass/treble boost at low levels
```

#### 7.5.2 EBU R128 Integration (Phase 2)

PipeWire `ebur128` builtin type:
- `label = ebur128` — meter node, outputs LUFS control values
- `label = lufs2gain` — converts LUFS to linear gain multiplier

**Best-effort filter-chain config:**

```json
{ type = ebur128  name = lufs_meter  label = ebur128
  config = { "max-history" = 10.0  "max-window" = 3.0 } }
{ type = ebur128  name = lufs2gain  label = lufs2gain
  control = { "Target LUFS" = -14.0 } }
{ type = builtin  name = lou_gain_L  label = linear }
{ type = builtin  name = lou_gain_R  label = linear }
```

**Control signal routing (verify with PipeWire >=1.0):**
```
{ output = "lufs_meter:Shortterm LUFS"  input = "lufs2gain:LUFS" }
{ output = "lufs2gain:Gain"             input = "lou_gain_L:Control" }
{ output = "lufs2gain:Gain"             input = "lou_gain_R:Control" }
```

**KNOWN RISK:** `ebur128` in real-time filter-chain may not work reliably in
PipeWire 1.0.x. If so, Phase 2 fallback is static gain only. Phase 3 replaces
with ISO 226 which is fully self-contained.

#### 7.5.3 ISO 226 Dynamic Loudness EQ (Phase 3)

Custom C SPA plugin implementing ISO 226:2023 equal-loudness contours:
1. Reads system volume from PipeWire metadata or ALSA mixer
2. Computes target curve for that volume level (20–80 phon range)
3. Applies dynamic bass boost (low volume) -> flat (high volume)
4. Smooth interpolation with ~500 ms time constant

**Key characteristic:** At 40 phon, 100 Hz needs ~+12 dB relative to 1 kHz.
At 80 phon, 100 Hz needs only ~+3 dB. Bass boost naturally decreases as
volume increases — exactly what Fletcher-Munson predicts.

Volume metadata:
- Read `pipewire.sec.default-sink-volume` on session start
- Subscribe to metadata changes for real-time updates
- Fallback: ALSA mixer `Master` control

#### 7.5.4 Bypass Behavior

On ebur128 failure: collapse to `linear` passthrough (Mult=1.0).
User can set static gain manually via CLI.

---

### 7.6 Stage 8: Dialogue Enhancement — Center Channel Extraction

#### 7.6.1 Algorithm

Dialogue is typically center-panned (equal L+R). Enhancement strategy:
1. **M/S Decode:** Split L/R into M (mono sum) and S (stereo difference)
2. **Mid boost:** Peaking EQ at 2 kHz (voice formant), Q=1.0, +3 to +6 dB on M
3. **Optional S attenuation:** High-shelf cut on Side channel to reduce ambience
4. **M/S Encode:** Reconstruct L = M+S, R = M-S

#### 7.6.2 Technology: Builtin M/S Matrix + Biquads

Same M/S topology as Stage 5 (Stereo Enhancer). No LV2 plugin needed.
M/S math is identical — only the parameters differ.

Voicing EQ on Mid channel:
- Type: `builtin:bq_peaking`
- Center: 2000 Hz (adjustable 300–4000 Hz)
- Q: 0.7–1.5 (default 1.0)
- Gain: 0 to +6 dB (default +3.0)

#### 7.6.3 Separate M/S Stages (Not Shared)

Despite both stages using M/S, separate infrastructure is preferred:
- **Option A (chosen): Separate M/S stages.** Independent, non-interfering controls.
- **Option B (rejected): Single compound M/S stage.** Fewer nodes (9 vs 14) but
  parameter space becomes hard to reason about.

**Nodes are cheap.** Clarity beats node count.

#### 7.6.4 Filter-Chain Node Definitions

```json
# M/S encode
{ type = builtin  name = dl_copy_L   label = copy }
{ type = builtin  name = dl_copy_R   label = copy }
{ type = builtin  name = dl_mix_M    label = mixer  control = { "Gain 1" = 0.5  "Gain 2" = 0.5 } }
{ type = builtin  name = dl_mix_S    label = mixer  control = { "Gain 1" = 0.5  "Gain 2" = -0.5 } }
# Voice boost on Mid
{ type = builtin  name = dl_voice    label = bq_peaking
  control = { "Freq" = 2000.0  "Gain" = 3.0  "Q" = 1.0 } }
# Ambience attenuation on Side (optional)
{ type = builtin  name = dl_amb      label = bq_highshelf
  control = { "Freq" = 300.0  "Gain" = -2.0  "Q" = 0.7 } }
# M/S decode
{ type = builtin  name = dl_mix_Lout label = mixer  control = { "Gain 1" = 1.0  "Gain 2" = 1.0 } }
{ type = builtin  name = dl_mix_Rout label = mixer  control = { "Gain 1" = 1.0  "Gain 2" = -1.0 } }
```

**Links:**
```
{ output = "lou_gain_L:Out"   input = "dl_copy_L:In" }
{ output = "lou_gain_R:Out"   input = "dl_copy_R:In" }
{ output = "dl_copy_L:Out"    input = "dl_mix_M:In 1" }
{ output = "dl_copy_R:Out"    input = "dl_mix_M:In 2" }
{ output = "dl_copy_L:Out"    input = "dl_mix_S:In 1" }
{ output = "dl_copy_R:Out"    input = "dl_mix_S:In 2" }
{ output = "dl_mix_M:Out"     input = "dl_voice:In" }
{ output = "dl_mix_S:Out"     input = "dl_amb:In" }
{ output = "dl_voice:Out"     input = "dl_mix_Lout:In 1" }
{ output = "dl_voice:Out"     input = "dl_mix_Rout:In 1" }
{ output = "dl_amb:Out"       input = "dl_mix_Lout:In 2" }
{ output = "dl_amb:Out"       input = "dl_mix_Rout:In 2" }
```

#### 7.6.5 DAX3 Integration

```python
dialogue_gain_db = dialog_enhancer * 6.0  # 0 dB at 0.0, +6 dB at 1.0
```

---

### 7.7 Stage 9: Virtual Surround — SOFA HRTF Spatialization

#### 7.7.1 Technology Decision

| Option | Latency | Quality | Dependencies | Verdict |
|--------|---------|---------|-------------|---------|
| **builtin:sofa/spatializer** | 128-256 samples | Good (HRTF) | libmysofa | **PRIMARY** |
| builtin:convolver (pre-baked IR) | 128 samples | Medium (static) | None | Fallback |
| LSP Room Builder LV2 | 1024+ samples | Excellent | LSP Plugins | Too much latency |

PipeWire filter-chain `sofa` builtin instantiates a `spatializer` node using
libmysofa to load SOFA-format HRTF files.

#### 7.7.2 SOFA File Requirements

- Format: SOFA v2.1 (SimpleFreeFieldHRIR or similar)
- Sample rate: Must match processing chain (48 kHz)
- Licensing: **CANNOT bundle.** User-provided or auto-downloaded.
- Source: SADIE II database (CC0), https://www.york.ac.uk/sadie-project/database.html
- Default path: `~/.config/da4linux/sofa/HRTF.sofa`

#### 7.7.3 Headphone Auto-Detection

The virtual surround stage is **only** engaged when headphones are detected.

Detection strategies (in priority order):
1. **ALSA jack sensing:** Parse `/proc/asound/card0/codec#0` for
   `Pin-ctls: 0xc0: OUT HP` (headphone) vs `Pin-ctls: 0x40: OUT` (speaker)
2. **PipeWire sink properties:** Check for `headphone` in node name or
   `alsa.id` values
3. **WirePlumber routing:** Default sink name pattern matching

```python
def detect_headphones() -> bool:
    codec = Path("/proc/asound/card0/codec#0")
    if codec.exists():
        content = codec.read_text()
        if re.search(r'Pin.*Headphone.*Present', content, re.IGNORECASE):
            return True
    return False
```

#### 7.7.4 Filter-Chain Node Definition

```json
{
    type = sofa
    name = hrtf
    label = spatializer
    config = {
        "filename"   = "/home/user/.config/da4linux/sofa/HRTF.sofa"
        "blocksize"  = 256
        "gain"       = -3.0         # Headroom for HRTF peaks
        "normalize"  = true
        "azimuth"    = 0
        "elevation"  = 0
    }
}
```

Audio ports: `In L`, `In R` -> `Out L`, `Out R`.

#### 7.7.5 Bypass Strategy: Graph Omission

When headphones are NOT detected, the sofa node is **excluded from the graph
entirely.** It is NOT replaced with a passthrough. Reason: the sofa node
allocates FFT buffers and adds latency even when disabled.

```python
if detect_headphones() and stage_config["surround"]["enabled"]:
    # Include sofa spatializer, link: dialogue_out -> sofa_in -> sofa_out -> limiter_in
else:
    # Direct link: dialogue_out -> limiter_in
```

#### 7.7.6 HeSuVi Fallback (Windows HRIR files)

HeSuVi uses .wav impulse responses. To support:
1. Convert .wav HRIR to .sofa via `scripts/hrir_to_sofa.py`
2. Requires `python-sofa` package
3. **Decision: Defer to Phase 4.** SOFA is the standard format.

---

### 7.8 Stage Bypass Strategy

#### 7.8.1 Design Principle

Every stage is independently toggleable. The bypass strategy must:
1. Maintain consistent graph topology (same node names regardless of state)
2. Add zero additional latency when disabled
3. Be resolvable at config generation time (no runtime graph edits)

#### 7.8.2 Implementation Table

| Stage | When Enabled | When Disabled |
|-------|-------------|---------------|
| Input Gain | `linear` with configured Mult | `linear` with Mult=1.0 |
| FIR Convolver | `convolver` with IR file | `linear` with Mult=1.0 |
| Parametric EQ | `param_eq` with filter array | `linear` with Mult=1.0 |
| MB Compressor | LV2 node | `linear` with Mult=1.0 |
| Stereo Enhancer | Full M/S matrix (8 nodes) | Two `linear` nodes (L/R passthrough) |
| Bass Enhancer | SPA/LV2 node | `linear` with Mult=1.0 |
| Loudness Comp | ebur128 + linear chain | `linear` with Mult=1.0 |
| Dialogue Enhancer | M/S matrix + EQ (8 nodes) | Two `linear` nodes (L/R passthrough) |
| Virtual Surround | `sofa` node | **Omitted entirely** (no node) |
| Output Limiter | LV2 node | `linear` with Mult=1.0 |

**Why omit VR:** The `sofa` node allocates FFT buffers and adds latency even
when configured to bypass. Omitting it avoids the latency penalty on speakers.

**ALS (Always-Linear-Stub) pattern:** When a stage is represented as `linear`
passthrough when disabled, the node name stays the same as when enabled.
The link table remains unchanged — no conditional links needed.

#### 7.8.3 CLI Stage Selection

```bash
# Enable specific stages (default: all)
da4linux generate --stages fir,peq,mbcomp,limiter

# Disable specific stages
da4linux generate --disable bass,surround

# Full listing with mode selection
da4linux generate --stages all --disable surround --mode headphone
```

**Stage name aliases (in `cli.py`):**

```python
STAGE_NAMES = {
    "fir":       "convolver",
    "peq":       "param_eq",
    "mbcomp":    "mb_compressor",
    "stereo":    "stereo_enhancer",
    "bass":      "bass_enhancer",
    "loudness":  "loudness_compensation",
    "dialogue":  "dialogue_enhancer",
    "surround":  "virtual_surround",
    "limiter":   "output_limiter",
}
DEFAULT_ENABLED = {"fir", "peq", "mbcomp", "stereo", "bass",
                    "loudness", "dialogue", "limiter"}
# Note: "surround" is NOT in DEFAULT_ENABLED — requires explicit --enable surround
```

---

### 7.9 Profile Format -- Phase 2+3 Extensions

#### 7.9.1 Updated Dataclasses

The existing Phase 1 `DAX3Profile` dataclass (`parser.py`) is extended with
new stage configuration types. New dataclasses to add to `parser.py`:

```python
@dataclass
class MBCompressorBand:
    enabled: bool = True
    freq_low_hz: float = 0.0
    freq_high_hz: float = 0.0
    threshold_db: float = -12.0
    ratio: float = 1.5
    attack_ms: float = 10.0
    release_ms: float = 50.0
    knee_db: float = 6.0
    makeup_db: float = 0.0

@dataclass
class StereoConfig:
    enabled: bool = True
    width: float = 1.0            # 0.0 (mono) to 3.0 (very wide)

@dataclass
class BassConfig:
    enabled: bool = True
    crossover_hz: float = 150.0
    amount: float = 0.3           # 0.0 to 1.0
    harmonic_order: int = 3        # 2, 3, or 4

@dataclass
class LoudnessConfig:
    enabled: bool = True
    target_lufs: float = -14.0
    use_iso226: bool = False       # Phase 3 flag

@dataclass
class DialogueConfig:
    enabled: bool = False          # Off by default (music mode)
    boost_db: float = 3.0          # 0 to +6 dB
    center_hz: float = 2000.0
    q: float = 1.0
    side_cut_db: float = 0.0

@dataclass
class SurroundConfig:
    enabled: bool = False          # Off by default (speakers)
    sofa_file: str = ""
    gain_db: float = -3.0
    auto_detect: bool = True
```

Extended `DAX3Profile` dataclass:

```python
@dataclass
class DAX3Profile:
    # === Phase 1 fields (unchanged) ===
    name: str = ""
    endpoint_type: str = ""
    peq_bands: list[PEQBand] = field(default_factory=list)
    ao_bands: list[AudioOptimizerBand] = field(default_factory=list)
    volmax_boost: float = 0.0
    regulator: RegulatorSettings = field(default_factory=RegulatorSettings)

    # === Phase 2 fields ===
    mb_compressor_bands: list[MBCompressorBand] = field(default_factory=list)
    stereo: StereoConfig = field(default_factory=StereoConfig)
    bass: BassConfig = field(default_factory=BassConfig)
    loudness: LoudnessConfig = field(default_factory=LoudnessConfig)

    # === Phase 3 fields ===
    dialogue: DialogueConfig = field(default_factory=DialogueConfig)
    surround: SurroundConfig = field(default_factory=SurroundConfig)

    # === DAX3 raw parsed values (for mapping) ===
    ieq_enabled: bool = False
    ieq_amount: float = 0.0
    ieq_curve: list[float] = field(default_factory=list)
    dialog_enhancer: float = 0.0
    volume_leveler: float = 0.0
    surround_boost: float = 0.0
```

#### 7.9.2 Mode-Specific Defaults

```python
MODE_DEFAULTS = {
    "music": {
        "mb_compressor_bands": [
            {"freq_low_hz": 20, "freq_high_hz": 120, "threshold_db": -20,
             "ratio": 2.0, "attack_ms": 20, "release_ms": 80, "makeup_db": 3.0},
            {"freq_low_hz": 120, "freq_high_hz": 500, "threshold_db": -15,
             "ratio": 1.5, "attack_ms": 15, "release_ms": 60},
            {"freq_low_hz": 500, "freq_high_hz": 3000, "threshold_db": -12,
             "ratio": 1.2, "attack_ms": 10, "release_ms": 40},
            {"freq_low_hz": 3000, "freq_high_hz": 20000, "threshold_db": -15,
             "ratio": 1.5, "attack_ms": 5, "release_ms": 30},
        ],
        "stereo": {"enabled": True, "width": 1.0},
        "bass": {"enabled": True, "crossover_hz": 150, "amount": 0.3},
        "loudness": {"enabled": True, "target_lufs": -14, "use_iso226": False},
        "dialogue": {"enabled": False},
        "surround": {"enabled": False},
    },
    "movie": {
        "mb_compressor_bands": [
            {"freq_low_hz": 20, "freq_high_hz": 120, "threshold_db": -18,
             "ratio": 3.0, "attack_ms": 30, "release_ms": 120, "makeup_db": 3.0},
            {"freq_low_hz": 120, "freq_high_hz": 500, "threshold_db": -12,
             "ratio": 2.0, "attack_ms": 20, "release_ms": 80},
            {"freq_low_hz": 500, "freq_high_hz": 3000, "threshold_db": -8,
             "ratio": 1.8, "attack_ms": 15, "release_ms": 60},
            {"freq_low_hz": 3000, "freq_high_hz": 20000, "threshold_db": -12,
             "ratio": 2.0, "attack_ms": 10, "release_ms": 40},
        ],
        "stereo": {"enabled": True, "width": 1.3},
        "bass": {"enabled": True, "crossover_hz": 120, "amount": 0.5},
        "loudness": {"enabled": True, "target_lufs": -23},
        "dialogue": {"enabled": True, "boost_db": 4.0, "center_hz": 2000, "q": 0.8},
        "surround": {"enabled": True, "auto_detect": True},
    },
    "voice": {
        "mb_compressor_bands": [
            {"freq_low_hz": 20, "freq_high_hz": 120, "threshold_db": -24,
             "ratio": 1.5, "attack_ms": 30, "release_ms": 100},
            {"freq_low_hz": 120, "freq_high_hz": 500, "threshold_db": -20,
             "ratio": 1.2, "attack_ms": 20, "release_ms": 80},
            {"freq_low_hz": 500, "freq_high_hz": 3000, "threshold_db": -15,
             "ratio": 1.5, "attack_ms": 15, "release_ms": 60},
            {"freq_low_hz": 3000, "freq_high_hz": 20000, "threshold_db": -20,
             "ratio": 1.2, "attack_ms": 10, "release_ms": 40},
        ],
        "stereo": {"enabled": False},
        "bass": {"enabled": True, "amount": 0.2},
        "loudness": {"enabled": True, "target_lufs": -16},
        "dialogue": {"enabled": True, "boost_db": 6.0,
                     "center_hz": 1500, "q": 1.2, "side_cut_db": -3.0},
        "surround": {"enabled": False},
    },
}
```

#### 7.9.3 User Override File (`~/.config/da4linux/config.yaml`)

```yaml
# User preferences -- override mode defaults
mode: music           # music | movie | voice | auto
latency: medium       # low | medium | high

# Per-stage overrides (optional)
overrides:
  bass:
    amount: 0.5
  stereo:
    width: 1.3
  loudness:
    target_lufs: -16.0
  dialogue:
    enabled: true
  surround:
    sofa_file: "~/.config/da4linux/sofa/my_HRTF.sofa"
```

---

### 7.10 Implementation Plan — Phase 2+3 Tasks

#### Phase 2: Dynamics & Enhancement (3-4 weeks)

| # | Task | File(s) | Owner | Effort |
|---|------|---------|-------|--------|
| P2-1 | Extend `parser.py` with Phase 2 dataclasses (MBCompressorBand, StereoConfig, BassConfig, LoudnessConfig) | `src/da4linux/parser.py` | @coder | 2h |
| P2-2 | Add MB comp LV2 port symbol constants and threshold conversion helpers | `src/da4linux/constants.py` | @coder | 1h |
| P2-3 | Implement `resolve_mb_compressor()` fallback logic in generator | `src/da4linux/generator.py` | @coder | 2h |
| P2-4 | Generate MB compressor filter-chain config from per-band settings | `src/da4linux/generator.py` | @coder | 4h |
| P2-5 | Implement M/S stereo enhancer node generation (8-node topology) | `src/da4linux/generator.py` | @coder | 3h |
| P2-6 | Create C SPA bass enhancer plugin skeleton (SPA interface) | `src/dsp/spa_bass_enhancer.c` | @coder (C) | 8h |
| P2-7 | Implement core bass enhancer DSP (biquads + waveshaper) | `src/dsp/bass_enhancer.c` | @coder (C) | 6h |
| P2-8 | Meson build for SPA plugin | `src/dsp/meson.build` | @coder | 2h |
| P2-9 | EBU R128 filter-chain integration (ebur128 + lufs2gain) | `src/da4linux/generator.py` | @coder | 4h |
| P2-10 | Stage bypass logic: ALS (Always-Linear-Stub) pattern | `src/da4linux/generator.py` | @coder | 3h |
| P2-11 | CLI: `--stages` and `--disable` flags | `src/da4linux/cli.py` | @coder | 2h |
| P2-12 | CLI: `--mode music|movie|voice` flag with MODE_DEFAULTS | `src/da4linux/cli.py` | @coder | 2h |
| P2-13 | Update `profiles/__init__.py` with Phase 2 mode defaults | `src/da4linux/profiles/__init__.py` | @coder | 2h |
| P2-14 | Integration test: end-to-end config generation for all modes | `tests/test_generator.py` | @scout | 4h |
| P2-15 | Test on target hardware (ThinkPad T14s) with all LSP plugins | @scout | 4h |

#### Phase 3: Spatial & Intelligence (4-6 weeks)

| # | Task | File(s) | Owner | Effort |
|---|------|---------|-------|--------|
| P3-1 | Implement dialogue enhancer M/S + voice EQ node generation | `src/da4linux/generator.py` | @coder | 3h |
| P3-2 | Implement SOFA spatializer config generation | `src/da4linux/generator.py` | @coder | 2h |
| P3-3 | Headphone auto-detection via ALSA jack sensing | `src/da4linux/detect.py` | @coder | 3h |
| P3-4 | Conditional VR inclusion (only when headphones detected) | `src/da4linux/generator.py` | @coder | 2h |
| P3-5 | SOFA file downloader script (SADIE II database) | `scripts/download_sofa.py` | @coder | 2h |
| P3-6 | Implement ISO 226 dynamic EQ (Volume->Loudness mapper) | `src/dsp/loudness_iso226.c` | @coder (C) | 10h |
| P3-7 | SPA plugin wrapper for ISO 226 | `src/dsp/spa_loudness_iso226.c` | @coder (C) | 6h |
| P3-8 | Volume metadata subscription (PipeWire + ALSA fallback) | `src/dsp/volume_monitor.c` | @coder (C) | 4h |
| P3-9 | Bass enhancer Phase 3 enhancements (Chebyshev, per-channel) | `src/dsp/bass_enhancer.c` | @coder (C) | 4h |
| P3-10 | WirePlumber Lua policy: auto-switch profile on sink change | `src/service/wireplumber/50-da4linux.lua` | @researcher | 4h |
| P3-11 | Systemd user service with auto-start on login | `src/service/da4linux.service` | @coder | 2h |
| P3-12 | Integration test: full 10-stage chain with all Phase 3 features | `tests/` | @scout | 6h |
| P3-13 | Latency measurement (pw-top, jack_iodelay) — verify <10ms | @scout | 2h |
| P3-14 | Headphone detection integration test: plug/unplug cycle | @scout | 3h |

**Total Phase 2:** ~49 engineering-hours (3-4 weeks at 15h/week)  
**Total Phase 3:** ~53 engineering-hours (4-6 weeks at 10h/week)

---

### 7.11 Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| `ebur128` in filter-chain unreliable (PipeWire 1.0.x bug) | **HIGH** | Phase 2 falls back to static gain; Phase 3 replaces with ISO 226. Flag this for early testing. |
| SPA plugin API changes between PipeWire 1.0 and 1.2 | **MEDIUM** | Target PipeWire 1.0 API as minimum; add CI matrix for 1.0/1.2 |
| LSP plugin update changes port indices | **MEDIUM** | Pin to LSP 1.2.x; the .ttl port symbols are stable within major versions |
| M/S node fan-out limit in filter-chain | **LOW** | If one output cannot feed multiple inputs, insert `copy` tee nodes |
| SOFA HRTF licensing prevents bundling | **LOW** | Never bundle; provide downloader script; users can use any SOFA file |
| Audio glitches when enabling/disabling stages at runtime | **LOW** | Configs are generated statically; applied on PipeWire restart; no runtime switching |
| MaxxBass-style harmonic generation causes clipping | **LOW** | Waveshaper is soft-clipping by design; limiter stage catches any peaks |
| LV2 plugin unavailable on user system | **LOW** | Multi-level fallback chain for every LV2 stage; all stages default to linear passthrough |

---

### 7.12 Open Questions for Stakeholders

1. **ebur128 reliability:** Should Phase 2 include ebur128 at all, or defer
   loudness entirely to Phase 3's ISO 226? The ebur128 filter-chain support
   in PipeWire 1.0 is uncertain. **Recommendation:** Attempt ebur128 in Phase 2
   but treat it as experimental. Fall back to static gain immediately if it
   doesn_t work. Do not block Phase 2 on ebur128.

2. **SPA plugin vs LV2 for bass enhancer:** Is writing a C SPA plugin for
   bass enhancement worth the effort vs. just packaging CALF? CALF is GPL,
   could be made a dependency. **Recommendation:** Write the SPA plugin.
   It_s ~200 lines of DSP code and gives us full control over latency,
   parameter ranges, and integration. CALF can be documented as an alternative.

3. **M/S stage consolidation:** Should we merge stereo enhancer and dialogue
   enhancer into a single M/S stage? It would reduce nodes and potentially
   improve latency. **Recommendation:** Keep separate for v0.2. Optimize in
   v0.3 after we have real-world performance data.

4. **Headphone virtual surround for music?** The current design disables VR
   for music mode. Some users may want spatial audio for music too.
   **Recommendation:** Make it user-configurable. Default off for music,
   default on for movie.

5. **SOFA vs HeSuVi format preference:** Should we support HeSuVi .wav impulse
   response files directly? **Recommendation:** SOFA-first. HeSuVi conversion
   in Phase 4.

6. **Per-app mode switching:** Should the auto-detector switch modes based
   on the application producing audio? (e.g., Firefox -> movie mode,
   Spotify -> music mode). **Recommendation:** Defer to Phase 4. WirePlumber
   can detect application.name metadata.

---

### 7.13 Appendix D: LSP Limiter Stereo Port Symbols (Verified)

For reference, the correct LV2 port symbols for the Phase 1 output limiter,
verified against `/usr/lib/lv2/lsp-plugins.lv2/limiter_stereo.ttl` (LSP 1.2.33):

**Audio ports:**
| Index | Symbol | Name |
|-------|--------|------|
| 0 | `in_l` | Input L |
| 1 | `in_r` | Input R |
| 2 | `out_l` | Output L |
| 3 | `out_r` | Output R |

**Key control ports (Phase 1 config needs updating):**
| Index | Symbol | Type | Range | Default | Notes |
|-------|--------|------|-------|---------|-------|
| 8 | `enabled` | toggle | 0/1 | 1 | |
| 9 | `g_in` | log gain | 0-1000 | 1.0 | Input gain |
| 10 | `g_out` | log gain | 0-1000 | 1.0 | Output gain |
| 12 | `alr` | toggle | 0/1 | 1 | Auto Level Regulation |
| 13 | `alr_at` | ms | 0.1-200 | 5.0 | ALR attack |
| 14 | `alr_rt` | ms | 10-1000 | 50.0 | ALR release |
| 15 | `mode` | enum | 0-11 | 0 | 0=Herm Thin |
| 16 | `th` | linear gain | 0.004-1.0 | 1.0 | Threshold (-1 dB = 0.891) |
| 17 | `knee` | linear gain | 0.25-3.98 | 1.0 | |
| 18 | `boost` | toggle | 0/1 | 1 | Gain boost |
| 19 | `lk` | ms | 0.1-20 | 5.0 | Lookahead |
| 20 | `at` | ms | 0.25-20 | 5.0 | Attack |
| 21 | `rt` | ms | 0.25-20 | 5.0 | Release |
| 22 | `ovs` | enum | 0-22 | 0 | Oversampling (6=4x/24bit Half) |
| 23 | `dith` | enum | 0-8 | 0 | Dithering |
| 27 | `slink` | pc | 0-100 | 100 | Stereo linking |
| 44 | `smooth` | dB | -48-0 | -5.0 | Knee smooth |

**CRITICAL FIX for Phase 1 generator.py:** The current `generator.py` uses
incorrect port names (`"th"`, `"lk"`, `"at"`, `"rt"`, `"ovs"`, `"boost"`,
`"enabled"`, `"g_in"`, `"g_out"`). Some of these are correct (`th`, `lk`,
`at`, `rt`, `boost`, `enabled`, `g_in`, `g_out`), but the oversampling value
`"ovs" = 6` is WRONG. PipeWire filter-chain may use 0-based indexing for
LV2 enum ports. The value 6 corresponds to "Half x4/24 bit" in LSP.

**Recommended limiter config (revised):**

```json
{
    type = lv2
    name = limiter
    plugin = "http://lsp-plug.in/plugins/lv2/limiter_stereo"
    control = {
        "enabled" = 1
        "g_in"    = 1.0
        "g_out"   = 1.0
        "alr"     = 1
        "alr_at"  = 5.0
        "alr_rt"  = 50.0
        "mode"    = 0       # Herm Thin
        "th"      = 0.891   # -1.0 dBFS (10^(-1/20) = 0.891)
        "knee"    = 1.0
        "boost"   = 1       # Gain boost ON (compensates for limiting)
        "lk"      = 5.0     # 5ms lookahead (0.1-20ms)
        "at"      = 5.0     # 5ms attack
        "rt"      = 10.0    # 10ms release
        "ovs"     = 6       # Half x4/24 bit
        "dith"    = 0       # No dithering (float output)
        "slink"   = 100.0   # Full stereo linking
        "smooth"  = -5.0    # dB knee smoothing
    }
}
```

---

### 7.14 Appendix E: CALF Bass Enhancer LV2 Port Symbols (Reference)

If the CALF LV2 plugins are installed, the bass enhancer port symbols
(verified from source) are:

| Symbol | Name | Range |
|--------|------|-------|
| `in_l` | Input L | audio |
| `in_r` | Input R | audio |
| `out_l` | Output L | audio |
| `out_r` | Output R | audio |
| `bypass` | Bypass | 0/1 |
| `amount` | Amount | 0-1 |
| `drive` | Drive | 0-1 |
| `frequency` | Frequency (Hz) | 50-300 |
| `listen` | Listen | 0/1 |
| `output` | Output (dB) | -20 to +20 |

---

### 7.15 Appendix F: ISO 226 Reference Curve Data

For the Phase 3 ISO 226 equal-loudness implementation, the standard
frequencies (1/3 octave, 20 Hz – 12.5 kHz) and their gains relative to
1 kHz at various phon levels:

| Freq (Hz) | 20 phon | 40 phon | 60 phon | 80 phon |
|-----------|---------|---------|---------|---------|
| 20 | +56.4 | +46.4 | +41.6 | +38.9 |
| 25 | +49.9 | +40.4 | +35.9 | +33.3 |
| 31.5 | +43.6 | +34.5 | +30.3 | +28.0 |
| 40 | +37.6 | +28.9 | +25.1 | +23.0 |
| 50 | +32.6 | +24.2 | +20.6 | +18.7 |
| 63 | +27.9 | +19.9 | +16.7 | +14.9 |
| 80 | +23.7 | +16.2 | +13.3 | +11.7 |
| 100 | +20.2 | +13.2 | +10.6 | +9.1 |
| 125 | +17.2 | +10.6 | +8.3 | +7.0 |
| 200 | +9.5 | +4.6 | +3.0 | +2.0 |
| 250 | +6.5 | +2.5 | +1.3 | +0.6 |
| 315 | +4.1 | +1.1 | +0.3 | -0.2 |
| 400 | +2.3 | +0.1 | -0.4 | -0.6 |
| 500 | +1.2 | -0.3 | -0.7 | -0.8 |
| 630 | +0.5 | -0.5 | -0.8 | -0.8 |
| 800 | +0.0 | -0.5 | -0.7 | -0.7 |
| 1000 | 0.0 | 0.0 | 0.0 | 0.0 |
| 1250 | +0.2 | +0.5 | +0.6 | +0.6 |
| 1600 | +0.5 | +1.0 | +1.3 | +1.3 |
| 2000 | +0.8 | +1.6 | +2.0 | +2.0 |
| 2500 | +1.2 | +2.2 | +2.7 | +2.8 |
| 3150 | +1.6 | +3.0 | +3.7 | +3.8 |
| 4000 | +2.2 | +4.1 | +5.0 | +5.1 |
| 5000 | +3.0 | +5.1 | +6.2 | +6.3 |
| 6300 | +3.9 | +6.1 | +7.3 | +7.4 |
| 8000 | +5.0 | +7.0 | +8.2 | +8.3 |
| 10000 | +6.0 | +7.9 | +9.0 | +9.1 |
| 12500 | +7.3 | +8.8 | +9.7 | +9.8 |

Source: ISO 226:2023. Table shows gain (dB) relative to 1 kHz reference at
each phon level. Positive values mean more gain needed for equal loudness.

The dynamic EQ applies a low-shelf filter below 200 Hz and a high-shelf
filter above 6 kHz. Shelf gains are computed by interpolating between 
two phon levels based on current system volume.


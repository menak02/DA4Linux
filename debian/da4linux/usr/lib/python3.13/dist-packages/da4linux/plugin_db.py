"""LV2 plugin registry — confirmed URIs and port symbols.

All port symbols verified against actual .ttl files at:
  /usr/lib/x86_64-linux-gnu/lv2/calf.lv2/
  /usr/lib/lv2/lsp-plugins.lv2/
"""

# ── CALF Plugins ────────────────────────────────────────────────────────

CALF_BASS_ENHANCER_URI = "http://calf.sourceforge.net/plugins/BassEnhancer"
CALF_BASS_ENHANCER_PORTS = {
    # Audio ports (index 0-3)
    "in_l":      0,     "in_r":      1,
    "out_l":     2,     "out_r":     3,
    # Control ports (index 4-19)
    "bypass":    0,     "level_in":  1.0,
    "level_out": 1.0,   "amount":    0.5,
    "drive":     0.3,   "blend":     0.5,
    "freq":      150.0, "listen":    0,
    "floor_active": 0,  "floor":     80.0,
}

CALF_STEREO_TOOLS_URI = "http://calf.sourceforge.net/plugins/StereoTools"
CALF_STEREO_TOOLS_PORTS = {
    # Audio ports (index 0-3)
    "in_l":       0,     "in_r":       1,
    "out_l":      2,     "out_r":      3,
    # Control ports (index 4-)
    "bypass":     0,     "level_in":   1.0,
    "level_out":  1.0,   "balance_in": 0.0,
    "balance_out": 0.0,  "softclip":   0,
    "mutel":      0,     "muter":      0,
    "phasel":     0,     "phaser":     0,
    "mode":       0,     "slev":       1.0,
    "sbal":       0.0,   "mlev":       1.0,
    "mpan":       0.0,   "stereo_base": 1.0,
    "delay":      0.0,   "sc_level":   1.0,
    "stereo_phase": 0.0,
}

CALF_REVERB_URI = "http://calf.sourceforge.net/plugins/Reverb"
CALF_REVERB_PORTS = {
    "in_l":         0,     "in_r":         1,
    "out_l":        2,     "out_r":        3,
    "decay_time":   1.5,   "hf_damp":      8000.0,
    "room_size":    0.5,   "diffusion":    0.75,
    "amount":       0.2,   "dry":          0.8,
    "predelay":     15.0,  "bass_cut":     200.0,
    "treble_cut":   6000.0, "on":          1,
    "level_in":     1.0,   "level_out":    1.0,
}

CALF_DEESSER_URI = "http://calf.sourceforge.net/plugins/Deesser"
CALF_DEESSER_PORTS = {
    "in_l":         0,     "in_r":         1,
    "out_l":        2,     "out_r":        3,
    "bypass":       0,     "detection":    0,
    "mode":         0,     "threshold":    -24.0,
    "ratio":        3.0,   "laxity":       2.0,
    "makeup":       0.0,   "f1_freq":      6000.0,
}

CALF_EXCITER_URI = "http://calf.sourceforge.net/plugins/Exciter"
CALF_EXCITER_PORTS = {
    "in_l":         0,     "in_r":         1,
    "out_l":        2,     "out_r":        3,
    "bypass":       0,     "level_in":     1.0,
    "level_out":    1.0,   "amount":       0.5,
    "drive":        0.3,   "blend":        0.5,
    "freq":         3000.0,
}

CALF_COMPRESSOR_URI = "http://calf.sourceforge.net/plugins/Compressor"
CALF_COMPRESSOR_PORTS = {
    "in_l":         0,     "in_r":         1,
    "out_l":        2,     "out_r":        3,
    "bypass":       0,     "level_in":     1.0,
    "threshold":    -20.0, "ratio":        2.0,
    "attack":       5.0,   "release":      50.0,
    "makeup":       0.0,   "knee":         2.0,
}


# ── LSP Plugins (URIs: http://lsp-plug.in/plugins/lv2/...) ──────────────

LSP_MB_COMPRESSOR_URI = "http://lsp-plug.in/plugins/lv2/mb_compressor_stereo"
# Port names confirmed from mb_compressor_stereo.ttl (240+ ports, 8 bands).
# Band index convention: _0.._7 (band 1..8).
# Audio: in_l(0), in_r(1), out_l(2), out_r(3)
# Split frequencies: sf_1..sf_7 (indexes 32,34,36,38,40,42,44)
# Per-band compressor params: ce_N, cm_N, at_N, rt_N, cr_N, kn_N, bth_N, bsa_N, mk_N
LSP_MB_COMPRESSOR_PORTS = {
    # Audio
    "in_l": 0, "in_r": 1, "out_l": 2, "out_r": 3,
    # Top-level
    "enabled": 1, "mode": 1,
    "g_in": 1.0, "g_out": 1.0,
    "g_dry": -90.0, "g_wet": 0.0, "drywet": 1.0,
    "react": 50.0, "shift": 0.0, "zoom": 1.0, "envb": 1.0,
    "ssplit": 0,
    # Per band: threshold, ratio, attack, release, knee, makeup gain
    # Defaults for a 4-band setup (bands 1-4 active)
    "ce_0": 1, "cm_0": 1, "at_0": 10.0, "rt_0": 40.0, "cr_0": 1.5, "kn_0": 2.0, "bth_0": 1.0, "bsa_0": 0.0, "mk_0": 0.0,
    "ce_1": 1, "cm_1": 1, "at_1": 15.0, "rt_1": 60.0, "cr_1": 2.0, "kn_1": 2.0, "bth_1": 1.0, "bsa_1": 0.0, "mk_1": 0.0,
    "ce_2": 1, "cm_2": 1, "at_2": 15.0, "rt_2": 80.0, "cr_2": 2.0, "kn_2": 2.0, "bth_2": 1.0, "bsa_2": 0.0, "mk_2": 0.0,
    "ce_3": 1, "cm_3": 1, "at_3": 5.0,  "rt_3": 30.0, "cr_3": 1.5, "kn_3": 2.0, "bth_3": 1.0, "bsa_3": 0.0, "mk_3": 0.0,
    # Bands 5-8 disabled
    "ce_4": 0, "ce_5": 0, "ce_6": 0, "ce_7": 0,
}

LSP_LOUD_COMP_URI = "http://lsp-plug.in/plugins/lv2/loud_comp_stereo"
LSP_LOUD_COMP_PORTS = {
    "in_l":     0,  "in_r":      1,
    "out_l":    2,  "out_r":     3,
    "enabled":  1,  "input":     1.0,
    "mode":     0,  "std":       1,
    "fft":      10, "approx":    0,
    "volume":   1.0, "refer":    0,
    "reftype":  0,  "hclip":     0,
    "hcrange":  1.0,
}

LSP_LIMITER_URI = "http://lsp-plug.in/plugins/lv2/limiter_stereo"
LSP_LIMITER_PORTS = {
    "in_l":    0,  "in_r":     1,
    "out_l":   2,  "out_r":    3,
    "th":      0.89125, "lk":  5.0,
    "at":      5.0,  "rt":     20.0,
    "ovs":     0,    "boost":  0,
    "enabled": 1,    "g_in":   1.0,
    "g_out":   1.0,
}

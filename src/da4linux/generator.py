"""PipeWire filter-chain SPA-JSON config generator.

Produces configuration for libpipewire-module-filter-chain with:
  Input → fir_convolver → peq → mb_compressor → stereo_enhancer →
  bass_enhancer → dialogue_enhancer → loudness → virtual_surround → limiter → Output

SPA-JSON format is NOT regular JSON: unquoted keys, no trailing commas,
key=value separators, # comments.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .constants import (
    PARAM_EQ_TYPES, DEFAULT_SAMPLE_RATE, DEFAULT_FIR_TAPS,
    ALL_STAGES, DEFAULT_ENABLED_STAGES, MODE_PRESETS,
)
from .detect import DeviceInfo
from .parser import DAX3Profile, PEQBand
from .plugin_db import (
    CALF_BASS_ENHANCER_URI, CALF_STEREO_TOOLS_URI,
    LSP_MB_COMPRESSOR_URI, LSP_LOUD_COMP_URI, LSP_LIMITER_URI,
)


def get_lv2_search_paths() -> list[Path]:
    """Return list of LV2 plugin search directories."""
    paths = []
    lv2_env = os.environ.get("LV2_PATH")
    if lv2_env:
        for p in lv2_env.split(":"):
            if p.strip():
                paths.append(Path(p.strip()).expanduser())

    default_dirs = [
        Path("~/.lv2").expanduser(),
        Path("/usr/local/lib/lv2"),
        Path("/usr/lib/lv2"),
        Path("/usr/lib64/lv2"),
        Path("/usr/lib/x86_64-linux-gnu/lv2"),
        Path("/usr/lib/aarch64-linux-gnu/lv2"),
        Path("/usr/lib/arm-linux-gnueabihf/lv2"),
    ]
    for d in default_dirs:
        if d not in paths:
            paths.append(d)
    return paths


def get_ladspa_search_paths() -> list[Path]:
    """Return list of LADSPA plugin search directories."""
    paths = []
    env = os.environ.get("LADSPA_PATH")
    if env:
        for p in env.split(":"):
            if p.strip():
                paths.append(Path(p.strip()).expanduser())

    default_dirs = [
        Path("~/.ladspa").expanduser(),
        Path("/usr/local/lib/ladspa"),
        Path("/usr/lib/ladspa"),
        Path("/usr/lib64/ladspa"),
        Path("/usr/lib/x86_64-linux-gnu/ladspa"),
        Path("/usr/lib/aarch64-linux-gnu/ladspa"),
    ]
    for d in default_dirs:
        if d not in paths:
            paths.append(d)
    return paths


def find_lv2_plugin_ttl(bundle_dir_name: str, ttl_name: str) -> bool:
    """Check if an LV2 plugin TTL file exists across search paths."""
    for base in get_lv2_search_paths():
        candidate = base / bundle_dir_name / ttl_name
        if candidate.exists():
            return True
    return False


def peq_band_to_spa_filter(band: PEQBand) -> str:
    """Convert a PEQBand to a PipeWire param_eq filter entry string."""
    ftype = PARAM_EQ_TYPES.get(band.filter_type, "bq_peaking")
    return (
        f"{{ type = {ftype} "
        f"freq = {band.freq:.1f} "
        f"gain = {band.gain:.3f} "
        f"q = {band.q:.4f} }}"
    )


def _build_filters_string(bands: list[PEQBand]) -> str:
    if not bands:
        return "{ type = bq_peaking freq = 1000 gain = 0.0 q = 0.707 }"
    return " ".join(peq_band_to_spa_filter(b) for b in bands)


def _generate_convolver_nodes(
    ir_left: str, ir_right: str, label: str = "conv"
) -> str:
    """Generate convolver nodes for left and right channels."""
    return f"""                    {{
                        type = builtin
                        name = {label}_l
                        label = convolver
                        config = {{
                            filename = "{ir_left}"
                            channel = 0
                            gain = 1.0
                        }}
                    }}
                    {{
                        type = builtin
                        name = {label}_r
                        label = convolver
                        config = {{
                            filename = "{ir_right}"
                            channel = 0
                            gain = 1.0
                        }}
                    }}"""


def _generate_mb_compressor_node(
    enabled: bool = True,
    comp_ratio: float = 2.0,
    crossover_freqs: Optional[list[float]] = None,
) -> tuple[str, str, str, str, str]:
    """Generate LSP MB Compressor Stereo LV2 node.

    Returns (node_spa_json, prev_l_out, prev_r_out, prev_l_in, prev_r_in)
    where prev_l_out is the source node-port and prev_l_in is the dest node-port.
    """
    if not enabled:
        return (
            _passthrough_linear("mb_byp"),
            "mb_byp_l:Out", "mb_byp_r:Out",
            "mb_byp_l:In", "mb_byp_r:In",
        )

    # Use parsed crossover frequencies if available (needs 3 split frequencies sf_1, sf_2, sf_3)
    sf1 = crossover_freqs[0] if crossover_freqs and len(crossover_freqs) > 0 else 120
    sf2 = crossover_freqs[1] if crossover_freqs and len(crossover_freqs) > 1 else 500
    sf3 = crossover_freqs[2] if crossover_freqs and len(crossover_freqs) > 2 else 3000

    # Build control block dynamically for the per-band ratio
    # Default: 4-band compressor, mode=1 (modern)
    ratio_0 = min(comp_ratio * 0.6, 1.5)
    ratio_1 = comp_ratio
    ratio_2 = max(comp_ratio * 0.8, 1.2)
    ratio_3 = max(comp_ratio * 0.4, 1.1)

    node = f"""                    {{
                        type = lv2
                        name = mb
                        plugin = "{LSP_MB_COMPRESSOR_URI}"
                        control = {{
                            "enabled" = 1
                            "mode" = 1
                            "g_in" = 1.0
                            "g_out" = 0.0
                            "g_dry" = -90.0
                            "g_wet" = 0.0
                            "drywet" = 1.0
                            "react" = 50.0
                            "ssplit" = 0
                            "cbe_1" = 1
                            "sf_1" = {sf1}
                            "cbe_2" = 1
                            "sf_2" = {sf2}
                            "cbe_3" = 1
                            "sf_3" = {sf3}
                            "cbe_4" = 0 "cbe_5" = 0 "cbe_6" = 0 "cbe_7" = 0
                            "ce_0" = 1 "cm_0" = 1 "at_0" = 10.0 "rt_0" = 40.0 "cr_0" = {ratio_0} "kn_0" = 2.0 "bth_0" = 1.0 "bsa_0" = 0.0 "mk_0" = 0.0
                            "ce_1" = 1 "cm_1" = 1 "at_1" = 15.0 "rt_1" = 60.0 "cr_1" = {ratio_1} "kn_1" = 2.0 "bth_1" = 1.0 "bsa_1" = 0.0 "mk_1" = 0.0
                            "ce_2" = 1 "cm_2" = 1 "at_2" = 15.0 "rt_2" = 80.0 "cr_2" = {ratio_2} "kn_2" = 2.0 "bth_2" = 1.0 "bsa_2" = 0.0 "mk_2" = 0.0
                            "ce_3" = 1 "cm_3" = 1 "at_3" = 5.0 "rt_3" = 30.0 "cr_3" = {ratio_3} "kn_3" = 2.0 "bth_3" = 1.0 "bsa_3" = 0.0 "mk_3" = 0.0
                        }}
                    }}"""
    return node, "mb:out_l", "mb:out_r", "mb:in_l", "mb:in_r"


def _generate_stereo_enhancer_node(
    enabled: bool = True,
    width: float = 1.3,
) -> tuple[str, str, str, str, str]:
    """Generate stereo enhancement stage.

    Uses CALF StereoTools LV2 when available, else builtin M/S matrix.
    Returns (node_str, out_l, out_r, in_l, in_r).
    """
    if not enabled:
        return (
            _passthrough_linear("ste_byp"),
            "ste_byp_l:Out", "ste_byp_r:Out",
            "ste_byp_l:In", "ste_byp_r:In",
        )

    calf_stereo = find_lv2_plugin_ttl("calf.lv2", "StereoTools.ttl")

    if calf_stereo:
        node = f"""                    {{
                        type = lv2
                        name = stereo
                        plugin = "{CALF_STEREO_TOOLS_URI}"
                        control = {{
                            "bypass" = 0
                            "level_in" = 1.0
                            "level_out" = 1.0
                            "balance_in" = 0.0
                            "balance_out" = 0.0
                            "softclip" = 0
                            "mutel" = 0
                            "muter" = 0
                            "phasel" = 0
                            "phaser" = 0
                            "mode" = 0
                            "slev" = {width}
                            "sbal" = 0.0
                            "mlev" = 1.0
                            "mpan" = 0.0
                            "stereo_base" = 1.0
                            "delay" = 0.0
                            "sc_level" = 1.0
                            "stereo_phase" = 0.0
                        }}
                    }}"""
        return node, "stereo:out_l", "stereo:out_r", "stereo:in_l", "stereo:in_r"

    # Builtin M/S matrix fallback
    mid_gain = 1.0
    side_gain = width
    nodes = f"""                    {{
                        type = builtin
                        name = ms_cp1_l
                        label = copy
                    }}
                    {{
                        type = builtin
                        name = ms_cp1_r
                        label = copy
                    }}
                    {{
                        type = builtin
                        name = ms_mix_m
                        label = mixer
                        control = {{ "Gain 1" = 0.5 "Gain 2" = 0.5 }}
                    }}
                    {{
                        type = builtin
                        name = ms_mix_s
                        label = mixer
                        control = {{ "Gain 1" = 0.5 "Gain 2" = -0.5 }}
                    }}
                    {{
                        type = builtin
                        name = ms_gain_m
                        label = linear
                        control = {{ "Mult" = {mid_gain} "Add" = 0.0 }}
                    }}
                    {{
                        type = builtin
                        name = ms_gain_s
                        label = linear
                        control = {{ "Mult" = {side_gain} "Add" = 0.0 }}
                    }}
                    {{
                        type = builtin
                        name = ms_mix_l
                        label = mixer
                        control = {{ "Gain 1" = 1.0 "Gain 2" = 1.0 }}
                    }}
                    {{
                        type = builtin
                        name = ms_mix_r
                        label = mixer
                        control = {{ "Gain 1" = 1.0 "Gain 2" = -1.0 }}
                    }}"""
    return nodes, "ms_mix_l:Out", "ms_mix_r:Out", "ms_cp1_l:In", "ms_cp1_r:In"


def _generate_bass_enhancer_node(
    enabled: bool = True,
    amount: float = 0.5,
) -> tuple[str, str, str, str, str]:
    """Generate bass enhancement stage using CALF BassEnhancer LV2."""
    if not enabled:
        return (
            _passthrough_linear("bass_byp"),
            "bass_byp_l:Out", "bass_byp_r:Out",
            "bass_byp_l:In", "bass_byp_r:In",
        )

    calf_bass = find_lv2_plugin_ttl("calf.lv2", "BassEnhancer.ttl")

    if calf_bass:
        node = f"""                    {{
                        type = lv2
                        name = bass
                        plugin = "{CALF_BASS_ENHANCER_URI}"
                        control = {{
                            "bypass" = 0
                            "level_in" = 1.0
                            "level_out" = 1.0
                            "amount" = {amount}
                            "drive" = 0.3
                            "blend" = 0.5
                            "freq" = 150.0
                            "listen" = 0
                            "floor_active" = 0
                            "floor" = 80.0
                        }}
                    }}"""
        return node, "bass:out_l", "bass:out_r", "bass:in_l", "bass:in_r"

    # Fallback: low-shelf boost via biquad
    node = f"""                    {{
                        type = builtin
                        name = bass_l
                        label = bq_lowshelf
                        control = {{ "freq" = 150.0 "gain" = {amount * 6.0} "q" = 0.7 }}
                    }}
                    {{
                        type = builtin
                        name = bass_r
                        label = bq_lowshelf
                        control = {{ "freq" = 150.0 "gain" = {amount * 6.0} "q" = 0.7 }}
                    }}"""
    return node, "bass_l:Out", "bass_r:Out", "bass_l:In", "bass_r:In"


def _generate_dialogue_enhancer_node(
    enabled: bool = True,
    boost: float = 2.0,
) -> tuple[str, str, str, str, str]:
    """Generate dialogue enhancer using builtin M/S center extraction + voice EQ.

    Extracts mid signal, applies peaking boost + highpass, reconstructs L/R.
    Passthrough if disabled.
    """
    if not enabled or boost <= 1.0:
        return (
            _passthrough_linear("dial_byp"),
            "dial_byp_l:Out", "dial_byp_r:Out",
            "dial_byp_l:In", "dial_byp_r:In",
        )

    voice_gain_db = (boost - 1.0) * 3.0

    nodes = f"""                    {{
                        type = builtin
                        name = d_cp1_l
                        label = copy
                    }}
                    {{
                        type = builtin
                        name = d_cp1_r
                        label = copy
                    }}
                    {{
                        type = builtin
                        name = d_mix_m
                        label = mixer
                        control = {{ "Gain 1" = 0.5 "Gain 2" = 0.5 }}
                    }}
                    {{
                        type = builtin
                        name = d_mix_s
                        label = mixer
                        control = {{ "Gain 1" = 0.5 "Gain 2" = -0.5 }}
                    }}
                    {{
                        type = builtin
                        name = d_peq_v
                        label = bq_peaking
                        control = {{ "freq" = 2000.0 "gain" = {voice_gain_db:.1f} "q" = 1.5 }}
                    }}
                    {{
                        type = builtin
                        name = d_hp_v
                        label = bq_highpass
                        control = {{ "freq" = 200.0 "gain" = 0.0 "q" = 0.707 }}
                    }}
                    {{
                        type = builtin
                        name = d_mix_l
                        label = mixer
                        control = {{ "Gain 1" = 1.0 "Gain 2" = 1.0 }}
                    }}
                    {{
                        type = builtin
                        name = d_mix_r
                        label = mixer
                        control = {{ "Gain 1" = 1.0 "Gain 2" = -1.0 }}
                    }}"""
    return nodes, "d_mix_l:Out", "d_mix_r:Out", "d_cp1_l:In", "d_cp1_r:In"


def _generate_loudness_node(
    enabled: bool = True,
) -> tuple[str, str, str, str, str]:
    """Generate loudness compensation stage.

    Uses LSP loud_comp_stereo LV2 (ISO 226 equal-loudness) if available,
    else PipeWire builtin ebur128 meter for loudness-based gain riding.
    """
    if not enabled:
        return (
            _passthrough_linear("loud_byp"),
            "loud_byp_l:Out", "loud_byp_r:Out",
            "loud_byp_l:In", "loud_byp_r:In",
        )

    lsp_loud = find_lv2_plugin_ttl("lsp-plugins.lv2", "loud_comp_stereo.ttl")

    if lsp_loud:
        node = f"""                    {{
                        type = lv2
                        name = loud
                        plugin = "{LSP_LOUD_COMP_URI}"
                        control = {{
                            "enabled" = 1
                            "input" = 1.0
                            "mode" = 0
                            "std" = 1
                            "fft" = 10
                            "approx" = 0
                            "volume" = 1.0
                            "refer" = 0
                            "reftype" = 0
                            "hclip" = 0
                            "hcrange" = 1.0
                        }}
                    }}"""
        return node, "loud:out_l", "loud:out_r", "loud:in_l", "loud:in_r"

    # ebur128 + linear gain riding fallback
    node = f"""                    {{
                        type = builtin
                        name = ebu
                        label = ebur128
                    }}
                    {{
                        type = builtin
                        name = ld_l
                        label = linear
                        control = {{ "Mult" = 1.0 "Add" = 0.0 }}
                    }}
                    {{
                        type = builtin
                        name = ld_r
                        label = linear
                        control = {{ "Mult" = 1.0 "Add" = 0.0 }}
                    }}"""
    return node, "ld_l:Out", "ld_r:Out", "ld_l:In", "ld_r:In"


def _generate_virtual_surround_node(
    enabled: bool = True,
    hrir_path: str = "",
) -> tuple[str, str, str, str, str]:
    """Generate virtual surround stage using PipeWire builtin sofa/spatializer.

    When disabled, returns empty nodes (passthrough via link skip).
    """
    if not enabled or not hrir_path:
        return "", "", "", "", ""

    sofa_file = Path(hrir_path).expanduser()
    if not sofa_file.exists():
        return "", "", "", "", ""

    node = f"""                    {{
                        type = builtin
                        name = surround
                        label = spatializer
                        config = {{
                            filename = "{sofa_file}"
                            gain = 1.0
                            normalize = false
                        }}
                        control = {{
                            "Azimuth" = 0.0
                            "Elevation" = 0.0
                            "Radius" = 1.0
                        }}
                    }}"""
    return node, "surround:Out", "surround:Out", "surround:In", "surround:In"


def _passthrough_linear(label: str) -> str:
    """Generate two linear nodes that pass audio through unchanged."""
    return f"""                    {{
                        type = builtin
                        name = {label}_l
                        label = linear
                        control = {{ "Mult" = 1.0 "Add" = 0.0 }}
                    }}
                    {{
                        type = builtin
                        name = {label}_r
                        label = linear
                        control = {{ "Mult" = 1.0 "Add" = 0.0 }}
                    }}"""


# ── Link helpers ────────────────────────────────────────────────────────

def _link(src: str, dst: str) -> str:
    return f"{{ output = \"{src}\" input = \"{dst}\" }}"


def _link_pair(src_l: str, src_r: str, dst_l: str, dst_r: str) -> str:
    return f"                    {_link(src_l, dst_l)}\n                    {_link(src_r, dst_r)}"


# ── M/S matrix link helpers ─────────────────────────────────────────────

def _ms_matrix_links(
    name_prefix: str,
    src_l: str, src_r: str,
) -> str:
    """Generate links for an M/S matrix node set:
       copy_l.In  ← src_l    mix_m.In 1 ← copy_l.Out   (mid = 0.5L + 0.5R)
       copy_r.In  ← src_r    mix_m.In 2 ← copy_r.Out
                              mix_s.In 1 ← copy_l.Out   (side = 0.5L - 0.5R)
                              mix_s.In 2 ← copy_r.Out
    """
    p = name_prefix
    return f"""                    {{ output = "{src_l}" input = "{p}_l:In" }}
                    {{ output = "{src_r}" input = "{p}_r:In" }}
                    {{ output = "{p}_l:Out" input = "{p}_m:In 1" }}
                    {{ output = "{p}_r:Out" input = "{p}_m:In 2" }}
                    {{ output = "{p}_l:Out" input = "{p}_s:In 1" }}
                    {{ output = "{p}_r:Out" input = "{p}_s:In 2" }}"""


def _ms_reconstruct_links(
    prefix: str,
    mid_src: str, side_src: str,
    dst_l: str, dst_r: str,
) -> str:
    """Generate links for M/S → L/R reconstruction:
       mix_l.In 1 ← mid_processed  mix_l.In 2 ← side_processed
       mix_r.In 1 ← mid_processed  mix_r.In 2 ← side_processed (negated)
       mix_l.Out → dst_l           mix_r.Out → dst_r
    """
    return f"""                    {{ output = "{mid_src}" input = "{prefix}_l:In 1" }}
                    {{ output = "{side_src}" input = "{prefix}_l:In 2" }}
                    {{ output = "{mid_src}" input = "{prefix}_r:In 1" }}
                    {{ output = "{side_src}" input = "{prefix}_r:In 2" }}
                    {{ output = "{prefix}_l:Out" input = "{dst_l}" }}
                    {{ output = "{prefix}_r:Out" input = "{dst_r}" }}"""


# ── Main graph generator ────────────────────────────────────────────────

def generate_filter_graph(
    profile: DAX3Profile,
    device_info: DeviceInfo,
    ir_dir: str = "~/.local/share/da4linux/ir",
    limiter_type: str = "lv2",
    stages: Optional[dict] = None,
    mode: str = "music",
    hrir_path: str = "",
) -> str:
    """Generate the filter.graph section as a SPA-JSON string.

    Full chain (10 stages):
      Input → fir → peq → mb_compressor → stereo → bass → dialogue →
      loudness → surround → limiter → Output

    Args:
        profile: DAX3 parsing result with PEQ bands etc.
        device_info: Hardware detection result.
        ir_dir: Directory for impulse response WAV files.
        limiter_type: 'lv2', 'ladspa', 'zam', or 'clamp'.
        stages: Dict of stage_name -> bool to enable/disable.
        mode: 'music', 'movie', or 'voice' preset.
        hrir_path: Path to SOFA HRTF file for virtual surround.
    """
    if stages is None:
        stages = dict.fromkeys(DEFAULT_ENABLED_STAGES, True)

    mode_preset = MODE_PRESETS.get(mode, MODE_PRESETS["music"])

    # Derive stage params from mode
    stereo_width = mode_preset.get("stereo_width", 1.3)
    bass_amount = mode_preset.get("bass_amount", 0.6)
    dialogue_boost = mode_preset.get("dialogue_boost", 1.0)
    comp_ratio = mode_preset.get("comp_ratio", 2.5)
    surround_enabled = stages.get("surround", mode_preset.get("surround", False))

    ir_path = Path(ir_dir).expanduser()
    profile_key = f"{device_info.vendor}_{device_info.product_name}"
    profile_key = (
        profile_key.replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .lower()
    )
    if not profile_key:
        profile_key = "generic"

    ir_left = str(ir_path / f"{profile_key}_L.wav")
    ir_right = str(ir_path / f"{profile_key}_R.wav")
    use_fir = bool(profile.ao_bands) and stages.get("fir", True)

    has_ieq = profile.ieq_enabled and len(profile.ieq_curve) > 0
    has_real_peq = len(profile.peq_bands) > 0 and any(b.freq > 0 for b in profile.peq_bands)
    has_mb_comp = len(profile.mb_compressor) > 0 and any(b.threshold != 0 for b in profile.mb_compressor)

    if not has_mb_comp:
        stages["mb_compressor"] = False

    # Generate IEQ FIR when IEQ data is available (MUST happen before path check)
    if has_ieq:
        from .ir_generator import generate_minimum_phase_fir, write_wav_ir, _HAS_NUMPY
        if _HAS_NUMPY:
            ieq_db = [v / 16.0 for v in profile.ieq_curve]
            blend = profile.ieq_amount / 100.0
            ieq_db_blended = [v * blend for v in ieq_db]

            ieq_freqs = [47, 141, 234, 328, 469, 656, 844, 1031, 1313, 1688,
                         2250, 3000, 3750, 4688, 5813, 7125, 9000, 11250, 13875, 19688]

            ir = generate_minimum_phase_fir(ieq_db_blended, ieq_freqs)
            write_wav_ir(ir, ir_left, 48000)
            write_wav_ir(ir, ir_right, 48000)
            use_fir = True

    # NOW check if IR files exist (after IEQ generation may have created them)
    if not Path(ir_left).exists() and not Path(ir_right).exists():
        use_fir = False

    ir_left_path = ir_left if use_fir else "/dirac"
    ir_right_path = ir_right if use_fir else "/dirac"

    filters_str = _build_filters_string(profile.peq_bands)
    volmax_db = profile.volmax_boost / 16.0 if profile.volmax_boost > 0 else 0.0

    # Calculate cumulative gain across active stages to maintain headroom
    peq_max_boost = max([b.gain for b in profile.peq_bands if b.enabled and b.gain > 0] + [0.0])
    bass_boost = (bass_amount * 6.0) if stages.get("bass", True) else 0.0
    dial_boost = ((dialogue_boost - 1.0) * 3.0) if (stages.get("dialogue", True) and dialogue_boost > 1.0) else 0.0
    total_boost = peq_max_boost + bass_boost + dial_boost + volmax_db

    # Pre-attenuate volmax gain if cumulative boost exceeds +14dB headroom
    headroom_attenuation = max(0.0, total_boost - 14.0)
    net_volmax_db = max(0.0, volmax_db - headroom_attenuation)
    volmax_linear = pow(10.0, net_volmax_db / 20.0) if net_volmax_db > 0 else 1.0

    if use_fir:
        conv_nodes = _generate_convolver_nodes(ir_left, ir_right)
        conv_out_l, conv_out_r = "conv_l:Out", "conv_r:Out"
        conv_in_l, conv_in_r = "conv_l:In", "conv_r:In"
        graph_in_l, graph_in_r = conv_in_l, conv_in_r
    else:
        conv_nodes = ""
        conv_out_l = conv_out_r = conv_in_l = conv_in_r = ""
        graph_in_l, graph_in_r = "peq:In 1", "peq:In 2"

    peq_node = f"""                    {{
                        type = builtin
                        name = peq
                        label = param_eq
                        config = {{
                            filters = [
                                {filters_str}
                            ]
                        }}
                    }}"""
    peq_out_l, peq_out_r = "peq:Out 1", "peq:Out 2"
    peq_in_l, peq_in_r = "peq:In 1", "peq:In 2"

    mb_enabled = stages.get("mb_compressor", True)
    mb_node, mb_out_l, mb_out_r, mb_in_l, mb_in_r = _generate_mb_compressor_node(
        enabled=mb_enabled, comp_ratio=comp_ratio, crossover_freqs=profile.crossover_freqs,
    )

    ste_enabled = stages.get("stereo", True)
    ste_node, ste_out_l, ste_out_r, ste_in_l, ste_in_r = _generate_stereo_enhancer_node(
        enabled=ste_enabled, width=stereo_width,
    )

    bass_enabled = stages.get("bass", True)
    bass_node, bass_out_l, bass_out_r, bass_in_l, bass_in_r = _generate_bass_enhancer_node(
        enabled=bass_enabled, amount=bass_amount,
    )

    dial_enabled = stages.get("dialogue", True)
    dial_node, dial_out_l, dial_out_r, dial_in_l, dial_in_r = _generate_dialogue_enhancer_node(
        enabled=dial_enabled, boost=dialogue_boost,
    )

    loud_enabled = stages.get("loudness", True)
    loud_node, loud_out_l, loud_out_r, loud_in_l, loud_in_r = _generate_loudness_node(
        enabled=loud_enabled,
    )

    if surround_enabled and hrir_path:
        sur_node, sur_out_l, sur_out_r, sur_in_l, sur_in_r = _generate_virtual_surround_node(
            enabled=True, hrir_path=hrir_path,
        )
    else:
        sur_node, sur_out_l, sur_out_r, sur_in_l, sur_in_r = "", "", "", "", ""

    gain_node = f"""                    {{
                        type = builtin
                        name = gain_out_l
                        label = linear
                        control = {{ "Mult" = {volmax_linear:.6f} "Add" = 0.0 }}
                    }}
                    {{
                        type = builtin
                        name = gain_out_r
                        label = linear
                        control = {{ "Mult" = {volmax_linear:.6f} "Add" = 0.0 }}
                    }}"""
    gain_out_l, gain_out_r = "gain_out_l:Out", "gain_out_r:Out"
    gain_in_l, gain_in_r = "gain_out_l:In", "gain_out_r:In"

    if limiter_type == "lv2":
        lim_node = """                    {
                        type = lv2
                        name = limiter
                        plugin = "http://lsp-plug.in/plugins/lv2/limiter_stereo"
                        control = {
                            "th" = 0.89125
                            "lk" = 5.0
                            "at" = 5.0
                            "rt" = 20.0
                            "ovs" = 0
                            "boost" = 0
                            "enabled" = 1
                            "g_in" = 1.0
                            "g_out" = 1.0
                        }
                    }"""
        lim_in_l, lim_in_r = "limiter:in_l", "limiter:in_r"
        lim_out_l, lim_out_r = "limiter:out_l", "limiter:out_r"
    elif limiter_type == "ladspa":
        lim_node = """                    {
                        type = ladspa
                        name = limiter
                        plugin = "lsp-plugins-ladspa"
                        label = "sc_limiter_stereo"
                        control = {
                            "th" = -1.0
                            "at" = 5.0
                            "rt" = 50.0
                        }
                    }"""
        lim_in_l, lim_in_r = "limiter:Input L", "limiter:Input R"
        lim_out_l, lim_out_r = "limiter:Output L", "limiter:Output R"
    elif limiter_type == "zam":
        lim_node = """                    {
                        type = ladspa
                        name = limiter
                        plugin = "ZaMaximX2-ladspa"
                        label = "ZaMaximX2"
                        control = {
                            "Threshold" = -1.0
                            "Release" = 50.0
                        }
                    }"""
        lim_in_l, lim_in_r = "limiter:Input L", "limiter:Input R"
        lim_out_l, lim_out_r = "limiter:Output L", "limiter:Output R"
    else:
        lim_node = """                    {
                        type = builtin
                        name = limiter_l
                        label = clamp
                        control = {
                            "Min" = -1.0
                            "Max" = 1.0
                        }
                    }
                    {
                        type = builtin
                        name = limiter_r
                        label = clamp
                        control = {
                            "Min" = -1.0
                            "Max" = 1.0
                        }
                    }"""
        lim_in_l, lim_in_r = "limiter_l:In", "limiter_r:In"
        lim_out_l, lim_out_r = "limiter_l:Out", "limiter_r:Out"

    all_nodes = [conv_nodes, peq_node, mb_node, ste_node, bass_node,
                 dial_node, loud_node, sur_node, gain_node, lim_node]
    nodes_body = ""
    for n in all_nodes:
        if n.strip():
            if nodes_body:
                nodes_body += "\n"
            nodes_body += n

    links = []
    # Conv → PEQ (only if FIR convolver is active)
    if use_fir:
        links.append(f"                    {_link(conv_out_l, peq_in_l)}")
        links.append(f"                    {_link(conv_out_r, peq_in_r)}")

    # PEQ → MB Compressor
    links.append(f"                    {_link(peq_out_l, mb_in_l)}")
    links.append(f"                    {_link(peq_out_r, mb_in_r)}")

    # MB Comp → Stereo enhancer
    # If stereo enhancer is the M/S matrix (builtin), the first pair gets special links
    if not ste_enabled:
        links.append(f"                    {_link(mb_out_l, ste_in_l)}")
        links.append(f"                    {_link(mb_out_r, ste_in_r)}")
    elif find_lv2_plugin_ttl("calf.lv2", "StereoTools.ttl"):
        links.append(f"                    {_link(mb_out_l, ste_in_l)}")
        links.append(f"                    {_link(mb_out_r, ste_in_r)}")
    else:
        # M/S matrix builtin — fan-out links
        links.append(f"                    {_link(mb_out_l, 'ms_cp1_l:In')}")
        links.append(f"                    {_link(mb_out_r, 'ms_cp1_r:In')}")
        links.append(f"                    {{ output = \"ms_cp1_l:Out\" input = \"ms_mix_m:In 1\" }}")
        links.append(f"                    {{ output = \"ms_cp1_r:Out\" input = \"ms_mix_m:In 2\" }}")
        links.append(f"                    {{ output = \"ms_cp1_l:Out\" input = \"ms_mix_s:In 1\" }}")
        links.append(f"                    {{ output = \"ms_cp1_r:Out\" input = \"ms_mix_s:In 2\" }}")
        # Processed M/S → gains
        links.append(f"                    {{ output = \"ms_mix_m:Out\" input = \"ms_gain_m:In\" }}")
        links.append(f"                    {{ output = \"ms_mix_s:Out\" input = \"ms_gain_s:In\" }}")
        # Gains → reconstruct L/R
        links.append(f"                    {{ output = \"ms_gain_m:Out\" input = \"ms_mix_l:In 1\" }}")
        links.append(f"                    {{ output = \"ms_gain_s:Out\" input = \"ms_mix_l:In 2\" }}")
        links.append(f"                    {{ output = \"ms_gain_m:Out\" input = \"ms_mix_r:In 1\" }}")
        links.append(f"                    {{ output = \"ms_gain_s:Out\" input = \"ms_mix_r:In 2\" }}")
        # Now bass will receive from ms_mix_l:Out / ms_mix_r:Out instead
        ste_out_l = "ms_mix_l:Out"
        ste_out_r = "ms_mix_r:Out"

    # Stereo → Bass
    links.append(f"                    {_link(ste_out_l, bass_in_l)}")
    links.append(f"                    {_link(ste_out_r, bass_in_r)}")

    # Bass → Dialogue enhancer
    if not dial_enabled or dialogue_boost <= 1.0:
        links.append(f"                    {_link(bass_out_l, dial_in_l)}")
        links.append(f"                    {_link(bass_out_r, dial_in_r)}")
    else:
        # Dialogue enhancer uses M/S matrix builtin
        links.append(f"                    {_link(bass_out_l, 'd_cp1_l:In')}")
        links.append(f"                    {_link(bass_out_r, 'd_cp1_r:In')}")
        links.append(f"                    {{ output = \"d_cp1_l:Out\" input = \"d_mix_m:In 1\" }}")
        links.append(f"                    {{ output = \"d_cp1_r:Out\" input = \"d_mix_m:In 2\" }}")
        links.append(f"                    {{ output = \"d_cp1_l:Out\" input = \"d_mix_s:In 1\" }}")
        links.append(f"                    {{ output = \"d_cp1_r:Out\" input = \"d_mix_s:In 2\" }}")
        # Process M through voice EQ
        links.append(f"                    {{ output = \"d_mix_m:Out\" input = \"d_peq_v:In\" }}")
        links.append(f"                    {{ output = \"d_peq_v:Out\" input = \"d_hp_v:In\" }}")
        # Reconstruct L/R
        links.append(f"                    {{ output = \"d_hp_v:Out\" input = \"d_mix_l:In 1\" }}")
        links.append(f"                    {{ output = \"d_mix_s:Out\" input = \"d_mix_l:In 2\" }}")
        links.append(f"                    {{ output = \"d_hp_v:Out\" input = \"d_mix_r:In 1\" }}")
        links.append(f"                    {{ output = \"d_mix_s:Out\" input = \"d_mix_r:In 2\" }}")
        dial_out_l = "d_mix_l:Out"
        dial_out_r = "d_mix_r:Out"

    # Dialogue → Loudness
    links.append(f"                    {_link(dial_out_l, loud_in_l)}")
    links.append(f"                    {_link(dial_out_r, loud_in_r)}")

    # Loudness → Gain stage
    links.append(f"                    {_link(loud_out_l, gain_in_l)}")
    links.append(f"                    {_link(loud_out_r, gain_in_r)}")

    # Gain → (Surround →) Limiter
    if sur_node.strip():
        links.append(f"                    {_link(gain_out_l, sur_in_l)}")
        links.append(f"                    {_link(gain_out_r, sur_in_r)}")
        links.append(f"                    {_link(sur_out_l, lim_in_l)}")
        links.append(f"                    {_link(sur_out_r, lim_in_r)}")
    else:
        links.append(f"                    {_link(gain_out_l, lim_in_l)}")
        links.append(f"                    {_link(gain_out_r, lim_in_r)}")

    links_body = "\n".join(links)

    return f"""            filter.graph = {{
                nodes = [
{nodes_body}
                ]
                links = [
{links_body}
                ]
                inputs = [ "{graph_in_l}" "{graph_in_r}" ]
                outputs = [ "{lim_out_l}" "{lim_out_r}" ]
            }}"""


def _is_preferred_sink(name: str) -> bool:
    """Return True for a built-in speaker/analog sink (not HDMI/Digital)."""
    lower = name.lower()
    if "hdmi" in lower or "digital" in lower:
        return False
    return "speaker" in lower or "analog" in lower


def _get_default_sink(runner=None) -> Optional[str]:
    """Return the default sink name via `pactl get-default-sink`."""
    pactl = shutil.which("pactl")
    if not pactl:
        return None
    try:
        if runner is not None:
            result = runner(["pactl", "get-default-sink"])
        else:
            result = subprocess.run(
                [pactl, "get-default-sink"],
                capture_output=True, text=True, timeout=10,
            )
        return result.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def detect_hardware_sink(
    pactl_output: Optional[str] = None,
    runner=None,
) -> Optional[str]:
    """Detect the real hardware sink node name for the playback leg.

    Preference order:
      1. A built-in speaker/analog sink (name contains "Speaker"/"speaker"/
         "analog", not "HDMI"/"Digital") from `pactl list sinks short`.
      2. The default sink from `pactl get-default-sink`.
      3. Any other alsa_output.* sink.
      4. `pw-cli ls Node` fallback.

    da4linux nodes are always excluded. `pactl_output` injects fake pactl
    output (tests); `runner` injects a subprocess runner (tests).
    """
    real_mode = pactl_output is None
    if pactl_output is None:
        pactl = shutil.which("pactl")
        if pactl:
            try:
                if runner is not None:
                    result = runner(["pactl", "list", "sinks", "short"])
                else:
                    result = subprocess.run(
                        [pactl, "list", "sinks", "short"],
                        capture_output=True, text=True, timeout=10,
                    )
                pactl_output = result.stdout
            except (OSError, subprocess.TimeoutExpired):
                pactl_output = None

    sink_names = []
    if pactl_output:
        for line in pactl_output.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1].startswith("alsa_output."):
                if "da4linux" not in parts[1]:
                    sink_names.append(parts[1])

    # 1) Prefer a built-in speaker/analog sink over HDMI/Digital.
    for name in sink_names:
        if _is_preferred_sink(name):
            return name

    # 2) Fall back to the default sink.
    if real_mode or runner is not None:
        default_sink = _get_default_sink(runner)
        if (
            default_sink
            and default_sink.startswith("alsa_output.")
            and "da4linux" not in default_sink
        ):
            return default_sink

    # 3) Any other alsa_output sink.
    if sink_names:
        return sink_names[0]

    pw_cli = shutil.which("pw-cli")
    if pw_cli:
        try:
            if runner is not None:
                result = runner(["pw-cli", "ls", "Node"])
            else:
                result = subprocess.run(
                    [pw_cli, "ls", "Node"],
                    capture_output=True, text=True, timeout=10,
                )
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith("node.name = "):
                    name = line.split("=", 1)[1].strip().strip('"')
                    if name.startswith("alsa_output.") and "da4linux" not in name:
                        return name
        except (OSError, subprocess.TimeoutExpired):
            pass

    print(
        "Warning: could not detect a hardware sink (pactl/pw-cli unavailable "
        "or no alsa_output.* sink found); generating config without "
        "target.object.",
        file=sys.stderr,
    )
    return None


def generate_pipewire_config(
    profile: DAX3Profile,
    device_info: DeviceInfo,
    ir_dir: str = "~/.local/share/da4linux/ir",
    limiter_type: Optional[str] = None,
    stages: Optional[dict] = None,
    mode: str = "music",
    hrir_path: str = "",
    hardware_sink: Optional[str] = None,
    pactl_output: Optional[str] = None,
) -> str:
    """Generate a complete PipeWire SPA-JSON config from a DAX3 profile.

    Returns the config text as a string, ready to write to a .conf file.
    """
    if limiter_type is None:
        limiter_type = detect_available_limiter()

    if hardware_sink is None:
        hardware_sink = detect_hardware_sink(pactl_output=pactl_output)

    device_name = device_info.product_name or "DA4Linux"
    label = device_info.product_name.replace(" ", "_") if device_info.product_name else "DA4Linux"

    filter_graph = generate_filter_graph(
        profile, device_info, ir_dir, limiter_type,
        stages=stages, mode=mode, hrir_path=hrir_path,
    )

    playback_props = (
        '                node.name = "effect_output.da4linux"\n'
        '                node.passive = true\n'
        '                node.description = "DA4Linux — Output"\n'
    )
    if hardware_sink:
        playback_props += f'                target.object = "{hardware_sink}"\n'

    config = f"""# DA4Linux — PipeWire filter-chain config
# Generated for: {device_name}
# Profile: {profile.name or "default"}
# Mode: {mode}
# DO NOT EDIT MANUALLY — use 'da4linux generate'

context.modules = [
    {{
        name = libpipewire-module-filter-chain
        flags = [ ifexists nofail ]
        args = {{
            node.description = "DA4Linux ({device_name})"
            media.name = "DA4Linux ({device_name})"
            audio.rate = {DEFAULT_SAMPLE_RATE}
{filter_graph}
            audio.channels = 2
            audio.position = [ FL FR ]
            capture.props = {{
                node.name = "effect_input.da4linux"
                media.class = Audio/Sink
                priority.session = 900
                node.description = "DA4Linux — Virtual Sink"
            }}
            playback.props = {{
{playback_props}            }}
        }}
    }}
]
"""
    return config


def detect_available_limiter() -> str:
    """Detect the best available limiter plugin for PipeWire filter-chain.

    Returns one of: "lv2" (LSP LV2), "ladspa" (LSP LADSPA), "zam" (ZaMaximX2),
    or "clamp" (built-in clamp fallback).
    """
    for base in get_lv2_search_paths():
        manifest = base / "lsp-plugins.lv2" / "manifest.ttl"
        if manifest.exists():
            try:
                content = manifest.read_text()
                if "limiter_stereo" in content:
                    return "lv2"
            except (OSError, PermissionError):
                pass

    for ladspa_dir in get_ladspa_search_paths():
        if not ladspa_dir.is_dir():
            continue
        try:
            for f in ladspa_dir.iterdir():
                if f.is_file() and "sc_limiter" in f.name:
                    return "ladspa"
        except (OSError, PermissionError):
            pass

    for ladspa_dir in get_ladspa_search_paths():
        if not ladspa_dir.is_dir():
            continue
        try:
            for f in ladspa_dir.iterdir():
                if f.is_file() and "ZaMaximX2" in f.name:
                    return "zam"
        except (OSError, PermissionError):
            pass

    return "clamp"



def verify_spa_json_syntax(config_text: str) -> bool:
    """Verify bracket balance and basic SPA-JSON formatting."""
    return (
        config_text.count("{") == config_text.count("}")
        and config_text.count("[") == config_text.count("]")
    )


def write_config(config_text: str, output_path: str) -> None:
    """Write the PipeWire config to a file after validating syntax."""
    if not verify_spa_json_syntax(config_text):
        raise ValueError("Generated PipeWire config has unbalanced SPA-JSON brackets")
    p = Path(output_path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(config_text)

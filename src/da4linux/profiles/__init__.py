"""Built-in profiles for known hardware.

When no DAX3 XML is available, these profiles provide safe defaults
for known laptop models.
"""

from ..parser import DAX3Profile, PEQBand, RegulatorSettings, MBCompressorBand, AudioOptimizerBand

STAGE_DEFAULTS = {
    "fir": True,
    "peq": True,
    "mb_compressor": True,
    "stereo": True,
    "bass": True,
    "dialogue": True,
    "loudness": True,
    "surround": False,
    "limiter": True,
}

MODE_PRESETS = {
    "music": {
        "stereo_width": 1.3,
        "bass_amount": 0.6,
        "dialogue_boost": 1.0,
        "comp_ratio": 2.5,
        "surround": False,
    },
    "movie": {
        "stereo_width": 1.5,
        "bass_amount": 0.8,
        "dialogue_boost": 2.5,
        "comp_ratio": 3.0,
        "surround": True,
    },
    "voice": {
        "stereo_width": 1.0,
        "bass_amount": 0.2,
        "dialogue_boost": 4.0,
        "comp_ratio": 1.5,
        "surround": False,
    },
}

BUILTIN_PROFILES = {
    "LENOVO_T14SG2_ALC3287": {
        "name": "ThinkPad T14s Gen 2 (Intel)",
        "vendor": "LENOVO",
        "product_family": "ThinkPad T14s Gen 2i",
        "codec": "ALC3287",
        "description": "2x2W stereo speakers, upward-firing, no subwoofer",
        "peq_bands": [
            {"type": "highpass", "freq": 95, "gain": 0.0, "q": 0.7},
            {"type": "peaking", "freq": 160, "gain": 4.0, "q": 1.2},
            {"type": "peaking", "freq": 500, "gain": -1.5, "q": 1.5},
            {"type": "peaking", "freq": 3500, "gain": -2.0, "q": 2.0},
            {"type": "highshelf", "freq": 8000, "gain": 2.0, "q": 0.7},
        ],
        "volmax_boost": 208.0,  # 208 / 16 = +13.0dB
        "use_fir": False,
    },
    "LENOVO_20WNS73J00_RealtekALC257": {
        "name": "ThinkPad T14s Gen 2i (ALC257)",
        "vendor": "LENOVO",
        "product_family": "ThinkPad T14s Gen 2i",
        "codec": "ALC257",
        "description": "2x2W stereo speakers, upward-firing, no subwoofer — Realtek ALC257 codec",
        "peq_bands": [
            {"type": "highpass", "freq": 95, "gain": 0.0, "q": 0.7},
            {"type": "peaking", "freq": 160, "gain": 4.0, "q": 1.2},
            {"type": "peaking", "freq": 500, "gain": -1.5, "q": 1.5},
            {"type": "peaking", "freq": 3500, "gain": -2.0, "q": 2.0},
            {"type": "highshelf", "freq": 8000, "gain": 2.0, "q": 0.7},
        ],
        "volmax_boost": 208.0,  # 208 / 16 = +13.0dB
        "use_fir": False,
    },
    "GENERIC_LAPTOP": {
        "name": "Generic Laptop Speakers",
        "description": "Optimized defaults for clarity, soundstage, and punch without distortion",
        "peq_bands": [
            {"type": "highpass", "freq": 90, "gain": 0.0, "q": 0.7},
            {"type": "peaking", "freq": 150, "gain": 3.5, "q": 1.2},
            {"type": "peaking", "freq": 500, "gain": -1.5, "q": 1.0},
            {"type": "peaking", "freq": 3500, "gain": -2.0, "q": 1.5},
            {"type": "highshelf", "freq": 8000, "gain": 2.5, "q": 0.7},
        ],
        "volmax_boost": 224.0,  # 224 / 16 = +14.0dB
        "use_fir": False,
    },
}


import json
import os
from pathlib import Path


def load_user_profiles() -> dict[str, dict]:
    """Load external custom JSON profiles from user config and system config dirs."""
    profiles = {}
    config_dirs = [
        Path("/etc/da4linux/profiles"),
        Path(os.environ.get("XDG_CONFIG_HOME") or "~/.config").expanduser() / "da4linux" / "profiles",
    ]
    for d in config_dirs:
        if d.is_dir():
            for json_file in d.glob("*.json"):
                try:
                    data = json.loads(json_file.read_text())
                    key = data.get("key") or json_file.stem
                    profiles[key] = data
                except Exception:
                    pass
    return profiles


def get_profile(key: str) -> DAX3Profile | None:
    """Get a profile by key, checking user profiles first then built-in profiles."""
    user_profiles = load_user_profiles()
    data = user_profiles.get(key) or BUILTIN_PROFILES.get(key)
    if data is None:
        data = BUILTIN_PROFILES.get("GENERIC_LAPTOP")
        if data is None:
            return None

    bands = []
    for b in data.get("peq_bands", []):
        bands.append(
            PEQBand(
                filter_type=b.get("filter_type", b.get("type", "bell")),
                freq=b.get("freq", 1000.0),
                gain=b.get("gain", 0.0),
                q=b.get("q", 0.707),
                enabled=b.get("enabled", True),
            )
        )

    mb_compressor = []
    for b in data.get("mb_compressor", []):
        mb_compressor.append(
            MBCompressorBand(
                threshold=b.get("threshold", 0.0),
                ratio=b.get("ratio", 1.0),
                attack=b.get("attack", 5.0),
                release=b.get("release", 50.0),
                knee=b.get("knee", 0.0),
                makeup_gain=b.get("makeup_gain", 0.0),
            )
        )
        
    ao_bands = []
    for b in data.get("ao_bands", []):
        ao_bands.append(AudioOptimizerBand(gains=b.get("gains", [0.0] * 20)))

    return DAX3Profile(
        name=data.get("name", key),
        endpoint_type=data.get("endpoint_type", "internal_speaker"),
        peq_bands=bands,
        ao_bands=ao_bands,
        mb_compressor=mb_compressor,
        volmax_boost=data.get("volmax_boost", 4.0),
        ieq_enabled=data.get("ieq_enabled", False),
        ieq_amount=data.get("ieq_amount", 0.0),
        ieq_curve=data.get("ieq_curve", []),
        dialog_enhancer=data.get("dialog_enhancer", 0.0),
        volume_leveler=data.get("volume_leveler", 0.0),
        surround_boost=data.get("surround_boost", 0.0),
        crossover_freqs=data.get("crossover_freqs", []),
    )

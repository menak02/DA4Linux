"""Built-in profiles for known hardware.

When no DAX3 XML is available, these profiles provide safe defaults
for known laptop models.
"""

from ..parser import DAX3Profile, PEQBand, RegulatorSettings

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
            {"type": "lowshelf", "freq": 200, "gain": 3.0, "q": 0.7},
            {"type": "peaking", "freq": 500, "gain": -1.5, "q": 1.5},
            {"type": "peaking", "freq": 3000, "gain": 2.0, "q": 2.0},
            {"type": "highshelf", "freq": 8000, "gain": -2.0, "q": 0.7},
        ],
        "volmax_boost": 6.0,
        "use_fir": False,
    },
    "LENOVO_20WNS73J00_RealtekALC257": {
        "name": "ThinkPad T14s Gen 2i (ALC257)",
        "vendor": "LENOVO",
        "product_family": "ThinkPad T14s Gen 2i",
        "codec": "ALC257",
        "description": "2x2W stereo speakers, upward-firing, no subwoofer — Realtek ALC257 codec",
        "peq_bands": [
            {"type": "lowshelf", "freq": 200, "gain": 3.0, "q": 0.7},
            {"type": "peaking", "freq": 500, "gain": -1.5, "q": 1.5},
            {"type": "peaking", "freq": 3000, "gain": 2.0, "q": 2.0},
            {"type": "highshelf", "freq": 8000, "gain": -2.0, "q": 0.7},
        ],
        "volmax_boost": 6.0,
        "use_fir": False,
    },
    "GENERIC_LAPTOP": {
        "name": "Generic Laptop Speakers",
        "description": "Safe defaults for unknown laptop speakers",
        "peq_bands": [
            {"type": "lowshelf", "freq": 150, "gain": 4.0, "q": 0.7},
            {"type": "peaking", "freq": 3000, "gain": 2.0, "q": 1.5},
            {"type": "highshelf", "freq": 10000, "gain": -3.0, "q": 0.7},
        ],
        "volmax_boost": 4.0,
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
                filter_type=b.get("type", "bell"),
                freq=b.get("freq", 1000.0),
                gain=b.get("gain", 0.0),
                q=b.get("q", 0.707),
                enabled=b.get("enabled", True),
            )
        )

    return DAX3Profile(
        name=data.get("name", key),
        endpoint_type="internal_speaker",
        peq_bands=bands,
        volmax_boost=data.get("volmax_boost", 4.0),
    )

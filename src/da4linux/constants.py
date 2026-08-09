"""Windows Audio Effect Type GUIDs and DAX3 XML constants.

All effect type GUIDs are from Microsoft's public ksmedia.h documentation.
"""

# — Windows Audio Effect Type GUIDs (ksmedia.h — public Microsoft documentation) —

EFFECT_TYPE_ACOUSTIC_ECHO_CANCELLATION = "{6f64adbe-9f3e-4f34-9a5c-8c8c3e3af7a8}"
EFFECT_TYPE_NOISE_SUPPRESSION = "{6f64adbf-9f3e-4f34-9a5c-8c8c3e3af7a8}"
EFFECT_TYPE_AUTOMATIC_GAIN_CONTROL = "{6f64adc0-9f3e-4f34-9a5c-8c8c3e3af7a8}"
EFFECT_TYPE_EQUALIZER = "{6f64adc3-9f3e-4f34-9a5c-8c8c3e3af7a8}"
EFFECT_TYPE_LOUDNESS_EQUALIZER = "{6f64adc4-9f3e-4f34-9a5c-8c8c3e3af7a8}"
EFFECT_TYPE_BASS_BOOST = "{6f64adc5-9f3e-4f34-9a5c-8c8c3e3af7a8}"
EFFECT_TYPE_VIRTUAL_SURROUND = "{6f64adc6-9f3e-4f34-9a5c-8c8c3e3af7a8}"
EFFECT_TYPE_VIRTUAL_HEADPHONES = "{6f64adc7-9f3e-4f34-9a5c-8c8c3e3af7a8}"
EFFECT_TYPE_ROOM_CORRECTION = "{6f64adc9-9f3e-4f34-9a5c-8c8c3e3af7a8}"
EFFECT_TYPE_BASS_MANAGEMENT = "{6f64adca-9f3e-4f34-9a5c-8c8c3e3af7a8}"
EFFECT_TYPE_SPEAKER_PROTECTION = "{6f64adcc-9f3e-4f34-9a5c-8c8c3e3af7a8}"
EFFECT_TYPE_SPEAKER_COMPENSATION = "{6f64adcd-9f3e-4f34-9a5c-8c8c3e3af7a8}"
EFFECT_TYPE_DYNAMIC_RANGE_COMPRESSION = "{6f64adce-9f3e-4f34-9a5c-8c8c3e3af7a8}"

# Map GUID strings to human-readable effect type names
EFFECT_TYPE_NAMES = {
    EFFECT_TYPE_ACOUSTIC_ECHO_CANCELLATION: "Acoustic Echo Cancellation",
    EFFECT_TYPE_NOISE_SUPPRESSION: "Noise Suppression",
    EFFECT_TYPE_AUTOMATIC_GAIN_CONTROL: "Automatic Gain Control",
    EFFECT_TYPE_EQUALIZER: "Equalizer",
    EFFECT_TYPE_LOUDNESS_EQUALIZER: "Loudness Equalizer",
    EFFECT_TYPE_BASS_BOOST: "Bass Boost",
    EFFECT_TYPE_VIRTUAL_SURROUND: "Virtual Surround",
    EFFECT_TYPE_VIRTUAL_HEADPHONES: "Virtual Headphones",
    EFFECT_TYPE_ROOM_CORRECTION: "Room Correction",
    EFFECT_TYPE_BASS_MANAGEMENT: "Bass Management",
    EFFECT_TYPE_SPEAKER_PROTECTION: "Speaker Protection",
    EFFECT_TYPE_SPEAKER_COMPENSATION: "Speaker Compensation",
    EFFECT_TYPE_DYNAMIC_RANGE_COMPRESSION: "Dynamic Range Compression",
}

# — DAX3 XML namespace and element constants —

DAX3_NAMESPACE = "http://www.dolby.com/dax3"
DAX3_ROOT_TAG = "dax3"
DAX3_TUNING_TAG = "tuning"
DAX3_ENDPOINT_TAG = "endpoint"
DAX3_PROFILE_TAG = "profile"
DAX3_TUNING_CP_TAG = "tuning-cp"
DAX3_TUNING_VLLDP_TAG = "tuning-vlldp"
DAX3_CONSTANT_TAG = "constant"
DAX3_SPEAKER_PEQ_FILTERS_TAG = "speaker-peq-filters"
DAX3_AUDIO_OPTIMIZER_BANDS_TAG = "audio-optimizer-bands"
DAX3_MB_COMPRESSOR_TUNING_TAG = "mb-compressor-tuning"
DAX3_REGULATOR_TUNING_TAG = "regulator-tuning"

# PEQ filter type mapping (DAX3 int -> internal name)
PEQ_FILTER_TYPES = {
    1: "bell",
    3: "highshelf",
    4: "lowpass",
    6: "notch",
    7: "highpass",
    9: "lowshelf",
}

# PipeWire param_eq filter type name for each PEQ type
PARAM_EQ_TYPES = {
    "bell": "bq_peaking",
    "peaking": "bq_peaking",
    "highshelf": "bq_highshelf",
    "lowshelf": "bq_lowshelf",
    "highpass": "bq_highpass",
    "lowpass": "bq_lowpass",
    "notch": "bq_notch",
}

# Default audio optimizer frequency grid (20 bands, approximate ISO octave centers)
DEFAULT_AO_FREQ_GRID = [
    20, 40, 63, 80, 100, 125, 160, 200, 250, 315,
    400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150,
    4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000,
]

# Default IEQ frequency grid — often specified in the <constant> section
DEFAULT_IEQ_FREQ_GRID = [
    20, 40, 63, 80, 100, 125, 160, 200, 250, 315,
    400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150,
    4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000,
]

# Default sample rate for processing
DEFAULT_SAMPLE_RATE = 48000
# Default FIR tap count
DEFAULT_FIR_TAPS = 4096

# PipeWire config defaults
PW_CONFIG_DIR = "~/.config/pipewire/pipewire.conf.d"
PW_CONFIG_FILE = "50-da4linux.conf"
PW_IR_DIR = "~/.local/share/da4linux/ir"

# ── DSP Stage names ─────────────────────────────────────────────────────

ALL_STAGES = [
    "fir", "peq", "mb_compressor", "stereo",
    "bass", "dialogue", "loudness", "surround", "limiter",
]

DEFAULT_ENABLED_STAGES = [
    "fir", "peq", "mb_compressor", "stereo",
    "bass", "dialogue", "loudness", "limiter",
]

# ── Mode presets ────────────────────────────────────────────────────────

VALID_MODES = ["music", "movie", "voice"]

MODE_PRESETS = {
    "music": {
        "stereo_width": 1.3,
        "bass_amount": 0.6,
        "dialogue_boost": 1.0,
        "comp_ratio": 2.5,
        "surround": False,
        "description": "Wider stereo, moderate bass, moderate compression",
    },
    "movie": {
        "stereo_width": 1.5,
        "bass_amount": 0.8,
        "dialogue_boost": 2.5,
        "comp_ratio": 3.0,
        "surround": True,
        "description": "Virtual surround enabled, heavier bass, dialog boost",
    },
    "voice": {
        "stereo_width": 1.0,
        "bass_amount": 0.2,
        "dialogue_boost": 4.0,
        "comp_ratio": 1.5,
        "surround": False,
        "description": "Dialogue boost max, bass minimal, compressor gentle",
    },
}

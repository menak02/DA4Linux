"""DAX3 XML parser — extracts speaker tuning data from Dolby DAX3 XML files."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from .constants import PEQ_FILTER_TYPES


# — Data model —


@dataclass
class PEQBand:
    """Parametric EQ band from DAX3 speaker-peq-filters."""

    filter_type: str = ""
    freq: float = 0.0
    gain: float = 0.0
    q: float = 0.707
    enabled: bool = True


@dataclass
class AudioOptimizerBand:
    """20-band gain array for a single channel."""

    gains: list[float] = field(default_factory=lambda: [0.0] * 20)


@dataclass
class MBCompressorBand:
    """Multiband compressor band settings."""

    threshold: float = 0.0
    ratio: float = 1.0
    attack: float = 5.0
    release: float = 50.0
    knee: float = 0.0
    makeup_gain: float = 0.0


@dataclass
class RegulatorSettings:
    """Speaker protection regulator settings."""

    threshold_high: float = -1.0
    distortion_slope: float = 0.5
    timbre_preservation: float = 0.5


@dataclass
class DAX3Profile:
    """A single endpoint profile (e.g., music on internal speakers)."""

    name: str = ""
    endpoint_type: str = ""
    peq_bands: list[PEQBand] = field(default_factory=list)
    ao_bands: list[AudioOptimizerBand] = field(default_factory=list)
    mb_compressor: list[MBCompressorBand] = field(default_factory=list)
    regulator: RegulatorSettings = field(default_factory=RegulatorSettings)
    volmax_boost: float = 0.0
    ieq_enabled: bool = False
    ieq_amount: float = 0.0
    ieq_curve: list[float] = field(default_factory=list)
    dialog_enhancer: float = 0.0
    volume_leveler: float = 0.0
    surround_boost: float = 0.0


@dataclass
class DAX3Tuning:
    """Complete DAX3 tuning data with endpoints and constants."""

    endpoints: dict[str, DAX3Profile] = field(default_factory=dict)
    constants: dict[str, object] = field(default_factory=dict)


# — Parsing helpers —


def _text(element, tag, default=""):
    # Check attribute on element itself first (DAX3 <filter> elements use attributes)
    attr = element.get(tag)
    if attr is not None:
        return attr.strip()
    # Check child element
    child = element.find(tag)
    if child is not None:
        # New DAX3 format: <element value="123"/>
        val = child.get("value")
        if val is not None:
            return val.strip()
        # Old format: <element>text</element>
        if child.text:
            return child.text.strip()
    return default


def _float_elem(element, tag, default=0.0):
    val = _text(element, tag)
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _int_elem(element, tag, default=0):
    val = _text(element, tag)
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _bool_elem(element, tag, default=False):
    val = _text(element, tag)
    if val in ("1", "true", "True"):
        return True
    if val in ("0", "false", "False"):
        return False
    return default


def _find_all_elements(element, tag):
    """Find child elements with given tag, ignoring namespace."""
    results = []
    for child in element:
        tag_name = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag_name == tag:
            results.append(child)
    return results


# — Public parsing functions —


def parse_peq_filters(element) -> list[PEQBand]:
    bands = []
    peq_container = element.find("speaker-peq-filters")
    if peq_container is None:
        return bands

    for filt in peq_container.findall("filter"):
        enabled = _bool_elem(filt, "enabled", True)
        if not enabled:
            continue
        ftype = _int_elem(filt, "type", 1)
        # Try f0 (new DAX3 format), fall back to freq
        freq_val = _text(filt, "f0")
        if not freq_val:
            freq_val = _text(filt, "freq")
        freq = float(freq_val) if freq_val else 0.0
        # Gain defaults to 0.0 (crossover filters don't have gain)
        gain = _float_elem(filt, "gain", 0.0)
        # Try order (new DAX3 format), fall back to q
        q_val = _text(filt, "order")
        if not q_val:
            q_val = _text(filt, "q")
        q = float(q_val) if q_val else 0.707
        bands.append(
            PEQBand(
                filter_type=PEQ_FILTER_TYPES.get(ftype, "bell"),
                freq=freq,
                gain=gain,
                q=q,
                enabled=True,
            )
        )
    return bands


def parse_audio_optimizer(element) -> list[AudioOptimizerBand]:
    bands = []
    ao_container = element.find("audio-optimizer-bands")
    if ao_container is None:
        return bands

    for child in ao_container:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if not tag.startswith("ch_"):
            continue

        # New format: <ch_00 value="-240,-240,96,..."/>
        val_attr = child.get("value")
        if val_attr is not None:
            gains = []
            for v in val_attr.split(","):
                try:
                    gains.append(float(v.strip()))
                except ValueError:
                    gains.append(0.0)
            bands.append(AudioOptimizerBand(gains=gains))
            continue

        # Preset format: <ch_00 preset="array_20_zero"/>
        preset = child.get("preset")
        if preset is not None:
            if preset == "array_20_zero":
                bands.append(AudioOptimizerBand(gains=[0.0] * 20))
            elif preset == "array_20_n192":
                bands.append(AudioOptimizerBand(gains=[-192.0] * 20))
            else:
                bands.append(AudioOptimizerBand(gains=[0.0] * 20))
            continue

        # Old format: <ch_00>0,0,0,...</ch_00>
        if child.text:
            gains = []
            for val in child.text.strip().split(","):
                try:
                    gains.append(float(val.strip()))
                except ValueError:
                    gains.append(0.0)
            bands.append(AudioOptimizerBand(gains=gains))
    return bands


def parse_mb_compressor(element) -> list[MBCompressorBand]:
    bands = []
    mb_container = element.find("mb-compressor-tuning")
    if mb_container is None:
        return bands

    for group in mb_container:
        tag = group.tag.split("}")[-1] if "}" in group.tag else group.tag
        if not tag.startswith("band_group_"):
            continue

        # New format: <band_group_0 value="20,0,32767,22641,27238,0"/>
        val_attr = group.get("value")
        if val_attr is not None:
            int_vals = []
            for p in val_attr.split(","):
                try:
                    int_vals.append(int(p.strip()))
                except ValueError:
                    int_vals.append(0)
            while len(int_vals) < 6:
                int_vals.append(0)
            int_vals = int_vals[:6]
            bands.append(
                MBCompressorBand(
                    threshold=float(int_vals[0]),
                    attack=float(int_vals[1]),
                    ratio=float(int_vals[2]) / 32767.0 if int_vals[2] else 1.0,
                    release=float(int_vals[3]),
                    knee=float(int_vals[4]) / 32767.0 if int_vals[4] else 0.0,
                    makeup_gain=float(int_vals[5]) / 32767.0 if int_vals[5] else 0.0,
                )
            )
            continue

        # Old format: <band_group_0 threshold="-24" ratio="2.0" .../>
        bands.append(
            MBCompressorBand(
                threshold=_float_elem(group, "threshold"),
                ratio=_float_elem(group, "ratio", 1.0),
                attack=_float_elem(group, "attack", 5.0),
                release=_float_elem(group, "release", 50.0),
                knee=_float_elem(group, "knee", 0.0),
                makeup_gain=_float_elem(group, "makeup_gain", 0.0),
            )
        )
    return bands


def parse_regulator(element) -> RegulatorSettings:
    reg_container = element.find("regulator-tuning")
    if reg_container is None:
        return RegulatorSettings()

    return RegulatorSettings(
        threshold_high=_float_elem(reg_container, "threshold_high", -1.0),
        distortion_slope=_float_elem(reg_container, "distortion_slope", 0.5),
        timbre_preservation=_float_elem(reg_container, "timbre_preservation", 0.5),
    )


def parse_constants(root) -> dict[str, object]:
    """Extract constant section: frequency grids, IEQ gain curves, etc."""
    constants: dict[str, object] = {}
    const_elem = root.find(".//constant")
    if const_elem is None:
        return constants

    for child in const_elem:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        # New format: <ieq_detailed target="150,142,188,..."/>
        target = child.get("target")
        if target is not None:
            values = []
            for v in target.split(","):
                try:
                    values.append(float(v.strip()))
                except ValueError:
                    values.append(v.strip())
            constants[tag] = values
        elif child.text and child.text.strip():
            text = child.text.strip()
            if "," in text:
                values = []
                for v in text.split(","):
                    try:
                        values.append(float(v.strip()))
                    except ValueError:
                        values.append(v.strip())
                constants[tag] = values
            else:
                try:
                    constants[tag] = float(text)
                except ValueError:
                    constants[tag] = text
        else:
            # Attribute-based constants (e.g., <band_20_freq fs_44100="43,129,..." fs_48000="47,141,..."/>)
            attrib_values: dict[str, object] = {}
            for attr_name, attr_val in child.attrib.items():
                if "," in attr_val:
                    vals = []
                    for v in attr_val.split(","):
                        try:
                            vals.append(float(v.strip()))
                        except ValueError:
                            vals.append(v.strip())
                    attrib_values[attr_name] = vals
                else:
                    try:
                        attrib_values[attr_name] = float(attr_val)
                    except ValueError:
                        attrib_values[attr_name] = attr_val
            if attrib_values:
                constants[tag] = attrib_values
    return constants


def parse_crossover_frequencies(element) -> list[float]:
    """Extract MB compressor crossover/split frequencies from DAX3 XML.

    Looks for crossover frequency elements (split_freq, crossover_freq,
    cross_freq, xover_freq) under mb-compressor-tuning.
    """
    freqs = []
    mb_container = element.find("mb-compressor-tuning")
    if mb_container is None:
        return freqs

    for child in mb_container:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if "split" in tag.lower() or "crossover" in tag.lower() or "cross" in tag.lower() or "xover" in tag.lower():
            try:
                val = child.get("value")
                if val is not None:
                    if "," in val:
                        for v in val.split(","):
                            try:
                                freqs.append(float(v.strip()))
                            except ValueError:
                                pass
                    else:
                        freqs.append(float(val.strip()))
                else:
                    freqs.append(float(child.text.strip()))
            except (ValueError, TypeError, AttributeError):
                pass
    return freqs


def _parse_tuning_cp(cp_elem, profile: DAX3Profile, constants: dict[str, object] | None = None) -> None:
    profile.ieq_enabled = _bool_elem(cp_elem, "ieq-enable", False)
    profile.ieq_amount = _float_elem(cp_elem, "ieq-amount", 0.0)
    # Try new format tag first (dialog-enhancer-amount), fall back to old (dialog-enhancer)
    profile.dialog_enhancer = _float_elem(cp_elem, "dialog-enhancer-amount")
    if profile.dialog_enhancer == 0.0:
        profile.dialog_enhancer = _float_elem(cp_elem, "dialog-enhancer", 0.0)
    profile.volume_leveler = _float_elem(cp_elem, "volume-leveler-amount")
    if profile.volume_leveler == 0.0:
        profile.volume_leveler = _float_elem(cp_elem, "volume-leveler", 0.0)
    profile.surround_boost = _float_elem(cp_elem, "surround-boost", 0.0)
    # volmax-boost may be in tuning-cp (new format) or tuning-vlldp (old format)
    profile.volmax_boost = _float_elem(cp_elem, "volmax-boost", 0.0)

    # IEQ curve: resolve <ieq-bands-set preset="XXX"/> from constants
    ieq_bands_set = cp_elem.find("ieq-bands-set")
    if ieq_bands_set is not None:
        preset_name = ieq_bands_set.get("preset")
        if preset_name and constants and preset_name in constants:
            curve = constants[preset_name]
            if isinstance(curve, list):
                profile.ieq_curve = [float(v) if isinstance(v, (int, float)) else 0.0 for v in curve]

    # Fallback: old format inline ieq-curve/ieq-gains
    if not profile.ieq_curve:
        ieq_curve_text = _text(cp_elem, "ieq-curve") or _text(cp_elem, "ieq-gains")
        if ieq_curve_text:
            for val in ieq_curve_text.split(","):
                try:
                    profile.ieq_curve.append(float(val.strip()))
                except ValueError:
                    pass


def _adjust_constant(name, label):
    """Handle the constant/*_freq and other sub-elements for adjusting."""
    return name, label


def _parse_tuning_vlldp(vlldp_elem, profile: DAX3Profile) -> None:
    profile.peq_bands = parse_peq_filters(vlldp_elem)
    profile.ao_bands = parse_audio_optimizer(vlldp_elem)
    profile.mb_compressor = parse_mb_compressor(vlldp_elem)
    profile.regulator = parse_regulator(vlldp_elem)
    # volmax-boost from vlldp overrides tuning-cp value if present
    volmax = _float_elem(vlldp_elem, "volmax-boost", 0.0)
    if volmax != 0.0:
        profile.volmax_boost = volmax


def parse_dax3_xml(filepath: str) -> DAX3Tuning:
    tree = ET.parse(filepath)
    root = tree.getroot()

    tuning = DAX3Tuning()
    tuning.constants = parse_constants(root)

    tuning_elem = root.find("tuning")
    if tuning_elem is not None:
        root = tuning_elem

    for endpoint in root.findall("endpoint"):
        endpoint_type = endpoint.get("type", "unknown")
        for profile_elem in endpoint.findall("profile"):
            profile_name = profile_elem.get("type", endpoint_type)
            key = f"{endpoint_type}/{profile_name}"

            p = DAX3Profile(
                name=profile_name,
                endpoint_type=endpoint_type,
            )

            cp = profile_elem.find("tuning-cp")
            if cp is not None:
                _parse_tuning_cp(cp, p, tuning.constants)

            vlldp = profile_elem.find("tuning-vlldp")
            if vlldp is not None:
                _parse_tuning_vlldp(vlldp, p)

            tuning.endpoints[key] = p

    if not tuning.endpoints:
        # Try flat <tuning-cp> and <tuning-vlldp> directly under root
        p = DAX3Profile(name="default", endpoint_type="internal_speaker")
        cp = root.find("tuning-cp")
        if cp is not None:
            _parse_tuning_cp(cp, p)
        vlldp = root.find("tuning-vlldp")
        if vlldp is not None:
            _parse_tuning_vlldp(vlldp, p)
        # Only add if we actually found tuning data
        if cp is not None or vlldp is not None:
            tuning.endpoints["internal_speaker/default"] = p

    return tuning

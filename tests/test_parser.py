"""Tests for the DAX3 XML parser."""

import io
import sys
from pathlib import Path

# Add src to path for direct test running
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from da4linux.parser import parse_dax3_xml, DAX3Tuning


SAMPLE_DAX3_XML = """<?xml version="1.0" encoding="utf-8"?>
<dax3>
  <tuning>
    <endpoint type="internal_speaker" operating_mode="normal">
      <profile type="music">
        <tuning-cp>
          <ieq-enable>1</ieq-enable>
          <ieq-amount>10</ieq-amount>
          <dialog-enhancer>5</dialog-enhancer>
          <volume-leveler>8</volume-leveler>
          <surround-boost>3</surround-boost>
        </tuning-cp>
        <tuning-vlldp>
          <speaker-peq-filters>
            <filter enabled="1" type="1" freq="500" gain="3.0" q="2.0"/>
            <filter enabled="1" type="9" freq="100" gain="6.0" q="0.707"/>
            <filter enabled="1" type="3" freq="8000" gain="-2.0" q="0.7"/>
            <filter enabled="0" type="1" freq="1000" gain="-5.0" q="1.0"/>
          </speaker-peq-filters>
          <audio-optimizer-bands>
            <ch_00>0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0</ch_00>
            <ch_01>1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1</ch_01>
          </audio-optimizer-bands>
          <mb-compressor-tuning>
            <band_group_0 threshold="-24" ratio="2.0" attack="20" release="80"/>
            <band_group_1 threshold="-18" ratio="1.5" attack="15" release="60"/>
          </mb-compressor-tuning>
          <regulator-tuning>
            <threshold_high>-2.0</threshold_high>
            <distortion_slope>0.3</distortion_slope>
            <timbre_preservation>0.8</timbre_preservation>
          </regulator-tuning>
          <volmax-boost>6.0</volmax-boost>
        </tuning-vlldp>
      </profile>
    </endpoint>
  </tuning>
  <constant>
    <band_20_freq>20,40,63,80,100,125,160,200,250,315,400,500,630,800,1000,1250,1600,2000,2500,3150,4000,5000,6300,8000,10000,12500,16000,20000</band_20_freq>
    <ieq_balanced>0,0.5,1.0,1.5,2.0,2.5,3.0,3.5,4.0,4.5,5.0,5.5,6.0,5.0,4.0,3.0,2.0,1.0,0,-1.0,-2.0,-3.0,-4.0,-5.0,-6.0,-7.0,-8.0,-9.0</ieq_balanced>
  </constant>
</dax3>"""


def test_parse_minimal_xml():
    """Parse a minimal but well-formed DAX3 XML string."""
    import tempfile
    import os

    fd, tmp = tempfile.mkstemp(suffix=".xml", text=True)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(SAMPLE_DAX3_XML)
        tuning = parse_dax3_xml(tmp)
        assert isinstance(tuning, DAX3Tuning)
        assert len(tuning.endpoints) > 0
    finally:
        os.unlink(tmp)


def test_parse_endpoint_keys():
    """Verify endpoint keys use the expected format."""
    import tempfile
    import os

    fd, tmp = tempfile.mkstemp(suffix=".xml", text=True)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(SAMPLE_DAX3_XML)
        tuning = parse_dax3_xml(tmp)
        keys = list(tuning.endpoints.keys())
        assert len(keys) == 1
        assert "/" in keys[0]
    finally:
        os.unlink(tmp)


def test_parse_peq_bands():
    """Verify PEQ bands are parsed with correct types and values."""
    import tempfile
    import os

    fd, tmp = tempfile.mkstemp(suffix=".xml", text=True)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(SAMPLE_DAX3_XML)
        tuning = parse_dax3_xml(tmp)
        profile = list(tuning.endpoints.values())[0]
        bands = profile.peq_bands
        # 4 filters in XML, but one disabled -> 3 active
        assert len(bands) == 3
        # First band: type 1 -> bell, freq 500, gain 3.0, q 2.0
        assert bands[0].filter_type == "bell"
        assert bands[0].freq == 500.0
        assert bands[0].gain == 3.0
        assert bands[0].q == 2.0
        # Second band: type 9 -> lowshelf
        assert bands[1].filter_type == "lowshelf"
        # Third band: type 3 -> highshelf
        assert bands[2].filter_type == "highshelf"
    finally:
        os.unlink(tmp)


def test_parse_audio_optimizer():
    """Verify audio optimizer bands are parsed."""
    import tempfile
    import os

    fd, tmp = tempfile.mkstemp(suffix=".xml", text=True)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(SAMPLE_DAX3_XML)
        tuning = parse_dax3_xml(tmp)
        profile = list(tuning.endpoints.values())[0]
        # 2 channels
        assert len(profile.ao_bands) == 2
        assert len(profile.ao_bands[0].gains) == 20
        assert profile.ao_bands[0].gains[0] == 0.0
        assert profile.ao_bands[1].gains[0] == 1.0
    finally:
        os.unlink(tmp)


def test_parse_mb_compressor():
    """Verify multiband compressor bands are parsed."""
    import tempfile
    import os

    fd, tmp = tempfile.mkstemp(suffix=".xml", text=True)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(SAMPLE_DAX3_XML)
        tuning = parse_dax3_xml(tmp)
        profile = list(tuning.endpoints.values())[0]
        assert len(profile.mb_compressor) == 2
        assert profile.mb_compressor[0].threshold == -24.0
        assert profile.mb_compressor[0].ratio == 2.0
    finally:
        os.unlink(tmp)


def test_parse_regulator():
    """Verify regulator settings are parsed."""
    import tempfile
    import os

    fd, tmp = tempfile.mkstemp(suffix=".xml", text=True)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(SAMPLE_DAX3_XML)
        tuning = parse_dax3_xml(tmp)
        profile = list(tuning.endpoints.values())[0]
        reg = profile.regulator
        assert reg.threshold_high == -2.0
        assert reg.distortion_slope == 0.3
        assert reg.timbre_preservation == 0.8
    finally:
        os.unlink(tmp)


def test_parse_constants():
    """Verify constant section is parsed."""
    import tempfile
    import os

    fd, tmp = tempfile.mkstemp(suffix=".xml", text=True)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(SAMPLE_DAX3_XML)
        tuning = parse_dax3_xml(tmp)
        assert "band_20_freq" in tuning.constants
        assert "ieq_balanced" in tuning.constants
        assert isinstance(tuning.constants["band_20_freq"], list)
    finally:
        os.unlink(tmp)


def test_parse_empty_xml():
    """Parse an empty dax3 root element."""
    import tempfile
    import os

    fd, tmp = tempfile.mkstemp(suffix=".xml", text=True)
    try:
        with os.fdopen(fd, "w") as f:
            f.write("<dax3></dax3>")
        tuning = parse_dax3_xml(tmp)
        assert isinstance(tuning, DAX3Tuning)
        assert len(tuning.endpoints) == 0
    finally:
        os.unlink(tmp)


def test_parse_volmax_boost():
    """Verify volmax-boost is parsed."""
    import tempfile
    import os

    fd, tmp = tempfile.mkstemp(suffix=".xml", text=True)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(SAMPLE_DAX3_XML)
        tuning = parse_dax3_xml(tmp)
        profile = list(tuning.endpoints.values())[0]
        assert profile.volmax_boost == 6.0
    finally:
        os.unlink(tmp)


def test_parse_crossover_frequencies():
    """Verify crossover frequencies can be extracted."""
    import tempfile
    import os
    idxml = """<?xml version="1.0" encoding="utf-8"?>
<dax3>
  <tuning>
    <endpoint type="internal_speaker">
      <profile type="music">
        <tuning-vlldp>
          <mb-compressor-tuning>
            <split_freq_0>120</split_freq_0>
            <split_freq_1>500</split_freq_1>
            <split_freq_2>3000</split_freq_2>
          </mb-compressor-tuning>
        </tuning-vlldp>
      </profile>
    </endpoint>
  </tuning>
</dax3>"""
    from da4linux.parser import parse_crossover_frequencies
    import xml.etree.ElementTree as ET
    root = ET.fromstring(idxml)
    # Walk into tuning-vlldp
    vlldp = root.find(".//tuning-vlldp")
    freqs = parse_crossover_frequencies(vlldp)
    assert len(freqs) == 3
    assert freqs[0] == 120.0
    assert freqs[1] == 500.0
    assert freqs[2] == 3000.0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

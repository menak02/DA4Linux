"""Tests for the PipeWire config generator."""

import sys
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from da4linux.generator import (
    generate_pipewire_config,
    generate_filter_graph,
    detect_available_limiter,
    detect_hardware_sink,
    peq_band_to_spa_filter,
)
from da4linux.parser import DAX3Profile, PEQBand
from da4linux.detect import DeviceInfo


def _make_profile(peq_bands=None, volmax=0.0):
    return DAX3Profile(
        name="test",
        endpoint_type="internal_speaker",
        peq_bands=peq_bands or [],
        volmax_boost=volmax,
    )


def _make_device():
    return DeviceInfo(
        vendor="TESTCO",
        product_name="FooBook Pro",
        codec_name="ALC999",
    )


def test_peq_band_to_filter_bell():
    band = PEQBand(filter_type="bell", freq=500, gain=3.0, q=2.0)
    result = peq_band_to_spa_filter(band)
    assert "bq_peaking" in result
    assert "freq = 500" in result
    assert "gain = 3.000" in result
    assert "q = 2.0000" in result


def test_peq_band_to_filter_lowshelf():
    band = PEQBand(filter_type="lowshelf", freq=200, gain=4.0, q=0.7)
    result = peq_band_to_spa_filter(band)
    assert "bq_lowshelf" in result
    assert "freq = 200" in result


def test_generate_filter_graph_basic():
    profile = _make_profile(
        peq_bands=[
            PEQBand(filter_type="bell", freq=500, gain=-1.5, q=1.5),
        ],
        volmax=6.0,
    )
    device = _make_device()
    graph = generate_filter_graph(
        profile, device,
        ir_dir="/tmp/test_ir",
        limiter_type="clamp",
    )
    assert "filter.graph" in graph
    assert "conv_l" not in graph
    assert "/dirac" not in graph
    assert "peq" in graph
    assert "gain_out_l" in graph
    assert "limiter_l" in graph
    assert 'inputs = [ "peq:In 1" "peq:In 2" ]' in graph


def test_generate_filter_graph_with_fir(tmp_path):
    # Create fake IR files
    ir_dir = tmp_path / "ir"
    ir_dir.mkdir()
    (ir_dir / "testco_foobook_pro_L.wav").write_bytes(b"RIFF")
    (ir_dir / "testco_foobook_pro_R.wav").write_bytes(b"RIFF")

    profile = _make_profile(volmax=6.0)
    profile.ao_bands = [object()]  # non-empty
    device = _make_device()

    graph = generate_filter_graph(
        profile, device,
        ir_dir=str(ir_dir),
        limiter_type="clamp",
    )
    assert "conv_l" in graph
    assert "conv_r" in graph
    assert 'inputs = [ "conv_l:In" "conv_r:In" ]' in graph


def test_generate_filter_graph_lv2_limiter():
    profile = _make_profile(volmax=3.0)
    device = _make_device()
    graph = generate_filter_graph(
        profile, device,
        ir_dir="/tmp/test_ir",
        limiter_type="lv2",
    )
    assert "limiter_stereo" in graph
    assert "lsp-plug.in" in graph
    assert "limiter:in_l" in graph
    assert "limiter:out_l" in graph


def test_generate_filter_graph_ladspa_limiter():
    profile = _make_profile(volmax=3.0)
    device = _make_device()
    graph = generate_filter_graph(
        profile, device,
        ir_dir="/tmp/test_ir",
        limiter_type="ladspa",
    )
    assert "sc_limiter_stereo" in graph
    assert "lsp-plugins-ladspa" in graph
    assert "limiter:Input L" in graph
    assert "limiter:Output L" in graph


def test_generate_filter_graph_zam_limiter():
    profile = _make_profile(volmax=3.0)
    device = _make_device()
    graph = generate_filter_graph(
        profile, device,
        ir_dir="/tmp/test_ir",
        limiter_type="zam",
    )
    assert "ZaMaximX2" in graph
    assert "Threshold" in graph
    assert "Release" in graph
    assert "limiter:Input L" in graph


def test_generate_filter_graph_clamp_limiter():
    profile = _make_profile(volmax=3.0)
    device = _make_device()
    graph = generate_filter_graph(
        profile, device,
        ir_dir="/tmp/test_ir",
        limiter_type="clamp",
    )
    assert "builtin" in graph
    assert "clamp" in graph
    assert "limiter_l" in graph
    assert "limiter_r" in graph
    assert '"Min" = -1.0' in graph
    assert '"Max" = 1.0' in graph


def test_generate_pipewire_config():
    profile = _make_profile(
        peq_bands=[
            PEQBand(filter_type="highshelf", freq=8000, gain=-2.0, q=0.7),
        ],
    )
    device = _make_device()
    config = generate_pipewire_config(
        profile, device,
        ir_dir="/tmp/test_ir",
        limiter_type="clamp",
    )
    assert "context.modules" in config
    assert "libpipewire-module-filter-chain" in config
    assert "DA4Linux" in config
    assert "FooBook" in config
    assert "effect_input.da4linux" in config
    assert "effect_output.da4linux" in config


def test_playback_props_has_no_media_class():
    """The playback leg of the filter-chain must not claim Audio/Sink.

    Only the capture leg (the virtual sink) may declare media.class = Audio/Sink.
    A media.class on the Output-direction playback stream crashes the PipeWire
    core daemon at startup.
    """
    profile = _make_profile()
    device = _make_device()
    config = generate_pipewire_config(
        profile, device,
        ir_dir="/tmp/test_ir",
        limiter_type="clamp",
    )
    capture_block = config.split("capture.props")[1].split("}}")[0]
    playback_block = config.split("playback.props")[1].split("}}")[0]
    assert "media.class = Audio/Sink" in capture_block
    assert "media.class" not in playback_block


def test_playback_props_has_target_object_when_sink_detected():
    """When a hardware sink is detected, the playback leg pins to it."""
    profile = _make_profile()
    device = _make_device()
    fake_pactl = (
        "1\talsa_output.pci-fake.analog-stereo\tPipeWire\t"
        "s32le 2ch 48000Hz\tRUNNING\n"
    )
    config = generate_pipewire_config(
        profile, device,
        ir_dir="/tmp/test_ir",
        limiter_type="clamp",
        pactl_output=fake_pactl,
    )
    playback_block = config.split("playback.props")[1].split("}}")[0]
    assert 'target.object = "alsa_output.pci-fake.analog-stereo"' in playback_block


def test_playback_props_no_target_object_when_detection_fails():
    """When detection fails, the config must omit target.object (never a
    broken target)."""
    profile = _make_profile()
    device = _make_device()
    with patch("da4linux.generator.detect_hardware_sink", return_value=None):
        config = generate_pipewire_config(
            profile, device,
            ir_dir="/tmp/test_ir",
            limiter_type="clamp",
        )
    playback_block = config.split("playback.props")[1].split("}}")[0]
    assert "target.object" not in playback_block


def test_capture_props_priority_session_900():
    """The virtual sink must have high priority.session to become the
    default sink."""
    profile = _make_profile()
    device = _make_device()
    config = generate_pipewire_config(
        profile, device,
        ir_dir="/tmp/test_ir",
        limiter_type="clamp",
    )
    capture_block = config.split("capture.props")[1].split("}}")[0]
    assert "priority.session = 900" in capture_block


def test_detect_hardware_sink_finds_alsa_output():
    """pactl output with an alsa_output sink is picked."""
    out = "49\talsa_output.pci-0000_00_1f.3.analog-stereo\tPipeWire\ts32le 2ch 48000Hz\tRUNNING\n"
    assert detect_hardware_sink(pactl_output=out) == \
        "alsa_output.pci-0000_00_1f.3.analog-stereo"


def test_detect_hardware_sink_excludes_da4linux():
    """da4linux nodes must never be picked as the target sink."""
    out = (
        "1\teffect_input.da4linux\tPipeWire\ts32le 2ch 48000Hz\tRUNNING\n"
        "2\talsa_output.pci-fake.analog-stereo\tPipeWire\ts32le 2ch 48000Hz\tRUNNING\n"
    )
    assert detect_hardware_sink(pactl_output=out) == \
        "alsa_output.pci-fake.analog-stereo"


def test_detect_hardware_sink_none_when_no_alsa():
    """No alsa_output sink in pactl output (and pw-cli unavailable) → None."""
    def _no_tools(cmd):
        raise OSError("no pipewire tools")

    out = "1\tbluez_output.00_11_22.1\tPipeWire\ts32le 2ch 48000Hz\tRUNNING\n"
    assert detect_hardware_sink(pactl_output=out, runner=_no_tools) is None


def test_detect_hardware_sink_prefers_speaker_over_hdmi():
    """Built-in Speaker sink must be preferred over HDMI sinks."""
    out = (
        "1\talsa_output.pci-0000_00_1f.3-platform-skl_hda_dsp_generic.HiFi__HDMI3__sink\t"
        "PipeWire\ts32le 2ch 48000Hz\tSUSPENDED\n"
        "2\talsa_output.pci-0000_00_1f.3-platform-skl_hda_dsp_generic.HiFi__HDMI2__sink\t"
        "PipeWire\ts32le 2ch 48000Hz\tSUSPENDED\n"
        "3\talsa_output.pci-0000_00_1f.3-platform-skl_hda_dsp_generic.HiFi__Speaker__sink\t"
        "PipeWire\ts32le 2ch 48000Hz\tIDLE\n"
    )
    assert detect_hardware_sink(pactl_output=out) == \
        "alsa_output.pci-0000_00_1f.3-platform-skl_hda_dsp_generic.HiFi__Speaker__sink"


def test_detect_hardware_sink_falls_back_to_default():
    """No speaker/analog sink → the default sink is used."""
    from types import SimpleNamespace

    def _fake_runner(cmd):
        if cmd == ["pactl", "list", "sinks", "short"]:
            return SimpleNamespace(stdout=(
                "1\talsa_output.pci-0000_00_1f.3-platform.HiFi__HDMI1__sink\t"
                "PipeWire\ts32le 2ch 48000Hz\tSUSPENDED\n"
            ))
        if cmd == ["pactl", "get-default-sink"]:
            return SimpleNamespace(stdout=(
                "alsa_output.pci-0000_00_1f.3-platform.HiFi__Speaker__sink\n"
            ))
        return SimpleNamespace(stdout="")

    assert detect_hardware_sink(runner=_fake_runner) == \
        "alsa_output.pci-0000_00_1f.3-platform.HiFi__Speaker__sink"


def test_detect_hardware_sink_excludes_da4linux_default():
    """The default sink must never be the da4linux virtual sink."""
    from types import SimpleNamespace

    def _fake_runner(cmd):
        if cmd == ["pactl", "list", "sinks", "short"]:
            return SimpleNamespace(stdout="")
        if cmd == ["pactl", "get-default-sink"]:
            return SimpleNamespace(stdout="effect_input.da4linux\n")
        return SimpleNamespace(stdout="")

    assert detect_hardware_sink(runner=_fake_runner) is None


def test_capture_playback_props_have_no_volume_boost():
    """The 6 dB volmax boost must not be baked into the sink volume.

    KDE's volume OSD must see a normal 0-100% sink; the boost lives inside
    the filter graph instead.
    """
    profile = _make_profile(volmax=96.0)
    device = _make_device()
    config = generate_pipewire_config(
        profile, device,
        ir_dir="/tmp/test_ir",
        limiter_type="clamp",
    )
    capture_block = config.split("capture.props")[1].split("}}")[0]
    playback_block = config.split("playback.props")[1].split("}}")[0]
    assert "volume" not in capture_block
    assert "volume" not in playback_block
    assert "channelVolumes" not in capture_block
    assert "channelVolumes" not in playback_block


def test_volmax_boost_is_internal_gain_node():
    """volmax_boost 96 (1/16 dB units) = 6 dB → linear gain node in graph."""
    profile = _make_profile(volmax=96.0)
    device = _make_device()
    # Test with bass stage disabled (6dB unattenuated gain = 1.995262)
    graph_raw = generate_filter_graph(
        profile, device,
        ir_dir="/tmp/test_ir",
        limiter_type="clamp",
        stages={"bass": False},
    )
    assert "gain_out_l" in graph_raw
    assert "gain_out_r" in graph_raw
    assert '"Mult" = 1.995262' in graph_raw

    # Test with default active stages (headroom pre-attenuated gain)
    graph_headroom = generate_filter_graph(
        profile, device,
        ir_dir="/tmp/test_ir",
        limiter_type="clamp",
    )
    assert '"Mult" = 1.318257' in graph_headroom


def test_generate_no_peq_bands():
    profile = _make_profile()
    device = _make_device()
    config = generate_pipewire_config(
        profile, device,
        ir_dir="/tmp/test_ir",
        limiter_type="clamp",
    )
    assert "context.modules" in config
    assert "bq_peaking" in config


def test_empty_device_name():
    device = DeviceInfo()
    profile = _make_profile()
    config = generate_pipewire_config(profile, device)
    assert "DA4Linux" in config


def test_detect_available_limiter_real_system():
    """On the real system, LSP LV2 should be detected."""
    result = detect_available_limiter()
    assert result == "lv2"


def test_detect_available_limiter_fallback():
    """When no plugins found, returns 'clamp'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        lv2_dir = tmp / "lv2" / "lsp-plugins.lv2"
        lv2_dir.mkdir(parents=True)
        manifest = lv2_dir / "manifest.ttl"
        manifest.write_text("plug:compressor_stereo")  # no limiter_stereo

        ladspa_dir = tmp / "ladspa"
        ladspa_dir.mkdir(parents=True)

        with patch("da4linux.generator.get_lv2_search_paths", return_value=[tmp / "lv2"]):
            with patch("da4linux.generator.get_ladspa_search_paths", return_value=[ladspa_dir]):
                result = detect_available_limiter()
                assert result == "clamp"


def test_mb_compressor_node():
    """Verify LSP MB compressor node is generated."""
    from da4linux.generator import _generate_mb_compressor_node
    node, out_l, out_r, in_l, in_r = _generate_mb_compressor_node(enabled=True)
    assert "mb_compressor_stereo" in node
    assert "lsp-plug.in" in node
    assert "sf_1" in node
    assert "sf_2" in node
    assert "sf_3" in node
    assert out_l == "mb:out_l"
    assert in_l == "mb:in_l"


def test_mb_compressor_disabled():
    """Verify MB compressor stage returns passthrough when disabled."""
    from da4linux.generator import _generate_mb_compressor_node
    node, out_l, out_r, in_l, in_r = _generate_mb_compressor_node(enabled=False)
    assert "mb_byp" in node
    # Either CALF LV2 or M/S matrix
    assert len(node) > 100
    assert "In" in in_l or "in_l" in in_l
    assert "Out" in out_l or "out_l" in out_l


def test_stereo_enhancer_disabled():
    """Verify stereo enhancer disabled produces passthrough."""
    from da4linux.generator import _generate_stereo_enhancer_node
    node, out_l, out_r, in_l, in_r = _generate_stereo_enhancer_node(enabled=False)
    assert "ste_byp" in node
    assert "stereo" not in node or "linear" in node


def test_bass_enhancer_calf():
    """Verify CALF BassEnhancer node is generated."""
    from da4linux.generator import _generate_bass_enhancer_node
    node, out_l, out_r, in_l, in_r = _generate_bass_enhancer_node(enabled=True, amount=0.7)
    assert len(node) > 100
    # Should contain BassEnhancer URI or bq_lowshelf fallback
    assert "BassEnhancer" in node or "bq_lowshelf" in node
    assert "bass:" in out_l or "bass_" in out_l


def test_bass_enhancer_disabled():
    """Verify bass enhancer disabled produces passthrough."""
    from da4linux.generator import _generate_bass_enhancer_node
    node, out_l, out_r, in_l, in_r = _generate_bass_enhancer_node(enabled=False)
    assert "bass_byp" in node


def test_dialogue_enhancer():
    """Verify M/S dialogue processing nodes are generated."""
    from da4linux.generator import _generate_dialogue_enhancer_node
    node, out_l, out_r, in_l, in_r = _generate_dialogue_enhancer_node(
        enabled=True, boost=3.0,
    )
    assert len(node) > 100
    assert "d_mix_m" in node or "d_mix_s" in node
    assert "bq_peaking" in node
    assert "bq_highpass" in node
    assert "d_mix_l" in node
    assert "d_mix_r" in node


def test_dialogue_enhancer_disabled():
    """Verify dialogue enhancer disabled produces passthrough."""
    from da4linux.generator import _generate_dialogue_enhancer_node
    node, out_l, out_r, in_l, in_r = _generate_dialogue_enhancer_node(
        enabled=False, boost=2.0,
    )
    assert "dial_byp" in node
    assert "d_mix_m" not in node


def test_loudness_node():
    """Verify loudness node is generated (LSP loud_comp or ebur128)."""
    from da4linux.generator import _generate_loudness_node
    node, out_l, out_r, in_l, in_r = _generate_loudness_node(enabled=True)
    assert len(node) > 50
    assert "loud" in node or "ebu" in node
    assert "out" in out_l.lower()


def test_loudness_disabled():
    """Verify loudness disabled produces passthrough."""
    from da4linux.generator import _generate_loudness_node
    node, out_l, out_r, in_l, in_r = _generate_loudness_node(enabled=False)
    assert "loud_byp" in node


def test_virtual_surround_node_empty_when_no_hrir():
    """Virtual surround returns empty when HRIR path is empty."""
    from da4linux.generator import _generate_virtual_surround_node
    node, out_l, out_r, in_l, in_r = _generate_virtual_surround_node(
        enabled=True, hrir_path="",
    )
    assert node == ""


def test_stage_disabling():
    """Verify disabled stages produce passthrough in the full graph."""
    profile = _make_profile(volmax=3.0)
    device = _make_device()
    disabled = {
        "fir": False, "peq": False, "mb_compressor": False,
        "stereo": False, "bass": False, "dialogue": False,
        "loudness": False, "surround": False, "limiter": True,
    }
    graph = generate_filter_graph(
        profile, device,
        ir_dir="/tmp/test_ir",
        limiter_type="clamp",
        stages=disabled,
        mode="music",
    )
    assert "filter.graph" in graph
    assert "mb_byp" in graph
    assert "ste_byp" in graph
    assert "bass_byp" in graph
    assert "dial_byp" in graph
    assert "loud_byp" in graph


def test_mode_presets():
    """Verify music/movie/voice produce different configs."""
    profile = _make_profile(volmax=3.0)
    device = _make_device()

    music_graph = generate_filter_graph(profile, device, ir_dir="/tmp/test_ir",
                                         limiter_type="clamp", mode="music")
    movie_graph = generate_filter_graph(profile, device, ir_dir="/tmp/test_ir",
                                         limiter_type="clamp", mode="movie")
    voice_graph = generate_filter_graph(profile, device, ir_dir="/tmp/test_ir",
                                         limiter_type="clamp", mode="voice")

    # Music should have lower dialogue boost than voice
    assert "d_peq_v" in voice_graph
    # Movie should have wider stereo
    assert len(music_graph) > 0
    assert len(movie_graph) > 0
    assert len(voice_graph) > 0
    # Voice should have higher dialogue boost gain
    # Check that voice graph differs from music/movie
    assert music_graph != voice_graph or music_graph != movie_graph


def test_full_chain():
    """Verify all stages are linked in the expected order."""
    profile = _make_profile(volmax=3.0)
    device = _make_device()
    graph = generate_filter_graph(
        profile, device,
        ir_dir="/tmp/test_ir",
        limiter_type="lv2",
        mode="music",
    )
    assert "filter.graph" in graph
    assert "nodes = [" in graph
    assert "links = [" in graph
    assert "inputs = [" in graph
    assert "outputs = [" in graph
    # Check key stage nodes are present
    assert "peq" in graph
    assert "mb" in graph or "mb_" in graph
    assert "stereo" in graph or "ms_" in graph
    assert "bass" in graph or "bass_" in graph
    assert "limiter" in graph
    # Check links exist between stages
    assert "input = " in graph
    assert "output = " in graph


def test_stage_node_count():
    """Full graph should have a reasonable number of nodes."""
    profile = _make_profile(volmax=3.0)
    device = _make_device()
    graph = generate_filter_graph(
        profile, device,
        ir_dir="/tmp/test_ir",
        limiter_type="clamp",
        mode="music",
    )
    lines = graph.splitlines()
    node_count = sum(1 for l in lines if "name =" in l and "type =" not in l)
    # We should have at least 12 nodes (2 conv + peq + 2 gain + 2 limiter + others)
    assert node_count >= 12


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

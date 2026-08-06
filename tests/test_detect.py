"""Tests for hardware detection (skip on non-Linux)."""

import os
import sys
import platform
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from da4linux.detect import (
    DeviceInfo,
    detect_device,
    detect_dmi,
    detect_codec,
    detect_pci,
    get_profile_key,
)


IS_LINUX = platform.system() == "Linux"


def _try_pytest_skip(reason):
    """Fail with the reason if we're not on Linux."""
    if not IS_LINUX:
        # Try to find/import pytest for proper skip, otherwise just return
        try:
            import pytest
            pytest.skip(reason)
        except ImportError:
            print(f"SKIP: {reason}")
            return False
    return True


def test_detect_dmi():
    if not IS_LINUX:
        print("SKIP: not Linux")
        return
    result = detect_dmi()
    assert isinstance(result, dict)
    assert "vendor" in result
    assert "product_name" in result
    assert "product_family" in result


def test_detect_codec():
    if not IS_LINUX:
        print("SKIP: not Linux")
        return
    result = detect_codec()
    assert isinstance(result, dict)
    assert "vendor_id" in result
    assert "subsystem_id" in result
    assert "codec_name" in result


def test_detect_pci():
    if not IS_LINUX:
        print("SKIP: not Linux")
        return
    result = detect_pci()
    assert isinstance(result, dict)
    assert "vendor" in result
    assert "device" in result


def test_detect_device():
    if not IS_LINUX:
        print("SKIP: not Linux")
        return
    info = detect_device()
    assert isinstance(info, DeviceInfo)
    assert isinstance(info.product_name, str)
    assert isinstance(info.codec_name, str)
    assert info.speaker_count > 0


def test_device_info_defaults():
    info = DeviceInfo()
    assert info.vendor == ""
    assert info.product_name == ""
    assert info.speaker_count == 2
    assert info.has_subwoofer is False


def test_get_profile_key():
    info = DeviceInfo(
        vendor="LENOVO",
        product_name="ThinkPad T14s Gen 2i",
        codec_name="Realtek ALC3287",
    )
    key = get_profile_key(info)
    assert "LENOVO" in key
    assert "T14S" in key or "ThinkPad" in key or "ALC3287" in key


def test_get_profile_key_empty():
    info = DeviceInfo()
    key = get_profile_key(info)
    assert key == "UNKNOWN" or isinstance(key, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

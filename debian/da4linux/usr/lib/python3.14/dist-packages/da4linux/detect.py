"""Hardware detection via DMI and ALSA sysfs (no root required)."""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DeviceInfo:
    vendor: str = ""
    product_name: str = ""
    product_family: str = ""
    product_version: str = ""
    codec_name: str = ""
    codec_vendor_id: str = ""
    codec_subsystem_id: str = ""
    pci_vendor: str = ""
    pci_device: str = ""
    speaker_count: int = 2
    has_subwoofer: bool = False


def _read_sysfs(path: str) -> str:
    p = Path(path)
    if p.exists():
        try:
            return p.read_text().strip()
        except (OSError, PermissionError):
            pass
    return ""


def detect_dmi() -> dict[str, str]:
    base = "/sys/class/dmi/id"
    return {
        "vendor": _read_sysfs(f"{base}/sys_vendor"),
        "product_name": _read_sysfs(f"{base}/product_name"),
        "product_family": _read_sysfs(f"{base}/product_family"),
        "product_version": _read_sysfs(f"{base}/product_version"),
    }


def detect_codec() -> dict[str, str]:
    result: dict[str, str] = {
        "vendor_id": "",
        "subsystem_id": "",
        "codec_name": "",
    }
    proc = Path("/proc/asound")
    if not proc.exists():
        return result

    cards = sorted(
        p for p in proc.iterdir()
        if p.name.startswith("card") and p.is_dir()
    )
    for card in cards:
        for item in card.iterdir():
            if not item.name.startswith("codec#"):
                continue
            try:
                content = item.read_text(errors="replace")
            except (OSError, PermissionError):
                continue

            m = re.search(r"Codec:\s*(.+)", content)
            if m:
                result["codec_name"] = m.group(1).strip()

            m = re.search(r"Vendor Id:\s*(0x[0-9a-fA-F]+)", content)
            if m:
                result["vendor_id"] = m.group(1).strip()

            m = re.search(r"Subsystem Id:\s*(0x[0-9a-fA-F]+)", content)
            if m:
                result["subsystem_id"] = m.group(1).strip()

            if result["codec_name"]:
                return result
    return result


def detect_pci() -> dict[str, str]:
    result = {"vendor": "", "device": ""}
    base = Path("/sys/class/sound")
    if not base.exists():
        return result

    for card_dir in sorted(base.iterdir()):
        if not card_dir.is_dir():
            continue
        device_dir = card_dir / "device"
        if not device_dir.is_dir():
            continue

        result["vendor"] = _read_sysfs(str(device_dir / "vendor")) or _read_sysfs(
            str(device_dir / "subsystem_vendor")
        )
        result["device"] = _read_sysfs(str(device_dir / "device")) or _read_sysfs(
            str(device_dir / "subsystem_device")
        )
        if result["vendor"]:
            return result
    return result


def detect_device() -> DeviceInfo:
    dmi = detect_dmi()
    codec = detect_codec()
    pci = detect_pci()

    return DeviceInfo(
        vendor=dmi["vendor"],
        product_name=dmi["product_name"],
        product_family=dmi["product_family"],
        product_version=dmi["product_version"],
        codec_name=codec["codec_name"],
        codec_vendor_id=codec["vendor_id"],
        codec_subsystem_id=codec["subsystem_id"],
        pci_vendor=pci["vendor"],
        pci_device=pci["device"],
        speaker_count=2,
        has_subwoofer=False,
    )


def get_profile_key(info: DeviceInfo) -> str:
    """Generate a profile lookup key, preferring most-specific match."""
    codec_short = re.sub(r"[^A-Za-z0-9]", "", info.codec_name)
    model_short = re.sub(r"[^A-Za-z0-9]", "", info.product_name)
    vendor_short = info.vendor.upper()
    family_short = re.sub(r"[^A-Za-z0-9]", "", info.product_family)

    if vendor_short and model_short and codec_short:
        return f"{vendor_short}_{model_short}_{codec_short}"
    if vendor_short and family_short and codec_short:
        return f"{vendor_short}_{family_short}_{codec_short}"
    if codec_short:
        return codec_short
    return "UNKNOWN"


def detect_easyeffects() -> dict:
    """Detect if EasyEffects is installed and/or running.

    Returns dict with:
        installed: bool — easyeffects binary exists on system
        running: bool — easyeffects process is currently active
        has_config: bool — EasyEffects filter-chain config exists in pipewire.conf.d
        config_files: list[str] — paths to any EasyEffects PipeWire configs found
    """
    import shutil

    result = {
        "installed": False,
        "running": False,
        "has_config": False,
        "config_files": [],
    }

    # Check if easyeffects binary exists
    if shutil.which("easyeffects"):
        result["installed"] = True

    # Check if easyeffects process is running (init-agnostic — uses /proc)
    for pid_dir in Path("/proc").iterdir():
        if not pid_dir.name.isdigit():
            continue
        try:
            comm = (pid_dir / "comm").read_text().strip()
            if "easyeffects" in comm.lower():
                result["running"] = True
                break
        except (OSError, PermissionError):
            continue

    # Check for EasyEffects PipeWire config files
    pw_conf_d = Path("~/.config/pipewire/pipewire.conf.d").expanduser()
    if pw_conf_d.is_dir():
        for f in pw_conf_d.glob("*easyeffects*"):
            result["config_files"].append(str(f))
            result["has_config"] = True
        for f in pw_conf_d.glob("*ee_*"):
            # EasyEffects often names configs with ee_ prefix
            try:
                content = f.read_text()
                if "easyeffects" in content.lower() or "EasyEffects" in content:
                    result["config_files"].append(str(f))
                    result["has_config"] = True
            except (OSError, PermissionError):
                pass

    return result


def disable_easyeffects_config() -> bool:
    """Disable EasyEffects PipeWire configs by renaming to .disabled.

    Returns True if any configs were disabled.
    """
    import shutil

    info = detect_easyeffects()
    disabled = False

    for config_file in info["config_files"]:
        disabled_path = config_file + ".disabled-by-da4linux"
        try:
            shutil.move(config_file, disabled_path)
            disabled = True
        except (OSError, PermissionError):
            pass

    return disabled


def reenable_easyeffects_config() -> bool:
    """Re-enable EasyEffects configs that DA4Linux previously disabled."""
    pw_conf_d = Path("~/.config/pipewire/pipewire.conf.d").expanduser()
    reenabled = False

    if pw_conf_d.is_dir():
        for f in pw_conf_d.glob("*.disabled-by-da4linux"):
            original = str(f).replace(".disabled-by-da4linux", "")
            try:
                f.rename(original)
                reenabled = True
            except (OSError, PermissionError):
                pass

    return reenabled

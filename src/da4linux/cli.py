#!/usr/bin/env python3
"""DA4Linux CLI — Dolby Audio-like processing for Linux via PipeWire."""

import argparse
import subprocess
import sys
from pathlib import Path

from . import __version__


def _detect_headphones() -> bool:
    """Check if headphones are currently plugged in."""
    try:
        result = subprocess.run(
            ["amixer", "-c", "0", "contents"],
            capture_output=True, text=True, timeout=5,
        )
        stdout = result.stdout
        if "Headphone" not in stdout:
            for card in range(4):
                r = subprocess.run(
                    ["amixer", "-c", str(card), "contents"],
                    capture_output=True, text=True, timeout=5,
                )
                if "Headphone" in r.stdout:
                    stdout = r.stdout
                    break
        has_headphone = "Headphone" in stdout
        has_on = "values=on" in stdout
        # Also check via ALSA control names
        for line in stdout.splitlines():
            if "Headphone" in line and "Jack" in line:
                return has_on
        return False
    except Exception:
        return False


def _parse_stages(stages_str: str, disable_str: str) -> dict:
    """Parse --stages and --disable into a stage config dict."""
    from .constants import DEFAULT_ENABLED_STAGES

    result = {}
    for s in DEFAULT_ENABLED_STAGES:
        result[s] = True
    # surround is off by default
    result["surround"] = False

    if stages_str:
        enabled = set(s.strip() for s in stages_str.split(",") if s.strip())
        # Reset all to False, enable only specified
        for s in result:
            result[s] = s in enabled

    if disable_str:
        disabled = set(s.strip() for s in disable_str.split(",") if s.strip())
        for s in disabled:
            if s in result:
                result[s] = False

    return result


def _cmd_detect(args):
    from .detect import detect_device, get_profile_key

    info = detect_device()
    print("=== DA4Linux Hardware Detection ===")
    print(f"  Vendor:        {info.vendor or '(unknown)'}")
    print(f"  Product:       {info.product_name or '(unknown)'}")
    print(f"  Family:        {info.product_family or '(unknown)'}")
    print(f"  Version:       {info.product_version or '(unknown)'}")
    print(f"  Codec:         {info.codec_name or '(unknown)'}")
    print(f"  Codec Vendor:  {info.codec_vendor_id or '(unknown)'}")
    print(f"  Codec Subs.:   {info.codec_subsystem_id or '(unknown)'}")
    print(f"  PCI Vendor:    {info.pci_vendor or '(unknown)'}")
    print(f"  PCI Device:    {info.pci_device or '(unknown)'}")
    print(f"  Profile Key:   {get_profile_key(info)}")
    print(f"  Speakers:      {info.speaker_count}ch{' + subwoofer' if info.has_subwoofer else ''}")
    hp = _detect_headphones()
    print(f"  Headphones:    {'connected' if hp else 'not detected'}")


def _cmd_parse(args):
    from .parser import parse_dax3_xml

    tuning = parse_dax3_xml(args.xml_file)
    print(f"=== DAX3 XML: {args.xml_file} ===")
    endpoints = tuning.endpoints
    if not endpoints:
        print("  No endpoints found in the XML.")
        return

    for key, profile in endpoints.items():
        peq_count = len(profile.peq_bands)
        ao_count = len(profile.ao_bands)
        mb_count = len(profile.mb_compressor)
        print(f"  Endpoint: {key}")
        print(f"    PEQ bands:     {peq_count}")
        print(f"    AO bands:      {ao_count} channels")
        print(f"    MB compressor: {mb_count} bands")
        print(f"    Volmax boost:  {profile.volmax_boost} dB")
        print(f"    IEQ:           {'on' if profile.ieq_enabled else 'off'} "
              f"(amount={profile.ieq_amount})")
        if profile.peq_bands:
            for band in profile.peq_bands:
                print(f"      PEQ: {band.filter_type} f={band.freq}Hz "
                      f"g={band.gain}dB q={band.q}")


def _cmd_generate(args):
    from .detect import detect_device, get_profile_key
    from .parser import parse_dax3_xml, DAX3Profile
    from .generator import (
        generate_pipewire_config,
        detect_available_limiter,
        write_config,
    )
    from .profiles import get_profile
    from .constants import VALID_MODES

    output_dir = Path(args.output).expanduser()
    ir_dir = Path(args.ir_dir).expanduser() if args.ir_dir else None

    profile = None
    device_info = detect_device()

    # Check for EasyEffects conflict
    from .detect import detect_easyeffects, disable_easyeffects_config

    ee = detect_easyeffects()
    if ee["installed"] or ee["running"] or ee["has_config"]:
        print()
        print("⚠️  EasyEffects detected — running both simultaneously will cause double-processing!")
        if ee["running"]:
            print("    EasyEffects is currently RUNNING.")
        if ee["has_config"]:
            print(f"    Found {len(ee['config_files'])} EasyEffects PipeWire config(s).")

        if getattr(args, 'disable_easyeffects', False):
            disabled = disable_easyeffects_config()
            if disabled:
                print("    ✓ EasyEffects PipeWire configs disabled (renamed to .disabled-by-da4linux).")
                print("    Run 'da4linux reenable-easyeffects' to restore them.")
            elif ee["running"]:
                print("    Could not disable EasyEffects PipeWire configs (none found).")
                print("    EasyEffects is running as a process — close it manually:")
                print("      killall easyeffects")
        else:
            if ee["running"]:
                print("    To disable EasyEffects: close the EasyEffects application.")
                print("    Or run: killall easyeffects")
            if ee["has_config"]:
                print("    To disable EasyEffects configs: da4linux disable-easyeffects")
                print("    Or run: da4linux generate --disable-easyeffects")
        print()

    if args.xml:
        print(f"Parsing DAX3 XML: {args.xml}")
        tuning = parse_dax3_xml(args.xml)
        if tuning.endpoints:
            key = list(tuning.endpoints.keys())[0]
            profile = tuning.endpoints[key]
            print(f"  Using endpoint: {key}")
        else:
            print("  Warning: No endpoints found. Using built-in fallback.")

    if profile is None:
        profile_key = args.profile or get_profile_key(device_info)
        print(f"Using built-in profile: {profile_key}")
        profile = get_profile(profile_key)
        if profile is None:
            print(f"  Warning: No profile for '{profile_key}'. Using generic laptop profile.")
            profile = get_profile("GENERIC_LAPTOP")
            if profile is None:
                print("  Error: No profiles available!")
                sys.exit(1)

    # Stage config
    stages = _parse_stages(args.stages, args.disable)
    mode = args.mode or "music"
    if mode not in VALID_MODES:
        print(f"  Warning: Unknown mode '{mode}'. Using 'music'.")
        mode = "music"

    # Auto-enable surround if headphones detected
    hp = _detect_headphones()
    if hp and not stages.get("surround", False) and not args.disable:
        if args.hrir:
            stages["surround"] = True
            print("  Headphones detected — auto-enabling virtual surround.")

    # HRIR path
    hrir_path = args.hrir or ""
    if stages.get("surround") and not hrir_path:
        default_hrir = Path("~/.local/share/da4linux/hrir/HRTF.sofa").expanduser()
        if default_hrir.exists():
            hrir_path = str(default_hrir)

    # Limiter
    limiter_type = detect_available_limiter()
    limiter_labels = {
        "lv2": "LSP LV2 limiter_stereo",
        "ladspa": "LSP LADSPA sc_limiter_stereo",
        "zam": "ZamAudio ZaMaximX2 LADSPA",
        "clamp": "built-in clamp (last resort)",
    }
    print(f"  Limiter: {limiter_labels.get(limiter_type, limiter_type)}")

    # Print stage summary
    print(f"  Mode: {mode}")
    print(f"  Stages:")
    for s_name, s_val in sorted(stages.items()):
        status = "on" if s_val else "OFF"
        print(f"    {s_name:20s} {status}")
    if stages.get("surround") and hrir_path:
        print(f"    HRIR: {hrir_path}")
    if hp:
        print(f"    Headphones detected: yes")

    ir_dir_str = str(ir_dir) if ir_dir else "~/.local/share/da4linux/ir"

    config = generate_pipewire_config(
        profile,
        device_info,
        ir_dir=ir_dir_str,
        limiter_type=limiter_type,
        stages=stages,
        mode=mode,
        hrir_path=hrir_path,
    )

    output_file = output_dir / "50-da4linux.conf"
    write_config(config, str(output_file))
    print(f"\nConfig written to: {output_file}")
    print()
    print("To apply, restart PipeWire. The command depends on your init system:")
    print("  runit:     sv restart pipewire         (or killall -HUP pipewire)")
    print("  systemd:   systemctl --user restart pipewire")
    print("  openrc:    rc-service pipewire restart")
    print("  s6:        s6-svc -r /run/service/pipewire")
    print("  generic:   killall pipewire && pipewire &")
    print()
    print("Or test without restarting:")
    print(f"  pipewire -c {output_file}")


def _cmd_status(args):
    from .detect import detect_device, get_profile_key
    from .profiles import BUILTIN_PROFILES
    from pathlib import Path

    info = detect_device()
    key = get_profile_key(info)

    print("=== DA4Linux Status ===")
    print(f"  Device:     {info.product_name or 'unknown'}")
    print(f"  Codec:      {info.codec_name or 'unknown'}")
    print(f"  Profile:    {key}")
    print(f"  Built-in:   {'yes' if key in BUILTIN_PROFILES else 'no'}")

    config_path = Path("~/.config/pipewire/pipewire.conf.d/50-da4linux.conf").expanduser()
    if config_path.exists():
        print(f"  Config:     {config_path} (installed)")
    else:
        print(f"  Config:     not installed")

    hp = _detect_headphones()
    print(f"  Headphones: {'connected' if hp else 'not detected'}")

    from .detect import detect_easyeffects
    ee = detect_easyeffects()
    if ee["installed"]:
        print(f"  EasyEffects: installed{' (RUNNING — CONFLICT!)' if ee['running'] else ''}")
        if ee["has_config"]:
            print(f"    Configs:    {len(ee['config_files'])} active")
        if not ee["running"] and not ee["has_config"]:
            print(f"    Status:     installed but inactive (OK)")
    else:
        print(f"  EasyEffects: not installed (OK)")


def _cmd_disable_easyeffects(args):
    from .detect import detect_easyeffects, disable_easyeffects_config

    ee = detect_easyeffects()
    if not ee["installed"] and not ee["has_config"]:
        print("EasyEffects is not installed and no PipeWire configs found.")
        return

    print("=== Disabling EasyEffects ===")

    if ee["running"]:
        print("EasyEffects is currently running. Close it with:")
        print("  killall easyeffects")

    disabled = disable_easyeffects_config()
    if disabled:
        print("✓ EasyEffects PipeWire configs disabled.")
        print("  Restart PipeWire to apply: sv restart pipewire")
        print("  To restore: da4linux reenable-easyeffects")
    else:
        print("No EasyEffects PipeWire configs found to disable.")
        if ee["running"]:
            print("EasyEffects is running as a process — it will continue to process audio.")
            print("Kill it: killall easyeffects")
        else:
            print("If EasyEffects uses a different config location, disable it manually.")


def _cmd_reenable_easyeffects(args):
    from .detect import reenable_easyeffects_config

    reenabled = reenable_easyeffects_config()
    if reenabled:
        print("✓ EasyEffects PipeWire configs restored.")
        print("  Restart PipeWire to apply: sv restart pipewire")
    else:
        print("No EasyEffects configs were found in disabled state.")
        print("(DA4Linux renames configs with the .disabled-by-da4linux suffix)")


def main():
    parser = argparse.ArgumentParser(
        prog="da4linux",
        description="Dolby Audio-like processing for Linux via PipeWire filter-chain.",
        epilog="GNU GPL v3. https://github.com/menak02/DA4Linux",
    )
    parser.add_argument("--version", action="version", version=f"da4linux {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    # detect
    detect_parser = subparsers.add_parser("detect", help="Detect audio hardware")

    # parse
    parse_parser = subparsers.add_parser("parse", help="Parse DAX3 XML tuning file")
    parse_parser.add_argument("xml_file", help="Path to dax3_ext_*.xml file")

    # generate
    gen_parser = subparsers.add_parser(
        "generate", help="Generate PipeWire filter-chain config"
    )
    gen_parser.add_argument(
        "--xml", help="DAX3 XML tuning file path (optional; uses built-in profile if omitted)"
    )
    gen_parser.add_argument(
        "--output",
        default="~/.config/pipewire/pipewire.conf.d",
        help="Output directory for PipeWire config",
    )
    gen_parser.add_argument(
        "--profile",
        help="Profile name override (e.g., LENOVO_T14SG2_ALC3287)",
    )
    gen_parser.add_argument(
        "--ir-dir",
        default="~/.local/share/da4linux/ir",
        help="Directory for impulse response WAV files",
    )
    gen_parser.add_argument(
        "--stages",
        help="Comma-separated stages to enable (default: all except surround)",
    )
    gen_parser.add_argument(
        "--disable",
        help="Comma-separated stages to disable",
    )
    gen_parser.add_argument(
        "--mode",
        choices=["music", "movie", "voice"],
        default="music",
        help="Processing mode preset",
    )
    gen_parser.add_argument(
        "--hrir",
        help="Path to SOFA HRTF file for virtual surround",
    )
    gen_parser.add_argument(
        "--disable-easyeffects",
        action="store_true",
        help="Disable EasyEffects PipeWire configs (rename to .disabled)",
    )

    # status
    status_parser = subparsers.add_parser("status", help="Show current status")

    # disable-easyeffects
    disable_ee_parser = subparsers.add_parser(
        "disable-easyeffects",
        help="Disable EasyEffects PipeWire configs to avoid conflicts",
    )

    # reenable-easyeffects
    reenable_ee_parser = subparsers.add_parser(
        "reenable-easyeffects",
        help="Restore EasyEffects PipeWire configs previously disabled by DA4Linux",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    commands = {
        "detect": _cmd_detect,
        "parse": _cmd_parse,
        "generate": _cmd_generate,
        "status": _cmd_status,
        "disable-easyeffects": _cmd_disable_easyeffects,
        "reenable-easyeffects": _cmd_reenable_easyeffects,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()

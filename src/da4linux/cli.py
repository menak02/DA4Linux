#!/usr/bin/env python3
"""DA4Linux CLI — Dolby Audio-like processing for Linux via PipeWire."""

import argparse
import os
import shutil
import socket
import stat
import subprocess
import sys
import time
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


def _cmd_profiles(args):
    from .profiles import BUILTIN_PROFILES, load_user_profiles

    print("=== DA4Linux Available Profiles ===")
    user_profiles = load_user_profiles()

    if user_profiles:
        print("\n  Custom User Profiles (~/.config/da4linux/profiles/):")
        for key, p in user_profiles.items():
            name = p.get("name", key)
            print(f"    - {key:32s} {name}")

    print("\n  Built-in Profiles:")
    for key, p in BUILTIN_PROFILES.items():
        name = p.get("name", key)
        print(f"    - {key:32s} {name}")


def _cmd_parse(args):
    import json
    from dataclasses import asdict
    from .parser import parse_dax3_xml

    tuning = parse_dax3_xml(args.xml_file)
    
    if getattr(args, "json", False):
        print(json.dumps(asdict(tuning), indent=2))
        return

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
        detect_hardware_sink,
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
            print(f"  DAX3 tuning loaded:")
            print(f"    IEQ:           {'on' if profile.ieq_enabled else 'off'} "
                  f"(amount={profile.ieq_amount}, curve={'yes' if profile.ieq_curve else 'no'})")
            print(f"    PEQ filters:   {len(profile.peq_bands)} bands")
            print(f"    MB compressor: {'on' if any(b.threshold != 0 for b in profile.mb_compressor) else 'off'}")
            print(f"    Dialogue enh:  {profile.dialog_enhancer}")
            print(f"    Volmax boost:  {profile.volmax_boost / 16.0:.1f} dB")
        else:
            print("  Warning: No endpoints found. Using built-in fallback.")

    if profile is None:
        if getattr(args, "json_profile", None):
            import json
            from .parser import PEQBand, MBCompressorBand, AudioOptimizerBand
            data = json.loads(args.json_profile)
            bands = [
                PEQBand(
                    filter_type=b.get("filter_type", b.get("type", "bell")),
                    freq=b.get("freq", 1000.0),
                    gain=b.get("gain", 0.0),
                    q=b.get("q", 0.707),
                    enabled=b.get("enabled", True),
                )
                for b in data.get("peq_bands", [])
            ]
            mb_compressor = [
                MBCompressorBand(
                    threshold=b.get("threshold", 0.0),
                    ratio=b.get("ratio", 1.0),
                    attack=b.get("attack", 5.0),
                    release=b.get("release", 50.0),
                    knee=b.get("knee", 0.0),
                    makeup_gain=b.get("makeup_gain", 0.0),
                )
                for b in data.get("mb_compressor", [])
            ]
            ao_bands = [AudioOptimizerBand(gains=b.get("gains", [0.0]*20)) for b in data.get("ao_bands", [])]
            
            profile = DAX3Profile(
                name=data.get("name", "Custom UI Profile"),
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
            print("Using custom UI JSON profile")
        else:
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

    if getattr(args, "headphone", False):
        stages["peq"] = False
        print("  Headphone mode active — bypassing speaker PEQ filter.")

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

    sink = detect_hardware_sink()
    config = generate_pipewire_config(
        profile,
        device_info,
        ir_dir=ir_dir_str,
        limiter_type=limiter_type,
        stages=stages,
        mode=mode,
        hrir_path=hrir_path,
        hardware_sink=sink,
    )

    output_file = output_dir / "50-da4linux.conf"
    write_config(config, str(output_file))
    print(f"\nConfig written to: {output_file}")
    if sink:
        print(f"  Audio sink: routed to hardware sink '{sink}'")
    else:
        print("  Warning: no hardware sink detected — config has no target.object.")
        print("  Processed audio will not be routed to your speakers.")
        print("  Install pulseaudio-utils (pactl) and re-run 'da4linux generate'.")
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


def _runtime_dir() -> str:
    """Return the PipeWire runtime dir (XDG_RUNTIME_DIR or /run/user/<uid>)."""
    return os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"


def _pgrep(name: str) -> bool:
    """Return True if a process with the exact name is running."""
    try:
        return subprocess.run(["pgrep", "-x", name], capture_output=True).returncode == 0
    except FileNotFoundError:
        return False


def _kill_and_wait(names, timeout: float = 5.0, sigkill: bool = False) -> bool:
    """Kill processes by exact name (tolerating absence) and wait for exit."""
    for name in names:
        try:
            cmd = ["pkill", "-x"]
            if sigkill:
                cmd.append("-9")
            cmd.append(name)
            subprocess.run(cmd, capture_output=True)
        except FileNotFoundError:
            pass
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not any(_pgrep(n) for n in names):
            return True
        time.sleep(0.1)
    return not any(_pgrep(n) for n in names)


def _wait_for_process(name: str, timeout: float) -> bool:
    """Poll until a process with the exact name appears."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _pgrep(name):
            return True
        time.sleep(0.2)
    return _pgrep(name)


def _pid_alive(pid: int) -> bool:
    """Return True if a process with the given PID is alive."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_for_pid(pid: int, timeout: float) -> bool:
    """Poll until a process with the given PID is alive."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _pid_alive(pid):
            return True
        time.sleep(0.2)
    return _pid_alive(pid)


def _socket_accepts(path: str) -> bool:
    """Return True if path is a Unix socket that accepts connections."""
    try:
        if not stat.S_ISSOCK(os.stat(path).st_mode):
            return False
    except OSError:
        return False
    try:
        with socket.socket(socket.AF_UNIX) as s:
            return s.connect_ex(path) == 0
    except OSError:
        return False


def _wait_for_socket(path: str, timeout: float) -> bool:
    """Poll until a live Unix socket accepts connections at path.

    A stale socket file left by a dead daemon is not enough: the path must
    be a socket AND accept a connection (i.e. the daemon is bound).
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _socket_accepts(path):
            return True
        time.sleep(0.2)
    return _socket_accepts(path)


def _log_path(name: str) -> str:
    """Log file for a daemon: XDG_RUNTIME_DIR if writable, else /tmp."""
    base = _runtime_dir()
    if not os.path.isdir(base):
        base = "/tmp"
    return os.path.join(base, f"da4linux-{name}.log")


def _spawn(binary: str, log_path: str) -> subprocess.Popen:
    """Start a daemon detached from the CLI so it survives exit."""
    with open(log_path, "ab") as log:
        return subprocess.Popen(
            [binary],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )


def _validate_runtime_dir(runtime: str) -> bool:
    """Validate XDG_RUNTIME_DIR exists and is writable before touching processes."""
    if not os.path.isdir(runtime):
        print(f"  Error: runtime dir does not exist: {runtime}")
        print("  XDG_RUNTIME_DIR is not set or points to a missing directory.")
        print("  Set XDG_RUNTIME_DIR (e.g. export XDG_RUNTIME_DIR=/run/user/$(id -u))")
        print("  and make sure /run/user/<uid> exists (created by your session).")
        return False
    if not os.access(runtime, os.W_OK):
        print(f"  Error: runtime dir is not writable: {runtime}")
        print("  Check permissions on XDG_RUNTIME_DIR (should be owned by you, mode 0700).")
        return False
    return True


def _unlink_stale_sockets(runtime: str) -> None:
    """Remove leftover socket files from dead daemons before starting new ones."""
    for rel in ("pipewire-0", "pipewire-0-manager", os.path.join("pulse", "native")):
        path = os.path.join(runtime, rel)
        try:
            if os.path.lexists(path):
                os.unlink(path)
                print(f"  Removed stale socket: {path}")
        except OSError as e:
            print(f"  Warning: could not remove stale socket {path}: {e}")


def _service_dirs() -> list:
    """Candidate runit service directories for pipewire, in priority order."""
    xdg_config = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.path.expanduser("~"), ".config"
    )
    return [
        "/etc/service/pipewire",
        "/etc/sv/pipewire",
        os.path.join(os.path.expanduser("~"), ".config", "runit", "pipewire"),
        os.path.join(xdg_config, "runit", "pipewire"),
    ]


def detect_init_system() -> str:
    """Detect the active init system / service supervisor for PipeWire.

    Returns one of: 'systemd', 'runit', 'openrc', 'dinit', 's6', or 'standalone'.
    """
    # 1. Systemd
    systemctl = shutil.which("systemctl")
    if systemctl:
        try:
            r = subprocess.run(
                [systemctl, "--user", "is-active", "pipewire"],
                capture_output=True, text=True, timeout=3,
            )
            if r.returncode == 0 or "active" in r.stdout.lower():
                return "systemd"
        except (OSError, subprocess.TimeoutExpired):
            pass

    # 2. Runit
    for d in _service_dirs():
        if os.path.isdir(d):
            return "runit"
    sv = shutil.which("sv")
    if sv:
        try:
            r = subprocess.run([sv, "status", "pipewire"], capture_output=True, timeout=3)
            if r.returncode == 0:
                return "runit"
        except (OSError, subprocess.TimeoutExpired):
            pass

    # 3. OpenRC
    rc_service = shutil.which("rc-service")
    if rc_service:
        try:
            r = subprocess.run([rc_service, "pipewire", "status"], capture_output=True, timeout=3)
            if r.returncode == 0 or "started" in r.stdout.lower():
                return "openrc"
        except (OSError, subprocess.TimeoutExpired):
            pass

    # 4. Dinit
    dinitctl = shutil.which("dinitctl")
    if dinitctl:
        try:
            r = subprocess.run([dinitctl, "status", "pipewire"], capture_output=True, timeout=3)
            if r.returncode == 0 or "RUNNING" in r.stdout:
                return "dinit"
        except (OSError, subprocess.TimeoutExpired):
            pass

    # 5. s6
    if os.path.isdir("/run/service/pipewire") or os.path.isdir(os.path.expanduser("~/.s6/sv/pipewire")):
        return "s6"

    return "standalone"


def _is_supervised() -> bool:
    """Return True if pipewire is supervised by runit."""
    return detect_init_system() == "runit"


def _is_systemd_supervised() -> bool:
    """Return True if PipeWire is managed by systemd user session."""
    return detect_init_system() == "systemd"


def _print_summary_and_exit(runtime, pw_socket, pulse_socket, pw_ok, wp_ok, pulse_ok, spawned):
    """Print the final summary and exit PASS/FAIL (socket + process checks only)."""
    pactl_ok = None
    if shutil.which("pactl"):
        try:
            r = subprocess.run(["pactl", "info"], capture_output=True, text=True, timeout=10)
            pactl_ok = r.returncode == 0
        except subprocess.TimeoutExpired:
            pactl_ok = False
    else:
        print("  Note: pactl not found, skipping end-to-end check.")

    print()
    print("=== Restart Summary ===")
    print(f"  pipewire socket ({pw_socket}): {'PASS' if pw_ok else 'FAIL'}")
    print(f"  wireplumber process:          {'PASS' if wp_ok else 'FAIL'}")
    print(f"  pulse socket ({pulse_socket}): {'PASS' if pulse_ok else 'FAIL'}")
    if pactl_ok is None:
        print("  pactl info:                   UNVERIFIED (pactl not found)")
    else:
        print(f"  pactl info:                   {'PASS' if pactl_ok else 'FAIL'}")
    if spawned:
        print(f"  started by this command:      {', '.join(spawned)}")

    if not (pw_ok and wp_ok and pulse_ok):
        print()
        print("  Some components failed to start. Check:")
        print(f"    - XDG_RUNTIME_DIR is set and writable (currently: {runtime})")
        print("    - Log files:")
        for n in ("pipewire", "wireplumber", "pipewire-pulse"):
            print(f"        {_log_path(n)}")
        print("    - If you run under a session manager, start its pipewire")
        print("      script instead (e.g. /usr/share/pipewire/pipewire.conf")
        print("      or your session's autostart).")
        sys.exit(1)


def _restart_supervised(runtime: str, pw_socket: str, pulse_socket: str) -> None:
    """Restart via runit's sv when pipewire is supervised (no pkill+spawn)."""
    print("  PipeWire is supervised by runit; delegating to sv restart ...")
    sv = shutil.which("sv")
    try:
        r = subprocess.run(
            [sv, "restart", "pipewire", "pipewire-pulse", "wireplumber"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"  Error running sv restart: {e}")
        sys.exit(1)
    if r.returncode != 0:
        print(f"  sv restart failed (exit {r.returncode}):")
        if r.stderr:
            print(r.stderr)
        sys.exit(1)

    pw_ok = _wait_for_socket(pw_socket, timeout=10.0)
    pulse_ok = _wait_for_socket(pulse_socket, timeout=10.0)
    wp_ok = _wait_for_process("wireplumber", timeout=5.0)
    _print_summary_and_exit(runtime, pw_socket, pulse_socket, pw_ok, wp_ok, pulse_ok, {})


def _restart_systemd(runtime: str, pw_socket: str, pulse_socket: str) -> None:
    """Restart via systemctl --user when PipeWire is managed by systemd."""
    print("  PipeWire is managed by systemd; delegating to systemctl --user restart ...")
    systemctl = shutil.which("systemctl")
    try:
        r = subprocess.run(
            [systemctl, "--user", "restart", "pipewire", "pipewire-pulse", "wireplumber"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"  Error running systemctl --user restart: {e}")
        sys.exit(1)
    if r.returncode != 0:
        print(f"  systemctl restart failed (exit {r.returncode}):")
        if r.stderr:
            print(r.stderr)
        sys.exit(1)

    pw_ok = _wait_for_socket(pw_socket, timeout=10.0)
    pulse_ok = _wait_for_socket(pulse_socket, timeout=10.0)
    wp_ok = _wait_for_process("wireplumber", timeout=5.0)
    _print_summary_and_exit(runtime, pw_socket, pulse_socket, pw_ok, wp_ok, pulse_ok, {})


def _restart_openrc(runtime: str, pw_socket: str, pulse_socket: str) -> None:
    """Restart via OpenRC rc-service."""
    print("  PipeWire is managed by OpenRC; delegating to rc-service restart ...")
    rc = shutil.which("rc-service")
    try:
        subprocess.run([rc, "pipewire", "restart"], capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"  Error running rc-service restart: {e}")
        sys.exit(1)

    pw_ok = _wait_for_socket(pw_socket, timeout=10.0)
    pulse_ok = _wait_for_socket(pulse_socket, timeout=10.0)
    wp_ok = _wait_for_process("wireplumber", timeout=5.0)
    _print_summary_and_exit(runtime, pw_socket, pulse_socket, pw_ok, wp_ok, pulse_ok, {})


def _restart_dinit(runtime: str, pw_socket: str, pulse_socket: str) -> None:
    """Restart via dinitctl."""
    print("  PipeWire is managed by Dinit; delegating to dinitctl restart ...")
    dinitctl = shutil.which("dinitctl")
    try:
        subprocess.run([dinitctl, "restart", "pipewire"], capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"  Error running dinitctl restart: {e}")
        sys.exit(1)

    pw_ok = _wait_for_socket(pw_socket, timeout=10.0)
    pulse_ok = _wait_for_socket(pulse_socket, timeout=10.0)
    wp_ok = _wait_for_process("wireplumber", timeout=5.0)
    _print_summary_and_exit(runtime, pw_socket, pulse_socket, pw_ok, wp_ok, pulse_ok, {})


def _restart_s6(runtime: str, pw_socket: str, pulse_socket: str) -> None:
    """Restart via s6-svc."""
    print("  PipeWire is managed by s6; delegating to s6-svc -r ...")
    s6_svc = shutil.which("s6-svc")
    target = "/run/service/pipewire" if os.path.isdir("/run/service/pipewire") else os.path.expanduser("~/.s6/sv/pipewire")
    try:
        subprocess.run([s6_svc, "-r", target], capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"  Error running s6-svc: {e}")
        sys.exit(1)

    pw_ok = _wait_for_socket(pw_socket, timeout=10.0)
    pulse_ok = _wait_for_socket(pulse_socket, timeout=10.0)
    wp_ok = _wait_for_process("wireplumber", timeout=5.0)
    _print_summary_and_exit(runtime, pw_socket, pulse_socket, pw_ok, wp_ok, pulse_ok, {})


def _cmd_restart_pipewire(args):
    runtime = _runtime_dir()
    pw_socket = os.path.join(runtime, "pipewire-0")
    pulse_socket = os.path.join(runtime, "pulse", "native")

    print("=== Restarting PipeWire (user session) ===")
    print(f"  Runtime dir: {runtime}")

    init_sys = detect_init_system()
    if init_sys == "systemd":
        _restart_systemd(runtime, pw_socket, pulse_socket)
        return
    elif init_sys == "runit":
        _restart_supervised(runtime, pw_socket, pulse_socket)
        return
    elif init_sys == "openrc":
        _restart_openrc(runtime, pw_socket, pulse_socket)
        return
    elif init_sys == "dinit":
        _restart_dinit(runtime, pw_socket, pulse_socket)
        return
    elif init_sys == "s6":
        _restart_s6(runtime, pw_socket, pulse_socket)
        return

    missing = [b for b in ("pipewire", "wireplumber", "pipewire-pulse")
               if not shutil.which(b)]
    if missing:
        print(f"  Error: not found in PATH: {', '.join(missing)}")
        print("  Install PipeWire/WirePlumber (e.g. apt install pipewire wireplumber).")
        sys.exit(1)

    # Validate the runtime dir before touching any process.
    if not _validate_runtime_dir(runtime):
        sys.exit(2)

    # Stop existing instances: pulse first, then wireplumber, then the main
    # daemon (pipewire-pulse is a separate process on modern setups).
    print("  Stopping pipewire-pulse, wireplumber, pipewire ...")
    stopped = _kill_and_wait(("pipewire-pulse", "wireplumber", "pipewire"), timeout=5.0)
    if not stopped:
        print("  Warning: some processes still running after 5s; sending SIGKILL ...")
        alive = [n for n in ("pipewire-pulse", "wireplumber", "pipewire") if _pgrep(n)]
        if alive:
            _kill_and_wait(alive, timeout=2.0, sigkill=True)

    # Remove stale socket files left by dead daemons so the new pipewire can
    # bind, and so the wait cannot pass on a dead socket.
    _unlink_stale_sockets(runtime)

    # Start the main daemon and wait for its socket.
    print("  Starting pipewire ...")
    spawned = {}
    try:
        spawned["pipewire"] = _spawn("pipewire", _log_path("pipewire"))
    except OSError as e:
        print(f"  Error starting pipewire: {e}")
    pw_ok = _wait_for_socket(pw_socket, timeout=10.0)

    # Start the session manager, then give it a moment.
    print("  Starting wireplumber ...")
    try:
        spawned["wireplumber"] = _spawn("wireplumber", _log_path("wireplumber"))
    except OSError as e:
        print(f"  Error starting wireplumber: {e}")
    time.sleep(1.0)

    # Start PulseAudio compatibility and wait for its socket.
    print("  Starting pipewire-pulse ...")
    try:
        spawned["pipewire-pulse"] = _spawn("pipewire-pulse", _log_path("pipewire-pulse"))
    except OSError as e:
        print(f"  Error starting pipewire-pulse: {e}")
    pulse_ok = _wait_for_socket(pulse_socket, timeout=10.0)

    # Final verification: use the PIDs we spawned, not pgrep-by-name (which
    # can match stray instances).
    if "wireplumber" in spawned:
        wp_ok = _wait_for_pid(spawned["wireplumber"].pid, timeout=5.0)
    else:
        wp_ok = False

    _print_summary_and_exit(runtime, pw_socket, pulse_socket, pw_ok, wp_ok, pulse_ok, spawned)


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
    parse_parser.add_argument("--json", action="store_true", help="Output parsed DAX3Tuning as JSON")

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
        "--json-profile",
        help="Raw JSON string containing a full custom profile to inject",
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
    gen_parser.add_argument(
        "--headphone",
        action="store_true",
        help="Bypass speaker PEQ filter for headphone listening",
    )

    # status
    status_parser = subparsers.add_parser("status", help="Show current status")

    # profiles
    profiles_parser = subparsers.add_parser(
        "profiles", help="List available built-in and custom user profiles"
    )

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

    # restart-pipewire
    restart_parser = subparsers.add_parser(
        "restart-pipewire",
        help="Restart the PipeWire user session (pipewire, wireplumber, pipewire-pulse)",
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
        "profiles": _cmd_profiles,
        "disable-easyeffects": _cmd_disable_easyeffects,
        "reenable-easyeffects": _cmd_reenable_easyeffects,
        "restart-pipewire": _cmd_restart_pipewire,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()

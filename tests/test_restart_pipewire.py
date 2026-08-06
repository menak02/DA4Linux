"""Tests for the restart-pipewire command helpers (da4linux.cli)."""

import os
import socket
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from da4linux import cli


def test_wait_for_socket_regular_file(tmp_path):
    """A regular file is not a socket, so readiness must be False."""
    p = tmp_path / "pipewire-0"
    p.write_text("stale")
    assert cli._wait_for_socket(str(p), timeout=0.5) is False


def test_wait_for_socket_stale_socket(tmp_path):
    """A socket inode with no listener (dead daemon's leftover) is not ready."""
    p = tmp_path / "pipewire-0"
    os.mknod(str(p), stat.S_IFSOCK | 0o600)
    assert cli._wait_for_socket(str(p), timeout=0.5) is False


def test_wait_for_socket_bound(tmp_path):
    """A real bound Unix socket is ready (connect succeeds)."""
    p = tmp_path / "pipewire-0"
    s = socket.socket(socket.AF_UNIX)
    s.bind(str(p))
    s.listen(1)
    try:
        assert cli._wait_for_socket(str(p), timeout=0.5) is True
    finally:
        s.close()


def test_is_supervised_true(monkeypatch, tmp_path):
    """A runit service dir for pipewire means supervision is detected."""
    svc = tmp_path / "pipewire"
    svc.mkdir()
    monkeypatch.setattr(cli, "_service_dirs", lambda: [str(svc)])
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)
    assert cli._is_supervised() is True


def test_is_supervised_false(monkeypatch, tmp_path):
    """No service dir and no sv status match means not supervised."""
    svc = tmp_path / "pipewire"
    monkeypatch.setattr(cli, "_service_dirs", lambda: [str(svc)])
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)
    assert cli._is_supervised() is False


def test_validate_runtime_dir_missing(tmp_path):
    assert cli._validate_runtime_dir(str(tmp_path / "nope")) is False


def test_validate_runtime_dir_ok(tmp_path):
    assert cli._validate_runtime_dir(str(tmp_path)) is True


def test_validate_runtime_dir_not_writable(monkeypatch, tmp_path):
    monkeypatch.setattr(cli.os, "access", lambda path, mode: False)
    assert cli._validate_runtime_dir(str(tmp_path)) is False


def test_restart_guard_exits_2_on_bad_runtime_dir(monkeypatch):
    """The runtime-dir guard exits with code 2 before touching processes."""
    monkeypatch.setattr(cli, "_is_supervised", lambda: False)
    monkeypatch.setattr(cli.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(cli, "_validate_runtime_dir", lambda runtime: False)
    with pytest.raises(SystemExit) as exc:
        cli._cmd_restart_pipewire(None)
    assert exc.value.code == 2
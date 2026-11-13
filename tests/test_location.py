import subprocess
import time

import pytest

from deplacements import location

CURRENT_POSITION = location.current_position  # la vraie, avant le remplacement de conftest.py


@pytest.fixture(autouse=True)
def on_windows(monkeypatch):
    monkeypatch.setattr(location, "USE_PC_LOCATION", True)
    monkeypatch.setattr(location.sys, "platform", "win32")


def test_phone_position_saved_then_read():
    location.save_phone_position(48.84, 2.37, 12)
    assert location.phone_position() == "48.84,2.37"


def test_phone_position_too_old(monkeypatch):
    location.save_phone_position(48.84, 2.37)
    later = time.time() + location.PHONE_POSITION_MAX_AGE + 1
    monkeypatch.setattr(location.time, "time", lambda: later)
    assert location.phone_position() is None


def test_phone_position_cleared():
    location.save_phone_position(48.84, 2.37)
    location.clear_phone_position()
    assert location.phone_position() is None
    location.clear_phone_position()  # deux fois : pas d'erreur


def test_phone_position_corrupted_file():
    location.POSITION_FILE.write_text("pas du json", encoding="utf-8")
    assert location.phone_position() is None


def test_pc_position_from_windows(fake_powershell):
    fake_powershell(location, stdout="48.8443,2.3743\r\n")
    assert location.pc_position() == "48.8443,2.3743"


@pytest.mark.parametrize("returncode, stdout", [(2, ""), (0, "illisible")])  # accès refusé, réponse abîmée
def test_pc_position_unavailable(fake_powershell, returncode, stdout):
    fake_powershell(location, stdout=stdout, returncode=returncode)
    assert location.pc_position() is None


def test_pc_position_disabled_or_not_windows(monkeypatch, fake_powershell):
    calls = fake_powershell(location, stdout="1,2")
    monkeypatch.setattr(location, "USE_PC_LOCATION", False)
    assert location.pc_position() is None
    monkeypatch.setattr(location, "USE_PC_LOCATION", True)
    monkeypatch.setattr(location.sys, "platform", "linux")
    assert location.pc_position() is None
    assert calls == []


def test_pc_position_timeout(monkeypatch):
    def slow(script, timeout):
        raise subprocess.TimeoutExpired("powershell", timeout)
    monkeypatch.setattr(location, "run_powershell", slow)
    assert location.pc_position() is None


def test_phone_wins_over_pc(fake_powershell):
    calls = fake_powershell(location, stdout="1,2")
    location.save_phone_position(48.84, 2.37)
    assert CURRENT_POSITION() == "48.84,2.37" and calls == []  # le PC n'est même pas interrogé


def test_pc_used_when_phone_silent(fake_powershell):
    fake_powershell(location, stdout="48.85,2.35")
    assert CURRENT_POSITION() == "48.85,2.35"

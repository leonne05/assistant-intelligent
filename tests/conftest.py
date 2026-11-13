import subprocess

import pytest

from deplacements import location


@pytest.fixture(autouse=True)
def no_real_position(monkeypatch):
    """Les tests ne lisent jamais la vraie position (GPS du téléphone ou localisation Windows)."""
    monkeypatch.setattr(location, "current_position", lambda: None)


@pytest.fixture(autouse=True)
def tmp_position_file(monkeypatch, tmp_path):
    """Les tests n'écrivent jamais dans le vrai fichier de position du téléphone."""
    monkeypatch.setattr(location, "POSITION_FILE", tmp_path / "position.json")


@pytest.fixture
def fake_powershell(monkeypatch):
    """fake_powershell(module, stdout=, returncode=) remplace run_powershell dans `module`
    et renvoie la liste des scripts reçus."""
    def install(module, stdout="", returncode=0):
        calls = []

        def run(script, timeout):
            calls.append(script)
            return subprocess.CompletedProcess("powershell", returncode, stdout, "erreur")
        monkeypatch.setattr(module, "run_powershell", run)
        return calls
    return install

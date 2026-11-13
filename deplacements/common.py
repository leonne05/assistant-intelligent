"""Outils partagés : une seule exception, un seul appel HTTP et un seul appel PowerShell."""
import subprocess

import requests

from .config import TIMEOUT


class DeplacementsError(Exception):
    """Erreur 'attendue' dont le message peut être lu tel quel à l'utilisateur."""


def get_json(url: str, params: dict | None = None, headers: dict | None = None) -> dict:
    """GET + contrôle d'erreur + JSON. Toute panne devient une DeplacementsError."""
    try:
        r = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.Timeout:
        raise DeplacementsError("Le service ne répond pas (timeout).")
    except requests.HTTPError as e:
        code = e.response.status_code
        if code in (401, 403):
            raise DeplacementsError("Clé API refusée.")
        raise DeplacementsError(f"Erreur du service (HTTP {code}).")
    except (requests.RequestException, ValueError):
        raise DeplacementsError("Service injoignable.")


def run_powershell(script: str, timeout: int) -> subprocess.CompletedProcess:
    """Script Windows PowerShell : outils intégrés à Windows (localisation, certificat), rien à installer."""
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                          capture_output=True, text=True, timeout=timeout)

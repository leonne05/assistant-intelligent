"""Position actuelle de l'utilisateur : téléphone d'abord, puis PC, sinon None.

- Téléphone : la page du serveur de position (position_server.py) envoie la position GPS une fois
  l'autorisation donnée dans le navigateur ; on la garde dans un petit fichier local.
- PC : service de localisation Windows (Paramètres > Confidentialité > Localisation).
Aucune position n'est envoyée ailleurs que dans ce fichier local et vers l'API d'itinéraires.
"""
import json
import logging
import subprocess
import sys
import time

from .common import run_powershell
from .config import PHONE_POSITION_MAX_AGE, POSITION_FILE, USE_PC_LOCATION

log = logging.getLogger(__name__)

# Service de localisation Windows via .NET (présent dans Windows PowerShell, rien à installer).
# Si l'utilisateur refuse l'accès à la localisation, le script renvoie 2.
_PS_SCRIPT = r"""
Add-Type -AssemblyName System.Device
$w = New-Object System.Device.Location.GeoCoordinateWatcher([System.Device.Location.GeoPositionAccuracy]::High)
if (-not $w.TryStart($false, [TimeSpan]::FromSeconds(5))) { exit 1 }
$deadline = (Get-Date).AddSeconds(8)
while ($w.Position.Location.IsUnknown -and $w.Permission -ne 'Denied' -and (Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 200
}
$c = $w.Position.Location; $perm = $w.Permission; $w.Stop()
if ($perm -ne 'Granted') { exit 2 }
if ($c.IsUnknown) { exit 3 }
$inv = [Globalization.CultureInfo]::InvariantCulture
$c.Latitude.ToString($inv) + ',' + $c.Longitude.ToString($inv)
"""
_PS_ERRORS = {1: "service de localisation indisponible", 2: "accès à la localisation refusé",
              3: "position pas encore trouvée"}


def save_phone_position(lat: float, lon: float, accuracy: float | None = None) -> None:
    """Appelé par le serveur de position quand le téléphone envoie sa position."""
    POSITION_FILE.write_text(json.dumps({"lat": lat, "lon": lon, "accuracy": accuracy,
                                         "time": time.time()}), encoding="utf-8")


def clear_phone_position() -> None:
    """L'utilisateur arrête le partage : on oublie la dernière position."""
    POSITION_FILE.unlink(missing_ok=True)


def phone_position() -> str | None:
    """Dernière position du téléphone 'lat,lon', si elle date de moins de PHONE_POSITION_MAX_AGE s."""
    try:
        data = json.loads(POSITION_FILE.read_text(encoding="utf-8"))
        if time.time() - data["time"] <= PHONE_POSITION_MAX_AGE:
            return f"{data['lat']},{data['lon']}"
    except (OSError, ValueError, KeyError, TypeError):
        pass  # pas de fichier, ou fichier abîmé : pas de position téléphone
    return None


def pc_position() -> str | None:
    """Position 'lat,lon' donnée par Windows, ou None (autre système, accès refusé, pas de signal)."""
    if not USE_PC_LOCATION or sys.platform != "win32":
        return None
    try:
        r = run_powershell(_PS_SCRIPT, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as e:
        log.warning("Localisation du PC impossible : %s", e)
        return None
    if r.returncode != 0:
        log.warning("Localisation du PC : %s", _PS_ERRORS.get(r.returncode, r.stderr.strip()[:200]))
        return None
    try:
        lat, lon = (float(x) for x in r.stdout.strip().split(","))
    except ValueError:
        log.warning("Localisation du PC : réponse illisible")
        return None
    return f"{lat},{lon}"


def current_position() -> str | None:
    """Position actuelle 'lat,lon' : téléphone (plus précis, suit l'utilisateur), puis PC."""
    return phone_position() or pc_position()

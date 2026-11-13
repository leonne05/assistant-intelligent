"""Serveur de position : le téléphone partage sa position GPS avec JARVIS (Windows).

    python position_server.py

Puis, sur le téléphone (même Wi-Fi que le PC), ouvre le lien affiché et accepte la localisation.
Le navigateur n'autorise le GPS qu'en HTTPS : un certificat est créé au premier lancement avec
l'outil intégré de Windows. Le téléphone affichera un avertissement « connexion non privée »
la première fois : choisis « Continuer ».
Le lien contient un code secret, pour que personne d'autre sur le Wi-Fi ne puisse envoyer une
fausse position.
"""
import base64
import hmac
import ipaddress
import json
import logging
import secrets
import socket
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from deplacements import location
from deplacements.common import run_powershell
from deplacements.config import CERT_DIR, POSITION_PORT

log = logging.getLogger("position_server")
TOKEN = secrets.token_urlsafe(16)
PAGE = (Path(__file__).parent / "position_page.html").read_bytes()

# Certificat auto-signé créé par Windows, puis retiré du magasin : il ne sert qu'à ce serveur.
# Sortie : certificat et clé privée (PKCS#8) en base64, une ligne chacun.
_PS_CERT = r"""
$c = New-SelfSignedCertificate -Subject 'CN=JARVIS' -KeyAlgorithm RSA -KeyLength 2048 `
  -KeyExportPolicy Exportable -TextExtension @('2.5.29.17={text}IPAddress=__IP__&IPAddress=127.0.0.1') `
  -CertStoreLocation 'Cert:\CurrentUser\My' -NotAfter (Get-Date).AddYears(2)
try {
  $key = [Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($c)
  [Convert]::ToBase64String($c.RawData)
  [Convert]::ToBase64String($key.Key.Export([Security.Cryptography.CngKeyBlobFormat]::Pkcs8PrivateBlob))
} finally { Remove-Item ('Cert:\CurrentUser\My\' + $c.Thumbprint) }
"""


def parse_position(body: bytes) -> tuple[float, float, float | None] | None:
    """Corps JSON {lat, lon, accuracy} -> (lat, lon, accuracy) ; None si {clear: true}.
    Lève ValueError, KeyError ou TypeError si ce n'est pas une position valable."""
    data = json.loads(body or b"{}")
    if not isinstance(data, dict):
        raise ValueError("objet JSON attendu")
    if data.get("clear"):
        return None
    lat, lon = float(data["lat"]), float(data["lon"])
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("coordonnées hors limites")
    accuracy = data.get("accuracy")
    return lat, lon, float(accuracy) if accuracy is not None else None


class Handler(BaseHTTPRequestHandler):
    def _authorized(self) -> bool:
        token = parse_qs(urlparse(self.path).query).get("t", [""])[0]
        return hmac.compare_digest(token, TOKEN)

    def _reply(self, code: int, body: bytes = b"", ctype: str = "text/plain; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if urlparse(self.path).path != "/" or not self._authorized():
            return self._reply(403, "Lien invalide : utilise celui affiché par JARVIS.".encode())
        self._reply(200, PAGE, "text/html; charset=utf-8")

    def do_POST(self):
        if urlparse(self.path).path != "/position" or not self._authorized():
            return self._reply(403, b"Refus")
        length = min(int(self.headers.get("Content-Length") or 0), 1024)
        try:
            pos = parse_position(self.rfile.read(length))
        except (ValueError, KeyError, TypeError):
            return self._reply(400, b"Position invalide")
        if pos is None:
            location.clear_phone_position()
            log.info("Partage de position arrêté par le téléphone.")
        else:
            location.save_phone_position(*pos)
            log.info("Position du téléphone reçue.")
        self._reply(204)

    def log_message(self, fmt, *args):  # pas de journal brut : les URL contiennent le code secret
        pass


def lan_ip() -> str:
    """Adresse du PC sur le Wi-Fi (aucun paquet n'est envoyé : on lit juste la route choisie)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("192.0.2.1", 80))  # adresse de documentation, jamais contactée
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def _pem(label: str, b64: str) -> str:
    return f"-----BEGIN {label}-----\n{base64.encodebytes(base64.b64decode(b64)).decode()}-----END {label}-----\n"


def ensure_certificate(ip: str) -> tuple[Path, Path]:
    """Certificat auto-signé pour `ip`, créé une fois (recréé si l'adresse du PC change)."""
    cert, key, marker = CERT_DIR / "cert.pem", CERT_DIR / "key.pem", CERT_DIR / "ip.txt"
    if cert.exists() and key.exists() and marker.exists() and marker.read_text() == ip:
        return cert, key
    ipaddress.ip_address(ip)  # garde-fou : seule une vraie adresse IP entre dans le script
    r = run_powershell(_PS_CERT.replace("__IP__", ip), timeout=60)
    if r.returncode != 0 or len(r.stdout.split()) != 2:
        raise SystemExit(f"Création du certificat impossible : {r.stderr.strip()[:300]}")
    cert_b64, key_b64 = r.stdout.split()
    CERT_DIR.mkdir(exist_ok=True)
    cert.write_text(_pem("CERTIFICATE", cert_b64), encoding="ascii")
    key.write_text(_pem("PRIVATE KEY", key_b64), encoding="ascii")
    marker.write_text(ip)
    return cert, key


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ip = lan_ip()
    cert, key = ensure_certificate(ip)
    server = ThreadingHTTPServer(("0.0.0.0", POSITION_PORT), Handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    print(f"Sur le téléphone (même Wi-Fi), ouvre :\n  https://{ip}:{POSITION_PORT}/?t={TOKEN}\n"
          "Avertissement de sécurité la première fois : « Paramètres avancés » puis « Continuer ».\n"
          "Ctrl+C pour arrêter.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

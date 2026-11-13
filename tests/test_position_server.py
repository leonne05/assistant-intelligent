"""Serveur de position : vraies requêtes HTTP sur un serveur local (sans TLS, port libre)."""
import base64
import json
import threading
from http.server import ThreadingHTTPServer

import pytest
import requests

import position_server
from deplacements import location

TOKEN = {"t": position_server.TOKEN}


@pytest.fixture
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), position_server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def get(url, params=None):
    return requests.get(url, params=params, timeout=5)


def post(base, body, params=TOKEN):
    return requests.post(f"{base}/position", params=params, data=json.dumps(body), timeout=5)


def test_page_needs_the_secret(server):
    page = get(server, TOKEN)
    assert page.status_code == 200 and "Partager ma position" in page.text
    assert page.headers["Content-Type"].startswith("text/html")
    assert get(server).status_code == 403
    assert get(server, {"t": "faux"}).status_code == 403
    assert get(f"{server}/autre", TOKEN).status_code == 403


def test_position_saved_then_cleared(server):
    assert post(server, {"lat": 48.84, "lon": 2.37, "accuracy": 12}).status_code == 204
    assert location.phone_position() == "48.84,2.37"
    assert post(server, {"clear": True}).status_code == 204
    assert location.phone_position() is None


def test_position_refused(server):
    assert post(server, {"lat": 48.84, "lon": 2.37}, {"t": "faux"}).status_code == 403
    assert post(server, {"lat": 999, "lon": 2.37}).status_code == 400
    assert location.phone_position() is None


def test_parse_position():
    assert position_server.parse_position(b'{"lat": 48.8, "lon": 2.3, "accuracy": 9}') == (48.8, 2.3, 9.0)
    assert position_server.parse_position(b'{"lat": 48.8, "lon": 2.3}') == (48.8, 2.3, None)
    assert position_server.parse_position(b'{"clear": true}') is None


@pytest.mark.parametrize("body", [b'{"lat": 120, "lon": 2}', b'{"lat": "x", "lon": 2}', b'{"lon": 2}',
                                  b"[1, 2]", b"pas du json"])
def test_parse_position_rejects(body):
    with pytest.raises((ValueError, KeyError, TypeError)):
        position_server.parse_position(body)


@pytest.fixture
def cert_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(position_server, "CERT_DIR", tmp_path / "certs")


def test_certificate_created_once_per_ip(cert_dir, fake_powershell):
    der = bytes(range(100))
    calls = fake_powershell(position_server, stdout=f"Q0VSVA==\n{base64.b64encode(der).decode()}\n")
    cert, key = position_server.ensure_certificate("192.168.1.20")
    assert "IPAddress=192.168.1.20" in calls[0]
    assert cert.read_text().startswith("-----BEGIN CERTIFICATE-----\nQ0VSVA==")
    lines = key.read_text().splitlines()
    assert lines[0] == "-----BEGIN PRIVATE KEY-----" and lines[-1] == "-----END PRIVATE KEY-----"
    assert all(len(line) <= 76 for line in lines) and base64.b64decode("".join(lines[1:-1])) == der
    position_server.ensure_certificate("192.168.1.20")
    assert len(calls) == 1                                  # même adresse : réutilisé
    position_server.ensure_certificate("192.168.1.21")
    assert len(calls) == 2                                  # le PC a changé d'adresse : recréé


def test_certificate_refuses_non_ip(cert_dir, fake_powershell):
    calls = fake_powershell(position_server, stdout="A\nB\n")
    with pytest.raises(ValueError):
        position_server.ensure_certificate("1.2.3.4'; Remove-Item C:\\ #")
    assert calls == []


def test_certificate_tool_failure(cert_dir, fake_powershell):
    fake_powershell(position_server, returncode=1)
    with pytest.raises(SystemExit, match="certificat impossible"):
        position_server.ensure_certificate("192.168.1.20")

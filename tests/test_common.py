"""Appel HTTP partagé : chaque panne devient une phrase lisible par l'utilisateur."""
import pytest
import requests

from deplacements import common, transport
from deplacements.common import DeplacementsError


class FakeResponse:
    def __init__(self, status=200, data=None):
        self.status_code, self.data = status, data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self):
        if self.data is None:
            raise ValueError("pas du JSON")
        return self.data


def fake_get(monkeypatch, outcome):
    def get(url, params=None, headers=None, timeout=None):
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    monkeypatch.setattr(common.requests, "get", get)


def test_get_json_ok(monkeypatch):
    fake_get(monkeypatch, FakeResponse(200, {"ok": 1}))
    assert common.get_json("https://x") == {"ok": 1}


@pytest.mark.parametrize("outcome, message", [
    (requests.Timeout(), "ne répond pas"),
    (FakeResponse(401), "Clé API refusée"),
    (FakeResponse(403), "Clé API refusée"),
    (FakeResponse(500), "HTTP 500"),
    (requests.ConnectionError(), "injoignable"),
    (FakeResponse(200, None), "injoignable"),  # réponse qui n'est pas du JSON
])
def test_get_json_errors_become_sentences(monkeypatch, outcome, message):
    fake_get(monkeypatch, outcome)
    with pytest.raises(DeplacementsError, match=message):
        common.get_json("https://x")


def test_prim_without_key(monkeypatch):
    monkeypatch.setattr(transport, "PRIM_API_KEY", "")
    with pytest.raises(DeplacementsError, match="PRIM_API_KEY manquante"):
        transport._get("places")

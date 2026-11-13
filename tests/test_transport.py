from datetime import datetime

import pytest

from deplacements import transport
from deplacements.common import DeplacementsError

LINE = "line:IDFM:C01742"

# Extraits de vraies réponses PRIM, réduits aux champs que le code lit.
PLACES = {"places": [{"name": "27bis Rue du Progrès (Montreuil)", "embedded_type": "address",
                      "address": {"coord": {"lon": "2.44", "lat": "48.86"}}}]}
JOURNEYS = {"journeys": [{
    "departure_date_time": "20261127T080000", "arrival_date_time": "20261127T084200",
    "duration": 2520, "nb_transfers": 1,
    "sections": [
        {"type": "street_network"},  # marche : ignorée
        {"type": "public_transport",
         "display_informations": {"commercial_mode": "RER", "label": "A",
                                  "links": [{"type": "line", "id": LINE}]}},
    ],
}]}


@pytest.fixture(autouse=True)
def fake_prim(monkeypatch):
    """Faux PRIM : renvoie l'extrait selon le chemin et note chaque appel."""
    calls = []
    answers = {"places": PLACES, "journeys": JOURNEYS}
    monkeypatch.setattr(transport, "_get",
                        lambda path, params=None: calls.append((path, params)) or answers.get(path, {}))
    transport.resolve_place.cache_clear()  # sinon le cache garde les adresses d'un autre test
    return calls


def test_resolve_place_gives_coords_and_name(fake_prim):
    assert transport.resolve_place("27 bis rue du Progrès") == ("2.44;48.86", "27bis Rue du Progrès (Montreuil)")
    transport.resolve_place("27 bis rue du Progrès")
    assert len(fake_prim) == 1  # deuxième fois : servi par le cache


def test_resolve_place_not_found(monkeypatch):
    monkeypatch.setattr(transport, "_get", lambda path, params=None: {"places": []})
    with pytest.raises(DeplacementsError, match="introuvable"):
        transport.resolve_place("Nulle part")


def test_get_journeys_reads_api_answer(fake_prim):
    [j] = transport.get_journeys("A", "B", datetime(2026, 11, 27, 8, 50), {LINE})
    assert j == {"departure": datetime(2026, 11, 27, 8, 0), "arrival": datetime(2026, 11, 27, 8, 42),
                 "duration_min": 42, "transfers": 1, "from": "27bis Rue du Progrès (Montreuil)",
                 "to": "27bis Rue du Progrès (Montreuil)",
                 "lines": [{"id": LINE, "name": "RER A"}]}
    path, params = fake_prim[-1]
    assert path == "journeys" and params["datetime_represents"] == "arrival"
    assert params["datetime"] == "20261127T085000" and params["forbidden_uris[]"] == [LINE]


def test_get_journeys_leaving_now(fake_prim):
    transport.get_journeys("A", "B", datetime(2026, 11, 27, 8, 50), by_arrival=False)
    assert fake_prim[-1][1]["datetime_represents"] == "departure"


def places(*found):
    """Réponse PRIM /places : found = (type, nom)..."""
    return {"places": [{"name": name, "embedded_type": kind, kind: {"coord": {"lon": str(i), "lat": "48"}}}
                       for i, (kind, name) in enumerate(found)]}


def test_resolve_place_gps_position_skips_api(fake_prim):
    assert transport.resolve_place("48.85, 2.35") == ("2.35;48.85", "ta position")
    assert fake_prim == []


def test_resolve_place_station_wins_over_town(monkeypatch):
    monkeypatch.setattr(transport, "_get", lambda path, params=None: places(
        ("administrative_region", "Melun"), ("stop_area", "Melun (Melun)")))
    assert transport.resolve_place("Gare de Melun") == ("1;48", "la station Melun (Melun)")


def test_resolve_place_station_label_not_doubled(monkeypatch):
    monkeypatch.setattr(transport, "_get", lambda path, params=None: places(("stop_area", "Gare de Lyon (Paris)")))
    assert transport.resolve_place("gare de lyon")[1] == "Gare de Lyon (Paris)"


def test_resolve_place_refuses_unrelated_match(monkeypatch):
    """« HETIC » : l'API répond quand même, avec un lieu sans rapport."""
    monkeypatch.setattr(transport, "_get", lambda path, params=None: places(
        ("stop_area", "La Bochetière (Choisy-en-Brie)"), ("poi", "Maryam Esthetic (Paris)")))
    with pytest.raises(DeplacementsError, match="introuvable : HETIC.*La Bochetière"):
        transport.resolve_place("HETIC")


def disruption(text, kind, begin, end, obj_id=LINE):
    return {"messages": [{"text": text}],
            "application_periods": [{"begin": begin, "end": end}],
            "impacted_objects": [{"pt_object": {"embedded_type": kind, "id": obj_id, "name": "RER A"}}]}


def test_get_disruptions_keeps_only_active_line_level(monkeypatch):
    reports = {"disruptions": [
        disruption("Trafic interrompu", "line", "20261127T060000", "20261127T120000"),
        disruption("Ascenseur en panne", "stop_area", "20261127T060000", "20261127T120000", "sa:1"),
        disruption("Travaux terminés", "line", "20261101T000000", "20261102T000000"),
    ]}
    monkeypatch.setattr(transport, "_get", lambda path, params=None: reports)
    found = transport.get_disruptions(LINE, datetime(2026, 11, 27, 9, 0))
    assert [d["message"] for d in found] == ["Trafic interrompu"]


def test_get_disruptions_strips_html(monkeypatch):
    raw = ('<p>Le trafic est perturb&#233;.<br><br>Consultez le <a href="https://x.com">fil X</a>.'
           "<br><br>Pour plus d'informations sur cette perturbation, consultez le "
           '<a href="https://x.com">fil X du RER A</a>.'
           '<br>Motif : panne&nbsp;&#224; Nanterre.</p>')
    reports = {"disruptions": [disruption(raw, "line", "20261127T060000", "20261127T120000")]}
    monkeypatch.setattr(transport, "_get", lambda path, params=None: reports)
    [d] = transport.get_disruptions(LINE, datetime(2026, 11, 27, 9, 0))
    assert d["message"] == "Le trafic est perturbé. Consultez le fil X. Motif : panne à Nanterre."

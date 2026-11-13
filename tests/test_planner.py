from datetime import datetime, timedelta

import pytest

from deplacements import planner, transport, weather
from deplacements.common import DeplacementsError

# Toujours dans le futur, pour que les tests ne périment pas.
ARRIVAL = (datetime.now() + timedelta(days=3)).replace(hour=9, minute=0, second=0, microsecond=0)
DEPARTURE = ARRIVAL - timedelta(minutes=55)  # départ réel renvoyé par l'API : 08:05


def journey(duration, line_id, name, transfers=0):
    return {"duration_min": duration, "transfers": transfers, "departure": DEPARTURE,
            "arrival": DEPARTURE + timedelta(minutes=duration),
            "from": "A", "to": "B", "lines": [{"id": line_id, "name": name}]}


def fake_journeys(monkeypatch, journeys):
    """Remplace get_journeys et renvoie la liste des heures d'arrivée demandées."""
    asked = []
    monkeypatch.setattr(transport, "get_journeys",
                        lambda origin, destination, arrive_by, *a: asked.append(arrive_by) or journeys)
    return asked


def journeys_with_alternative(origin, destination, arrive_by, forbidden=(), by_arrival=True):
    """RER A d'abord ; Bus 113 quand des lignes sont exclues."""
    return [journey(55, "BUS", "Bus 113")] if forbidden else [journey(40, "L1", "RER A")]


def cut(*line_ids):
    """Faux get_disruptions : les lignes `line_ids` sont perturbées."""
    return lambda lid, at=None: [{"line_id": lid, "line_name": lid, "message": "coupée"}] if lid in line_ids else []


@pytest.fixture(autouse=True)
def no_weather(monkeypatch):
    """Par défaut destination 'B', pas de météo ni de perturbation ; un test peut le remplacer."""
    monkeypatch.setattr(transport, "resolve_place", lambda query: ("2.3;48.8", "B"))
    monkeypatch.setattr(weather, "get_weather", lambda *a: None)
    monkeypatch.setattr(transport, "get_disruptions", cut())


def test_best_journey_tie_on_transfers():
    js = [journey(50, "a", "A"), journey(40, "b", "B", 2), journey(40, "c", "C", 1)]
    assert planner.best_journey(js)["lines"][0]["id"] == "c"


def test_plan_normal(monkeypatch):
    asked = fake_journeys(monkeypatch, [journey(40, "L1", "RER A")])
    plan = planner.plan_travel("A", "B", ARRIVAL)
    assert asked == [ARRIVAL - timedelta(minutes=10)]  # arrivée - marge de 10 min
    assert plan["journey"]["departure"] == DEPARTURE    # pas recalculé : heure réelle du trajet
    assert "Pars à 08:05 de A vers B" in planner.format_plan(plan)
    assert "arrivée vers 08:45" in planner.format_plan(plan)


def test_plan_switches_when_line_disrupted(monkeypatch):
    monkeypatch.setattr(transport, "get_journeys", journeys_with_alternative)
    monkeypatch.setattr(transport, "get_disruptions", cut("L1"))
    plan = planner.plan_travel("A", "B", ARRIVAL)
    assert plan["switched"] and plan["journey"]["lines"][0]["name"] == "Bus 113"
    assert "J'ai choisi un trajet qui l'évite" in planner.format_plan(plan)


def test_plan_keeps_trip_when_alternative_also_disrupted(monkeypatch):
    monkeypatch.setattr(transport, "get_journeys", journeys_with_alternative)
    monkeypatch.setattr(transport, "get_disruptions", cut("L1", "BUS"))
    plan = planner.plan_travel("A", "B", ARRIVAL)
    assert not plan["switched"] and plan["journey"]["lines"][0]["name"] == "RER A"
    assert "prévois du retard" in planner.format_plan(plan)


def test_plan_survives_failing_extras(monkeypatch):
    def down(*a):
        raise DeplacementsError("panne")

    fake_journeys(monkeypatch, [journey(40, "L1", "RER A")])
    monkeypatch.setattr(transport, "get_disruptions", down)
    monkeypatch.setattr(weather, "get_weather", down)
    plan = planner.plan_travel("A", "B", ARRIVAL)
    assert plan["disrupted"] == [] and plan["weather"] is None


def test_plan_rain_adds_margin(monkeypatch):
    rainy = {"snow_cm": 0, "rain_mm": 4, "rain_prob": 90}
    asked = fake_journeys(monkeypatch, [journey(40, "L1", "RER A")])
    weather_asked = []
    monkeypatch.setattr(weather, "get_weather", lambda *a: weather_asked.append(a) or rainy)
    planner.plan_travel("A", "B", ARRIVAL)
    assert weather_asked == [("B", ARRIVAL.date(), ("48.8", "2.3"))]  # météo à destination (lat, lon)
    assert asked == [ARRIVAL - timedelta(minutes=15)]  # 10 min + 5 min de pluie


def test_no_journey(monkeypatch):
    fake_journeys(monkeypatch, [])
    with pytest.raises(DeplacementsError, match="Aucun itinéraire"):
        planner.plan_travel("A", "B", ARRIVAL)


def test_arrival_in_the_past():
    with pytest.raises(DeplacementsError, match="déjà passée"):
        planner.plan_travel("A", "B", datetime.now() - timedelta(hours=1))


def test_plan_leave_now_without_arrival_time(monkeypatch):
    asked = []
    monkeypatch.setattr(transport, "get_journeys",
                        lambda o, d, when, forbidden, by_arrival: asked.append((when, by_arrival))
                        or [journey(40, "L1", "RER A")])
    before = datetime.now()
    plan = planner.plan_travel("A", "B")
    [(when, by_arrival)] = asked
    assert by_arrival is False and before <= when <= datetime.now()  # départ maintenant, sans marge
    assert plan["leave_now"]


def test_plan_leave_now_rain_is_not_a_margin(monkeypatch):
    fake_journeys(monkeypatch, [journey(40, "L1", "RER A")])
    monkeypatch.setattr(weather, "get_weather", lambda *a: {"snow_cm": 0, "rain_mm": 4, "rain_prob": 90})
    txt = planner.format_plan(planner.plan_travel("A", "B"))
    assert "prends de quoi te couvrir" in txt and "marge" not in txt

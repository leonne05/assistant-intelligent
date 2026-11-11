from datetime import datetime

import pytest

from deplacements import planner, transport, weather
from deplacements.common import DeplacementsError

ARRIVAL = datetime(2026, 11, 27, 9, 0)


def journey(duration, line_id, name, transfers=0):
    return {"duration_min": duration, "transfers": transfers,
            "lines": [{"id": line_id, "name": name}]}


def test_compute_departure():
    assert planner.compute_departure(ARRIVAL, 40, 10) == datetime(2026, 11, 27, 8, 10)


def test_best_journey_tie_on_transfers():
    js = [journey(50, "a", "A"), journey(40, "b", "B", 2), journey(40, "c", "C", 1)]
    assert planner.best_journey(js)["lines"][0]["id"] == "c"


def test_plan_normal(monkeypatch):
    monkeypatch.setattr(transport, "get_journeys", lambda *a: [journey(40, "L1", "RER A")])
    monkeypatch.setattr(transport, "get_disruptions", lambda *a: [])
    monkeypatch.setattr(weather, "get_weather", lambda *a: None)
    plan = planner.plan_travel("A", "B", ARRIVAL)
    assert plan["leave_at"] == datetime(2026, 11, 27, 8, 10)
    assert "Pars à 08:10" in planner.format_plan(plan)


def test_plan_switches_when_line_disrupted(monkeypatch):
    def fake_journeys(origin, destination, arrive_by, forbidden=()):
        return [journey(55, "BUS", "Bus 113")] if forbidden else [journey(40, "L1", "RER A")]

    monkeypatch.setattr(transport, "get_journeys", fake_journeys)
    monkeypatch.setattr(transport, "get_disruptions",
                        lambda lid, at=None: [{"line_id": "L1", "line_name": "RER A", "message": "coupée"}] if lid == "L1" else [])
    monkeypatch.setattr(weather, "get_weather", lambda *a: None)
    plan = planner.plan_travel("A", "B", ARRIVAL)
    assert plan["switched"] and plan["journey"]["lines"][0]["name"] == "Bus 113"
    assert "RER A" in planner.format_plan(plan)


def test_plan_survives_failing_extras(monkeypatch):
    def down(*a):
        raise DeplacementsError("panne")

    monkeypatch.setattr(transport, "get_journeys", lambda *a: [journey(40, "L1", "RER A")])
    monkeypatch.setattr(transport, "get_disruptions", down)
    monkeypatch.setattr(weather, "get_weather", down)
    plan = planner.plan_travel("A", "B", ARRIVAL)
    assert plan["disrupted"] == [] and plan["weather"] is None


def test_plan_rain_adds_margin(monkeypatch):
    rainy = {"snow_cm": 0, "rain_mm": 4, "rain_prob": 90}
    monkeypatch.setattr(transport, "get_journeys", lambda *a: [journey(40, "L1", "RER A")])
    monkeypatch.setattr(transport, "get_disruptions", lambda *a: [])
    monkeypatch.setattr(weather, "get_weather", lambda *a: rainy)
    assert planner.plan_travel("A", "B", ARRIVAL)["leave_at"] == datetime(2026, 11, 27, 8, 5)


def test_no_journey(monkeypatch):
    monkeypatch.setattr(transport, "get_journeys", lambda *a: [])
    with pytest.raises(DeplacementsError):
        planner.plan_travel("A", "B", ARRIVAL)

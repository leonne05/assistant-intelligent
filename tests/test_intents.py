from datetime import date, datetime

from deplacements import ACTIONS, handle_intent, planner, transport, weather
from deplacements.common import DeplacementsError

FAKE_WEATHER = {"city": "Caen", "day": date(2026, 11, 12), "description": "pluie", "t_min": 5,
                "t_max": 9, "rain_mm": 4, "snow_cm": 0, "rain_prob": 80, "wind_kmh": 15}


def test_router_contract():
    """Le routeur appelle fonction(entities, text_interaction) et attend une str."""
    assert set(ACTIONS) == {"GET_WEATHER", "CHECK_TRANSPORT", "PLAN_TRAVEL"}
    assert isinstance(ACTIONS["PLAN_TRAVEL"]({}, "Comment aller à Caen ?"), str)


def test_unknown_intent():
    assert "inconnue" in handle_intent("DANCE")


def test_weather_uses_location_and_date(monkeypatch):
    seen = {}
    monkeypatch.setattr(weather, "get_weather", lambda city, day: seen.update(city=city, day=day) or FAKE_WEATHER)
    answer = handle_intent("GET_WEATHER", {"location": "Caen", "datetime": "2026-11-12T14:00"}, "")
    assert seen == {"city": "Caen", "day": date(2026, 11, 12)}
    assert "Caen" in answer


def test_weather_without_entities(monkeypatch):
    monkeypatch.setattr(weather, "get_weather", lambda city, day: FAKE_WEATHER)
    assert isinstance(handle_intent("GET_WEATHER", {}, ""), str)


def test_bad_date():
    assert handle_intent("GET_WEATHER", {"datetime": "demain"}, "") == "Je n'ai pas compris la date."


def test_line_found_in_sentence(monkeypatch):
    seen = {}
    monkeypatch.setattr(transport, "check_line", lambda name: seen.setdefault("line", name) and [])
    answer = handle_intent("CHECK_TRANSPORT", {}, "Y a-t-il des perturbations sur le RER A ?")
    assert seen["line"] == "RER A" and "Aucune perturbation" in answer


def test_missing_line():
    assert "De quelle ligne" in handle_intent("CHECK_TRANSPORT", {}, "Ça roule ?")


def test_error_becomes_sentence(monkeypatch):
    def down(name):
        raise DeplacementsError("API en panne")

    monkeypatch.setattr(transport, "check_line", down)
    assert handle_intent("CHECK_TRANSPORT", {}, "RER A ?") == "API en panne"


def test_plan_uses_location_and_datetime(monkeypatch):
    seen = {}
    monkeypatch.setattr(planner, "plan_travel", lambda o, d, a: seen.update(dest=d, arrive=a) or {})
    monkeypatch.setattr(planner, "format_plan", lambda plan: "ok")
    assert handle_intent("PLAN_TRAVEL", {"location": "Gare Saint-Lazare", "datetime": "2026-11-12T14:00"}, "") == "ok"
    assert seen == {"dest": "Gare Saint-Lazare", "arrive": datetime(2026, 11, 12, 14, 0)}


def test_plan_without_agenda_connected():
    assert "Planning" in handle_intent("PLAN_TRAVEL", {}, "")

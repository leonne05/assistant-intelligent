from datetime import date, datetime

from deplacements import ACTIONS, handle_intent, location, planner, transport, weather
from deplacements.common import DeplacementsError
from deplacements.config import HOME_ADDRESS

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


def fake_plan(monkeypatch):
    """Remplace le planificateur et renvoie ce qu'il a reçu."""
    seen = {}
    monkeypatch.setattr(planner, "plan_travel", lambda o, d, a: seen.update(origin=o, dest=d, arrive=a) or {})
    monkeypatch.setattr(planner, "format_plan", lambda plan: "ok")
    return seen


def test_plan_uses_location_and_datetime(monkeypatch):
    seen = fake_plan(monkeypatch)
    assert handle_intent("PLAN_TRAVEL", {"location": "Gare Saint-Lazare", "datetime": "2026-11-12T14:00"}, "") == "ok"
    assert seen == {"origin": HOME_ADDRESS, "dest": "Gare Saint-Lazare", "arrive": datetime(2026, 11, 12, 14, 0)}


def test_plan_destination_without_time_leaves_now(monkeypatch):
    seen = fake_plan(monkeypatch)
    assert handle_intent("PLAN_TRAVEL", {"location": "Gare de Melun"}, "") == "ok"
    assert seen["arrive"] is None


def test_plan_origin_entity(monkeypatch):
    seen = fake_plan(monkeypatch)
    handle_intent("PLAN_TRAVEL", {"location": "Melun", "origin": "Gare de Lyon"}, "")
    assert seen["origin"] == "Gare de Lyon"
    handle_intent("PLAN_TRAVEL", {"location": "Melun", "origin": {"lat": 48.85, "lon": 2.35}}, "")
    assert seen["origin"] == "48.85,2.35"


TOMORROW_9AM = {"location": "Gare de Melun", "datetime": "2099-01-01T09:00"}


def test_plan_leaving_now_uses_current_position(monkeypatch):
    seen = fake_plan(monkeypatch)
    monkeypatch.setattr(location, "current_position", lambda: "48.84,2.37")
    assert handle_intent("PLAN_TRAVEL", {"location": "Gare de Melun"}, "") == "ok"
    assert seen["origin"] == "48.84,2.37"


def test_plan_later_trip_starts_from_home(monkeypatch):
    seen = fake_plan(monkeypatch)
    monkeypatch.setattr(location, "current_position", lambda: "48.84,2.37")
    handle_intent("PLAN_TRAVEL", TOMORROW_9AM, "Je dois être à Melun demain à 9 h")
    assert seen["origin"] == HOME_ADDRESS


def test_plan_later_trip_from_my_position_when_asked(monkeypatch):
    seen = fake_plan(monkeypatch)
    monkeypatch.setattr(location, "current_position", lambda: "48.84,2.37")
    handle_intent("PLAN_TRAVEL", TOMORROW_9AM, "À Melun demain à 9 h depuis ma position")
    assert seen["origin"] == "48.84,2.37"


def test_plan_origin_entity_beats_current_position(monkeypatch):
    seen = fake_plan(monkeypatch)
    monkeypatch.setattr(location, "current_position", lambda: "48.84,2.37")
    handle_intent("PLAN_TRAVEL", {"location": "Melun", "origin": "Châtelet"}, "")
    assert seen["origin"] == "Châtelet"


def test_plan_present_location_unknown_says_so(monkeypatch):
    fake_plan(monkeypatch)
    answer = handle_intent("PLAN_TRAVEL", {"location": "Gare de Melun"},
                           "je veux aller à la gare de Melun depuis ma position")
    assert answer == "Je n'ai pas ta position, je pars de ton adresse. ok"


def test_plan_without_agenda_connected():
    assert "Planning" in handle_intent("PLAN_TRAVEL", {}, "")
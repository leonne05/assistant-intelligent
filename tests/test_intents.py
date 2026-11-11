from deplacements import handle_intent, transport
from deplacements.common import DeplacementsError


def test_unknown_intent():
    assert "inconnue" in handle_intent("DANCE")


def test_error_becomes_sentence(monkeypatch):
    def down(name):
        raise DeplacementsError("API en panne")

    monkeypatch.setattr(transport, "check_line", down)
    assert handle_intent("CHECK_TRANSPORT", line="RER A") == "API en panne"


def test_no_disruption(monkeypatch):
    monkeypatch.setattr(transport, "check_line", lambda name: [])
    assert "Aucune perturbation" in handle_intent("CHECK_TRANSPORT", line="RER A")


def test_plan_without_agenda_connected():
    assert "Planning" in handle_intent("PLAN_TRAVEL")


def test_missing_param_never_raises():
    assert "erreur" in handle_intent("CHECK_TRANSPORT")

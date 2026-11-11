"""Actions appelées par le routeur : fonction(entities, text_interaction) -> str."""
import logging
import re
from datetime import datetime
from functools import wraps

from . import agenda, planner, transport, weather
from .common import DeplacementsError
from .config import HOME_ADDRESS

log = logging.getLogger(__name__)

# "RER A", "ligne 14", "bus 113"... repéré directement dans la phrase de l'utilisateur
LINE_RE = re.compile(r"\b(?:rer|m[ée]tro|ligne|bus|tram|transilien)\s+(?:[a-z]\b|\d+[a-z]?\b)", re.I)


def _when(entities: dict) -> datetime | None:
    """Entité 'datetime' (texte ISO, ex. '2026-11-12T14:00') -> datetime, ou None si absente."""
    value = entities.get("datetime")
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise DeplacementsError("Je n'ai pas compris la date.")


def _safe(action):
    """Une action ne lève jamais d'exception : elle renvoie toujours une phrase."""
    @wraps(action)
    def wrapper(entities=None, text_interaction=""):
        try:
            return action(entities or {}, text_interaction or "")
        except DeplacementsError as e:
            return str(e)
        except Exception:
            log.exception("Erreur inattendue dans %s", action.__name__)
            return "Désolé, une erreur est survenue."
    return wrapper


@_safe
def get_weather(entities, text_interaction):
    when = _when(entities)
    return weather.format_weather(
        weather.get_weather(entities.get("location"), when.date() if when else None))


@_safe
def check_transport(entities, text_interaction):
    match = LINE_RE.search(text_interaction)
    line = match.group(0) if match else entities.get("location")
    if not line:
        raise DeplacementsError("De quelle ligne parles-tu ?")
    hits = transport.check_line(line)
    if not hits:
        return f"Aucune perturbation signalée sur {line}."
    return f"Perturbation sur {line} : {hits[0]['message'] or 'perturbation en cours'}"


@_safe
def plan_travel(entities, text_interaction):
    destination, arrive_by = entities.get("location"), _when(entities)
    if not (destination and arrive_by):  # rien de précisé -> prochain rendez-vous
        rdv = agenda.get_next_appointment()
        destination, arrive_by = rdv["place"], rdv["time"]
    return planner.format_plan(planner.plan_travel(HOME_ADDRESS, destination, arrive_by))


ACTIONS = {"GET_WEATHER": get_weather, "CHECK_TRANSPORT": check_transport, "PLAN_TRAVEL": plan_travel}


def handle_intent(intent: str, entities: dict | None = None, text_interaction: str = "") -> str:
    action = ACTIONS.get(intent)
    if action is None:
        return f"Intention inconnue : {intent}"
    return action(entities, text_interaction)

"""Point d'entrée pour l'assistant vocal : handle_intent(nom, **params) -> str."""
import logging
from datetime import date, datetime

from . import agenda, planner, transport, weather
from .common import DeplacementsError
from .config import HOME_ADDRESS

log = logging.getLogger(__name__)


def _parse(value, cls):
    """Accepte une chaîne ISO ou un objet date/datetime déjà prêt."""
    return cls.fromisoformat(value) if isinstance(value, str) else value


def _weather(city=None, day=None):
    return weather.format_weather(weather.get_weather(city, _parse(day, date) if day else None))


def _transport(line):
    hits = transport.check_line(line)
    if not hits:
        return f"Aucune perturbation signalée sur {line}."
    return f"Perturbation sur {line} : {hits[0]['message'] or 'perturbation en cours'}"


def _plan(origin=None, destination=None, arrive_by=None, city=None):
    if not (destination and arrive_by):  # pas de précision -> prochain rendez-vous
        rdv = agenda.get_next_appointment()
        destination, arrive_by = rdv["place"], rdv["time"]
    plan = planner.plan_travel(origin or HOME_ADDRESS, destination, _parse(arrive_by, datetime), city)
    return planner.format_plan(plan)


HANDLERS = {"GET_WEATHER": _weather, "CHECK_TRANSPORT": _transport, "PLAN_TRAVEL": _plan}


def handle_intent(intent: str, **params) -> str:
    """Ne lève jamais d'exception : renvoie toujours une phrase."""
    handler = HANDLERS.get(intent)
    if handler is None:
        return f"Intention inconnue : {intent}"
    try:
        return handler(**params)
    except DeplacementsError as e:
        return str(e)
    except Exception:
        log.exception("Erreur inattendue dans %s", intent)
        return "Désolé, une erreur est survenue."

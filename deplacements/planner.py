"""PLAN_TRAVEL : choix du trajet, alternative si perturbation, heure de départ."""
import logging
from datetime import datetime, timedelta

from . import transport, weather
from .common import DeplacementsError
from .config import BUFFER_MINUTES

log = logging.getLogger(__name__)


def compute_departure(arrival: datetime, duration_min: int, margin_min: int = BUFFER_MINUTES) -> datetime:
    """Heure de départ = arrivée - durée du trajet - marge."""
    return arrival - timedelta(minutes=duration_min + margin_min)


def best_journey(journeys: list[dict]) -> dict:
    """Le plus court, puis le moins de correspondances."""
    return min(journeys, key=lambda j: (j["duration_min"], j["transfers"]))


def _try(fn, default, *args):
    """Appel facultatif : en cas de panne on logue et on continue avec `default`."""
    try:
        return fn(*args)
    except DeplacementsError as e:
        log.warning("%s indisponible : %s", fn.__name__, e)
        return default


def plan_travel(origin: str, destination: str, arrive_by: datetime,
                weather_city: str | None = None) -> dict:
    journeys = transport.get_journeys(origin, destination, arrive_by)
    if not journeys:
        raise DeplacementsError("Aucun itinéraire trouvé.")
    chosen = best_journey(journeys)

    # Perturbations sur les lignes du trajet -> on relance sans ces lignes.
    line_ids = {line["id"] for line in chosen["lines"] if line["id"]}
    disrupted = [d for lid in sorted(line_ids)
                 for d in _try(transport.get_disruptions, [], lid, arrive_by)]
    switched = False
    if disrupted:
        banned = {d["line_id"] for d in disrupted}
        alternatives = _try(transport.get_journeys, [], origin, destination, arrive_by, banned)
        if alternatives:
            chosen, switched = best_journey(alternatives), True

    # La météo allonge la marge.
    w = _try(weather.get_weather, None, weather_city, arrive_by.date())
    margin = BUFFER_MINUTES + (weather.extra_margin(w) if w else 0)

    return {
        "leave_at": compute_departure(arrive_by, chosen["duration_min"], margin),
        "journey": chosen,
        "disrupted": sorted({d["line_name"] for d in disrupted}),
        "switched": switched,
        "weather": w,
    }


def format_plan(plan: dict) -> str:
    j = plan["journey"]
    lines = ", ".join(line["name"] for line in j["lines"]) or "à pied"
    txt = f"Pars à {plan['leave_at']:%H:%M} : {lines}, {j['duration_min']} min."
    if plan["disrupted"]:
        txt += f" Attention, perturbation sur {', '.join(plan['disrupted'])}."
        txt += (" J'ai choisi un trajet qui l'évite." if plan["switched"]
                else " Pas d'alternative trouvée, prévois du retard.")
    if plan["weather"] and weather.extra_margin(plan["weather"]):
        txt += " Pluie ou neige prévue, j'ai ajouté de la marge."
    return txt

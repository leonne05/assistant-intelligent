"""PLAN_TRAVEL : choix du trajet, alternative si perturbation, heure de départ."""
import logging
from datetime import datetime, timedelta

from . import transport, weather
from .common import DeplacementsError
from .config import BUFFER_MINUTES

log = logging.getLogger(__name__)


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


def _disruptions(journey: dict, at: datetime) -> list[dict]:
    """Perturbations actives à `at` sur les lignes du trajet."""
    line_ids = sorted({line["id"] for line in journey["lines"] if line["id"]})
    return [d for lid in line_ids for d in _try(transport.get_disruptions, [], lid, at)]


def plan_travel(origin: str, destination: str, arrive_by: datetime | None = None) -> dict:
    """Trajet pour arriver avant `arrive_by`, ou en partant maintenant si `arrive_by` est None."""
    now = datetime.now()
    if arrive_by and arrive_by <= now:
        raise DeplacementsError("L'heure d'arrivée est déjà passée.")
    at = arrive_by or now  # moment du trajet : météo et perturbations
    by_arrival = arrive_by is not None

    coord, name = transport.resolve_place(destination)  # mémorisé : pas d'appel en plus
    lon, lat = coord.split(";")
    w = _try(weather.get_weather, None, name, at.date(), (lat, lon))
    when = now
    if by_arrival:
        # La marge (allongée par la météo à destination) avance l'heure d'arrivée demandée à l'API.
        when = arrive_by - timedelta(minutes=BUFFER_MINUTES + (weather.extra_margin(w) if w else 0))

    search = (origin, destination, when)
    journeys = transport.get_journeys(*search, (), by_arrival)
    if not journeys:
        raise DeplacementsError("Aucun itinéraire trouvé.")
    chosen = best_journey(journeys)

    # Perturbations sur le trajet -> on relance sans ces lignes,
    # et on ne garde l'alternative que si elle n'est pas perturbée elle aussi.
    disrupted = _disruptions(chosen, at)
    switched = False
    if disrupted:
        banned = {d["line_id"] for d in disrupted}
        alternatives = _try(transport.get_journeys, [], *search, banned, by_arrival)
        alt = best_journey(alternatives) if alternatives else None
        if alt and not _disruptions(alt, at):
            chosen, switched = alt, True

    return {
        "journey": chosen,  # chosen["departure"] : heure réelle du premier départ, donnée par l'API
        "disrupted": sorted({d["line_name"] for d in disrupted}),
        "switched": switched,
        "weather": w,
        "leave_now": not by_arrival,
    }


def format_plan(plan: dict) -> str:
    j = plan["journey"]
    lines = ", ".join(line["name"] for line in j["lines"]) or "à pied"
    txt = (f"Pars à {j['departure']:%H:%M} de {j['from']} vers {j['to']} : {lines}, "
           f"{j['duration_min']} min, arrivée vers {j['arrival']:%H:%M}.")
    if plan["disrupted"]:
        txt += f" Attention, perturbation sur {', '.join(plan['disrupted'])}."
        txt += (" J'ai choisi un trajet qui l'évite." if plan["switched"]
                else " Pas d'alternative trouvée, prévois du retard.")
    if plan["weather"] and weather.extra_margin(plan["weather"]):
        txt += (" Pluie ou neige prévue, prends de quoi te couvrir." if plan["leave_now"]
                else " Pluie ou neige prévue, j'ai ajouté de la marge.")
    return txt

"""CHECK_TRANSPORT : lieux, itinéraires et perturbations via l'API PRIM (Navitia IDFM)."""
from datetime import datetime

from .common import DeplacementsError, get_json
from .config import NAVITIA, PRIM_API_KEY

FMT = "%Y%m%dT%H%M%S"  # format de date de Navitia


def _get(path: str, params: dict | None = None) -> dict:
    """Seul point d'accès à PRIM : clé, URL de base et gestion d'erreur au même endroit."""
    if not PRIM_API_KEY:
        raise DeplacementsError("PRIM_API_KEY manquante : renseigne-la dans le fichier .env.")
    return get_json(f"{NAVITIA}/{path}", params, {"apiKey": PRIM_API_KEY})


def resolve_place(query: str) -> str:
    """Nom de lieu ou adresse -> 'lon;lat' (longitude en premier, format Navitia)."""
    places = _get("places", {"q": query, "count": 1}).get("places")
    if not places:
        raise DeplacementsError(f"Lieu introuvable : {query}")
    kind = places[0]["embedded_type"]
    coord = places[0][kind]["coord"]
    return f"{coord['lon']};{coord['lat']}"


def _lines(journey: dict) -> list[dict]:
    """Lignes de transport en commun d'un trajet : [{'id', 'name'}]."""
    lines = []
    for section in journey.get("sections", []):
        if section.get("type") != "public_transport":
            continue
        info = section["display_informations"]
        links = section.get("links", []) + info.get("links", [])
        line_id = next((l["id"] for l in links if l.get("type") == "line"), None)
        name = f"{info.get('commercial_mode', '')} {info.get('label', '')}".strip()
        lines.append({"id": line_id, "name": name})
    return lines


def get_journeys(origin: str, destination: str, arrive_by: datetime,
                 forbidden_lines=(), count: int = 3) -> list[dict]:
    """Itinéraires arrivant avant `arrive_by`, en excluant éventuellement des lignes (ids)."""
    params = {
        "from": resolve_place(origin), "to": resolve_place(destination), "count": count,
        "datetime": arrive_by.strftime(FMT), "datetime_represents": "arrival",
    }
    if forbidden_lines:
        params["forbidden_uris[]"] = list(forbidden_lines)
    return [{
        "departure": datetime.strptime(j["departure_date_time"], FMT),
        "arrival": datetime.strptime(j["arrival_date_time"], FMT),
        "duration_min": round(j["duration"] / 60),
        "transfers": j.get("nb_transfers", 0),
        "lines": _lines(j),
    } for j in _get("journeys", params).get("journeys", [])]


def _active_at(disruption: dict, at: datetime) -> bool:
    return any(datetime.strptime(p["begin"], FMT) <= at <= datetime.strptime(p["end"], FMT)
               for p in disruption.get("application_periods", []))


def get_disruptions(line_id: str, at: datetime | None = None) -> list[dict]:
    """Perturbations de la ligne `line_id` actives à `at` (maintenant par défaut).

    On ignore celles qui ne touchent qu'une gare (ascenseurs...) : seule la ligne compte.
    Retourne [{'line_id', 'line_name', 'message'}].
    """
    at = at or datetime.now()
    out = []
    for d in _get(f"lines/{line_id}/line_reports", {"count": 100}).get("disruptions", []):
        if not _active_at(d, at):
            continue
        message = (d.get("messages") or [{}])[0].get("text", "")
        for obj in d.get("impacted_objects", []):
            pt = obj.get("pt_object", {})
            if pt.get("embedded_type") == "line" and pt.get("id") == line_id:
                out.append({"line_id": line_id, "line_name": pt.get("name", ""), "message": message})
    return out


def find_line(name: str) -> str:
    """Nom de ligne (ex. 'RER A', 'Métro 1') -> identifiant Navitia."""
    found = _get("pt_objects", {"q": name, "type[]": "line", "count": 1}).get("pt_objects")
    if not found:
        raise DeplacementsError(f"Ligne introuvable : {name}")
    return found[0]["id"]


def check_line(name: str) -> list[dict]:
    """Perturbations en cours sur la ligne `name` (ex. 'RER A')."""
    return get_disruptions(find_line(name))

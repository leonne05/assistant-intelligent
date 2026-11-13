"""CHECK_TRANSPORT : lieux, itinéraires et perturbations via l'API PRIM (Navitia IDFM)."""
import html
import re
import unicodedata
from datetime import datetime
from functools import lru_cache

from .common import DeplacementsError, get_json
from .config import NAVITIA, PRIM_API_KEY

FMT = "%Y%m%dT%H%M%S"  # format de date de Navitia


def _get(path: str, params: dict | None = None) -> dict:
    """Seul point d'accès à PRIM : clé, URL de base et gestion d'erreur au même endroit."""
    if not PRIM_API_KEY:
        raise DeplacementsError("PRIM_API_KEY manquante : renseigne-la dans le fichier .env.")
    return get_json(f"{NAVITIA}/{path}", params, {"apiKey": PRIM_API_KEY})


# "48.85,2.35" : position GPS (latitude, longitude) envoyée par l'appareil de l'utilisateur
COORDS_RE = re.compile(r"^\s*(-?\d{1,3}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$")
STATION_WORDS = {"gare", "station", "arret"}
# Mots trop vagues pour dire si l'API a trouvé le bon lieu
STOPWORDS = STATION_WORDS | {"rue", "avenue", "boulevard", "place", "chemin", "allee", "route",
                             "quai", "bis", "ter", "des", "les", "aux", "sur", "sous"}


def _tokens(text: str) -> set[str]:
    """Mots sans accents ni majuscules : 'Gare de Melun' -> {'gare', 'de', 'melun'}."""
    text = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    return set(re.findall(r"[a-z0-9]+", text))


def _words(text: str) -> set[str]:
    """Mots significatifs : 'Gare de Melun' -> {'melun'}."""
    return {w for w in _tokens(text) if len(w) >= 3} - STOPWORDS


def _matches(query_words: set[str], name: str) -> bool:
    """Le nom trouvé (sans la ville entre parenthèses) partage-t-il un mot avec la demande ?"""
    found = _words(name.split(" (")[0])
    return any(f.startswith(q) or q.startswith(f) for q in query_words for f in found)


def _label(place: dict) -> str:
    name = place["name"]
    if place["embedded_type"] == "stop_area" and not _tokens(name) & STATION_WORDS:
        return f"la station {name}"  # 'Melun (Melun)' est la gare, pas la ville
    return name


@lru_cache  # une adresse n'est demandée qu'une fois à l'API (les échecs ne sont pas mémorisés)
def resolve_place(query: str) -> tuple[str, str]:
    """Lieu, adresse ou position 'lat,lon' -> ('lon;lat', nom lisible) (longitude en premier, format Navitia).

    L'API renvoie toujours quelque chose, même pour un nom qu'elle ne connaît pas : on refuse
    un résultat qui n'a aucun mot en commun avec la demande plutôt que d'envoyer au hasard.
    """
    gps = COORDS_RE.match(query)
    if gps:
        lat, lon = gps.groups()
        return f"{lon};{lat}", "ta position"
    places = _get("places", {"q": query, "count": 5}).get("places")
    if not places:
        raise DeplacementsError(f"Lieu introuvable : {query}")
    wanted = _words(query)
    candidates = [p for p in places if _matches(wanted, p["name"])] if wanted else places
    if not candidates:
        raise DeplacementsError(f"Lieu introuvable : {query} (l'API propose « {places[0]['name']} »). "
                                "Donne une adresse.")
    if _tokens(query) & STATION_WORDS:  # « gare de … » : un arrêt plutôt que la ville ou une rue
        candidates.sort(key=lambda p: p["embedded_type"] != "stop_area")  # tri stable : ordre de l'API gardé
    place = candidates[0]
    coord = place[place["embedded_type"]]["coord"]
    return f"{coord['lon']};{coord['lat']}", _label(place)


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


def get_journeys(origin: str, destination: str, when: datetime, forbidden_lines=(),
                 by_arrival: bool = True, count: int = 3) -> list[dict]:
    """Itinéraires arrivant avant `when` (ou partant après `when` si by_arrival=False),
    en excluant éventuellement des lignes (ids)."""
    from_coord, from_name = resolve_place(origin)
    to_coord, to_name = resolve_place(destination)
    params = {
        "from": from_coord, "to": to_coord, "count": count,
        "datetime": when.strftime(FMT), "datetime_represents": "arrival" if by_arrival else "departure",
    }
    if forbidden_lines:
        params["forbidden_uris[]"] = list(forbidden_lines)
    return [{
        "departure": datetime.strptime(j["departure_date_time"], FMT),
        "arrival": datetime.strptime(j["arrival_date_time"], FMT),
        "duration_min": round(j["duration"] / 60),
        "transfers": j.get("nb_transfers", 0),
        "lines": _lines(j),
        "from": from_name,
        "to": to_name,
    } for j in _get("journeys", params).get("journeys", [])]


def _clean_text(text: str) -> str:
    """Message PRIM en HTML -> texte lisible : balises retirées, entités décodées, espaces normalisés."""
    text = re.sub(r"<br\s*/?>|</p>", " ", text, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    # Phrase de renvoi (« Pour plus d'informations… consultez… ») : inutile à l'oral.
    text = re.sub(r"Pour (?:plus d['’]informations?|en savoir plus)[^.]*\.?", "", text, flags=re.I)
    return " ".join(text.split())  # split() absorbe aussi les espaces insécables


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
        message = _clean_text((d.get("messages") or [{}])[0].get("text", ""))
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

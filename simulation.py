"""Simulation de JARVIS Déplacements.

    python simulation.py          # monde simulé : pas de réseau, pas de vraie position, résultat stable
    python simulation.py --live   # vraies API (PRIM, Open-Meteo) et vraie position (téléphone / PC)

En mode simulé, seules les API et la position sont remplacées : tout le reste (intentions,
planificateur, lecture des réponses PRIM) est le vrai code. Chaque scénario dit ce que JARVIS
doit répondre ; la simulation vérifie la réponse et s'arrête en erreur si un scénario échoue.
"""
import argparse
import sys
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from unittest import mock

from deplacements import handle_intent, intents, location, transport, weather
from deplacements.common import DeplacementsError
from deplacements.transport import FMT

# ---------- Le monde simulé ----------

# Lignes : nom court -> (mode, indice), comme PRIM les décrit
LINES = {"RER A": ("RER", "A"), "RER E": ("RER", "E"), "Transilien R": ("Train Transilien", "R"),
         "Métro 14": ("Métro", "14"), "Bus 113": ("Bus", "113"), "Bus 122": ("Bus", "122"),
         "Bus 215": ("Bus", "215")}
HOME = "10 rue de la Simulation, Neuilly-sur-Marne"  # domicile fictif (pas celui du .env)
HOME_COORD = ("2.53", "48.86")  # tout lieu inconnu de la simulation est placé ici (le domicile)
# Mot de la demande (sans accent) -> (type PRIM, nom renvoyé, lon, lat)
PLACES = {
    "melun": ("stop_area", "Melun (Melun)", "2.655", "48.527"),
    "progres": ("address", "27bis Rue du Progrès (Montreuil)", "2.44", "48.86"),
    "chatelet": ("stop_area", "Châtelet (Paris)", "2.347", "48.858"),
    "hetic": ("stop_area", "La Bochetière (Choisy-en-Brie)", "2.77", "48.76"),  # l'API se trompe
}
# Destination -> départ ("home" ou "paris") -> trajets possibles (lignes, minutes, correspondances)
ROUTES = {
    "Melun (Melun)": {
        "home": [(("Bus 113", "RER A", "Transilien R"), 66, 2), (("Bus 113", "RER E", "Transilien R"), 74, 2)],
        "paris": [(("Métro 14", "Transilien R"), 44, 1)],
    },
    "27bis Rue du Progrès (Montreuil)": {
        "home": [(("Bus 113", "RER A", "Bus 215"), 42, 2), (("Bus 113", "Bus 122"), 55, 1)],
        "paris": [(("RER A", "Bus 215"), 30, 1)],
    },
}


def line_id(name: str) -> str:
    return "line:SIM:" + name.replace(" ", "")


@dataclass
class World:
    """État du monde pour un scénario."""
    phone: str | None = None   # position envoyée par le téléphone ('lat,lon')
    pc: str | None = None      # position donnée par Windows
    rain: bool = False
    disrupted: dict[str, str] = field(default_factory=dict)  # ligne -> message de perturbation
    api_down: bool = False

    def prim(self, path: str, params: dict | None = None) -> dict:
        """Faux PRIM : mêmes chemins et même forme de réponse que la vraie API."""
        if self.api_down:
            raise DeplacementsError("Le service ne répond pas (timeout).")
        params = params or {}
        if path == "places":
            return {"places": [self._place(params["q"])]}
        if path == "journeys":
            return {"journeys": self._journeys(params)}
        if path == "pt_objects":
            q = params["q"].lower()
            return {"pt_objects": [{"id": line_id(n)} for n, (_, label) in LINES.items()
                                   if q.endswith(" " + label.lower())][:1]}
        if path.endswith("/line_reports"):
            return {"disruptions": self._reports(path.split("/")[1])}
        return {}

    def meteo(self, url: str, params: dict | None = None, headers: dict | None = None) -> dict:
        """Faux Open-Meteo (recherche de ville et prévision du jour)."""
        if url == weather.GEO_URL:
            return {"results": [{"name": params["name"], "latitude": 48.85, "longitude": 2.35}]}
        return {"daily": {"weather_code": [63 if self.rain else 3], "temperature_2m_max": [11],
                          "temperature_2m_min": [5], "precipitation_sum": [6 if self.rain else 0],
                          "snowfall_sum": [0], "precipitation_probability_max": [90 if self.rain else 10],
                          "wind_speed_10m_max": [18]}}

    @staticmethod
    def _place(q: str) -> dict:
        kind, name, lon, lat = next((p for key, p in PLACES.items() if key in transport._tokens(q)),
                                    ("address", q.split(",")[0] + " (simulation)", *HOME_COORD))
        return {"name": name, "embedded_type": kind, kind: {"coord": {"lon": lon, "lat": lat}}}

    def _journeys(self, params: dict) -> list[dict]:
        to_name = next((n for _, n, lon, lat in PLACES.values() if f"{lon};{lat}" == params["to"]), None)
        start = "home" if params["from"] == ";".join(HOME_COORD) else "paris"
        banned = set(params.get("forbidden_uris[]", []))
        when = datetime.strptime(params["datetime"], FMT)
        out = []
        for lines, minutes, transfers in ROUTES.get(to_name, {}).get(start, []):
            if banned & {line_id(n) for n in lines}:
                continue
            if params["datetime_represents"] == "arrival":
                arrival = when - timedelta(minutes=3)
                departure = arrival - timedelta(minutes=minutes)
            else:
                departure = when + timedelta(minutes=4)
                arrival = departure + timedelta(minutes=minutes)
            out.append({
                "departure_date_time": departure.strftime(FMT), "arrival_date_time": arrival.strftime(FMT),
                "duration": minutes * 60, "nb_transfers": transfers,
                "sections": [{"type": "public_transport", "display_informations": {
                    "commercial_mode": LINES[n][0], "label": LINES[n][1],
                    "links": [{"type": "line", "id": line_id(n)}]}} for n in lines],
            })
        return out

    def _reports(self, lid: str) -> list[dict]:
        now = datetime.now()
        period = {"begin": (now - timedelta(days=1)).strftime(FMT), "end": (now + timedelta(days=30)).strftime(FMT)}
        return [{"messages": [{"text": f"<p>{message}</p>"}], "application_periods": [period],
                 "impacted_objects": [{"pt_object": {"embedded_type": "line", "id": lid, "name": name}}]}
                for name, message in self.disrupted.items() if line_id(name) == lid]

    def patches(self, stack: ExitStack) -> None:
        """Branche ce monde à la place des API et des capteurs de position."""
        stack.enter_context(mock.patch.object(intents, "HOME_ADDRESS", HOME))
        stack.enter_context(mock.patch.object(transport, "_get", self.prim))
        stack.enter_context(mock.patch.object(weather, "get_json", self.meteo))
        stack.enter_context(mock.patch.object(location, "phone_position", lambda: self.phone))
        stack.enter_context(mock.patch.object(location, "pc_position", lambda: self.pc))
        transport.resolve_place.cache_clear()  # lieux mémorisés : propres à chaque monde


# ---------- Les scénarios ----------

def at_tomorrow(hour: int) -> str:
    return (datetime.now() + timedelta(days=1)).replace(hour=hour, minute=0, second=0).strftime("%Y-%m-%dT%H:%M")


PHONE = "48.8443,2.3743"  # près de la gare de Lyon


@dataclass
class Scenario:
    title: str
    intent: str
    entities: dict
    text: str
    expect: tuple[str, ...]  # morceaux de phrase attendus dans la réponse
    world: World = field(default_factory=World)


SCENARIOS = [
    Scenario("Météo d'une ville", "GET_WEATHER", {"location": "Paris"}, "Quel temps à Paris ?",
             ("À Paris", "couvert")),
    Scenario("Ligne perturbée", "CHECK_TRANSPORT", {}, "Le RER A roule ?",
             ("Perturbation sur RER A : panne de signalisation",),
             World(disrupted={"RER A": "panne de signalisation"})),
    Scenario("Ligne normale", "CHECK_TRANSPORT", {}, "Et la ligne 14 ?",
             ("Aucune perturbation signalée sur ligne 14",)),
    Scenario("Partir maintenant, position du téléphone", "PLAN_TRAVEL", {"location": "Gare de Melun"},
             "Je veux aller à la gare de Melun", ("de ta position vers la station Melun (Melun)", "Métro 14"),
             World(phone=PHONE, pc="48.90,2.50")),
    Scenario("Téléphone muet : position du PC", "PLAN_TRAVEL", {"location": "Gare de Melun"},
             "Je veux aller à la gare de Melun", ("de ta position", "44 min"), World(pc=PHONE)),
    Scenario("Aucune position : domicile, et JARVIS le dit", "PLAN_TRAVEL", {"location": "Gare de Melun"},
             "Je veux aller à la gare de Melun depuis ma position",
             ("Je n'ai pas ta position, je pars de ton adresse.", "RER A", "66 min")),
    Scenario("Départ donné dans la demande", "PLAN_TRAVEL",
             {"location": "Gare de Melun", "origin": "Châtelet"}, "De Châtelet à la gare de Melun",
             ("de la station Châtelet (Paris)",), World(phone="1,1")),
    Scenario("Arriver demain à 9 h sous la pluie : départ du domicile, marge ajoutée", "PLAN_TRAVEL",
             {"location": "27 bis rue du Progrès, Montreuil", "datetime": at_tomorrow(9)}, "",
             ("Pars à 08:00 de 10 rue de la Simulation", "arrivée vers 08:42", "j'ai ajouté de la marge"),
             World(phone=PHONE, rain=True)),
    Scenario("Demain, mais « depuis ma position »", "PLAN_TRAVEL",
             {"location": "27 bis rue du Progrès, Montreuil", "datetime": at_tomorrow(9)},
             "Je dois être à Montreuil demain à 9 h, depuis ma position",
             ("de ta position", "RER A, Bus 215"), World(phone=PHONE)),
    Scenario("Ligne coupée : trajet de remplacement", "PLAN_TRAVEL",
             {"location": "27 bis rue du Progrès, Montreuil", "datetime": at_tomorrow(9)}, "",
             ("Bus 113, Bus 122", "perturbation sur RER A", "J'ai choisi un trajet qui l'évite"),
             World(disrupted={"RER A": "travaux"})),
    Scenario("Ligne coupée sans remplacement", "PLAN_TRAVEL", {"location": "Gare de Melun"}, "",
             ("perturbation sur Transilien R", "Pas d'alternative trouvée, prévois du retard"),
             World(disrupted={"Transilien R": "grève"})),
    Scenario("Pluie en partant maintenant", "PLAN_TRAVEL", {"location": "Gare de Melun"}, "",
             ("prends de quoi te couvrir",), World(rain=True)),
    Scenario("Lieu inconnu de l'API", "PLAN_TRAVEL", {"location": "HETIC"}, "Emmène-moi à HETIC",
             ("Lieu introuvable : HETIC", "La Bochetière", "Donne une adresse")),
    Scenario("Heure déjà passée", "PLAN_TRAVEL", {"location": "Gare de Melun", "datetime": "2020-01-01T09:00"},
             "", ("L'heure d'arrivée est déjà passée.",)),
    Scenario("Service en panne", "PLAN_TRAVEL", {"location": "Gare de Melun"}, "",
             ("Le service ne répond pas",), World(api_down=True)),
    Scenario("Intention inconnue", "DANCE", {}, "Danse !", ("Intention inconnue",)),
]


def run_scenario(s: Scenario) -> str:
    with ExitStack() as stack:
        s.world.patches(stack)
        return handle_intent(s.intent, s.entities, s.text)


def simulate() -> int:
    failures = 0
    for i, s in enumerate(SCENARIOS, 1):
        answer = run_scenario(s)
        missing = [e for e in s.expect if e not in answer]
        failures += bool(missing)
        print(f"{'OK ' if not missing else 'ÉCHEC'} {i:2}. {s.title}\n"
              f"      Toi    : {s.text or s.entities}\n      JARVIS : {answer}")
        if missing:
            print(f"      attendu, absent : {missing}")
        print()
    print(f"{len(SCENARIOS) - failures}/{len(SCENARIOS)} scénarios conformes.")
    return 1 if failures else 0


def live() -> int:
    """Les demandes des scénarios, sur les vraies API et la vraie position : réponses du jour, sans vérification."""
    requests = {(s.intent, repr(s.entities), s.text): s for s in SCENARIOS}.values()  # sans doublons
    for s in requests:
        print(f"Toi    : {s.text or s.entities}\nJARVIS : {handle_intent(s.intent, s.entities, s.text)}\n")
    return 0


if __name__ == "__main__":
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument("--live", action="store_true", help="vraies API et vraie position")
    sys.exit(live() if args.parse_args().live else simulate())

"""GET_WEATHER : météo d'un jour donné via Open-Meteo (sans clé API)."""
from datetime import date, timedelta

from .common import DeplacementsError, get_json
from .config import DEFAULT_CITY, RAIN_MARGIN, SNOW_MARGIN

MAX_FORECAST_DAYS = 16  # limite d'Open-Meteo (aujourd'hui inclus)

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
METEO_URL = "https://api.open-meteo.com/v1/forecast"
DAILY = ("weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
         "snowfall_sum,precipitation_probability_max,wind_speed_10m_max")

WMO = {
    0: "ciel dégagé", 1: "plutôt dégagé", 2: "partiellement nuageux", 3: "couvert",
    45: "brouillard", 48: "brouillard givrant",
    51: "bruine légère", 53: "bruine", 55: "bruine forte",
    61: "pluie légère", 63: "pluie", 65: "pluie forte",
    71: "neige légère", 73: "neige", 75: "neige forte",
    80: "averses légères", 81: "averses", 82: "averses violentes",
    95: "orage", 96: "orage avec grêle", 99: "orage violent avec grêle",
}


def _geocode(city: str) -> dict:
    results = get_json(GEO_URL, {"name": city, "count": 1, "language": "fr"}).get("results")
    if not results:
        raise DeplacementsError(f"Ville introuvable : {city}")
    return results[0]


def get_weather(city: str | None = None, day: date | None = None,
                coords: tuple | None = None) -> dict:
    """Météo de `city` pour le jour `day` (aujourd'hui par défaut).

    `coords` = (lat, lon) si on les connaît déjà : on ne cherche alors pas la ville.
    """
    day = day or date.today()
    if day > date.today() + timedelta(days=MAX_FORECAST_DAYS - 1):
        raise DeplacementsError(f"Pas de prévision météo au-delà de {MAX_FORECAST_DAYS} jours.")
    place = ({"name": city, "latitude": coords[0], "longitude": coords[1]} if coords
             else _geocode(city or DEFAULT_CITY))
    daily = get_json(METEO_URL, {
        "latitude": place["latitude"], "longitude": place["longitude"],
        "daily": DAILY, "start_date": day.isoformat(), "end_date": day.isoformat(),
        "timezone": "auto",
    }).get("daily")
    if not daily:
        raise DeplacementsError(f"Pas de prévision pour le {day:%d/%m/%Y}.")

    def value(key, default=0):  # l'API renvoie des listes d'un élément, parfois null
        v = (daily.get(key) or [None])[0]
        return default if v is None else v

    return {
        "city": place["name"], "day": day,
        "description": WMO.get(value("weather_code", None), "conditions inconnues"),
        "t_min": value("temperature_2m_min"), "t_max": value("temperature_2m_max"),
        "rain_mm": value("precipitation_sum"), "snow_cm": value("snowfall_sum"),
        "rain_prob": value("precipitation_probability_max"),
        "wind_kmh": value("wind_speed_10m_max"),
    }


def extra_margin(w: dict) -> int:
    """Règle d'impact sur le trajet : minutes de marge à ajouter selon la météo."""
    if w["snow_cm"] > 0:
        return SNOW_MARGIN
    if w["rain_mm"] >= 1 or w["rain_prob"] >= 60:
        return RAIN_MARGIN
    return 0


def format_weather(w: dict) -> str:
    txt = (f"À {w['city']} le {w['day']:%d/%m} : {w['description']}, "
           f"{w['t_min']:.0f} à {w['t_max']:.0f}°C, vent jusqu'à {w['wind_kmh']:.0f} km/h.")
    if extra_margin(w):
        txt += " Pluie ou neige prévue : prends un parapluie et prévois plus de temps."
    return txt

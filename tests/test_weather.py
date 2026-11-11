from datetime import date

import pytest

from deplacements import weather
from deplacements.common import DeplacementsError


def fake_json(url, params=None, headers=None):
    if url == weather.GEO_URL:
        return {"results": [{"name": "Paris", "latitude": 48.8, "longitude": 2.3}]}
    return {"daily": {"weather_code": [63], "temperature_2m_max": [9.0],
                      "temperature_2m_min": [4.0], "precipitation_sum": [5.2],
                      "snowfall_sum": [0], "precipitation_probability_max": [80],
                      "wind_speed_10m_max": [20]}}


def test_get_weather_normal(monkeypatch):
    monkeypatch.setattr(weather, "get_json", fake_json)
    w = weather.get_weather("Paris", date.today())
    assert w["description"] == "pluie"
    assert weather.extra_margin(w) == 5
    assert "parapluie" in weather.format_weather(w)


def test_unknown_city(monkeypatch):
    monkeypatch.setattr(weather, "get_json", lambda *a, **k: {})
    with pytest.raises(DeplacementsError, match="introuvable"):
        weather.get_weather("Nullepart")


@pytest.mark.parametrize("snow, rain, prob, expected", [
    (2, 0, 0, 10), (0, 3, 0, 5), (0, 0, 70, 5), (0, 0, 10, 0),
])
def test_extra_margin(snow, rain, prob, expected):
    assert weather.extra_margin({"snow_cm": snow, "rain_mm": rain, "rain_prob": prob}) == expected

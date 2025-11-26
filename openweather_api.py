# openweather_api.py

import os
import requests
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()  # loads .env if present

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")


def get_coordinates_for_city(city_name, country_code="IN"):
    """
    Use OpenWeather Geocoding API to convert 'city, country' → lat, lon.
    """
    if OPENWEATHER_API_KEY is None:
        raise RuntimeError("OPENWEATHER_API_KEY not set in environment")

    url = "http://api.openweathermap.org/geo/1.0/direct"
    params = {
        "q": f"{city_name},{country_code}",
        "limit": 1,
        "appid": OPENWEATHER_API_KEY,
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise ValueError(f"City not found: {city_name}")
    return data[0]["lat"], data[0]["lon"]


def get_hourly_forecast(lat, lon, hours=24):
    """
    Get hourly forecast for 'hours' ahead (<= 48) using OpenWeather One Call API.
    Returns a list of dicts: {time, temp, clouds, ...}
    """
    if OPENWEATHER_API_KEY is None:
        raise RuntimeError("OPENWEATHER_API_KEY not set in environment")

    url = "https://api.openweathermap.org/data/3.0/onecall"
    params = {
        "lat": lat,
        "lon": lon,
        "exclude": "current,minutely,daily,alerts",
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()

    hourly = data.get("hourly", [])
    result = []
    for i, h in enumerate(hourly[:hours]):
        ts = datetime.fromtimestamp(h["dt"], tz=timezone.utc)
        result.append({
            "time": ts,
            "temp": h.get("temp"),
            "clouds": h.get("clouds", 0) / 100.0,  # convert to 0–1
            "uvi": h.get("uvi", 0),
        })
    return result


def estimate_solar_from_weather(hourly_weather, solar_capacity_kw):
    """
    Very simple solar estimation: base curve * (1 - clouds) * capacity.
    Returns list of kWh per hour.
    """
    solar_kwh = []

    # base clear-sky curve by hour (0..23)
    base_curve = {
        6: 0.1,
        7: 0.3,
        8: 0.5,
        9: 0.7,
        10: 0.9,
        11: 1.0,
        12: 1.0,
        13: 0.95,
        14: 0.9,
        15: 0.7,
        16: 0.5,
        17: 0.3,
        18: 0.1,
    }

    for w in hourly_weather:
        hour = w["time"].hour
        clear_factor = base_curve.get(hour, 0.0)
        cloud_factor = 1.0 - float(w.get("clouds", 0.0))  # 0..1
        if cloud_factor < 0:
            cloud_factor = 0.0
        solar_kw = solar_capacity_kw * clear_factor * cloud_factor
        # approximate kWh in that hour = kW
        solar_kwh.append(max(solar_kw, 0.0))

    return solar_kwh

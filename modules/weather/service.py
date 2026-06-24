import os
import httpx
from typing import Dict, Any

WEATHER_LAT = float(os.getenv("WEATHER_LAT", "41.0082"))
WEATHER_LON = float(os.getenv("WEATHER_LON", "28.9784"))
WEATHER_CITY = os.getenv("WEATHER_CITY", "İstanbul")

# WMO Hava Durumu Yorumu Kodları → Türkçe
WMO_DESCRIPTIONS = {
    0: "Açık",
    1: "Çoğunlukla açık", 2: "Parçalı bulutlu", 3: "Bulutlu",
    45: "Sisli", 48: "Kırağılı sis",
    51: "Hafif çisenti", 53: "Orta çisenti", 55: "Yoğun çisenti",
    61: "Hafif yağmur", 63: "Orta yağmur", 65: "Şiddetli yağmur",
    71: "Hafif kar", 73: "Orta kar", 75: "Yoğun kar", 77: "Kar taneleri",
    80: "Hafif sağanak", 81: "Orta sağanak", 82: "Şiddetli sağanak",
    85: "Hafif kar sağanağı", 86: "Yoğun kar sağanağı",
    95: "Gökgürültülü fırtına", 96: "Dolulu fırtına", 99: "Yoğun dolulu fırtına",
}


def get_weather_emoji(code: int) -> str:
    if code == 0:
        return "☀️"
    if code in (1, 2):
        return "🌤"
    if code == 3:
        return "☁️"
    if code in (45, 48):
        return "🌫"
    if 51 <= code <= 67:
        return "🌧"
    if 71 <= code <= 77:
        return "❄️"
    if 80 <= code <= 82:
        return "🌦"
    if code >= 95:
        return "⛈"
    return "🌡"


async def get_weather() -> Dict[str, Any]:
    """Open-Meteo API'den güncel hava durumunu çeker (kayıt gerekmez)"""
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={WEATHER_LAT}&longitude={WEATHER_LON}"
        f"&current=temperature_2m,apparent_temperature,weathercode,windspeed_10m,relative_humidity_2m"
        f"&daily=temperature_2m_max,temperature_2m_min,weathercode"
        f"&timezone=Europe%2FIstanbul"
        f"&forecast_days=1"
    )

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    current = data["current"]
    daily = data["daily"]
    code = current["weathercode"]

    return {
        "city": WEATHER_CITY,
        "temperature": round(current["temperature_2m"]),
        "feels_like": round(current["apparent_temperature"]),
        "description": WMO_DESCRIPTIONS.get(code, "Bilinmiyor"),
        "humidity": current["relative_humidity_2m"],
        "wind_speed": round(current["windspeed_10m"]),
        "temp_max": round(daily["temperature_2m_max"][0]),
        "temp_min": round(daily["temperature_2m_min"][0]),
        "weather_code": code,
    }


def format_weather_message(weather: Dict[str, Any]) -> str:
    emoji = get_weather_emoji(weather["weather_code"])
    return (
        f"{emoji} {weather['city']}: {weather['temperature']}°C, {weather['description']}\n"
        f"🌡 Hissedilen: {weather['feels_like']}°C | Max: {weather['temp_max']}°C / Min: {weather['temp_min']}°C\n"
        f"💨 Rüzgar: {weather['wind_speed']} km/s | 💧 Nem: {weather['humidity']}%"
    )

import math
import os
import httpx
from typing import Dict, Any, Optional

from logging_setup import get_logger

log = get_logger("prism.weather")

WEATHER_LAT = float(os.getenv("WEATHER_LAT", "38.6748"))
WEATHER_LON = float(os.getenv("WEATHER_LON", "39.2225"))
WEATHER_CITY = os.getenv("WEATHER_CITY", "Elazığ")

# Konum bu mesafeden az değiştiyse şehir adı yeniden sorulmaz — aynı şehirde
# dolaşırken her girişte dışarıya istek atmanın anlamı yok.
AYNI_YER_KM = 15.0


def _mesafe_km(lat1, lon1, lat2, lon2) -> float:
    """İki nokta arası kabaca kaç km (haversine)."""
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


async def sehir_adi(enlem: float, boylam: float) -> Optional[str]:
    """Koordinattan şehir adı (OpenStreetMap Nominatim — anahtar gerektirmez).

    **Başarısızlığı sorun değil.** Hava durumu koordinatla çalışıyor; buradan
    dönen ad sadece ekranda "Elazığ 22°C" yazabilmek için. Servis yanıt vermezse
    None döner, çağıran taraf eski adı ya da varsayılanı kullanır — hava durumu
    hiçbir koşulda buna bağlı kalmaz.

    Nominatim kullanım koşulu gereği açıklayıcı bir User-Agent gönderiliyor ve
    çağrı yalnızca kullanıcı gerçekten yer değiştirdiğinde yapılıyor (AYNI_YER_KM).
    """
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": enlem, "lon": boylam, "format": "json",
                        "accept-language": "tr", "zoom": 10},
                headers={"User-Agent": "PRISM-Hub/1.0 (kisisel asistan)"},
            )
            resp.raise_for_status()
            adres = resp.json().get("address", {})
    except Exception as e:
        log.warning("Şehir adı çözülemedi (%s) — koordinat yeterli", type(e).__name__)
        return None

    for anahtar in ("province", "city", "town", "state", "county", "village"):
        if adres.get(anahtar):
            return adres[anahtar]
    return None

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


def kullanici_konumu(user: Dict[str, Any] = None) -> tuple:
    """(enlem, boylam, şehir) — kullanıcının kendi konumu, yoksa env'deki varsayılan.

    Konum kişiye bağlı: panele girerken tarayıcıdan alınıp `users` tablosuna
    yazılıyor. Hiç verilmemişse (izin verilmedi, Telegram'dan geliyor, eski
    kayıt) env'deki WEATHER_* değerleri kullanılır — yani konum olmadan da
    her şey eskisi gibi çalışır.
    """
    if user and user.get("enlem") is not None and user.get("boylam") is not None:
        return user["enlem"], user["boylam"], user.get("sehir") or "Konumun"
    return WEATHER_LAT, WEATHER_LON, WEATHER_CITY


async def get_weather(user: Dict[str, Any] = None) -> Dict[str, Any]:
    """Open-Meteo API'den güncel hava durumunu çeker (kayıt gerekmez)"""
    enlem, boylam, sehir = kullanici_konumu(user)
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={enlem}&longitude={boylam}"
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
        "city": sehir,
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

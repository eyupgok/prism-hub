"""Kişi başına hava durumu konumu.

Ağa çıkan kısımlar (Open-Meteo, Nominatim) burada sınanmıyor — sınanan şey
"hangi koordinat kullanılacak" kararı ve konum yokken varsayılana düşme.
"""

import pytest

from conftest import SAHIP, OTEKI
from modules.weather import service as hava


def test_konumu_olmayan_kullanici_varsayilana_duser(db):
    enlem, boylam, sehir = hava.kullanici_konumu({"id": 1, "enlem": None, "boylam": None})
    assert (enlem, boylam, sehir) == (hava.WEATHER_LAT, hava.WEATHER_LON, hava.WEATHER_CITY)


def test_kullanici_hic_verilmezse_varsayilan(db):
    """Telegram'dan gelen ya da kullanıcısı çözülemeyen çağrılar da çalışmalı."""
    assert hava.kullanici_konumu(None)[2] == hava.WEATHER_CITY
    assert hava.kullanici_konumu()[2] == hava.WEATHER_CITY


def test_konumu_olan_kullanici_kendi_yerini_alir(db):
    enlem, boylam, sehir = hava.kullanici_konumu(
        {"id": 2, "enlem": 41.0082, "boylam": 28.9784, "sehir": "İstanbul"}
    )
    assert (round(enlem, 4), round(boylam, 4), sehir) == (41.0082, 28.9784, "İstanbul")


def test_sehir_adi_cozulememisse_koordinat_yine_kullanilir(db):
    """Nominatim yanıt vermezse ad boş kalır ama hava durumu çalışmaya devam eder."""
    enlem, boylam, sehir = hava.kullanici_konumu(
        {"id": 2, "enlem": 41.0, "boylam": 29.0, "sehir": None}
    )
    assert (enlem, boylam) == (41.0, 29.0)
    assert sehir            # boş bırakılmıyor, anlamlı bir yedek konuyor


@pytest.mark.parametrize("a,b,beklenen_km", [
    ((38.6748, 39.2225), (38.6748, 39.2225), 0),        # aynı nokta
    ((41.0082, 28.9784), (41.0422, 29.0094), 5),        # İstanbul içi ~5 km
    ((38.6748, 39.2225), (41.0082, 28.9784), 900),      # Elazığ → İstanbul
])
def test_mesafe_hesabi(a, b, beklenen_km):
    olculen = hava._mesafe_km(a[0], a[1], b[0], b[1])
    assert abs(olculen - beklenen_km) < max(2, beklenen_km * 0.1)


def test_ayni_yer_esigi_makul():
    """Eşik şehir içi dolaşmayı 'taşındı' saymamalı, şehir değişimini saymalı."""
    istanbul_ici = hava._mesafe_km(41.0082, 28.9784, 41.0422, 29.0094)
    sehirler_arasi = hava._mesafe_km(38.6748, 39.2225, 41.0082, 28.9784)
    assert istanbul_ici < hava.AYNI_YER_KM < sehirler_arasi


def test_konum_sutunlari_users_tablosunda(db):
    sutunlar = {r["name"] for r in db.execute("PRAGMA table_info(users)")}
    assert {"sehir", "enlem", "boylam", "konum_at"} <= sutunlar


def test_konum_kisiye_ozel(db):
    """Birinin konumu diğerininkini değiştirmemeli."""
    db.execute("UPDATE users SET enlem = 41.0, boylam = 29.0, sehir = 'İstanbul' WHERE id = ?", (OTEKI,))
    sahip = dict(db.execute("SELECT * FROM users WHERE id = ?", (SAHIP,)).fetchone())
    oteki = dict(db.execute("SELECT * FROM users WHERE id = ?", (OTEKI,)).fetchone())
    assert hava.kullanici_konumu(sahip)[2] == hava.WEATHER_CITY      # dokunulmadı
    assert hava.kullanici_konumu(oteki)[2] == "İstanbul"

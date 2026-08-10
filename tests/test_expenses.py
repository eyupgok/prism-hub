"""Harcama servisi: tutar doğrulaması, iadeler, çift kayıt tespiti."""

import pytest

from modules.expenses import service as svc


# ── Tutar doğrulaması ────────────────────────────────────────────────────────

def test_pozitif_tutar_kabul():
    assert svc.validate_amount(185.5) == 185.5


def test_negatif_tutar_iade_olarak_kabul():
    """Negatif tutar hata değil — iade demek."""
    assert svc.validate_amount(-273.9) == -273.9
    assert svc.is_refund(-273.9) is True
    assert svc.is_refund(10) is False


def test_kurusa_yuvarlanir():
    assert svc.validate_amount(10.999) == 11.0


@pytest.mark.parametrize("bad", [0, 5_000_000, -5_000_000, "abc", None, float("inf")])
def test_gecersiz_tutarlar_reddedilir(bad):
    with pytest.raises(svc.InvalidAmount):
        svc.validate_amount(bad)


# ── İadeler ──────────────────────────────────────────────────────────────────

def test_iade_aylik_toplamdan_dusulur(db):
    svc.create_expense(db, 273.90, "alışveriş", "BIM", "2026-08-09")
    svc.create_expense(db, 100.00, "alışveriş", "A101", "2026-08-09")
    svc.create_expense(db, -273.90, "alışveriş", "BIM iade", "2026-08-10")

    summary = svc.get_monthly_summary(db, "2026-08")
    assert round(summary["total"], 2) == 100.0
    assert round(summary["by_category"]["alışveriş"], 2) == 100.0


def test_iade_sonrasi_butce_uyarisi_dogru(db):
    svc.set_budget(db, "alışveriş", 200.0)
    svc.create_expense(db, 190.0, "alışveriş", "Alışveriş", "2026-08-09")
    assert svc.check_budget_alert(db, "alışveriş", "2026-08") is not None

    svc.create_expense(db, -150.0, "alışveriş", "İade", "2026-08-10")
    assert svc.check_budget_alert(db, "alışveriş", "2026-08") is None


# ── Çift kayıt tespiti ───────────────────────────────────────────────────────

def _bildirim(db, amount, at, hash_):
    return svc.create_expense(
        db, amount, "alışveriş", "MIGROS", at[:10],
        source="notification", source_hash=hash_, source_at=at,
    )


def test_kisa_arayla_ayni_tutar_cift_sayilir(db):
    first = _bildirim(db, 185.50, "2026-08-09T14:23:11", "h1")
    twin = svc.find_duplicate(db, 185.50, "2026-08-09T14:25:02", 5)
    assert twin and twin["id"] == first["id"]


def test_uzun_arayla_ayni_tutar_ayri_sayilir(db):
    _bildirim(db, 185.50, "2026-08-09T14:23:11", "h1")
    assert svc.find_duplicate(db, 185.50, "2026-08-09T14:43:00", 5) is None


def test_gece_yarisini_asan_cift_yakalanir(db):
    _bildirim(db, 70.0, "2026-08-09T23:58:00", "h1")
    assert svc.find_duplicate(db, 70.0, "2026-08-10T00:01:00", 5) is not None


def test_elle_girilen_kayda_karisilmaz(db):
    svc.create_expense(db, 42.0, "yemek", "Elle girilen", "2026-08-09")  # source=manual
    assert svc.find_duplicate(db, 42.0, "2026-08-09T15:00:00", 5) is None


def test_iade_orijinal_harcamayla_cift_sanilmaz(db):
    _bildirim(db, 500.0, "2026-08-11T10:00:00", "h1")
    assert svc.find_duplicate(db, -500.0, "2026-08-11T10:02:00", 5) is None


def test_fis_gun_seviyesinde_cift_yakalar(db):
    """Fişte saat okunamadıysa aynı gün + aynı tutar yeterli."""
    _bildirim(db, 273.90, "2026-08-09T18:42:00", "h1")
    twin = svc.find_duplicate(db, 273.90, source_at=None, expense_date="2026-08-09", day_level=True)
    assert twin is not None


def test_gun_seviyesi_bildirim_yolunda_kapali(db):
    """Bildirim yolunda saat her zaman biliniyor; gün seviyesi fazla geniş olurdu."""
    _bildirim(db, 273.90, "2026-08-09T18:42:00", "h1")
    assert svc.find_duplicate(db, 273.90, "2026-08-09T23:50:00", 5) is None


def test_ayni_bildirim_ikinci_kez_kaydedilemez(db):
    _bildirim(db, 99.0, "2026-08-09T12:00:00", "ayni-hash")
    with pytest.raises(Exception):
        _bildirim(db, 99.0, "2026-08-09T12:00:00", "ayni-hash")

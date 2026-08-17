"""İki kullanıcılı yapının kuralı: okuma serbest, yazma yalnız kendi kaydına.

Bu dosya o kuralın kendisini sınar — modüllerin iş mantığını değil.
"""

import pytest

from conftest import SAHIP, OTEKI
from modules.notes import service as not_svc
from modules.reminders import service as rem_svc
from modules.expenses import service as exp_svc


def _not(db, sahip, baslik="Not"):
    return not_svc.create_note(db, sahip, baslik, "içerik")


def _hatirlatici(db, sahip, baslik="Görev"):
    return rem_svc.create_reminder(db, sahip, baslik, rem_svc.now_local().isoformat())


# ── Okuma: serbest ───────────────────────────────────────────────────────────

def test_baskasinin_kayitlari_okunabiliyor(db):
    _not(db, OTEKI, "Ötekinin notu")
    assert [n["title"] for n in not_svc.list_notes(db, OTEKI)] == ["Ötekinin notu"]


def test_listeler_birbirine_karismiyor(db):
    _not(db, SAHIP, "Benim")
    _not(db, OTEKI, "Onun")
    assert [n["title"] for n in not_svc.list_notes(db, SAHIP)] == ["Benim"]
    assert [n["title"] for n in not_svc.list_notes(db, OTEKI)] == ["Onun"]


def test_arama_da_sahibe_kilitli(db):
    _not(db, OTEKI, "gizli plan")
    assert not_svc.search_notes(db, SAHIP, "gizli") == []
    assert len(not_svc.search_notes(db, OTEKI, "gizli")) == 1


# ── Yazma: yalnız kendi kaydına ──────────────────────────────────────────────

def test_baskasinin_notu_degistirilemiyor(db):
    n = _not(db, OTEKI, "Dokunma")
    assert not_svc.update_note(db, SAHIP, n["id"], title="Değiştim") is None
    assert not_svc.get_note_by_id(db, n["id"])["title"] == "Dokunma"


def test_baskasinin_notu_silinemiyor(db):
    n = _not(db, OTEKI)
    assert not_svc.delete_note(db, SAHIP, n["id"]) is False
    assert not_svc.get_note_by_id(db, n["id"]) is not None


def test_baskasinin_hatirlaticisi_tamamlanamiyor(db):
    r = _hatirlatici(db, OTEKI)
    assert rem_svc.complete_reminder(db, SAHIP, r["id"]) is None
    assert rem_svc.get_reminder_by_id(db, r["id"])["is_completed"] == 0


def test_baskasinin_hatirlaticisi_ertelenemiyor(db):
    r = _hatirlatici(db, OTEKI)
    onceki = rem_svc.get_reminder_by_id(db, r["id"])["due_datetime"]
    assert rem_svc.snooze_reminder(db, SAHIP, r["id"], 60) is None
    assert rem_svc.get_reminder_by_id(db, r["id"])["due_datetime"] == onceki


def test_baskasinin_harcamasi_silinemiyor(db):
    e = exp_svc.create_expense(db, OTEKI, 100.0, "yemek", "Onun")
    assert exp_svc.delete_expense(db, SAHIP, e["id"]) is False
    assert exp_svc.get_expense_by_id(db, e["id"]) is not None


def test_kendi_kaydina_yazabiliyor(db):
    """Kilit fazla sıkı olmasın — kendi kaydında her şey normal çalışmalı."""
    n = _not(db, SAHIP, "Benimki")
    assert not_svc.update_note(db, SAHIP, n["id"], title="Yeni")["title"] == "Yeni"
    assert not_svc.delete_note(db, SAHIP, n["id"]) is True


# ── Bütçe: aynı kategori ikisinde de olabilmeli ──────────────────────────────

def test_ayni_kategoriye_iki_ayri_butce(db):
    exp_svc.set_budget(db, SAHIP, "yemek", 3000.0)
    exp_svc.set_budget(db, OTEKI, "yemek", 1500.0)
    assert exp_svc.get_budget_by_category(db, SAHIP, "yemek")["monthly_limit"] == 3000.0
    assert exp_svc.get_budget_by_category(db, OTEKI, "yemek")["monthly_limit"] == 1500.0


def test_ayni_kisi_ayni_kategoriyi_gunceller_ikinci_kayit_acmaz(db):
    exp_svc.set_budget(db, SAHIP, "yemek", 3000.0)
    exp_svc.set_budget(db, SAHIP, "yemek", 4000.0)
    assert len(exp_svc.get_all_budgets(db, SAHIP)) == 1
    assert exp_svc.get_budget_by_category(db, SAHIP, "yemek")["monthly_limit"] == 4000.0


def test_butce_uyarisi_baskasinin_harcamasini_saymaz(db):
    exp_svc.set_budget(db, SAHIP, "yemek", 100.0)
    exp_svc.create_expense(db, OTEKI, 500.0, "yemek", "Onun ziyafeti")
    ay = exp_svc.datetime.now(exp_svc.TZ).strftime("%Y-%m")
    assert exp_svc.check_budget_alert(db, SAHIP, "yemek", ay) is None


# ── Çift kayıt: kişiler arası eşleşmemeli ────────────────────────────────────

def test_cift_kayit_kontrolu_kisiler_arasi_calismiyor(db):
    """Birlikte alışverişte ikinizin aynı tutarlı kaydı birbirini elememeli.

    Sahip süzgeci olmasaydı aynı gün aynı tutarı harcadığınızda ikinizden
    birinin kaydı 'çift' sanılıp sessizce yutulurdu.
    """
    exp_svc.create_expense(
        db, SAHIP, 185.50, "alışveriş", "MIGROS", "2026-08-09",
        source="notification", source_hash="h1", source_at="2026-08-09T14:23:11",
    )
    # Aynı dakikada, aynı tutarda, ama ÖTEKİNİN kaydı aranıyor
    assert exp_svc.find_duplicate(db, OTEKI, 185.50, "2026-08-09T14:25:02", 5) is None
    # Kendi kaydında ise çift yakalanmaya devam ediyor
    assert exp_svc.find_duplicate(db, SAHIP, 185.50, "2026-08-09T14:25:02", 5) is not None


def test_ayni_bildirim_ozeti_iki_kiside_ayri_ayri_kaydedilebiliyor(db):
    """source_hash tekilliği artık kişi başına — indeks (owner_id, source_hash)."""
    ortak = {
        "category": "yemek", "description": "Aynı metin", "expense_date": "2026-08-09",
        "source": "notification", "source_hash": "ayni-ozet",
        "source_at": "2026-08-09T12:00:00",
    }
    exp_svc.create_expense(db, SAHIP, 50.0, **ortak)
    exp_svc.create_expense(db, OTEKI, 50.0, **ortak)      # patlamamalı
    assert exp_svc.get_expense_by_source_hash(db, SAHIP, "ayni-ozet") is not None
    assert exp_svc.get_expense_by_source_hash(db, OTEKI, "ayni-ozet") is not None


# ── Zamanlayıcı herkesi görmeli ──────────────────────────────────────────────

def test_bildirim_dongusu_herkesin_hatirlaticisini_goruyor(db):
    _hatirlatici(db, SAHIP, "Benim görevim")
    _hatirlatici(db, OTEKI, "Onun görevi")
    hepsi = rem_svc.tum_hatirlaticilar(db)
    assert {r["title"] for r in hepsi} == {"Benim görevim", "Onun görevi"}
    # ...ama kullanıcıya açılan liste hâlâ kilitli
    assert len(rem_svc.list_reminders(db, SAHIP)) == 1

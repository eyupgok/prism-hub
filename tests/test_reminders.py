"""Hatırlatıcı servisi: gecikmiş tekrarlayanlar, erteleme, doğrulama."""

from datetime import timedelta

from modules.reminders import service as svc


def _in(minutes: int) -> str:
    return (svc.now_local() + timedelta(minutes=minutes)).isoformat()


# ── Gecikmiş tekrarlayanlar ──────────────────────────────────────────────────

def test_cok_gecikmis_tekrarlayan_bildirim_listesinde_olmaz(db):
    r = svc.create_reminder(db, "Her gün spor", _in(-300), 1, "daily")
    assert not any(x["id"] == r["id"] for x in svc.get_reminders_to_notify(db))


def test_cok_gecikmis_tekrarlayan_supurmeyle_otelenir(db):
    """Sunucu 1 saatten uzun kapalı kalırsa tekrarlayan hatırlatıcı sonsuza kadar
    geçmişte takılı kalıyordu — süpürme bunu düzeltir."""
    r = svc.create_reminder(db, "Her gün spor", _in(-300), 1, "daily")

    assert svc.reschedule_overdue_recurring(db) == 1

    after = svc.get_reminder_by_id(db, r["id"])
    assert svc.parse_dt(after["due_datetime"]) > svc.now_local()


def test_bildirim_penceresindekine_dokunulmaz(db):
    """Daha bildirilmemiş bir hatırlatıcı ötelenirse kullanıcı onu hiç görmez."""
    r = svc.create_reminder(db, "Az önce geçti", _in(-10), 1, "daily")
    before = svc.get_reminder_by_id(db, r["id"])["due_datetime"]

    svc.reschedule_overdue_recurring(db)

    assert svc.get_reminder_by_id(db, r["id"])["due_datetime"] == before
    assert any(x["id"] == r["id"] for x in svc.get_reminders_to_notify(db))


def test_tekrarlamayan_gecikmise_dokunulmaz(db):
    r = svc.create_reminder(db, "Tek seferlik", _in(-300), 2, "none")
    before = svc.get_reminder_by_id(db, r["id"])["due_datetime"]

    svc.reschedule_overdue_recurring(db)

    assert svc.get_reminder_by_id(db, r["id"])["due_datetime"] == before


# ── Doğrulama ────────────────────────────────────────────────────────────────

def test_oncelik_araliga_sikistirilir(db):
    r = svc.create_reminder(db, "Test", _in(60), 99, "none")
    assert r["priority"] == 3
    assert svc.normalize_priority(0) == 1
    assert svc.normalize_priority("abc") == 3


def test_gecersiz_tekrar_none_olur(db):
    r = svc.create_reminder(db, "Test", _in(60), 2, "saçmalık")
    assert r["recurrence"] == "none"


def test_negatif_erteleme_gecmise_tasimaz(db):
    """Negatif erteleme hatırlatıcıyı bildirim penceresinden düşürüp öldürüyordu."""
    r = svc.create_reminder(db, "Test", _in(5), 2, "none")
    snoozed = svc.snooze_reminder(db, r["id"], -500)
    assert svc.parse_dt(snoozed["due_datetime"]) > svc.now_local()


def test_asiri_erteleme_bir_haftayla_sinirli(db):
    r = svc.create_reminder(db, "Test", _in(5), 2, "none")
    snoozed = svc.snooze_reminder(db, r["id"], 999_999)
    days = (svc.parse_dt(snoozed["due_datetime"]) - svc.now_local()).total_seconds() / 86400
    assert days <= 7.01


# ── Tekrarlama mantığı ───────────────────────────────────────────────────────

def test_tamamlanan_tekrarlayan_olmez(db):
    r = svc.create_reminder(db, "Her gün", _in(5), 2, "daily")
    done = svc.complete_reminder(db, r["id"])
    assert done["rescheduled"] is True
    assert done["is_completed"] == 0
    assert svc.parse_dt(done["due_datetime"]) > svc.now_local()


def test_tamamlanan_tek_seferlik_kapanir(db):
    r = svc.create_reminder(db, "Tek seferlik", _in(5), 2, "none")
    done = svc.complete_reminder(db, r["id"])
    assert done["is_completed"] == 1

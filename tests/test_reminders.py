"""Hatırlatıcı servisi: gecikmiş tekrarlayanlar, erteleme, doğrulama."""

from datetime import timedelta

from modules.reminders import service as svc
from conftest import SAHIP, OTEKI


def _in(minutes: int) -> str:
    return (svc.now_local() + timedelta(minutes=minutes)).isoformat()


# ── Gecikmiş tekrarlayanlar ──────────────────────────────────────────────────

def test_cok_gecikmis_tekrarlayan_bildirim_listesinde_olmaz(db):
    r = svc.create_reminder(db, SAHIP, "Her gün spor", _in(-300), 1, "daily")
    assert not any(x["id"] == r["id"] for x in svc.get_reminders_to_notify(db))


def test_cok_gecikmis_tekrarlayan_supurmeyle_otelenir(db):
    """Sunucu 1 saatten uzun kapalı kalırsa tekrarlayan hatırlatıcı sonsuza kadar
    geçmişte takılı kalıyordu — süpürme bunu düzeltir."""
    r = svc.create_reminder(db, SAHIP, "Her gün spor", _in(-300), 1, "daily")

    assert svc.reschedule_overdue_recurring(db) == 1

    after = svc.get_reminder_by_id(db, r["id"])
    assert svc.parse_dt(after["due_datetime"]) > svc.now_local()


def test_bildirim_penceresindekine_dokunulmaz(db):
    """Daha bildirilmemiş bir hatırlatıcı ötelenirse kullanıcı onu hiç görmez."""
    r = svc.create_reminder(db, SAHIP, "Az önce geçti", _in(-10), 1, "daily")
    before = svc.get_reminder_by_id(db, r["id"])["due_datetime"]

    svc.reschedule_overdue_recurring(db)

    assert svc.get_reminder_by_id(db, r["id"])["due_datetime"] == before
    assert any(x["id"] == r["id"] for x in svc.get_reminders_to_notify(db))


def test_tekrarlamayan_gecikmise_dokunulmaz(db):
    r = svc.create_reminder(db, SAHIP, "Tek seferlik", _in(-300), 2, "none")
    before = svc.get_reminder_by_id(db, r["id"])["due_datetime"]

    svc.reschedule_overdue_recurring(db)

    assert svc.get_reminder_by_id(db, r["id"])["due_datetime"] == before


# ── Doğrulama ────────────────────────────────────────────────────────────────

def test_oncelik_araliga_sikistirilir(db):
    r = svc.create_reminder(db, SAHIP, "Test", _in(60), 99, "none")
    assert r["priority"] == 4
    assert svc.normalize_priority(0) == 1
    assert svc.normalize_priority("abc") == svc.DEFAULT_PRIORITY


def test_oncelik_belirtilmezse_sessiz(db):
    """Varsayılan gürültülü olursa her kayıt bildirim yağmuruna dönüyordu."""
    r = svc.create_reminder(db, SAHIP, "Test", _in(60))
    assert r["priority"] == 4
    assert svc.NOTIFICATION_POINTS[4] == [0]   # yalnız vadesinde


def test_gecersiz_tekrar_none_olur(db):
    r = svc.create_reminder(db, SAHIP, "Test", _in(60), 2, "saçmalık")
    assert r["recurrence"] == "none"


def test_negatif_erteleme_gecmise_tasimaz(db):
    """Negatif erteleme hatırlatıcıyı bildirim penceresinden düşürüp öldürüyordu."""
    r = svc.create_reminder(db, SAHIP, "Test", _in(5), 2, "none")
    snoozed = svc.snooze_reminder(db, SAHIP, r["id"], -500)
    assert svc.parse_dt(snoozed["due_datetime"]) > svc.now_local()


def test_asiri_erteleme_bir_haftayla_sinirli(db):
    r = svc.create_reminder(db, SAHIP, "Test", _in(5), 2, "none")
    snoozed = svc.snooze_reminder(db, SAHIP, r["id"], 999_999)
    days = (svc.parse_dt(snoozed["due_datetime"]) - svc.now_local()).total_seconds() / 86400
    assert days <= 7.01


# ── Bildirim planı ───────────────────────────────────────────────────────────
# Asıl mesele sayı. Eski "kalan süreye göre her N dakikada bir tekrarla" modelinde
# tekrarın sonu yoktu; bir hafta önceden kurulan tek bir kritik hatırlatıcı 34
# bildirim üretiyordu. Sabit noktalarda üst sınır listenin uzunluğu kadar —
# aşağıdaki testler o sınırı kilitliyor.

def _bildirim_anlari(priority: int, lead_minutes: int):
    """Vadesine `lead_minutes` kala kurulan hatırlatıcıyı dakika dakika yürütür.

    Dönen liste: bildirimlerin gittiği anlar, "vadeye kalan dakika" cinsinden
    (eksi değer vadeden sonrasını gösterir).
    """
    t0 = svc.now_local()
    due = t0 + timedelta(minutes=lead_minutes)
    r = {
        "due_datetime": due.isoformat(),
        "priority": priority,
        "last_notified_at": None,
        "created_at": t0.isoformat(),
    }

    anlar = []
    for adim in range(lead_minutes + svc.GIVE_UP_AFTER_MINUTES + 5):
        now = t0 + timedelta(minutes=adim)
        if svc.bildirim_gerekli(r, now):
            anlar.append(round((due - now).total_seconds() / 60))
            r["last_notified_at"] = now.isoformat()
    return anlar


def test_sessiz_yalniz_vadesinde_bir_kez_bildirir():
    assert _bildirim_anlari(4, 10080) == [0]


def test_hicbir_oncelik_planindan_fazla_bildirmez():
    for p in (1, 2, 3, 4):
        anlar = _bildirim_anlari(p, 10080)              # bir hafta önceden kuruldu
        assert anlar == svc.NOTIFICATION_POINTS[p]      # her nokta bir kez, sırayla


def test_kritik_yedi_bildirimle_sinirli():
    """Eskiden aynı senaryo 34 bildirim üretiyordu."""
    assert len(_bildirim_anlari(1, 10080)) == 7


def test_yeni_kayit_hemen_bildirim_yollamaz():
    """İki saat sonrasına kritik kurmak 'iki saat kaldı' bildirimi demek değil —
    kullanıcı kaydı bir saniye önce kendi yazdı."""
    assert _bildirim_anlari(1, 120) == [60, 15, 0, -15, -30]


def test_vadesi_gecmis_kurulan_yine_de_bildirilir(db):
    """'Saat 3'e kur' derken 3'ü on dakika geçmişse haber yine gelmeli.
    `created_at` susturması yalnız vadeden ÖNCEKİ noktalar için geçerli."""
    r = svc.create_reminder(db, SAHIP, "Geç kalmış", _in(-10), 4, "none")
    assert any(x["id"] == r["id"] for x in svc.get_reminders_to_notify(db))


def test_cok_gecmis_kayit_bildirim_listesinden_duser(db):
    gec = -(svc.GIVE_UP_AFTER_MINUTES + 30)
    r = svc.create_reminder(db, SAHIP, "Dünden kalma", _in(gec), 1, "none")
    assert not any(x["id"] == r["id"] for x in svc.get_reminders_to_notify(db))


def test_kacirilan_noktalar_tek_bildirime_iner():
    """Sunucu kapalıyken birkaç nokta birden geçtiyse dönüşte üst üste bildirim
    yığılmamalı; en dar nokta için tek haber gider."""
    t0 = svc.now_local()
    due = t0 + timedelta(minutes=5)
    r = {
        "due_datetime": due.isoformat(),
        "priority": 1,
        "last_notified_at": None,
        "created_at": (t0 - timedelta(days=2)).isoformat(),   # 1440/180/60 kaçtı
    }

    assert svc.bildirim_gerekli(r, t0)
    r["last_notified_at"] = t0.isoformat()
    assert not svc.bildirim_gerekli(r, t0 + timedelta(minutes=1))


def test_erteleme_hemen_geri_gelmez(db):
    """Damga sıfırlansaydı yeni vade bir noktanın içine düşer ve bildirim,
    erteleme tuşuna basıldıktan saniyeler sonra geri gelirdi."""
    r = svc.create_reminder(db, SAHIP, "Test", _in(2), 1, "none")
    svc.snooze_reminder(db, SAHIP, r["id"], 30)
    db.commit()

    assert not any(x["id"] == r["id"] for x in svc.get_reminders_to_notify(db))


def test_tarih_duzenlemesi_hemen_bildirim_yollamaz(db):
    """Panelden saati ileri almak da 'şimdi haber ver' anlamına gelmiyor."""
    r = svc.create_reminder(db, SAHIP, "Test", _in(5), 1, "none")
    svc.update_reminder(db, SAHIP, r["id"], due_datetime=_in(45))
    db.commit()

    assert not any(x["id"] == r["id"] for x in svc.get_reminders_to_notify(db))


# ── Tekrarlama mantığı ───────────────────────────────────────────────────────

def test_tamamlanan_tekrarlayan_olmez(db):
    r = svc.create_reminder(db, SAHIP, "Her gün", _in(5), 2, "daily")
    done = svc.complete_reminder(db, SAHIP, r["id"])
    assert done["rescheduled"] is True
    assert done["is_completed"] == 0
    assert svc.parse_dt(done["due_datetime"]) > svc.now_local()


def test_tamamlanan_tek_seferlik_kapanir(db):
    r = svc.create_reminder(db, SAHIP, "Tek seferlik", _in(5), 2, "none")
    done = svc.complete_reminder(db, SAHIP, r["id"])
    assert done["is_completed"] == 1

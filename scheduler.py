from datetime import datetime

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from logging_setup import get_logger

log = get_logger("prism.scheduler")

TZ = pytz.timezone("Europe/Istanbul")
scheduler = AsyncIOScheduler(timezone=TZ)

# Hatırlatıcı döngüsünün en son ne zaman baştan sona döndüğü.
# `scheduler.running` yalnızca "zamanlayıcı ayakta" demek — iş bir yerde takılırsa
# ya da her turda çöküyorsa bayrak yine yeşil görünür. Sağlık kontrolü bu damgaya
# bakarak "çalışıyor ama iş görmüyor" halini de yakalayabiliyor.
last_reminder_check: datetime | None = None

# Dakikada bir dönmesi gereken iş bu kadar süre haber vermezse takılmış sayılır.
REMINDER_HEARTBEAT_TIMEOUT_SECONDS = 300


def reminder_loop_age_seconds() -> float | None:
    """Hatırlatıcı döngüsünün son turundan bu yana geçen saniye (hiç dönmediyse None)"""
    if last_reminder_check is None:
        return None
    return (datetime.now(TZ) - last_reminder_check).total_seconds()


async def bekleyen_iletiler():
    """Vakti gelen iletileri alıcılarına gönderir (dakikalık iş).

    ⚠️ İşaretleme gönderimden SONRA (`svc.iletildi`): Telegram'a ulaşılamazsa
    ileti gönderilmemiş sayılıp bir sonraki turda yeniden denenmeli. Ters
    sırada yapılsaydı bir ağ hatası mesajı sessizce yutardı.

    Gönderene teslim haberi yalnız ZAMANLANMIŞ iletiler için gidiyor: hemen
    gönderilende zaten onay mesajını görüyor, ikinci bir haber gürültü olur.
    """
    from database import get_db
    from modules.iletiler import service as svc
    from telegram_bot import ileti_gonder, sahibin_chati, send_message

    with get_db() as conn:
        sirada = svc.vakti_gelenler(conn)

    for ileti in sirada:
        try:
            if not await ileti_gonder(ileti):
                continue
            with get_db() as conn:
                svc.iletildi(conn, ileti["id"])

            gecikmeli = ileti["iletilecek_at"] > ileti["created_at"]
            if gecikmeli:
                from auth import kullanici_getir
                alici = kullanici_getir(ileti["alici_id"]) or {}
                await send_message(
                    f"✅ {alici.get('ad', 'Alıcı')} kişisine iletildi.",
                    chat_id=sahibin_chati(ileti["gonderen_id"]),
                )
        except Exception:
            log.exception("İleti gönderilemedi: %s", ileti["id"])

    if sirada:
        with get_db() as conn:
            svc.temizle(conn)


async def check_reminders():
    """Her 1 dakikada çalışır; bildirim zamanı gelen hatırlatıcıları gönderir"""
    global last_reminder_check

    from database import get_db
    from modules.reminders import service as svc
    from telegram_bot import send_reminder_notification

    with get_db() as conn:
        # Sunucu bir saatten uzun kapalı kaldıysa bildirilemeyen tekrarlayanlar
        # geçmişte takılı kalıyor — önce onları bir sonraki periyoda taşı.
        moved = svc.reschedule_overdue_recurring(conn)
        if moved:
            log.info(f"🔁 {moved} gecikmiş tekrarlayan hatırlatıcı sonraki periyoda taşındı")

        to_notify = svc.get_reminders_to_notify(conn)

    for reminder in to_notify:
        try:
            await send_reminder_notification(reminder)
            with get_db() as conn:
                svc.update_last_notified(conn, reminder["id"])
                # Tekrarlayan hatırlatıcı vadesi geçtiyse bir sonraki periyoda ötle
                if reminder.get("recurrence", "none") != "none":
                    due = svc.parse_dt(reminder["due_datetime"])
                    if due < svc.now_local():
                        svc.reschedule_recurring(conn, reminder["id"])
        except Exception as e:
            log.error(f"❌ Bildirim gönderilemedi [ID={reminder['id']}]: {e}")

    # En sonda: tur baştan sona tamamlandıysa damgayı at. Ortada patlarsa damga
    # eskir ve /health bunu görür.
    last_reminder_check = datetime.now(TZ)


async def cleanup_conversations():
    """Her gece 03:00'te 30 günden eski konuşma kayıtlarını temizler"""
    from database import delete_old_conversations

    try:
        deleted = delete_old_conversations(30)
        if deleted:
            log.info(f"🧹 {deleted} eski konuşma kaydı silindi")
    except Exception as e:
        log.error(f"❌ Konuşma temizliği başarısız: {e}")


async def nightly_backup():
    """Her gece 04:00'te veritabanı yedeğini Telegram'a gönderir.

    03:00'teki konuşma temizliğinden sonra çalışır ki yedek zaten sadeleşmiş
    veriyi içersin.
    """
    from backup import send_backup

    try:
        await send_backup()
    except Exception as e:
        log.error(f"❌ Yedekleme işi çöktü: {type(e).__name__}: {e}")


async def _herkese_ozet(uretici, ad: str):
    """Özeti her kullanıcı için ayrı üretip kendi sohbetine yollar.

    Telegram'a hiç bağlanmamış (chat_id'si boş) kullanıcı atlanır — özeti
    üretmenin anlamı yok, gidecek yer yok.

    Hata tek kişiyle sınırlı: birinin özeti patlarsa diğerininki yine gider.
    Tek try bloğuyla sarsaydık bir kişinin bozuk verisi herkesin sabah
    özetini sessizce düşürürdü.
    """
    from auth import tum_kullanicilar
    from telegram_bot import send_message

    for k in tum_kullanicilar():
        if not k["telegram_chat_id"]:
            continue
        try:
            await send_message(await uretici(k["id"]), chat_id=k["telegram_chat_id"])
            log.info("✅ %s gönderildi (%s)", ad, k["ad"])
        except Exception:
            log.exception("❌ %s gönderilemedi (%s)", ad, k["ad"])


async def send_morning_summary():
    """Her sabah 08:00'de (Istanbul) günlük özet gönderir — herkese kendi özeti"""
    from modules.summary import service as summary_svc

    await _herkese_ozet(summary_svc.get_morning_summary, "Sabah özeti")


async def send_evening_summary():
    """Her akşam 21:00'de günün karnesini gönderir"""
    from modules.summary import service as summary_svc

    await _herkese_ozet(summary_svc.get_evening_summary, "Akşam özeti")


async def send_weekly_report():
    """Her pazar 20:00'de haftalık raporu gönderir"""
    from modules.summary import service as summary_svc

    await _herkese_ozet(summary_svc.get_weekly_report, "Haftalık rapor")


async def gozlem_turu():
    """Asistanın kendi başına 'söylenecek bir şey var mı' diye baktığı tur.

    Diğer işlerden farkı: bu iş **mesaj göndermemek üzere** tasarlandı.
    Turların çoğu sinyal bulamadan ya da susma bütçesine takılıp biter;
    Groq'a ancak gerçekten bir şey fark edildiğinde uğrar.

    Kimin için çalışacağı `users.gozlem_sinir`e bağlı ve o sütun sıfır
    (kapalı) başlıyor — yani bu iş yayına alındığında hiç kimseye mesaj
    gitmez, açmak ayrı bir komut.
    """
    from modules.gozlem import service as gozlem

    try:
        await gozlem.herkes_icin_tur()
    except Exception:
        log.exception("❌ Gözlem turu başarısız")


async def hafiza_cikarimi():
    """Yeni konuşmalardan kalıcı bilgileri süzüp hafızaya yazar.

    Mesajın içinde değil, ayrı bir turda yapılıyor: her mesaja fazladan bir
    Groq çağrısı eklemek cevap süresini iki katına çıkarırdı. Yeni konuşma
    satırı yoksa model hiç çağrılmıyor.
    """
    from modules.gozlem import service as gozlem

    try:
        await gozlem.herkes_icin_hafiza()
    except Exception:
        log.exception("❌ Hafıza çıkarımı başarısız")


def start_scheduler():
    global last_reminder_check

    # İlk tur bir dakika sonra dönecek; o zamana kadar damga boş kalmasın diye
    # başlangıç anını yazıyoruz — yoksa açılışta /health kendini bozuk sanardı.
    last_reminder_check = datetime.now(TZ)

    # İletiler de dakikalık: ayrı bir iş açmak yerine aynı sıklıkta ikinci bir
    # job — check_reminders'ın içine gömülseydi hatırlatıcı hatası iletileri
    # de düşürürdü.
    scheduler.add_job(
        bekleyen_iletiler,
        "interval",
        minutes=1,
        id="bekleyen_iletiler",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        check_reminders,
        "interval",
        minutes=1,
        id="check_reminders",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        send_morning_summary,
        CronTrigger(hour=8, minute=0, timezone=TZ),
        id="morning_summary",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        cleanup_conversations,
        CronTrigger(hour=3, minute=0, timezone=TZ),
        id="cleanup_conversations",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        nightly_backup,
        CronTrigger(hour=4, minute=0, timezone=TZ),
        id="nightly_backup",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        send_evening_summary,
        CronTrigger(hour=21, minute=0, timezone=TZ),
        id="evening_summary",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        send_weekly_report,
        CronTrigger(day_of_week="sun", hour=20, minute=0, timezone=TZ),
        id="weekly_report",
        replace_existing=True,
        max_instances=1,
    )

    # Gözlem turu: 09:00–21:00 arası iki saatte bir, dakika 15'te.
    # Dakika 15 bilerek: :00'da sabah/akşam özetleri ve dakikalık hatırlatıcı
    # işi dönüyor, kendiliğinden mesajın onlarla aynı saniyeye denk gelip arka
    # arkaya iki bildirim olarak düşmesi istenmiyor.
    # Sessiz saat kontrolü ayrıca `service.tur()` içinde de var — burası
    # gereksiz turları önlüyor, oradaki ise elle çalıştırmada da koruyor.
    scheduler.add_job(
        gozlem_turu,
        CronTrigger(hour="9-21/2", minute=15, timezone=TZ),
        id="gozlem_turu",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        hafiza_cikarimi,
        CronTrigger(hour="*/3", minute=40, timezone=TZ),
        id="hafiza_cikarimi",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()
    log.info(
        "✅ Zamanlayıcı başlatıldı (hatırlatıcı: 1 dk · sabah 08:00 · akşam 21:00 · "
        "haftalık pazar 20:00 · temizlik 03:00 · yedek 04:00 · "
        "gözlem 09-21 arası 2 saatte bir · hafıza 3 saatte bir)"
    )


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        log.info("⏹ Zamanlayıcı durduruldu")

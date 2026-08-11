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


async def send_morning_summary():
    """Her sabah 08:00'de (Istanbul) günlük özet gönderir"""
    from modules.summary import service as summary_svc
    from telegram_bot import send_message

    try:
        text = await summary_svc.get_morning_summary()
        await send_message(text)
        log.info("✅ Sabah özeti gönderildi")
    except Exception as e:
        log.error(f"❌ Sabah özeti gönderilemedi: {e}")


async def send_evening_summary():
    """Her akşam 21:00'de günün karnesini gönderir"""
    from modules.summary import service as summary_svc
    from telegram_bot import send_message

    try:
        await send_message(await summary_svc.get_evening_summary())
        log.info("✅ Akşam özeti gönderildi")
    except Exception:
        log.exception("❌ Akşam özeti gönderilemedi")


async def send_weekly_report():
    """Her pazar 20:00'de haftalık raporu gönderir"""
    from modules.summary import service as summary_svc
    from telegram_bot import send_message

    try:
        await send_message(await summary_svc.get_weekly_report())
        log.info("✅ Haftalık rapor gönderildi")
    except Exception:
        log.exception("❌ Haftalık rapor gönderilemedi")


def start_scheduler():
    global last_reminder_check

    # İlk tur bir dakika sonra dönecek; o zamana kadar damga boş kalmasın diye
    # başlangıç anını yazıyoruz — yoksa açılışta /health kendini bozuk sanardı.
    last_reminder_check = datetime.now(TZ)

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

    scheduler.start()
    log.info(
        "✅ Zamanlayıcı başlatıldı (hatırlatıcı: 1 dk · sabah 08:00 · akşam 21:00 · "
        "haftalık pazar 20:00 · temizlik 03:00 · yedek 04:00)"
    )


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        log.info("⏹ Zamanlayıcı durduruldu")

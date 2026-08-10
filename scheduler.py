import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

TZ = pytz.timezone("Europe/Istanbul")
scheduler = AsyncIOScheduler(timezone=TZ)


async def check_reminders():
    """Her 1 dakikada çalışır; bildirim zamanı gelen hatırlatıcıları gönderir"""
    from database import get_db
    from modules.reminders import service as svc
    from telegram_bot import send_reminder_notification

    with get_db() as conn:
        # Sunucu bir saatten uzun kapalı kaldıysa bildirilemeyen tekrarlayanlar
        # geçmişte takılı kalıyor — önce onları bir sonraki periyoda taşı.
        moved = svc.reschedule_overdue_recurring(conn)
        if moved:
            print(f"🔁 {moved} gecikmiş tekrarlayan hatırlatıcı sonraki periyoda taşındı")

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
            print(f"❌ Bildirim gönderilemedi [ID={reminder['id']}]: {e}")


async def cleanup_conversations():
    """Her gece 03:00'te 30 günden eski konuşma kayıtlarını temizler"""
    from database import delete_old_conversations

    try:
        deleted = delete_old_conversations(30)
        if deleted:
            print(f"🧹 {deleted} eski konuşma kaydı silindi")
    except Exception as e:
        print(f"❌ Konuşma temizliği başarısız: {e}")


async def nightly_backup():
    """Her gece 04:00'te veritabanı yedeğini Telegram'a gönderir.

    03:00'teki konuşma temizliğinden sonra çalışır ki yedek zaten sadeleşmiş
    veriyi içersin.
    """
    from backup import send_backup

    try:
        await send_backup()
    except Exception as e:
        print(f"❌ Yedekleme işi çöktü: {type(e).__name__}: {e}")


async def send_morning_summary():
    """Her sabah 08:00'de (Istanbul) günlük özet gönderir"""
    from modules.summary import service as summary_svc
    from telegram_bot import send_message

    try:
        text = await summary_svc.get_morning_summary()
        await send_message(text)
        print("✅ Sabah özeti gönderildi")
    except Exception as e:
        print(f"❌ Sabah özeti gönderilemedi: {e}")


def start_scheduler():
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

    scheduler.start()
    print(
        "✅ Zamanlayıcı başlatıldı "
        "(hatırlatıcı: 1 dk, sabah özeti: 08:00, temizlik: 03:00, yedek: 04:00)"
    )


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("⏹ Zamanlayıcı durduruldu")

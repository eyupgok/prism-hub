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

    scheduler.start()
    print("✅ Zamanlayıcı başlatıldı (hatırlatıcı kontrolü: 1 dk, sabah özeti: 08:00)")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("⏹ Zamanlayıcı durduruldu")

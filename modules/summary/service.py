import html
from datetime import datetime
import pytz

TZ = pytz.timezone("Europe/Istanbul")


async def get_morning_summary() -> str:
    """Hava, görev, harcama ve notları birleştirerek günlük özet oluşturur"""
    from database import get_db
    from modules.reminders import service as reminder_svc
    from modules.notes import service as notes_svc
    from modules.expenses import service as expenses_svc
    from modules.weather import service as weather_svc

    now = datetime.now(TZ)
    today_str = now.strftime("%Y-%m-%d")
    month_str = now.strftime("%Y-%m")

    lines = ["☀️ Günaydın! Bugünün özeti:\n"]

    # --- Hava durumu ---
    try:
        weather = await weather_svc.get_weather()
        emoji = weather_svc.get_weather_emoji(weather["weather_code"])
        lines.append(
            f"{emoji} Hava: {weather['city']} {weather['temperature']}°C, {weather['description']}"
        )
    except Exception:
        lines.append("🌡 Hava durumu alınamadı")

    # --- Bugünkü görevler ---
    with get_db() as conn:
        all_reminders = reminder_svc.list_reminders(conn, include_completed=False)

    today_tasks = []
    for r in all_reminders:
        due = reminder_svc.parse_dt(r["due_datetime"])
        if due.strftime("%Y-%m-%d") == today_str:
            today_tasks.append(r)

    lines.append(f"\n📋 Bugün {len(today_tasks)} görev var:")
    if today_tasks:
        for r in today_tasks:
            due = reminder_svc.parse_dt(r["due_datetime"])
            emoji = reminder_svc.PRIORITY_EMOJIS.get(r["priority"], "🟢")
            lines.append(f"  {emoji} {html.escape(r['title'])} ({due.strftime('%H:%M')})")
    else:
        lines.append("  Bugün planlanmış görev yok")

    # --- Aylık harcama özeti ---
    with get_db() as conn:
        summary = expenses_svc.get_monthly_summary(conn, month_str)

    lines.append(f"\n💰 Bu ay toplam {summary['total']:.0f} TL harcandı")
    if summary["by_category"]:
        top3 = sorted(summary["by_category"].items(), key=lambda x: x[1], reverse=True)[:3]
        for cat, total in top3:
            lines.append(f"  • {cat}: {total:.0f} TL")

    # --- Son notlar ---
    with get_db() as conn:
        recent_notes = notes_svc.list_notes(conn)[:3]

    if recent_notes:
        lines.append("\n📝 Son notlar:")
        for n in recent_notes:
            lines.append(f"  • {html.escape(n['title'])} ({n['category']})")

    return "\n".join(lines)

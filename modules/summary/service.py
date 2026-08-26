import html
from datetime import datetime, timedelta
import pytz

TZ = pytz.timezone("Europe/Istanbul")

TURKISH_DAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def _day_bounds(day: datetime):
    """Verilen günün 00:00 ve ertesi gün 00:00 sınırları."""
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def _bar(value: float, maximum: float, width: int = 10) -> str:
    """Metin çubuğu: ▓▓▓▓░░░░░░ — grafik kütüphanesine gerek kalmadan görsel karşılaştırma."""
    if maximum <= 0:
        return "░" * width
    filled = int(round((value / maximum) * width))
    return "▓" * max(0, min(filled, width)) + "░" * max(0, width - filled)


def _money(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".")


async def get_morning_summary(owner_id: int) -> str:
    """Hava, görev, harcama ve notları birleştirerek günlük özet oluşturur.

    Özetler kişiye özel: zamanlayıcı her kullanıcı için ayrı ayrı üretip
    herkesin kendi Telegram'ına gönderiyor.
    """
    from database import get_db
    from modules.reminders import service as reminder_svc
    from modules.notes import service as notes_svc
    from modules.expenses import service as expenses_svc
    from modules.weather import service as weather_svc

    now = datetime.now(TZ)
    today_str = now.strftime("%Y-%m-%d")
    month_str = now.strftime("%Y-%m")

    lines = ["☀️ Günaydınlar. Bugünün özeti:\n"]

    # --- Hava durumu ---
    try:
        from auth import kullanici_getir

        weather = await weather_svc.get_weather(kullanici_getir(owner_id))
        emoji = weather_svc.get_weather_emoji(weather["weather_code"])
        lines.append(
            f"{emoji} Hava: {weather['city']} {weather['temperature']}°C, {weather['description']}"
        )
    except Exception:
        lines.append("🌡 Hava durumu alınamadı")

    # --- Bugünkü görevler ---
    with get_db() as conn:
        all_reminders = reminder_svc.list_reminders(conn, owner_id, include_completed=False)

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
        summary = expenses_svc.get_monthly_summary(conn, owner_id, month_str)

    lines.append(f"\n💰 Bu ay toplam {summary['total']:.0f} TL harcandı")
    if summary["by_category"]:
        top3 = sorted(summary["by_category"].items(), key=lambda x: x[1], reverse=True)[:3]
        for cat, total in top3:
            lines.append(f"  • {cat}: {total:.0f} TL")

    # --- Son notlar ---
    with get_db() as conn:
        recent_notes = notes_svc.list_notes(conn, owner_id)[:3]

    if recent_notes:
        lines.append("\n📝 Son notlar:")
        for n in recent_notes:
            lines.append(f"  • {html.escape(n['title'])} ({n['category']})")

    return "\n".join(lines)


async def get_evening_summary(owner_id: int) -> str:
    """Akşam 21:00 özeti: bugün ne yapıldı, yarın ne bekliyor."""
    from database import get_db
    from modules.expenses import service as expenses_svc
    from modules.reminders import service as reminder_svc

    now = datetime.now(TZ)
    today_start, tomorrow_start = _day_bounds(now)
    day_after = tomorrow_start + timedelta(days=1)
    today_str = now.strftime("%Y-%m-%d")

    with get_db() as conn:
        completed = reminder_svc.count_completed_between(conn, owner_id, today_start, tomorrow_start)
        remaining = reminder_svc.list_due_between(conn, owner_id, today_start, tomorrow_start)
        tomorrow = reminder_svc.list_due_between(conn, owner_id, tomorrow_start, day_after)
        todays_expenses = expenses_svc.list_expenses(
            conn, owner_id, since=today_str, until=None, month=today_str[:7]
        )
        todays_expenses = [e for e in todays_expenses if e["expense_date"] == today_str]

    spent = sum(e["amount"] for e in todays_expenses)

    lines = [f"🌙 <b>Günün özeti</b> — {now.strftime('%d.%m.%Y')}\n"]

    if completed:
        lines.append(f"✅ Bugün {completed} görev tamamladınız.")
    else:
        lines.append("✅ Bugün tamamlanan görev yok.")

    if remaining:
        lines.append(f"\n⏳ Bugünden kalan {len(remaining)} görev:")
        for r in remaining[:5]:
            due = reminder_svc.parse_dt(r["due_datetime"])
            emoji = reminder_svc.PRIORITY_EMOJIS.get(r["priority"], "🟢")
            lines.append(f"  {emoji} {html.escape(r['title'])} ({due.strftime('%H:%M')})")

    if todays_expenses:
        lines.append(f"\n💰 Bugün {_money(spent)} TL harcadınız ({len(todays_expenses)} kayıt)")
        refunds = [e for e in todays_expenses if e["amount"] < 0]
        if refunds:
            lines.append(f"  ↩️ {len(refunds)} iade dahil")
    else:
        lines.append("\n💰 Bugün harcama kaydı yok.")

    if tomorrow:
        lines.append(f"\n📅 Yarın {len(tomorrow)} görev var:")
        for r in tomorrow[:5]:
            due = reminder_svc.parse_dt(r["due_datetime"])
            emoji = reminder_svc.PRIORITY_EMOJIS.get(r["priority"], "🟢")
            lines.append(f"  {emoji} {html.escape(r['title'])} ({due.strftime('%H:%M')})")
    else:
        lines.append("\n📅 Yarın için planlanmış görev yok. İyi geceler, efendim.")

    return "\n".join(lines)


async def get_weekly_report(owner_id: int) -> str:
    """Pazar akşamı haftalık rapor: görev ve harcama karnesi, geçen haftayla kıyas."""
    from database import get_db
    from modules.expenses import service as expenses_svc
    from modules.reminders import service as reminder_svc

    now = datetime.now(TZ)
    today_start, tomorrow_start = _day_bounds(now)
    week_start = today_start - timedelta(days=6)          # son 7 gün (bugün dahil)
    prev_week_start = week_start - timedelta(days=7)

    with get_db() as conn:
        completed = reminder_svc.count_completed_between(conn, owner_id, week_start, tomorrow_start)
        prev_completed = reminder_svc.count_completed_between(conn, owner_id, prev_week_start, week_start)
        # Sadece iki haftalık aralık çekiliyor — tüm geçmişi okumaya gerek yok
        all_expenses = expenses_svc.list_expenses(
            conn,
            owner_id,
            since=prev_week_start.strftime("%Y-%m-%d"),
            until=tomorrow_start.strftime("%Y-%m-%d"),
        )

    def total_between(start: datetime, end: datetime) -> float:
        return sum(
            e["amount"] for e in all_expenses
            if start.strftime("%Y-%m-%d") <= e["expense_date"] < end.strftime("%Y-%m-%d")
        )

    this_week = total_between(week_start, tomorrow_start)
    last_week = total_between(prev_week_start, week_start)

    lines = [
        f"📊 <b>Haftalık rapor</b>",
        f"<i>{week_start.strftime('%d.%m')} — {now.strftime('%d.%m.%Y')}</i>\n",
        f"✅ Tamamlanan görev: <b>{completed}</b>"
        + (f" (geçen hafta {prev_completed})" if prev_completed else ""),
        f"💰 Harcama: <b>{_money(this_week)} TL</b>",
    ]

    if last_week:
        diff = this_week - last_week
        pct = abs(diff / last_week * 100)
        if abs(diff) < 1:
            lines.append("  → Geçen haftayla neredeyse aynı")
        elif diff > 0:
            lines.append(f"  📈 Geçen haftadan %{pct:.0f} fazla (+{_money(diff)} TL)")
        else:
            lines.append(f"  📉 Geçen haftadan %{pct:.0f} az ({_money(diff)} TL)")

    # Günlük dağılım — metin çubuğuyla
    daily = []
    for i in range(7):
        day = week_start + timedelta(days=i)
        day_key = day.strftime("%Y-%m-%d")
        amount = sum(e["amount"] for e in all_expenses if e["expense_date"] == day_key)
        daily.append((TURKISH_DAYS[day.weekday()][:3], amount))

    peak = max((amount for _, amount in daily), default=0)
    if peak > 0:
        lines.append("\n<b>Günlük dağılım</b>")
        for label, amount in daily:
            lines.append(f"<code>{label} {_bar(amount, peak)} {_money(amount):>6}</code>")

    # Kategori kırılımı
    by_category = {}
    for e in all_expenses:
        if week_start.strftime("%Y-%m-%d") <= e["expense_date"] < tomorrow_start.strftime("%Y-%m-%d"):
            by_category[e["category"]] = by_category.get(e["category"], 0) + e["amount"]

    top = sorted(by_category.items(), key=lambda x: x[1], reverse=True)[:5]
    if top:
        lines.append("\n<b>Kategoriler</b>")
        for cat, amount in top:
            lines.append(f"  • {cat}: {_money(amount)} TL")

    return "\n".join(lines)

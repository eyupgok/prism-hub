import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
import pytz

TZ = pytz.timezone("Europe/Istanbul")

PRIORITY_NAMES = {1: "Kritik", 2: "Önemli", 3: "Normal"}
PRIORITY_EMOJIS = {1: "🔴", 2: "🟡", 3: "🟢"}


def now_local() -> datetime:
    return datetime.now(TZ)


def parse_dt(dt_str: str) -> datetime:
    """ISO string'i timezone-aware datetime'a çevirir"""
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = TZ.localize(dt)
    return dt


def format_dt(dt: datetime) -> str:
    """Datetime'ı Türkçe okunabilir formata çevirir"""
    local = dt.astimezone(TZ)
    return local.strftime("%d.%m.%Y %H:%M")


def format_time_remaining(minutes: float) -> str:
    """Kalan/geçen süreyi okunabilir stringe çevirir"""
    if minutes < 0:
        abs_m = abs(minutes)
        if abs_m < 60:
            return f"{int(abs_m)} dakika geçti"
        return f"{int(abs_m / 60)} saat geçti"
    if minutes < 60:
        return f"{int(minutes)} dakika kaldı"
    if minutes < 1440:
        h = int(minutes / 60)
        m = int(minutes % 60)
        return f"{h} saat {m} dk kaldı" if m else f"{h} saat kaldı"
    return f"{int(minutes / 1440)} gün kaldı"


def get_notification_interval(priority: int, minutes_remaining: float) -> Optional[int]:
    """
    Kaç dakikada bir bildirim gönderileceğini döner.
    None → henüz bildirim zamanı değil.
    """
    # Süresi geçmiş hatırlatıcıları maksimum frekansta bildir
    effective = max(0.0, minutes_remaining)

    if priority == 1:  # Kritik
        if effective <= 60:
            return 15
        if effective <= 180:
            return 30
        if effective <= 360:
            return 60
        if effective <= 1440:
            return 180
        if effective <= 4320:
            return 360
        if effective <= 10080:
            return 1440
        return None

    if priority == 2:  # Önemli
        if effective <= 30:
            return 15
        if effective <= 180:
            return 60
        if effective <= 1440:
            return 360
        if effective <= 4320:
            return 1440
        return None

    # Normal (3)
    if effective <= 120:
        return 60
    if effective <= 1440:
        return 720
    return None


def create_reminder(
    conn: sqlite3.Connection,
    title: str,
    due_datetime: str,
    priority: int = 3,
) -> Dict[str, Any]:
    """Yeni hatırlatıcı oluşturur"""
    dt = parse_dt(due_datetime)
    cursor = conn.execute(
        "INSERT INTO reminders (title, due_datetime, priority, created_at) VALUES (?, ?, ?, ?)",
        (title, dt.isoformat(), priority, now_local().isoformat()),
    )
    return get_reminder_by_id(conn, cursor.lastrowid)


def get_reminder_by_id(conn: sqlite3.Connection, reminder_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
    return dict(row) if row else None


def list_reminders(conn: sqlite3.Connection, include_completed: bool = False) -> List[Dict[str, Any]]:
    query = "SELECT * FROM reminders"
    if not include_completed:
        query += " WHERE is_completed = 0"
    query += " ORDER BY due_datetime ASC"
    return [dict(r) for r in conn.execute(query).fetchall()]


def complete_reminder(conn: sqlite3.Connection, reminder_id: int) -> Optional[Dict[str, Any]]:
    conn.execute("UPDATE reminders SET is_completed = 1 WHERE id = ?", (reminder_id,))
    return get_reminder_by_id(conn, reminder_id)


def delete_reminder(conn: sqlite3.Connection, reminder_id: int) -> bool:
    cursor = conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
    return cursor.rowcount > 0


def snooze_reminder(conn: sqlite3.Connection, reminder_id: int, minutes: int) -> Optional[Dict[str, Any]]:
    """Hatırlatıcıyı şu andan itibaren belirtilen dakika kadar erteler"""
    reminder = get_reminder_by_id(conn, reminder_id)
    if not reminder:
        return None
    new_due = now_local() + timedelta(minutes=minutes)
    conn.execute(
        "UPDATE reminders SET due_datetime = ?, snooze_count = snooze_count + 1, last_notified_at = NULL WHERE id = ?",
        (new_due.isoformat(), reminder_id),
    )
    return get_reminder_by_id(conn, reminder_id)


def update_last_notified(conn: sqlite3.Connection, reminder_id: int):
    conn.execute(
        "UPDATE reminders SET last_notified_at = ? WHERE id = ?",
        (now_local().isoformat(), reminder_id),
    )


def get_reminders_to_notify(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Bildirim zamanı gelen hatırlatıcıları döner"""
    now = now_local()
    to_notify = []

    for r in list_reminders(conn, include_completed=False):
        due = parse_dt(r["due_datetime"])
        minutes_remaining = (due - now).total_seconds() / 60

        # 60 dakikadan fazla geçmişse artık bildir
        if minutes_remaining < -60:
            continue

        interval = get_notification_interval(r["priority"], minutes_remaining)
        if interval is None:
            continue

        if r["last_notified_at"]:
            last = parse_dt(r["last_notified_at"])
            minutes_since = (now - last).total_seconds() / 60
            if minutes_since < interval:
                continue

        to_notify.append(r)

    return to_notify


def format_reminder_notification(reminder: Dict[str, Any]) -> Tuple[str, List]:
    """Telegram mesaj metni ve inline keyboard döner"""
    due = parse_dt(reminder["due_datetime"])
    now = now_local()
    minutes_remaining = (due - now).total_seconds() / 60

    emoji = PRIORITY_EMOJIS.get(reminder["priority"], "🟢")
    priority_name = PRIORITY_NAMES.get(reminder["priority"], "Normal")

    text = (
        f"{emoji} <b>{reminder['title']}</b>\n"
        f"📅 {format_dt(due)} — {format_time_remaining(minutes_remaining)}\n"
        f"🏷 {priority_name}"
    )

    keyboard = [
        [
            {"text": "✅ Tamamlandı", "callback_data": f"complete_{reminder['id']}"},
            {"text": "⏰ 15 dk ertele", "callback_data": f"snooze_15_{reminder['id']}"},
            {"text": "⏰ 1 saat ertele", "callback_data": f"snooze_60_{reminder['id']}"},
        ]
    ]

    return text, keyboard

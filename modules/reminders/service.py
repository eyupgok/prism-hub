import calendar
import html
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
import pytz

TZ = pytz.timezone("Europe/Istanbul")

PRIORITY_NAMES = {1: "Kritik", 2: "Önemli", 3: "Normal"}
PRIORITY_EMOJIS = {1: "🔴", 2: "🟡", 3: "🟢"}
RECURRENCE_LABELS = {"daily": "Her gün", "weekly": "Her hafta", "monthly": "Her ay"}


VALID_RECURRENCES = {"none", "daily", "weekly", "monthly"}


def normalize_priority(priority: Any) -> int:
    """1-3 aralığına sıkıştırır. Aralık dışı değer bildirim sıklığı hesabını
    sessizce 'normal'e düşürüyordu; artık en yakın geçerli değere çekiliyor."""
    try:
        return max(1, min(int(priority), 3))
    except (TypeError, ValueError):
        return 3


def normalize_recurrence(recurrence: Any) -> str:
    return recurrence if recurrence in VALID_RECURRENCES else "none"


def now_local() -> datetime:
    return datetime.now(TZ)


def parse_dt(dt_str: str) -> datetime:
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = TZ.localize(dt)
    return dt


def format_dt(dt: datetime) -> str:
    return dt.astimezone(TZ).strftime("%d.%m.%Y %H:%M")


def format_time_remaining(minutes: float) -> str:
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
    effective = max(0.0, minutes_remaining)

    if priority == 1:
        if effective <= 60:   return 15
        if effective <= 180:  return 30
        if effective <= 360:  return 60
        if effective <= 1440: return 180
        if effective <= 4320: return 360
        if effective <= 10080: return 1440
        return None

    if priority == 2:
        if effective <= 30:   return 15
        if effective <= 180:  return 60
        if effective <= 1440: return 360
        if effective <= 4320: return 1440
        return None

    if effective <= 120:  return 60
    if effective <= 1440: return 720
    return None


def create_reminder(
    conn: sqlite3.Connection,
    owner_id: int,
    title: str,
    due_datetime: str,
    priority: int = 3,
    recurrence: str = "none",
) -> Dict[str, Any]:
    dt = parse_dt(due_datetime)
    cursor = conn.execute(
        "INSERT INTO reminders (owner_id, title, due_datetime, priority, recurrence, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (owner_id, title, dt.isoformat(), normalize_priority(priority),
         normalize_recurrence(recurrence), now_local().isoformat()),
    )
    return get_reminder_by_id(conn, cursor.lastrowid)


def get_reminder_by_id(conn: sqlite3.Connection, reminder_id: int) -> Optional[Dict[str, Any]]:
    """Sahibine bakmadan getirir — sahiplik kontrolünü rota yapar, böylece
    'yok' (404) ile 'senin değil' (403) ayrı ayrı cevaplanabiliyor."""
    row = conn.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
    return dict(row) if row else None


def list_reminders(
    conn: sqlite3.Connection, owner_id: int, include_completed: bool = False
) -> List[Dict[str, Any]]:
    query = "SELECT * FROM reminders WHERE owner_id = ?"
    if not include_completed:
        query += " AND is_completed = 0"
    query += " ORDER BY due_datetime ASC"
    return [dict(r) for r in conn.execute(query, (owner_id,)).fetchall()]


def tum_hatirlaticilar(
    conn: sqlite3.Connection, include_completed: bool = False
) -> List[Dict[str, Any]]:
    """SAHİPTEN BAĞIMSIZ liste — yalnız zamanlayıcı için.

    Bildirim döngüsünün herkesin hatırlatıcısına bakması, sonra her birini
    sahibinin Telegram'ına yollaması gerekiyor. Kullanıcıya açılan uçlar
    bunu değil `list_reminders`'ı kullanır.
    """
    query = "SELECT * FROM reminders"
    if not include_completed:
        query += " WHERE is_completed = 0"
    query += " ORDER BY due_datetime ASC"
    return [dict(r) for r in conn.execute(query).fetchall()]


def complete_reminder(
    conn: sqlite3.Connection, owner_id: int, reminder_id: int
) -> Optional[Dict[str, Any]]:
    r = get_reminder_by_id(conn, reminder_id)
    if not r or r["owner_id"] != owner_id:
        return None
    # Tekrarlayan hatırlatıcı tamamlanınca ölmez, bir sonraki periyoda geçer
    if r.get("recurrence", "none") != "none":
        updated = reschedule_recurring(conn, reminder_id)
        if updated:
            updated["rescheduled"] = True
            return updated
    conn.execute(
        "UPDATE reminders SET is_completed = 1, completed_at = ? WHERE id = ? AND owner_id = ?",
        (now_local().isoformat(), reminder_id, owner_id),
    )
    return get_reminder_by_id(conn, reminder_id)


def count_completed_between(
    conn: sqlite3.Connection, owner_id: int, start: datetime, end: datetime
) -> int:
    """İki an arasında tamamlanan görev sayısı (akşam özeti ve haftalık rapor için)."""
    row = conn.execute(
        "SELECT COUNT(*) c FROM reminders "
        "WHERE owner_id = ? AND completed_at >= ? AND completed_at < ?",
        (owner_id, start.isoformat(), end.isoformat()),
    ).fetchone()
    return row["c"]


def list_due_between(
    conn: sqlite3.Connection, owner_id: int, start: datetime, end: datetime
) -> List[Dict[str, Any]]:
    """Belirtilen aralıkta vadesi olan, tamamlanmamış hatırlatıcılar."""
    result = []
    for r in list_reminders(conn, owner_id, include_completed=False):
        due = parse_dt(r["due_datetime"])
        if start <= due < end:
            result.append(r)
    return result


def delete_reminder(conn: sqlite3.Connection, owner_id: int, reminder_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM reminders WHERE id = ? AND owner_id = ?", (reminder_id, owner_id)
    )
    return cursor.rowcount > 0


def update_reminder(
    conn: sqlite3.Connection,
    owner_id: int,
    reminder_id: int,
    title: str = None,
    due_datetime: str = None,
    priority: int = None,
    recurrence: str = None,
) -> Optional[Dict[str, Any]]:
    fields, values = [], []
    if title is not None:
        fields.append("title = ?")
        values.append(title)
    if due_datetime is not None:
        dt = parse_dt(due_datetime)
        fields.append("due_datetime = ?")
        fields.append("last_notified_at = ?")
        values.append(dt.isoformat())
        values.append(None)
    if priority is not None:
        fields.append("priority = ?")
        values.append(normalize_priority(priority))
    if recurrence is not None:
        fields.append("recurrence = ?")
        values.append(normalize_recurrence(recurrence))
    if not fields:
        return get_reminder_by_id(conn, reminder_id)
    values.extend([reminder_id, owner_id])
    cursor = conn.execute(
        f"UPDATE reminders SET {', '.join(fields)} WHERE id = ? AND owner_id = ?", values
    )
    if cursor.rowcount == 0:
        return None          # yok ya da başkasının
    return get_reminder_by_id(conn, reminder_id)


# Erteleme 1 dakika ile 1 hafta arasında olmalı. Negatif değer hatırlatıcıyı
# geçmişe taşıyıp bildirim penceresinden düşürüyordu — yani sessizce öldürüyordu.
MIN_SNOOZE_MINUTES = 1
MAX_SNOOZE_MINUTES = 7 * 24 * 60


def snooze_reminder(
    conn: sqlite3.Connection, owner_id: int, reminder_id: int, minutes: int
) -> Optional[Dict[str, Any]]:
    reminder = get_reminder_by_id(conn, reminder_id)
    if not reminder or reminder["owner_id"] != owner_id:
        return None
    minutes = max(MIN_SNOOZE_MINUTES, min(int(minutes), MAX_SNOOZE_MINUTES))
    new_due = now_local() + timedelta(minutes=minutes)
    conn.execute(
        "UPDATE reminders SET due_datetime = ?, snooze_count = snooze_count + 1, "
        "last_notified_at = NULL WHERE id = ? AND owner_id = ?",
        (new_due.isoformat(), reminder_id, owner_id),
    )
    return get_reminder_by_id(conn, reminder_id)


def _advance_period(due: datetime, recurrence: str) -> datetime:
    if recurrence == "daily":
        return due + timedelta(days=1)
    if recurrence == "weekly":
        return due + timedelta(weeks=1)
    if recurrence == "monthly":
        year, month = due.year, due.month + 1
        if month > 12:
            month, year = 1, year + 1
        last_day = calendar.monthrange(year, month)[1]
        return due.replace(year=year, month=month, day=min(due.day, last_day))
    return due


def reschedule_recurring(conn: sqlite3.Connection, reminder_id: int) -> Optional[Dict[str, Any]]:
    """Tekrarlayan hatırlatıcıyı bir sonraki periyoda öteler.

    Erken tamamlamada da çalışsın diye her zaman en az bir periyot ilerletir.
    """
    r = get_reminder_by_id(conn, reminder_id)
    if not r or r.get("recurrence", "none") == "none":
        return None

    due = parse_dt(r["due_datetime"])
    now = now_local()
    recurrence = r["recurrence"]

    due = _advance_period(due, recurrence)
    while due <= now:
        due = _advance_period(due, recurrence)

    conn.execute(
        "UPDATE reminders SET due_datetime = ?, last_notified_at = NULL, is_completed = 0 WHERE id = ?",
        (due.isoformat(), reminder_id),
    )
    return get_reminder_by_id(conn, reminder_id)


def reschedule_overdue_recurring(conn: sqlite3.Connection, older_than_minutes: int = 60) -> int:
    """Bildirim penceresinden düşmüş tekrarlayan hatırlatıcıları ileri sarar.

    `get_reminders_to_notify` vadesi 60 dakikadan fazla geçmiş kayıtları listeden
    çıkarıyor (eski bildirimlerle boğmamak için). Ama ötelemeyi de o döngü yaptığı
    için, sunucu bir saatten uzun kapalı kalırsa tekrarlayan hatırlatıcı hem
    bildirilmiyor hem de bir daha asla ötelenmiyordu — sessizce ölüyordu.

    Bu süpürme o boşluğu kapatıyor: bildirilme ihtimali kalmamış tekrarlayanları
    bir sonraki periyoda taşır. Bildirim penceresindekilere (son 60 dk) dokunmaz,
    yoksa kullanıcı bildirimi görmeden kayıt ilerlerdi.

    Kaç kaydın ötelendiğini döner.
    """
    cutoff = now_local() - timedelta(minutes=older_than_minutes)
    moved = 0

    for r in tum_hatirlaticilar(conn, include_completed=False):   # herkesinki süpürülür
        if r.get("recurrence", "none") == "none":
            continue
        if parse_dt(r["due_datetime"]) >= cutoff:
            continue
        if reschedule_recurring(conn, r["id"]):
            moved += 1

    return moved


def update_last_notified(conn: sqlite3.Connection, reminder_id: int):
    conn.execute(
        "UPDATE reminders SET last_notified_at = ? WHERE id = ?",
        (now_local().isoformat(), reminder_id),
    )


def get_reminders_to_notify(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Bildirilecek hatırlatıcılar — HERKESİNKİ. Dönen her kayıtta `owner_id` var;
    zamanlayıcı ona bakıp bildirimi doğru kişinin Telegram'ına yolluyor."""
    now = now_local()
    to_notify = []

    for r in tum_hatirlaticilar(conn, include_completed=False):
        due = parse_dt(r["due_datetime"])
        minutes_remaining = (due - now).total_seconds() / 60

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
    due = parse_dt(reminder["due_datetime"])
    now = now_local()
    minutes_remaining = (due - now).total_seconds() / 60

    emoji = PRIORITY_EMOJIS.get(reminder["priority"], "🟢")
    priority_name = PRIORITY_NAMES.get(reminder["priority"], "Normal")
    recurrence_label = RECURRENCE_LABELS.get(reminder.get("recurrence", "none"), "")

    text = (
        f"{emoji} <b>{html.escape(reminder['title'])}</b>\n"
        f"📅 {format_dt(due)} — {format_time_remaining(minutes_remaining)}\n"
        f"🏷 {priority_name}"
    )
    if recurrence_label:
        text += f" | 🔁 {recurrence_label}"

    keyboard = [
        [
            {"text": "✅ Tamamlandı", "callback_data": f"complete_{reminder['id']}"},
            {"text": "⏰ 15 dk ertele", "callback_data": f"snooze_15_{reminder['id']}"},
            {"text": "⏰ 1 saat ertele", "callback_data": f"snooze_60_{reminder['id']}"},
        ]
    ]

    return text, keyboard

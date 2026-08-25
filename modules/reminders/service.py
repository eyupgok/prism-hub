import calendar
import html
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
import pytz

TZ = pytz.timezone("Europe/Istanbul")

PRIORITY_NAMES = {1: "Kritik", 2: "Önemli", 3: "Normal", 4: "Sessiz"}
PRIORITY_EMOJIS = {1: "🔴", 2: "🟡", 3: "🟢", 4: "🔇"}
RECURRENCE_LABELS = {"daily": "Her gün", "weekly": "Her hafta", "monthly": "Her ay"}

# Öncelik belirtilmemişse en sessiz seviye. Bilinçli bir tercih: hatırlatıcıyı
# kuran kişi çoğu zaman "sesi ne kadar çıksın" diye düşünmüyor, sadece unutmak
# istemiyor. Varsayılan gürültülü olursa her kayıt bildirim yağmuruna dönüşüyor;
# gerçekten ısrar edilmesi gereken işi kullanıcı zaten kendi eliyle yükseltir.
DEFAULT_PRIORITY = 4

VALID_RECURRENCES = {"none", "daily", "weekly", "monthly"}


def normalize_priority(priority: Any) -> int:
    """1-4 aralığına sıkıştırır. Aralık dışı değer bildirim planı hesabını
    sessizce bozuyordu; artık en yakın geçerli değere çekiliyor."""
    try:
        return max(1, min(int(priority), 4))
    except (TypeError, ValueError):
        return DEFAULT_PRIORITY


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


# Bildirim anları: vadeye KAÇ DAKİKA KALA haber verilecek.
# Eksi değer vadeden sonrasını gösterir (-30 = vade geçtikten 30 dk sonra).
#
# Eskiden burada "kalan süreye göre her N dakikada bir tekrarla" vardı; tekrarın
# sonu olmadığı için tek bir kritik hatırlatıcı 34 bildirim üretebiliyordu ve
# "sadece vaktinde bir kez haber ver" diye bir seçenek yazılamıyordu. Sabit
# noktalarda kaç bildirim geleceği baştan belli: listenin uzunluğu kadar.
#
# Azalan sırada tutuluyor, `_aktif_nokta` en dar olanı seçiyor.
NOTIFICATION_POINTS = {
    1: [1440, 180, 60, 15, 0, -15, -30],   # Kritik  → 7 bildirim
    2: [1440, 60, 0, -30],                 # Önemli  → 4
    3: [60, 0],                            # Normal  → 2
    4: [0],                                # Sessiz  → 1 (yalnız vadesinde)
}

# Vade bu kadar dakika geçtikten sonra hatırlatıcı bildirim listesinden düşer.
# En geç bildirim noktasından (-30) sonrasına yer bırakıyor ki son nokta
# sunucu birkaç dakika meşgulken kaçırılmasın.
GIVE_UP_AFTER_MINUTES = 60


def get_notification_points(priority: int) -> List[int]:
    return NOTIFICATION_POINTS.get(normalize_priority(priority), NOTIFICATION_POINTS[DEFAULT_PRIORITY])


def _aktif_nokta(priority: int, minutes_remaining: float) -> Optional[int]:
    """Şu an hangi bildirim noktasının içindeyiz? Varılmamışsa None.

    Varılmış noktaların EN DARı seçilir — yani vadeye en yakın olanı. Sunucu
    bir süre kapalı kalıp birkaç nokta birden geçilmişse tek bildirim gider,
    üst üste yığılmaz.
    """
    varilan = [p for p in get_notification_points(priority) if minutes_remaining <= p]
    return min(varilan) if varilan else None


def bildirim_gerekli(reminder: Dict[str, Any], now: datetime) -> bool:
    """Bu hatırlatıcı şu an bildirilmeli mi?

    Tek bir damga hangi noktaların geçildiğini anlamaya yetiyor: damga anındaki
    kalan süre şu anki noktadan büyükse o nokta henüz duyurulmamış demektir.
    Böylece ayrı bir "hangi noktalar gönderildi" sütununa gerek kalmıyor.

    Hiç bildirilmemiş kayıtlarda vadeden ÖNCEKİ noktalar için `created_at`'e
    düşülüyor: kayıt kurulduğunda çoktan içinde olunan nokta "zaten biliniyor"
    sayılıyor. Olmasaydı iki saat sonrasına kurulan kritik bir hatırlatıcı, daha
    kaydedilir kaydedilmez "2 saat kaldı" bildirimi yollardı — kullanıcı onu bir
    saniye önce kendi yazdı.

    Vade anı ve sonrası bu kuralın dışında: hatırlatıcının varlık sebebi o an.
    Vadesi geçmiş olarak kurulan kayıt ("saat 3'e kurayım" derken saat 3'ü on
    dakika geçmişse) yine de haber vermeli.
    """
    due = parse_dt(reminder["due_datetime"])
    kalan = (due - now).total_seconds() / 60

    if kalan < -GIVE_UP_AFTER_MINUTES:
        return False

    nokta = _aktif_nokta(reminder["priority"], kalan)
    if nokta is None:
        return False

    referans = reminder["last_notified_at"]
    if not referans:
        if nokta <= 0:
            return True
        referans = reminder.get("created_at")
        if not referans:
            return True

    onceki_kalan = (due - parse_dt(referans)).total_seconds() / 60
    return onceki_kalan > nokta


def create_reminder(
    conn: sqlite3.Connection,
    owner_id: int,
    title: str,
    due_datetime: str,
    priority: int = DEFAULT_PRIORITY,
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
        # Erteleme ile aynı gerekçe: damga ŞU AN'a çekiliyor, sıfırlanmıyor.
        # Yeni vade zaten bir bildirim noktasının içine düşüyorsa, sıfır damga
        # kaydı düzenler düzenlemez bildirim yollardı.
        values.append(now_local().isoformat())
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
    now = now_local()
    new_due = now + timedelta(minutes=minutes)
    # Damga sıfırlanmıyor, ŞU ANA çekiliyor. Sıfırlansaydı sabit nokta modelinde
    # yeni vade zaten bir noktanın içinde kalacağı için bildirim erteleme tuşuna
    # basıldıktan hemen sonra geri gelirdi. Şimdiki damgayla nokta "duyurulmuş"
    # sayılıyor ve sıra ertelemenin bittiği ana geliyor.
    conn.execute(
        "UPDATE reminders SET due_datetime = ?, snooze_count = snooze_count + 1, "
        "last_notified_at = ? WHERE id = ? AND owner_id = ?",
        (new_due.isoformat(), now.isoformat(), reminder_id, owner_id),
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


def reschedule_overdue_recurring(
    conn: sqlite3.Connection, older_than_minutes: int = GIVE_UP_AFTER_MINUTES
) -> int:
    """Bildirim penceresinden düşmüş tekrarlayan hatırlatıcıları ileri sarar.

    `get_reminders_to_notify` vadesi `GIVE_UP_AFTER_MINUTES`'ten fazla geçmiş kayıtları
    listeden çıkarıyor (eski bildirimlerle boğmamak için). Ama ötelemeyi de o döngü yaptığı
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
    return [
        r for r in tum_hatirlaticilar(conn, include_completed=False)
        if bildirim_gerekli(r, now)
    ]


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

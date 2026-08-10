import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pytz

TZ = pytz.timezone("Europe/Istanbul")
VALID_CATEGORIES = {"yemek", "ulaşım", "eğlence", "fatura", "alışveriş", "diğer"}

# Negatif tutar = İADE. Bilinçli bir tasarım: ayrı bir tablo tutmak yerine eksi
# yazıyoruz, böylece aylık toplam ve bütçe uyarısı (ikisi de SUM(amount)) hiçbir
# ek koda gerek olmadan doğru sonuç veriyor.
#
# Sıfır anlamsız olduğu için reddedilir. Üst sınır ise okuma hatalarına karşı:
# fişteki "1.234,56" yanlışlıkla 123456 olarak okunursa fark edilsin.
MAX_ABS_AMOUNT = 1_000_000.0


class InvalidAmount(ValueError):
    """Tutar kabul edilebilir aralığın dışında"""


def validate_amount(amount: Any) -> float:
    try:
        value = float(amount)
    except (TypeError, ValueError):
        raise InvalidAmount("Tutar sayı olmalı")
    if value != value or value in (float("inf"), float("-inf")):
        raise InvalidAmount("Tutar geçersiz")
    if value == 0:
        raise InvalidAmount("Tutar sıfır olamaz")
    if abs(value) > MAX_ABS_AMOUNT:
        raise InvalidAmount(
            f"Tutar fazla büyük görünüyor ({value:,.2f}). Yanlış okunmuş olabilir."
        )
    return round(value, 2)


def is_refund(amount: float) -> bool:
    return amount < 0


def create_expense(
    conn: sqlite3.Connection,
    amount: float,
    category: str,
    description: str = "",
    expense_date: Optional[str] = None,
    source: str = "manual",
    source_hash: Optional[str] = None,
    source_at: Optional[str] = None,
) -> Dict[str, Any]:
    now = datetime.now(TZ)
    amount = validate_amount(amount)
    if category not in VALID_CATEGORIES:
        category = "diğer"
    if not expense_date:
        expense_date = now.strftime("%Y-%m-%d")

    cursor = conn.execute(
        """INSERT INTO expenses
             (amount, category, description, expense_date, created_at, source, source_hash, source_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (amount, category, description, expense_date, now.isoformat(),
         source, source_hash, source_at),
    )
    return get_expense_by_id(conn, cursor.lastrowid)


def parse_local(iso: Optional[str]) -> Optional[datetime]:
    """ISO metnini Europe/Istanbul saatine çevirir; saat dilimi yoksa yerel varsayar."""
    if not iso:
        return None
    try:
        parsed = datetime.fromisoformat(iso)
    except ValueError:
        return None
    return TZ.localize(parsed) if parsed.tzinfo is None else parsed.astimezone(TZ)


# Otomatik yakalanan kaynaklar. Elle girilenler (manual) bilerek dışarıda:
# kullanıcı aynı tutarı iki kez girdiyse bunu bilerek yapmıştır.
AUTO_SOURCES = ("notification", "sms", "receipt")


def find_duplicate(
    conn: sqlite3.Connection,
    amount: float,
    source_at: Optional[str] = None,
    window_minutes: int = 5,
    expense_date: Optional[str] = None,
    day_level: bool = False,
) -> Optional[Dict[str, Any]]:
    """Aynı alışveriş başka bir yoldan zaten kaydedilmiş mi?

    Aynı harcama banka uygulamasından, SMS'ten ve fiş fotoğrafından gelebiliyor;
    metinleri farklı olduğu için `source_hash` bunları eşleştiremez. Burada tutara
    ve zamana bakıyoruz.

    İki kıyaslama seviyesi var:
    - **Dakika**: iki kaydın da saati biliniyorsa, fark `window_minutes` içindeyse aynı sayılır.
    - **Gün** (`day_level=True`): saat bilinmiyorsa aynı gün + aynı tutar yeterli sayılır.
      Fiş fotoğrafında saat okunamayabildiği için gerekli; bildirim yolunda kullanılmaz
      çünkü orada saat her zaman var ve gün seviyesi fazla geniş kalır.

    Karşılaştırma `source_at` (olayın gerçekleştiği an) üzerinden yapılır, kayıt anı
    üzerinden değil — telefon çevrimdışıyken biriktirip sonra gönderdiğinde de doğru olsun diye.
    """
    reference = parse_local(source_at)
    day = reference.strftime("%Y-%m-%d") if reference else expense_date
    if not day:
        return None

    placeholders = ",".join("?" * len(AUTO_SOURCES))
    neighbours = conn.execute(
        f"""SELECT * FROM expenses
            WHERE source IN ({placeholders})
              AND expense_date IN (?, date(?, '-1 day'), date(?, '+1 day'))""",
        (*AUTO_SOURCES, day, day, day),
    ).fetchall()

    window = timedelta(minutes=window_minutes)
    same_day_match: Optional[Dict[str, Any]] = None

    for row in neighbours:
        if abs(row["amount"] - amount) > 0.005:
            continue

        other = parse_local(row["source_at"])
        if reference is not None and other is not None:
            if abs(other - reference) <= window:
                return dict(row)
            # İkisinin de saati belli ve aralık geniş → ayrı alışverişler
            continue

        # En az birinin saati yok; ancak gün seviyesinde kıyaslanabilir
        if day_level and row["expense_date"] == day and same_day_match is None:
            same_day_match = dict(row)

    return same_day_match


def get_expense_by_source_hash(conn: sqlite3.Connection, source_hash: str) -> Optional[Dict[str, Any]]:
    """Aynı bildirim daha önce işlendi mi? (tekrar kaydı önlemek için)"""
    row = conn.execute("SELECT * FROM expenses WHERE source_hash = ?", (source_hash,)).fetchone()
    return dict(row) if row else None


def update_expense_category(
    conn: sqlite3.Connection, expense_id: int, category: str
) -> Optional[Dict[str, Any]]:
    if category not in VALID_CATEGORIES:
        return None
    cursor = conn.execute(
        "UPDATE expenses SET category = ? WHERE id = ?", (category, expense_id)
    )
    if cursor.rowcount == 0:
        return None
    return get_expense_by_id(conn, expense_id)


def get_expense_by_id(conn: sqlite3.Connection, expense_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    return dict(row) if row else None


def list_expenses(
    conn: sqlite3.Connection,
    month: Optional[str] = None,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    query = "SELECT * FROM expenses WHERE 1=1"
    params: list = []

    if month:
        query += " AND expense_date LIKE ?"
        params.append(f"{month}%")
    if category:
        query += " AND category = ?"
        params.append(category)

    query += " ORDER BY expense_date DESC, created_at DESC"
    return [dict(r) for r in conn.execute(query, params).fetchall()]


def get_monthly_summary(
    conn: sqlite3.Connection,
    month: Optional[str] = None,
) -> Dict[str, Any]:
    if not month:
        month = datetime.now(TZ).strftime("%Y-%m")

    rows = conn.execute(
        "SELECT category, SUM(amount) as total FROM expenses WHERE expense_date LIKE ? GROUP BY category",
        (f"{month}%",),
    ).fetchall()

    by_category = {r["category"]: r["total"] for r in rows}
    total = sum(by_category.values())

    return {"month": month, "total": total, "by_category": by_category}


def delete_expense(conn: sqlite3.Connection, expense_id: int) -> bool:
    cursor = conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    return cursor.rowcount > 0


# ── Bütçe fonksiyonları ──────────────────────────────────────────────────────

def set_budget(conn: sqlite3.Connection, category: str, monthly_limit: float) -> Dict[str, Any]:
    now = datetime.now(TZ).isoformat()
    conn.execute(
        """INSERT INTO budgets (category, monthly_limit, created_at) VALUES (?, ?, ?)
           ON CONFLICT(category) DO UPDATE SET monthly_limit = excluded.monthly_limit""",
        (category, monthly_limit, now),
    )
    return get_budget_by_category(conn, category)


def get_budget_by_category(conn: sqlite3.Connection, category: str) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM budgets WHERE category = ?", (category,)).fetchone()
    return dict(row) if row else None


def get_all_budgets(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    return [dict(r) for r in conn.execute("SELECT * FROM budgets ORDER BY category").fetchall()]


def delete_budget(conn: sqlite3.Connection, category: str) -> bool:
    cursor = conn.execute("DELETE FROM budgets WHERE category = ?", (category,))
    return cursor.rowcount > 0


def check_budget_alert(conn: sqlite3.Connection, category: str, month: str = None) -> Optional[str]:
    """Kategori bütçesi %80+ kullanıldıysa uyarı mesajı döner, yoksa None"""
    if not month:
        month = datetime.now(TZ).strftime("%Y-%m")
    budget = get_budget_by_category(conn, category)
    if not budget:
        return None
    row = conn.execute(
        "SELECT SUM(amount) as total FROM expenses WHERE expense_date LIKE ? AND category = ?",
        (f"{month}%", category),
    ).fetchone()
    # İadeler eksi yazıldığı için toplamdan kendiliğinden düşüyor
    current = row["total"] or 0
    limit = budget["monthly_limit"]
    if current <= 0:
        return None
    pct = (current / limit) * 100
    if pct >= 100:
        return f"🚨 {category} bütçesi aşıldı! {current:.0f}/{limit:.0f} TL (%{pct:.0f})"
    if pct >= 80:
        return f"⚠️ {category} bütçesinin %{pct:.0f}'ini kullandın ({current:.0f}/{limit:.0f} TL)"
    return None

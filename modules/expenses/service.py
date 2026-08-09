import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional
import pytz

TZ = pytz.timezone("Europe/Istanbul")
VALID_CATEGORIES = {"yemek", "ulaşım", "eğlence", "fatura", "alışveriş", "diğer"}


def create_expense(
    conn: sqlite3.Connection,
    amount: float,
    category: str,
    description: str = "",
    expense_date: Optional[str] = None,
    source: str = "manual",
    source_hash: Optional[str] = None,
) -> Dict[str, Any]:
    now = datetime.now(TZ)
    if category not in VALID_CATEGORIES:
        category = "diğer"
    if not expense_date:
        expense_date = now.strftime("%Y-%m-%d")

    cursor = conn.execute(
        """INSERT INTO expenses (amount, category, description, expense_date, created_at, source, source_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (amount, category, description, expense_date, now.isoformat(), source, source_hash),
    )
    return get_expense_by_id(conn, cursor.lastrowid)


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
    current = row["total"] or 0
    limit = budget["monthly_limit"]
    pct = (current / limit) * 100
    if pct >= 100:
        return f"🚨 {category} bütçesi aşıldı! {current:.0f}/{limit:.0f} TL (%{pct:.0f})"
    if pct >= 80:
        return f"⚠️ {category} bütçesinin %{pct:.0f}'ini kullandın ({current:.0f}/{limit:.0f} TL)"
    return None

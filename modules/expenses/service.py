import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional
import pytz

TZ = pytz.timezone("Europe/Istanbul")
VALID_CATEGORIES = {"yemek", "ulaşım", "eğlence", "fatura", "diğer"}


def create_expense(
    conn: sqlite3.Connection,
    amount: float,
    category: str,
    description: str = "",
    expense_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Yeni harcama kaydeder"""
    now = datetime.now(TZ)
    if category not in VALID_CATEGORIES:
        category = "diğer"
    if not expense_date:
        expense_date = now.strftime("%Y-%m-%d")

    cursor = conn.execute(
        "INSERT INTO expenses (amount, category, description, expense_date, created_at) VALUES (?, ?, ?, ?, ?)",
        (amount, category, description, expense_date, now.isoformat()),
    )
    return get_expense_by_id(conn, cursor.lastrowid)


def get_expense_by_id(conn: sqlite3.Connection, expense_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    return dict(row) if row else None


def list_expenses(
    conn: sqlite3.Connection,
    month: Optional[str] = None,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """month formatı: YYYY-MM"""
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
    """Kategori bazlı aylık özet"""
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

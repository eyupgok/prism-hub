import sqlite3
from typing import List, Dict, Any, Optional
import pytz
from datetime import datetime

TZ = pytz.timezone("Europe/Istanbul")


def create_note(
    conn: sqlite3.Connection,
    title: str,
    content: str,
    category: str = "genel",
) -> Dict[str, Any]:
    """Yeni not oluşturur"""
    now = datetime.now(TZ).isoformat()
    cursor = conn.execute(
        "INSERT INTO notes (title, content, category, created_at) VALUES (?, ?, ?, ?)",
        (title, content, category, now),
    )
    return get_note_by_id(conn, cursor.lastrowid)


def get_note_by_id(conn: sqlite3.Connection, note_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    return dict(row) if row else None


def list_notes(conn: sqlite3.Connection, category: Optional[str] = None) -> List[Dict[str, Any]]:
    if category:
        rows = conn.execute(
            "SELECT * FROM notes WHERE category = ? ORDER BY created_at DESC",
            (category,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM notes ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def search_notes(conn: sqlite3.Connection, query: str) -> List[Dict[str, Any]]:
    """Başlık veya içerikte arama yapar"""
    rows = conn.execute(
        "SELECT * FROM notes WHERE title LIKE ? OR content LIKE ? ORDER BY created_at DESC",
        (f"%{query}%", f"%{query}%"),
    ).fetchall()
    return [dict(r) for r in rows]


def delete_note(conn: sqlite3.Connection, note_id: int) -> bool:
    cursor = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    return cursor.rowcount > 0

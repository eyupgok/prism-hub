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


def list_notes(
    conn: sqlite3.Connection,
    category: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    query = "SELECT * FROM notes"
    params: list = []
    if category:
        query += " WHERE category = ?"
        params.append(category)
    query += " ORDER BY created_at DESC"
    if limit is not None:
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, max(0, offset)])
    return [dict(r) for r in conn.execute(query, params).fetchall()]


def search_notes(
    conn: sqlite3.Connection,
    query: str,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Başlık veya içerikte arama yapar; istenirse kategoriyle daraltır"""
    sql = "SELECT * FROM notes WHERE (title LIKE ? OR content LIKE ?)"
    params: list = [f"%{query}%", f"%{query}%"]
    if category:
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY created_at DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def update_note(
    conn: sqlite3.Connection,
    note_id: int,
    title: Optional[str] = None,
    content: Optional[str] = None,
    category: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    fields, values = [], []
    if title is not None:
        fields.append("title = ?")
        values.append(title)
    if content is not None:
        fields.append("content = ?")
        values.append(content)
    if category is not None:
        fields.append("category = ?")
        values.append(category)
    if not fields:
        return get_note_by_id(conn, note_id)
    values.append(note_id)
    conn.execute(f"UPDATE notes SET {', '.join(fields)} WHERE id = ?", values)
    return get_note_by_id(conn, note_id)


def delete_note(conn: sqlite3.Connection, note_id: int) -> bool:
    cursor = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    return cursor.rowcount > 0

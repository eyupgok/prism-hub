"""Not işlemleri.

Sahiplik kuralı (üç modülde de aynı):

* **Okuma** fonksiyonları `owner_id`'yi *kimin verisine bakılacağı* olarak alır —
  ikiniz de birbirinizin notlarını görebiliyorsunuz, o yüzden burada kısıt yok.
* **Yazma** fonksiyonları `owner_id`'yi *giriş yapan kişi* olarak alır ve WHERE'e
  koyar. Başkasının kaydına yazmaya çalışan sorgu hiçbir satıra dokunmaz, fonksiyon
  da False/None döner. Rota bunu 403'e çevirir.

`owner_id`'nin varsayılan değeri bilerek yok: unutulan bir çağrı sessizce yanlış
kişiye yazmasın, Python hemen TypeError atsın.
"""

import sqlite3
from typing import List, Dict, Any, Optional
import pytz
from datetime import datetime

TZ = pytz.timezone("Europe/Istanbul")


def create_note(
    conn: sqlite3.Connection,
    owner_id: int,
    title: str,
    content: str,
    category: str = "genel",
) -> Dict[str, Any]:
    """Yeni not oluşturur"""
    now = datetime.now(TZ).isoformat()
    cursor = conn.execute(
        "INSERT INTO notes (owner_id, title, content, category, created_at) VALUES (?, ?, ?, ?, ?)",
        (owner_id, title, content, category, now),
    )
    return get_note_by_id(conn, cursor.lastrowid)


def get_note_by_id(conn: sqlite3.Connection, note_id: int) -> Optional[Dict[str, Any]]:
    """Sahibine bakmadan getirir — dönen kayıtta `owner_id` var, sahiplik kontrolünü
    rota yapar (böylece 'yok' ile 'senin değil' ayrı ayrı cevaplanabiliyor)."""
    row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    return dict(row) if row else None


def list_notes(
    conn: sqlite3.Connection,
    owner_id: int,
    category: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    query = "SELECT * FROM notes WHERE owner_id = ?"
    params: list = [owner_id]
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY created_at DESC"
    if limit is not None:
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, max(0, offset)])
    return [dict(r) for r in conn.execute(query, params).fetchall()]


def search_notes(
    conn: sqlite3.Connection,
    owner_id: int,
    query: str,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Başlık veya içerikte arama yapar; istenirse kategoriyle daraltır"""
    sql = "SELECT * FROM notes WHERE owner_id = ? AND (title LIKE ? OR content LIKE ?)"
    params: list = [owner_id, f"%{query}%", f"%{query}%"]
    if category:
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY created_at DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def update_note(
    conn: sqlite3.Connection,
    owner_id: int,
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
    values.extend([note_id, owner_id])
    cursor = conn.execute(
        f"UPDATE notes SET {', '.join(fields)} WHERE id = ? AND owner_id = ?", values
    )
    if cursor.rowcount == 0:
        return None          # yok ya da başkasının
    return get_note_by_id(conn, note_id)


def delete_note(conn: sqlite3.Connection, owner_id: int, note_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM notes WHERE id = ? AND owner_id = ?", (note_id, owner_id)
    )
    return cursor.rowcount > 0

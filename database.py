import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import List, Dict

import pytz

DB_PATH = os.getenv("DATABASE_PATH", "prism.db")
_TZ = pytz.timezone("Europe/Istanbul")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_message(chat_id: str, role: str, content: str):
    """Konuşma geçmişine mesaj ekler"""
    now = datetime.now(_TZ).isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO conversations (chat_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (chat_id, role, content, now),
        )


def get_recent_messages(chat_id: str, limit: int = 10) -> List[Dict]:
    """Son N mesajı kronolojik sırada döner"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT role, content FROM conversations WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (chat_id, limit),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def delete_old_conversations(days: int = 30) -> int:
    """Belirtilen günden eski konuşma kayıtlarını siler, silinen satır sayısını döner"""
    cutoff = (datetime.now(_TZ) - timedelta(days=days)).isoformat()
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM conversations WHERE created_at < ?", (cutoff,))
        return cursor.rowcount


def init_db():
    """Tüm modül tablolarını oluşturur"""
    from modules.reminders.models import create_reminders_table
    from modules.notes.models import create_notes_table
    from modules.expenses.models import create_expenses_table, create_budgets_table

    with get_db() as conn:
        create_reminders_table(conn)
        create_notes_table(conn)
        create_expenses_table(conn)
        create_budgets_table(conn)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id    TEXT    NOT NULL,
                role       TEXT    NOT NULL,
                content    TEXT    NOT NULL,
                created_at TEXT    NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_chat ON conversations(chat_id)")

    print("✅ Veritabanı başlatıldı")

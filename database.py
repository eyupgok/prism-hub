import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.getenv("DATABASE_PATH", "prism.db")


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


def init_db():
    """Tüm modül tablolarını oluşturur"""
    from modules.reminders.models import create_reminders_table
    from modules.notes.models import create_notes_table
    from modules.expenses.models import create_expenses_table

    with get_db() as conn:
        create_reminders_table(conn)
        create_notes_table(conn)
        create_expenses_table(conn)

    print("✅ Veritabanı başlatıldı")

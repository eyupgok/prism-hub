import sqlite3

from modules.auth.models import sahiplik_sutunu_ekle


def create_notes_table(conn: sqlite3.Connection):
    """Notlar tablosunu oluşturur"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT    NOT NULL,
            content     TEXT    NOT NULL,
            category    TEXT    NOT NULL DEFAULT 'genel',
            created_at  TEXT    NOT NULL
        )
    """)
    _migrate_notes(conn)


def _migrate_notes(conn: sqlite3.Connection):
    """Eski veritabanlarına sonradan eklenen sütunları ekler (idempotent)."""
    sahiplik_sutunu_ekle(conn, "notes")

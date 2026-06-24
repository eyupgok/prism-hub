import sqlite3


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

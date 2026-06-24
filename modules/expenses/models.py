import sqlite3


def create_expenses_table(conn: sqlite3.Connection):
    """Harcamalar tablosunu oluşturur"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            amount       REAL    NOT NULL,
            category     TEXT    NOT NULL DEFAULT 'diğer',
            description  TEXT    NOT NULL DEFAULT '',
            expense_date TEXT    NOT NULL,
            created_at   TEXT    NOT NULL
        )
    """)

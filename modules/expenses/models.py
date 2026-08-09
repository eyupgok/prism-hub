import sqlite3


def create_expenses_table(conn: sqlite3.Connection):
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
    _migrate_expenses(conn)


def _migrate_expenses(conn: sqlite3.Connection):
    """Eski veritabanlarına yeni sütunları ekler (ALTER TABLE tekrar çalıştırılamaz)."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(expenses)")}

    if "source" not in existing:
        # manual | telegram | notification | sms
        conn.execute("ALTER TABLE expenses ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'")

    if "source_hash" not in existing:
        # Bildirim/SMS metninin özeti — aynı bildirim iki kez gelirse ikinci kayıt açılmasın.
        # Ham metin saklanmaz, sadece bu özet.
        conn.execute("ALTER TABLE expenses ADD COLUMN source_hash TEXT")

    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_expenses_source_hash
        ON expenses(source_hash) WHERE source_hash IS NOT NULL
    """)


def create_budgets_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            category      TEXT    NOT NULL UNIQUE,
            monthly_limit REAL    NOT NULL,
            created_at    TEXT    NOT NULL
        )
    """)

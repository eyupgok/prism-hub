import sqlite3


def create_reminders_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            title            TEXT    NOT NULL,
            due_datetime     TEXT    NOT NULL,
            priority         INTEGER NOT NULL DEFAULT 3,
            is_completed     INTEGER NOT NULL DEFAULT 0,
            last_notified_at TEXT,
            snooze_count     INTEGER NOT NULL DEFAULT 0,
            recurrence       TEXT    NOT NULL DEFAULT 'none',
            created_at       TEXT    NOT NULL
        )
    """)
    # Mevcut DB'ler için migration
    try:
        conn.execute("ALTER TABLE reminders ADD COLUMN recurrence TEXT NOT NULL DEFAULT 'none'")
    except Exception:
        pass

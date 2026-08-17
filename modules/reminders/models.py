import sqlite3

from modules.auth.models import sahiplik_sutunu_ekle


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
    _migrate_reminders(conn)


def _migrate_reminders(conn: sqlite3.Connection):
    """Eski veritabanlarına sonradan eklenen sütunları ekler (idempotent)."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(reminders)")}

    if "recurrence" not in existing:
        conn.execute("ALTER TABLE reminders ADD COLUMN recurrence TEXT NOT NULL DEFAULT 'none'")

    if "completed_at" not in existing:
        # Tamamlanma anı: "bugün kaç görev bitirdin", "bu hafta nasıl geçti" gibi
        # sorulara cevap verebilmek için gerekli. Sadece is_completed=1 bilgisi
        # ne zaman olduğunu söylemiyor.
        conn.execute("ALTER TABLE reminders ADD COLUMN completed_at TEXT")

    sahiplik_sutunu_ekle(conn, "reminders")

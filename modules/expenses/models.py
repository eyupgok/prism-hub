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


def create_budgets_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            category      TEXT    NOT NULL UNIQUE,
            monthly_limit REAL    NOT NULL,
            created_at    TEXT    NOT NULL
        )
    """)

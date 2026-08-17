import sqlite3

from modules.auth.models import SAHIP_VARSAYILAN, sahiplik_sutunu_ekle
from logging_setup import get_logger

log = get_logger("prism.expenses.models")


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

    if "source_at" not in existing:
        # Bildirimin TELEFONA DÜŞTÜĞÜ an (kaydedildiği an değil). Telefon çevrimdışıyken
        # biriktirip sonra gönderdiğinde çift kayıt kontrolü doğru çalışsın diye gerekli.
        conn.execute("ALTER TABLE expenses ADD COLUMN source_at TEXT")

    sahiplik_sutunu_ekle(conn, "expenses")

    # Çift kayıt koruması artık kullanıcı başına. Eski indeks source_hash'i TÜM tabloda
    # tekil sayıyordu; iki kişide aynı özet teorik olarak çakışıp ikinci kişinin kaydını
    # sessizce yutabilirdi. Sütun listesi değiştiği için indeksi düşürüp yeniden kuruyoruz
    # (indeks yeniden kurmak ucuz, tablo yeniden kurmak gerekmiyor).
    if not _indeks_sutunlari(conn, "idx_expenses_source_hash") == ["owner_id", "source_hash"]:
        conn.execute("DROP INDEX IF EXISTS idx_expenses_source_hash")
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_expenses_source_hash
        ON expenses(owner_id, source_hash) WHERE source_hash IS NOT NULL
    """)


def _indeks_sutunlari(conn: sqlite3.Connection, ad: str) -> list:
    """İndeksin hangi sütunlardan kurulduğunu döner; indeks yoksa boş liste."""
    return [row["name"] for row in conn.execute(f"PRAGMA index_info({ad})")]


def create_budgets_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id      INTEGER NOT NULL DEFAULT 1,
            category      TEXT    NOT NULL,
            monthly_limit REAL    NOT NULL,
            created_at    TEXT    NOT NULL,
            UNIQUE(owner_id, category)
        )
    """)
    _migrate_budgets(conn)


def _migrate_budgets(conn: sqlite3.Connection):
    """budgets'ı tekillik kuralı kullanıcı başına olacak şekilde yeniden kurar.

    Eski tanımda `category TEXT NOT NULL UNIQUE` vardı — yani "yemek" bütçesini
    ikinizden yalnızca biri koyabilirdi, ikincisi sessizce reddedilirdi. Sütun
    seviyesindeki UNIQUE kısıtı SQLite'ta ALTER TABLE ile kaldırılamıyor; tek yol
    tabloyu yeniden kurup veriyi taşımak.

    Idempotent: owner_id sütunu zaten varsa tablo yeni tanımdadır, dokunulmaz.
    """
    mevcut = {row["name"] for row in conn.execute("PRAGMA table_info(budgets)")}
    if "owner_id" in mevcut:
        return

    log.info("budgets tablosu yeniden kuruluyor (category UNIQUE → UNIQUE(owner_id, category))")
    conn.execute("""
        CREATE TABLE budgets_yeni (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id      INTEGER NOT NULL DEFAULT 1,
            category      TEXT    NOT NULL,
            monthly_limit REAL    NOT NULL,
            created_at    TEXT    NOT NULL,
            UNIQUE(owner_id, category)
        )
    """)
    # id'ler korunuyor: panel ve Android silme/düzenlemede bu id'yi kullanıyor.
    conn.execute(
        "INSERT INTO budgets_yeni (id, owner_id, category, monthly_limit, created_at) "
        "SELECT id, ?, category, monthly_limit, created_at FROM budgets",
        (SAHIP_VARSAYILAN,),
    )
    tasinan = conn.execute("SELECT COUNT(*) AS n FROM budgets_yeni").fetchone()["n"]
    conn.execute("DROP TABLE budgets")
    conn.execute("ALTER TABLE budgets_yeni RENAME TO budgets")
    log.info("budgets yeniden kuruldu, %s kayıt taşındı", tasinan)

import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import List, Dict

import pytz

from logging_setup import get_logger

log = get_logger("prism.database")

DB_PATH = os.getenv("DATABASE_PATH", "prism.db")
_TZ = pytz.timezone("Europe/Istanbul")


def get_connection() -> sqlite3.Connection:
    # timeout: zamanlayıcı her dakika yazıyor; buna panelden gelen istek veya bir
    # banka bildirimi denk gelirse SQLite varsayılan olarak HİÇ beklemeden
    # "database is locked" atıyor. 5 saniye beklemek bu çakışmaları görünmez kılar.
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
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


def save_message(chat_id: str, role: str, content: str, gorunen: str = None):
    """Konuşma geçmişine mesaj ekler.

    İki sütun, iki ayrı okur kitle:

    - `content` → **modelin gördüğü**. Asistan tarafında bu ham JSON komut
      (`{"module": "reminders", ...}`); modelin bir sonraki turda kendi
      çıktı biçimini görmesi gerekiyor.
    - `gorunen` → **insanın gördüğü**. NULL ise ikisi aynı demektir
      (kullanıcının düz yazdığı mesaj gibi).

    Ayrım panelde sohbet geçmişini gösterebilmek için açıldı: ekrana ham
    JSON basılamaz, ama modele de formatlanmış metin verilemez.
    """
    now = datetime.now(_TZ).isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO conversations (chat_id, role, content, gorunen, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (chat_id, role, content, gorunen, now),
        )


def get_recent_messages(chat_id: str, limit: int = 10) -> List[Dict]:
    """Son N mesajı kronolojik sırada döner — MODELE bağlam olarak gider.

    Bilerek `gorunen`'e bakmıyor: model kendi ürettiği JSON'u görmeli.
    """
    with get_db() as conn:
        rows = conn.execute(
            "SELECT role, content FROM conversations WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (chat_id, limit),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def get_conversation(chat_id: str, limit: int = 60) -> List[Dict]:
    """Panelde gösterilecek okunur geçmiş — EKRANA gider.

    `gorunen` yoksa `content`'e düşer; eski kayıtlarda (sütun eklenmeden önce
    yazılanlar) asistan satırı ham JSON olduğu için ELENİR. Kullanıcıya
    `{"module": ...}` göstermektense o satırı hiç göstermemek daha iyi.
    """
    with get_db() as conn:
        rows = conn.execute(
            "SELECT role, content, gorunen, created_at FROM conversations "
            "WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (chat_id, limit),
        ).fetchall()

    gecmis = []
    for r in reversed(rows):
        metin = r["gorunen"] or r["content"]
        if r["role"] == "assistant" and not r["gorunen"]:
            continue
        gecmis.append({"role": r["role"], "metin": metin, "created_at": r["created_at"]})
    return gecmis


def delete_old_conversations(days: int = 30) -> int:
    """Belirtilen günden eski konuşma kayıtlarını siler, silinen satır sayısını döner"""
    cutoff = (datetime.now(_TZ) - timedelta(days=days)).isoformat()
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM conversations WHERE created_at < ?", (cutoff,))
        return cursor.rowcount


def _migrate_gorunen(conn: sqlite3.Connection):
    """Konuşmanın insan tarafı (idempotent).

    Sütun sonradan eklendi: eski satırlarda NULL kalır, yani eski asistan
    yanıtları panelde görünmez (ham JSON'du). Kullanıcı mesajları eskiden de
    okunur olduğu için onlar `content`'ten çiziliyor.
    """
    mevcut = {row["name"] for row in conn.execute("PRAGMA table_info(conversations)")}
    if "gorunen" not in mevcut:
        conn.execute("ALTER TABLE conversations ADD COLUMN gorunen TEXT")


def init_db():
    """Tüm modül tablolarını oluşturur"""
    from modules.auth.models import create_users_table
    from modules.reminders.models import create_reminders_table
    from modules.notes.models import create_notes_table
    from modules.expenses.models import create_expenses_table, create_budgets_table
    from modules.gozlem.models import create_gozlem_tables
    from modules.iletiler.models import create_iletiler_table

    with get_db() as conn:
        # Önce kullanıcılar: veri tablolarının owner_id göçü buradaki id'ye atıyor.
        create_users_table(conn)
        create_reminders_table(conn)
        create_notes_table(conn)
        create_expenses_table(conn)
        create_budgets_table(conn)
        create_gozlem_tables(conn)
        create_iletiler_table(conn)
        # conversations'a owner_id EKLENMİYOR — bilerek. Bu tablo yalnızca
        # get_recent_messages() tarafından, yalnızca Groq'a bağlam vermek için
        # okunuyor ve zaten chat_id'ye göre süzülüyor. İki kişinin chat_id'si
        # farklı olduğundan bağlamlar en baştan ayrı. Kullanılmayan bir sütun
        # eklemek yerine ayrımın chat_id'de olduğunu burada yazmak daha doğru.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id    TEXT    NOT NULL,
                role       TEXT    NOT NULL,
                content    TEXT    NOT NULL,
                gorunen    TEXT,
                created_at TEXT    NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_chat ON conversations(chat_id)")
        _migrate_gorunen(conn)

    log.info("✅ Veritabanı başlatıldı")

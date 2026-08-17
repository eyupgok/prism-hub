"""Testler geçici bir veritabanı kullanır — gerçek prism.db'ye asla dokunulmaz.

Çalıştırmak için:  pytest -q
"""

import os
import tempfile

import pytest

# database.py modül seviyesinde DB_PATH'i okuduğu için import'tan ÖNCE ayarlanmalı
os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.mkdtemp(), "test.db"))


# Testlerde kullanılan iki sahip. Çok kullanıcılı yapıdan sonra her kaydın bir
# sahibi olmak zorunda; ikincisi "başkasının kaydına dokunamaz" testleri için.
SAHIP = 1
OTEKI = 2


@pytest.fixture()
def db():
    """Her test için boş bir veritabanı + iki kayıtlı kullanıcı verir."""
    from database import get_db, init_db

    path = os.path.join(tempfile.mkdtemp(), "case.db")
    os.environ["DATABASE_PATH"] = path

    import database
    database.DB_PATH = path

    init_db()
    with get_db() as conn:
        for uid, ad, chat in ((SAHIP, "Test", "111"), (OTEKI, "Öteki", "222")):
            conn.execute(
                "INSERT OR IGNORE INTO users (id, ad, telegram_chat_id, parola_hash, created_at) "
                "VALUES (?, ?, ?, 'scrypt$00$00', '2026-01-01T00:00:00')",
                (uid, ad, chat),
            )
        yield conn

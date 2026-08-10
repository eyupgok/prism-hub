"""Testler geçici bir veritabanı kullanır — gerçek prism.db'ye asla dokunulmaz.

Çalıştırmak için:  pytest -q
"""

import os
import tempfile

import pytest

# database.py modül seviyesinde DB_PATH'i okuduğu için import'tan ÖNCE ayarlanmalı
os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.mkdtemp(), "test.db"))


@pytest.fixture()
def db():
    """Her test için boş bir veritabanı verir."""
    from database import get_db, init_db

    path = os.path.join(tempfile.mkdtemp(), "case.db")
    os.environ["DATABASE_PATH"] = path

    import database
    database.DB_PATH = path

    init_db()
    with get_db() as conn:
        yield conn

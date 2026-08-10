"""Yedek gerçekten geri yüklenebilir mi?

Bir yedeğin tek işe yarar testi budur: açılabiliyor ve veri içinde mi.
"""

import gzip
import os
import sqlite3
import tempfile

import backup
from modules.expenses import service as exp_svc


def test_yedek_geri_yuklenebilir(db):
    exp_svc.create_expense(db, 185.50, "yemek", "Test harcaması", "2026-08-09")
    db.commit()

    blob = backup.create_snapshot()
    assert blob[:2] == b"\x1f\x8b", "gzip başlığı yok"

    raw = gzip.decompress(blob)
    assert raw[:15] == b"SQLite format 3", "geçerli bir SQLite dosyası değil"

    restored_path = os.path.join(tempfile.mkdtemp(), "restored.db")
    with open(restored_path, "wb") as f:
        f.write(raw)

    conn = sqlite3.connect(restored_path)
    try:
        rows = conn.execute(
            "SELECT amount, description FROM expenses WHERE description = 'Test harcaması'"
        ).fetchall()
    finally:
        conn.close()

    assert rows == [(185.50, "Test harcaması")]

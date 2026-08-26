"""Kullanıcı tablosu ve ilk kurulum göçü.

Sistem tek kişilikken kimlik diye bir şey yoktu: panel parolası `PANEL_PASSWORD`
env'inde tek bir düz metindi, Telegram'da tek bir `TELEGRAM_CHAT_ID` kabul ediliyordu.
Artık her kaydın bir sahibi var; sahiplik bu tablodan geliyor.

Göç bilerek **sessiz ve kırılmaz**: mevcut veritabanı ilk kez açıldığında env'deki
parola ve chat_id ile tek bir kullanıcı (id=1) yaratılır ve bütün eski kayıtlar
ona atanır. Yani bu kod yayına alındığında Eyüp'ün hiçbir şeyi değişmez —
ikinci kullanıcı ayrıca `kullanici.py` ile eklenir.
"""

import os
import sqlite3
from datetime import datetime

import pytz

from auth import hash_password
from logging_setup import get_logger

log = get_logger("prism.users")

_TZ = pytz.timezone("Europe/Istanbul")

# Göçte eski kayıtların atandığı sahip. Tek kişilik dönemden kalan her şey Eyüp'ün.
SAHIP_VARSAYILAN = 1


def create_users_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            ad               TEXT    NOT NULL,
            telegram_chat_id TEXT    UNIQUE,
            parola_hash      TEXT    NOT NULL,
            created_at       TEXT    NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_chat ON users(telegram_chat_id)")
    _migrate_konum(conn)
    _migrate_hitap(conn)
    _seed_ilk_kullanici(conn)


def _migrate_hitap(conn: sqlite3.Connection):
    """Kişiye nasıl hitap edileceği — "Bey", "Hanım" (idempotent).

    Asistan resmî bir üslupla konuşuyor ve doğru hitabı bilmesi gerekiyor.
    Bu ADDAN ÇIKARILMIYOR: isme bakıp cinsiyet tahmin etmek yanlış sonuç
    verebilen bir iş, yanlış hitap da gerçek bir kişiyi rahatsız eder.
    Elle ayarlanıyor: `python kullanici.py hitap "<ad>" "Bey"`.

    NULL kalırsa asistan cinsiyetten bağımsız "efendim" ile idare eder —
    yani hiç doldurulmasa da üslup bozulmaz.
    """
    mevcut = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    if "hitap" not in mevcut:
        conn.execute("ALTER TABLE users ADD COLUMN hitap TEXT")


def _migrate_konum(conn: sqlite3.Connection):
    """Kişi başına hava durumu konumu (idempotent).

    Hepsi NULL başlar; NULL olan kullanıcı için env'deki WEATHER_* değerleri
    (Elazığ) kullanılır. Yani konum verilmeden de her şey eskisi gibi çalışır.
    """
    mevcut = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    for sutun, tip in (("sehir", "TEXT"), ("enlem", "REAL"),
                       ("boylam", "REAL"), ("konum_at", "TEXT")):
        if sutun not in mevcut:
            conn.execute(f"ALTER TABLE users ADD COLUMN {sutun} {tip}")


def _seed_ilk_kullanici(conn: sqlite3.Connection):
    """Tablo boşsa env'deki ayarlardan ilk kullanıcıyı yaratır.

    Amaç: bu sürüm sunucuya çıktığında Eyüp'ün girişinin bozulmaması. Parolası
    aynı kalır (artık düz metin değil, karması saklanır), Telegram'ı aynı çalışır.

    PANEL_PASSWORD yoksa kullanıcı yaratılmaz — parolasız bir hesap açıp herkesi
    içeri almaktansa panel girişinin kapalı kalması doğru davranış.
    """
    if conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        return

    parola = os.getenv("PANEL_PASSWORD", "")
    if not parola:
        log.warning(
            "PANEL_PASSWORD yok — ilk kullanıcı yaratılmadı. "
            "Panel girişi kapalı kalacak; kullanici.py ile ekle."
        )
        return

    conn.execute(
        "INSERT INTO users (id, ad, telegram_chat_id, parola_hash, created_at) VALUES (?, ?, ?, ?, ?)",
        (
            SAHIP_VARSAYILAN,
            os.getenv("PANEL_USER_NAME", "Eyüp"),
            os.getenv("TELEGRAM_CHAT_ID", "") or None,
            hash_password(parola),
            datetime.now(_TZ).isoformat(),
        ),
    )
    log.info("İlk kullanıcı env'den oluşturuldu (id=%s)", SAHIP_VARSAYILAN)


def sahiplik_sutunu_ekle(conn: sqlite3.Connection, tablo: str):
    """Veri tablosuna `owner_id` ekler. Her modülün models.py'si bunu çağırır.

    `REFERENCES users(id)` **bilerek yok**: SQLite, yabancı anahtar kontrolü
    açıkken (bizde açık) ALTER TABLE ile eklenen REFERENCES'lı sütunun
    varsayılanının NULL olmasını şart koşuyor — bize ise NOT NULL DEFAULT 1
    lazım, çünkü mevcut satırların hepsi bir sahibe geçmeli. Bütünlüğü
    uygulama katmanı koruyor: owner_id her zaman giriş yapmış kullanıcıdan
    geliyor, dışarıdan alınmıyor.
    """
    mevcut = {row["name"] for row in conn.execute(f"PRAGMA table_info({tablo})")}
    if "owner_id" not in mevcut:
        conn.execute(
            f"ALTER TABLE {tablo} ADD COLUMN owner_id INTEGER NOT NULL "
            f"DEFAULT {SAHIP_VARSAYILAN}"
        )
        log.info("%s tablosuna owner_id eklendi (eski kayıtlar id=%s'e atandı)",
                 tablo, SAHIP_VARSAYILAN)
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{tablo}_owner ON {tablo}(owner_id)"
    )

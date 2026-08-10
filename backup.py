"""Veritabanı yedeği — her gece Telegram'a dosya olarak gönderilir.

Neden Telegram: sunucu tamamen kaybolsa bile (disk arızası, hesap kapanması,
yanlışlıkla silme) yedek telefonundaki sohbette duruyor. Ücretsiz, kurulum
gerektirmeyen, sunucudan bağımsız bir kopya.

Neden `sqlite3.Connection.backup()`: dosyayı düpedüz kopyalamak, o sırada bir
yazma sürüyorsa bozuk bir kopya üretir. WAL modunda ayrıca `-wal` dosyasındaki
değişiklikler ana dosyaya işlenmemiş olabilir. Backup API tutarlı bir anlık
görüntü alır ve WAL'i de içerir.
"""

import gzip
import os
import sqlite3
import tempfile
from datetime import datetime

import pytz

TZ = pytz.timezone("Europe/Istanbul")

# Telegram sendDocument sınırı 50 MB; sıkıştırılmış yedek bunu aşarsa gönderilemez.
TELEGRAM_FILE_LIMIT = 50 * 1024 * 1024


def create_snapshot() -> bytes:
    """Veritabanının tutarlı bir kopyasını alıp gzip'lenmiş olarak döner."""
    from database import DB_PATH, get_connection

    tmp_path = None
    try:
        # delete=False: Windows'ta açık dosya ikinci kez açılamıyor
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_path = tmp.name

        source = get_connection()
        try:
            target = sqlite3.connect(tmp_path)
            try:
                source.backup(target)
            finally:
                target.close()
        finally:
            source.close()

        with open(tmp_path, "rb") as f:
            return gzip.compress(f.read(), compresslevel=6)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _human_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.0f} KB"
    return f"{num_bytes / (1024 * 1024):.1f} MB"


async def send_backup() -> bool:
    """Yedeği alır ve Telegram'a gönderir. Başarılıysa True döner."""
    from database import DB_PATH, get_db
    from telegram_bot import send_document, send_message

    now = datetime.now(TZ)
    filename = f"prism-{now.strftime('%Y-%m-%d')}.db.gz"

    try:
        blob = create_snapshot()
    except Exception as e:
        print(f"❌ Yedek alınamadı: {type(e).__name__}: {e}")
        try:
            await send_message(f"❌ Veritabanı yedeği alınamadı: {type(e).__name__}")
        except Exception:
            pass
        return False

    if len(blob) > TELEGRAM_FILE_LIMIT:
        print(f"❌ Yedek çok büyük ({_human_size(len(blob))}), Telegram'a gönderilemez")
        await send_message(
            f"⚠️ Veritabanı yedeği {_human_size(len(blob))} oldu, Telegram sınırını (50 MB) aştı.\n"
            "Yedekleme için başka bir yol kurmak gerekiyor."
        )
        return False

    # Kaç kayıt olduğunu da yazalım — yedeğin dolu geldiğini görmek için
    try:
        with get_db() as conn:
            counts = {
                table: conn.execute(f"SELECT COUNT(*) c FROM {table}").fetchone()["c"]
                for table in ("reminders", "notes", "expenses", "budgets")
            }
        summary = " · ".join(f"{k}: {v}" for k, v in counts.items())
    except Exception:
        summary = ""

    raw_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    caption = (
        f"🗄 <b>PRISM yedeği</b> — {now.strftime('%d.%m.%Y')}\n"
        f"{_human_size(raw_size)} → {_human_size(len(blob))} (sıkıştırılmış)"
    )
    if summary:
        caption += f"\n<i>{summary}</i>"

    result = await send_document(blob, filename, caption)
    if result.get("ok"):
        print(f"✅ Yedek gönderildi: {filename} ({_human_size(len(blob))})")
        return True

    print(f"❌ Yedek gönderilemedi: {result}")
    return False

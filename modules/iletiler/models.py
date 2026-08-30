"""İletiler — bir kullanıcının diğerine, asistanın ağzından ilettiği sözler.

## Neden ayrı bir tablo

"Zeynep'e akşam yedide şunu söyle" cümlesi mevcut hiçbir tabloya sığmıyor:

- **Hatırlatıcı değil.** Alıcı bunu bir görev olarak görmemeli, "tamamla"
  diyememeli, sabah özetinde iş listesinde çıkmamalı. `reminders`'a
  yazılsaydı üçü de olurdu.
- **Not değil.** Kimse bir şey saklamak istemiyor.
- **Takip değil.** Takip, kullanıcının kendi ağzından çıkan bir olayın
  sonucunu SORMAK için; burada sorulacak bir şey yok, iletilecek bir şey var.

Yapısı takibe benziyor (tek seferlik, zamanı gelince gönderilir, bir kez
gönderilir) ama sahibi ters: kaydı **gönderen** oluşturuyor, mesaj **alıcının**
sohbetine düşüyor.

## İki kip: imzalı ve imzasız

| | `imzasiz = 0` (varsayılan) | `imzasiz = 1` |
|---|---|---|
| Alıcı ne görür | "Eyüp Bey şunu iletmemi istedi, efendim: «...»" | asistanın kendi cümlesi |
| Kaynak | görünür | görünmez |
| Ne zaman | "Zeynep'e şunu söyle" | "kendi ağzından söyle", "benden geldiğini belli etme" |

⚠️ **Varsayılan imzalı ve şüphe imzalıdan yana çözülür.** Kaynağı boş yere
göstermek geri alınabilir bir fazlalık; göstermemek geri alınamaz. Kural
`ai_router` yönergesinde de açıkça yazılı.

## Sahiplik burada neden farklı

Projenin her yerinde `owner_id` "bu kayıt kimin" demek. Burada iki taraf var
ve ikisi de gerçek: `gonderen_id` kaydı kimin oluşturduğu (iptal etme hakkı
onda), `alici_id` mesajın kime gideceği. Tek bir `owner_id` yazılsaydı
"Zeynep'e giden ama Eyüp'ün iptal edebildiği" kayıt ifade edilemezdi.
"""

import sqlite3

from logging_setup import get_logger

log = get_logger("prism.iletiler")

# Bir kişinin aynı anda bekletebileceği azami ileti. Sınır, asistanı
# başkasına mesaj yağdırma aracına çevirmemek için: alıcı bu mesajları
# istemedi, gönderenin iyi niyetine güveniyor.
AZAMI_BEKLEYEN = 10

# Zamanı geçmiş ama gönderilememiş ileti bu kadar dakika sonra düşer.
# Sunucu kapalı kaldıysa "dört saat gecikmiş akşam mesajı" iletmek,
# iletmemekten kötü — bağlamı çoktan geçmiş olur.
VAZGECME_DAKIKA = 60


def create_iletiler_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS iletiler (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            gonderen_id    INTEGER NOT NULL,
            alici_id       INTEGER NOT NULL,
            mesaj          TEXT    NOT NULL,
            iletilecek_at  TEXT    NOT NULL,
            iletildi_at    TEXT,
            imzasiz        INTEGER NOT NULL DEFAULT 0,
            created_at     TEXT    NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ileti_bekleyen "
        "ON iletiler(iletilecek_at) WHERE iletildi_at IS NULL"
    )
    _migrate_imzasiz(conn)


def _migrate_imzasiz(conn: sqlite3.Connection):
    """İletinin kaynağı görünsün mü (idempotent).

    ⚠️ **DEFAULT 0 = imzalı**, yani eski kayıtlar ve belirsiz her durum
    kaynağı GÖSTEREN biçimde gider. Varsayılanın bu yönde olması bilinçli:
    kaynağı göstermek geri alınabilir bir fazlalık, göstermemek değil.
    """
    mevcut = {row["name"] for row in conn.execute("PRAGMA table_info(iletiler)")}
    if "imzasiz" not in mevcut:
        conn.execute("ALTER TABLE iletiler ADD COLUMN imzasiz INTEGER NOT NULL DEFAULT 0")

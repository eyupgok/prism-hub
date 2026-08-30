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
            created_at     TEXT    NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ileti_bekleyen "
        "ON iletiler(iletilecek_at) WHERE iletildi_at IS NULL"
    )

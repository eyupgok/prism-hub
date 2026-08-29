"""Gözlem katmanının tabloları: hafıza, karar günlüğü, ilerleme damgası.

Bu modül PRISM'e ikinci bir döngü ekliyor. Şimdiye kadar asistanın gönderdiği
her mesajın sebebi ya kullanıcının bir cümlesiydi ya da bir saat (08:00 özeti,
hatırlatıcı alarmı). Üçüncü bir sebep yoktu: **fark ettiği için** konuşmak.

Üç tablo var, üçü de o döngünün parçası:

- `hafiza`         → asistanın kişi hakkında biriktirdiği kalıcı bilgiler
- `gozlem_gunlugu` → her gözlem turunda ne karar verildiği (SUSTUĞU turlar dahil)
- `gozlem_durum`   → hafıza çıkarımının nereye kadar geldiği (damga)

Kendiliğinden mesaj yollamak **varsayılan olarak kapalı**: `users.gozlem_sinir`
sıfır başlar. Bu sürüm sunucuya çıktığında kimseye sürpriz bildirim gitmez;
açmak için `gozlem.py seviye "<ad>" 3` çalıştırmak gerekir.
"""

import sqlite3

from logging_setup import get_logger
from modules.auth.models import sahiplik_sutunu_ekle

log = get_logger("prism.gozlem")

# Hafıza kayıtlarının türleri. Yalnızca okunabilirlik için — kod hiçbirine göre
# dallanmıyor, ama SSH'tan bakarken "bu bir alışkanlık mı yoksa geçici bir durum
# mu" ayrımı çok işe yarıyor.
TURLER = ("alışkanlık", "tercih", "durum", "ilişki", "olgu")

# Bir kişi için tutulacak azami bilgi sayısı. Sınır lazım: hafıza yönergeye
# gömülüyor, sınırsız büyürse her mesajda Groq'a yüzlerce satır gider ve model
# asıl soruyu görmez olur. Sınıra varılınca en eski TEYİT EDİLMEMİŞ kayıt düşer.
AZAMI_BILGI = 60


# Bir kişi için aynı anda açık durabilecek azami takip sayısı. Sınır şart:
# her konuşmadan birkaç takip çıkarsa asistan sorgu hâkimi gibi olur.
AZAMI_ACIK_TAKIP = 5

# Sorulma vakti geldikten sonra bu kadar gün içinde sorulmazsa takip düşer.
# Geç kalmış soru sorulmamış sorudan kötü: "geçen hafta dişçi nasıl geçti?"
# ilgi değil dalgınlık gösterir.
TAKIP_BAYATLAMA_GUNU = 3


def create_gozlem_tables(conn: sqlite3.Connection):
    _hafiza(conn)
    _takipler(conn)
    _gunluk(conn)
    _durum(conn)
    _migrate_gozlem_sinir(conn)


def _hafiza(conn: sqlite3.Connection):
    """Asistanın kişi hakkında bildiği şeyler.

    `UNIQUE(owner_id, icerik)` yalnız birebir aynı cümleyi engelliyor —
    "kahveyi sever" ile "kahve içmeyi seviyor" ikisi de girebilir. Asıl
    tekrar önleme modelde: bilgi çıkarımı yapılırken mevcut liste modele
    gösteriliyor ve "bunlarda olmayan yeni bir şey varsa yaz" deniyor.
    Veritabanı kısıtı sadece son emniyet.

    `gecerlilik` geçici bilgiler için: "bu hafta sınav haftası" gibi bir şey
    süresiz durmamalı, yoksa asistan aylar sonra hâlâ sınavdan bahseder.
    NULL = süresiz.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hafiza (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            icerik       TEXT    NOT NULL,
            tur          TEXT    NOT NULL DEFAULT 'olgu',
            kaynak       TEXT    NOT NULL DEFAULT 'konuşma',
            gecerlilik   TEXT,
            created_at   TEXT    NOT NULL,
            son_teyit_at TEXT
        )
    """)
    sahiplik_sutunu_ekle(conn, "hafiza")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_hafiza_tekil ON hafiza(owner_id, icerik)"
    )


def _takipler(conn: sqlite3.Connection):
    """Kullanıcının ağzından çıkan, sonradan sorulmaya değer şeyler.

    "Yarın dişçiye gidiyorum" cümlesi hiçbir tabloya girmiyor: hatırlatıcı
    değil (kullanıcı kurmadı), not değil, hafıza da değil (kalıcı bir şey
    değil, tek seferlik bir olay). Ama bir uşağın ertesi akşam "dişçi nasıl
    geçti?" diye sorması, onu asistan olmaktan çıkarıp ilgili bir insana
    çeviren şeydir.

    `sorulacak_at`  → bu andan önce sorulmaz (olay daha yaşanmadı)
    `soruldu_at`    → bir kez sorulur, tekrar edilmez
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS takipler (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            konu         TEXT    NOT NULL,
            soru         TEXT    NOT NULL,
            sorulacak_at TEXT    NOT NULL,
            soruldu_at   TEXT,
            created_at   TEXT    NOT NULL
        )
    """)
    sahiplik_sutunu_ekle(conn, "takipler")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_takip_tekil ON takipler(owner_id, konu)"
    )


def _gunluk(conn: sqlite3.Connection):
    """Her gözlem turunun kararı — konuştuğu VE sustuğu turlar.

    Sustuğu turları da yazmak bilinçli. Sadece gönderilen mesajları saklasaydık
    "neden hiç konuşmuyor" sorusunun cevabı olmazdı; şimdi `gozlem.py gunluk`
    ile "şu sinyalleri gördüm, şu sebeple sustum" satırları okunabiliyor.
    Bu, susma bütçesini ayarlayabilmenin tek yolu.

    `sinyaller` o turda görülen bütün sinyallerin anahtarları (JSON dizi) —
    modelin hangisini seçtiğini değil, elinde ne olduğunu gösterir.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gozlem_gunlugu (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            karar      TEXT    NOT NULL,
            anahtar    TEXT,
            mesaj      TEXT,
            sebep      TEXT,
            sinyaller  TEXT,
            created_at TEXT    NOT NULL
        )
    """)
    sahiplik_sutunu_ekle(conn, "gozlem_gunlugu")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_gunluk_zaman ON gozlem_gunlugu(created_at)"
    )


def _durum(conn: sqlite3.Connection):
    """Hafıza çıkarımının nereye kadar geldiği.

    Konuşmalar `conversations` tablosunda artan id ile duruyor. Her çıkarım
    turunda baştan okumak hem pahalı hem anlamsız; damga son işlenen satırı
    tutuyor, tur yalnız ondan sonrasına bakıyor.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gozlem_durum (
            owner_id           INTEGER PRIMARY KEY,
            son_hafiza_conv_id INTEGER NOT NULL DEFAULT 0
        )
    """)
    # Takip çıkarımının damgası ayrı: hafıza çıkarımı hata verdiğinde takip
    # çıkarımının da o konuşmaları atlaması gerekmiyor. İkisi bağımsız
    # ilerliyor, biri diğerini sürüklemiyor.
    mevcut = {row["name"] for row in conn.execute("PRAGMA table_info(gozlem_durum)")}
    if "son_takip_conv_id" not in mevcut:
        conn.execute(
            "ALTER TABLE gozlem_durum ADD COLUMN son_takip_conv_id INTEGER NOT NULL DEFAULT 0"
        )


def _migrate_gozlem_sinir(conn: sqlite3.Connection):
    """`users.gozlem_sinir` — kişiye günde en fazla kaç kendiliğinden mesaj (idempotent).

    **DEFAULT 0, yani kapalı.** Bu sütunun varsayılanı en önemli güvenlik
    kararı: gözlem döngüsü kullanıcının istemediği bir mesajı gönderebilen tek
    mekanizma. Yeni bir yeteneği herkese açık hâlde yayına almak yerine, açmayı
    ayrı bir komuta bağlıyoruz.

    Zeynep'in tarafı da bu yüzden kapalı başlıyor: kod ikisi için de hazır,
    ama denemeler Eyüp üzerinde yapılacak.
    """
    mevcut = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    if "gozlem_sinir" not in mevcut:
        conn.execute(
            "ALTER TABLE users ADD COLUMN gozlem_sinir INTEGER NOT NULL DEFAULT 0"
        )
        log.info("users.gozlem_sinir eklendi (herkes kapalı başlıyor)")

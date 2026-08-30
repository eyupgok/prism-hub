"""İleti oluşturma, listeleme ve gönderime hazırlama."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pytz

from logging_setup import get_logger
from modules.iletiler.models import AZAMI_BEKLEYEN, VAZGECME_DAKIKA

log = get_logger("prism.iletiler")

TZ = pytz.timezone("Europe/Istanbul")

# Mesaj uzunluğu sınırı: Telegram'ın kendi sınırından çok önce, "asistan
# üzerinden roman yollamak" saçma olduğu için.
AZAMI_UZUNLUK = 1000


class IletiHatasi(Exception):
    """Kullanıcıya olduğu gibi gösterilebilecek, anlaşılır bir ret sebebi."""


def kisiyi_bul(conn, ad: str) -> Optional[Dict[str, Any]]:
    """Adı geçen kişiyi bulur (tam eşleşme, sonra baş harfleriyle).

    Model kullanıcının yazdığı adı olduğu gibi geçiriyor: "Zeynep",
    "zeynep", "Zeynep". Tam eşleşme aramak "zeynep" yazınca kişiyi
    bulamamak demekti.
    """
    ad = (ad or "").strip()
    if not ad:
        return None

    satirlar = [dict(r) for r in conn.execute("SELECT * FROM users").fetchall()]

    def sadelestir(m: str) -> str:
        # ⚠️ Türkçe büyük harf tuzağı: Python'da "İ".lower() → "i" + ayrı bir
        # birleşen nokta (U+0307), yani "ZEYNEP" ile "Zeynep" eşleşmiyordu.
        # Küçültmeden önce iki harfi elle eşliyoruz.
        m = m.replace("İ", "i").replace("I", "ı")
        return "".join(m.lower().split())

    hedef = sadelestir(ad)
    for k in satirlar:
        if sadelestir(k["ad"]) == hedef:
            return k
    # "Zeynep" → "Zeynep"; birden fazla kişiye uyuyorsa seçim yapmıyoruz
    adaylar = [k for k in satirlar if sadelestir(k["ad"]).startswith(hedef)]
    return adaylar[0] if len(adaylar) == 1 else None


def olustur(
    conn,
    gonderen_id: int,
    alici_ad: str,
    mesaj: str,
    iletilecek_at: Optional[str] = None,
    now: Optional[datetime] = None,
    imzasiz: bool = False,
) -> Dict[str, Any]:
    """İleti kaydeder. Engellerde `IletiHatasi` fırlatır — sebebi kullanıcıya gider.

    `imzasiz=True` ise mesaj alıcıya kaynağı gösterilmeden, asistanın kendi
    cümlesi gibi gider. ⚠️ Varsayılanın False olması bilinçli → models.py.
    """
    now = now or datetime.now(TZ)
    mesaj = (mesaj or "").strip()

    if not mesaj:
        raise IletiHatasi("İletilecek bir mesaj yok.")
    if len(mesaj) > AZAMI_UZUNLUK:
        raise IletiHatasi(f"Mesaj çok uzun (en fazla {AZAMI_UZUNLUK} karakter).")

    alici = kisiyi_bul(conn, alici_ad)
    if not alici:
        raise IletiHatasi(f"'{alici_ad}' diye bir kullanıcı bulamadım.")
    if alici["id"] == gonderen_id:
        raise IletiHatasi("Kendinize ileti gönderemezsiniz; hatırlatıcı kurabilirim.")

    # ⚠️ chat_id yoksa mesaj sahibini bulamayıp TELEGRAM_CHAT_ID'e, yani
    # GÖNDERENE düşerdi (bkz. telegram_bot.sahibin_chati). Sessizce yanlış
    # kişiye gitmesindense baştan reddetmek doğru.
    if not alici.get("telegram_chat_id"):
        raise IletiHatasi(
            f"{alici['ad']} Telegram'a bağlı değil, iletemem."
        )

    bekleyen = conn.execute(
        "SELECT COUNT(*) c FROM iletiler WHERE gonderen_id = ? AND iletildi_at IS NULL",
        (gonderen_id,),
    ).fetchone()["c"]
    if bekleyen >= AZAMI_BEKLEYEN:
        raise IletiHatasi(
            f"Bekleyen ileti sınırına ulaştınız ({AZAMI_BEKLEYEN}). "
            "Önce bekleyenlerden birini iptal edin."
        )

    an = _zaman_coz(iletilecek_at, now)

    cursor = conn.execute(
        "INSERT INTO iletiler (gonderen_id, alici_id, mesaj, iletilecek_at, imzasiz, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (gonderen_id, alici["id"], mesaj, an.isoformat(), int(bool(imzasiz)), now.isoformat()),
    )
    kayit = dict(conn.execute(
        "SELECT * FROM iletiler WHERE id = ?", (cursor.lastrowid,)
    ).fetchone())
    kayit["alici"] = alici
    kayit["hemen"] = an <= now
    return kayit


def _zaman_coz(ham: Optional[str], now: datetime) -> datetime:
    """Boş ya da bozuksa 'şimdi'. Geçmiş bir an verilirse de 'şimdi'.

    Geçmişe ileti göndermek diye bir şey yok; kullanıcı "saat 3'te söyle"
    derken 3'ü on dakika geçmişse kastettiği "hemen"dir.
    """
    if not ham:
        return now
    try:
        an = datetime.fromisoformat(ham)
    except (ValueError, TypeError):
        log.warning("İleti zamanı çözülemedi: %r — hemen gönderilecek", ham)
        return now
    if an.tzinfo is None:
        an = TZ.localize(an)
    return max(an, now)


def bekleyenler(conn, gonderen_id: int) -> List[Dict[str, Any]]:
    return [dict(r) for r in conn.execute(
        "SELECT i.*, u.ad AS alici_ad FROM iletiler i "
        "JOIN users u ON u.id = i.alici_id "
        "WHERE i.gonderen_id = ? AND i.iletildi_at IS NULL "
        "ORDER BY i.iletilecek_at ASC",
        (gonderen_id,),
    ).fetchall()]


def vakti_gelenler(conn, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Gönderilmeyi bekleyen ve henüz bayatlamamış iletiler."""
    now = now or datetime.now(TZ)
    esik = (now - timedelta(minutes=VAZGECME_DAKIKA)).isoformat()
    return [dict(r) for r in conn.execute(
        "SELECT * FROM iletiler WHERE iletildi_at IS NULL "
        "AND iletilecek_at <= ? AND iletilecek_at >= ? "
        "ORDER BY iletilecek_at ASC",
        (now.isoformat(), esik),
    ).fetchall()]


def iletildi(conn, ileti_id: int, now: Optional[datetime] = None):
    """⚠️ Gönderim BAŞARILI olduktan sonra çağrılmalı — Telegram'a
    ulaşılamazsa bir sonraki turda yeniden denenmeli."""
    conn.execute(
        "UPDATE iletiler SET iletildi_at = ? WHERE id = ?",
        ((now or datetime.now(TZ)).isoformat(), ileti_id),
    )


def iptal(conn, gonderen_id: int, ileti_id: int) -> Optional[Dict[str, Any]]:
    """Yalnız GÖNDEREN iptal edebilir; alıcının haberi bile yok."""
    row = conn.execute(
        "SELECT * FROM iletiler WHERE id = ? AND gonderen_id = ? AND iletildi_at IS NULL",
        (ileti_id, gonderen_id),
    ).fetchone()
    if not row:
        return None
    conn.execute("DELETE FROM iletiler WHERE id = ?", (ileti_id,))
    return dict(row)


def temizle(conn, gun: int = 30, now: Optional[datetime] = None) -> int:
    """İletilmişleri ve bayatlayıp gönderilememişleri siler."""
    now = now or datetime.now(TZ)
    eski = (now - timedelta(days=gun)).isoformat()
    bayat = (now - timedelta(minutes=VAZGECME_DAKIKA)).isoformat()
    return conn.execute(
        "DELETE FROM iletiler WHERE (iletildi_at IS NOT NULL AND iletildi_at < ?) "
        "OR (iletildi_at IS NULL AND iletilecek_at < ?)",
        (eski, bayat),
    ).rowcount

"""Asistanın kişi hakkında biriktirdiği kalıcı bilgiler.

## Neden gerekli

`get_recent_messages(chat_id, limit=10)` — asistanın şimdiye kadarki tüm
"hafızası" buydu: son on mesaj, üstelik `conversations` her gece 30 günde bir
temizleniyor. Yani PRISM kullanıcıyı her sabah yeniden tanıyordu.

Bu modül konuşmalardan kalıcı olanı süzüp ayrı bir tabloya yazıyor ve her
mesajda yönergeye ekliyor.

## Neye "bilgi" denir, neye denmez

⚠️ En kolay yapılan hata, hafızayı veritabanının kopyası hâline getirmek.
"Yarın 14:00'te dişçi randevusu var" bir bilgi DEĞİL — o zaten `reminders`
tablosunda duruyor, hafızaya da yazılırsa randevu geçtikten sonra orada
yalan olarak kalır. Hafıza, **hiçbir tabloya yazılmayan** şeyler için:
alışkanlıklar, tercihler, süregelen durumlar, ilişkiler.

Geçici olanlar `gecerlilik` tarihiyle giriyor ("bu dönem sınav haftası"),
o tarih geçince `temizle()` siliyor. Olmasaydı asistan aylar sonra hâlâ
o sınavdan bahsederdi.

## Panelde neden yok

Bilerek: bu tablo kişi hakkında çıkarım içeriyor ve yanlış bir çıkarımın
sessizce durması rahatsız edici. Görülmesi ve düzeltilmesi kolay olmalı ama
gündelik arayüzde durmasına gerek yok — `gozlem.py bilgi` ile SSH'tan
okunuyor, `gozlem.py unut <id>` ile siliniyor.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytz

from logging_setup import get_logger
from modules.gozlem.models import AZAMI_BILGI, TURLER

log = get_logger("prism.gozlem.hafiza")

TZ = pytz.timezone("Europe/Istanbul")

# Yönergeye en fazla kaç bilgi girer. Tabloda daha fazlası olabilir; buradaki
# sınır her Groq çağrısının maliyetini ve modelin dikkatini koruyor.
YONERGE_SINIRI = 25

# Tek bir çıkarım turunda en fazla kaç yeni bilgi yazılır. Sınır olmasaydı
# uzun bir sohbet hafızayı tek seferde doldururdu.
TUR_BASINA_AZAMI = 5

# Çıkarım turunda modele verilecek azami konuşma satırı.
CIKARIM_SATIR_SINIRI = 60

# Nereye kadar okunduğunun damgası (`gozlem_durum` sütunu). Takip çıkarımının
# damgası ayrı: biri hata verdiğinde diğerinin de o konuşmaları atlaması
# gerekmiyor.
DAMGA = "son_hafiza_conv_id"


CIKARIM_YONERGESI = """\
Bir kişisel asistanın hafıza katmanısın. Görevin, aşağıdaki konuşma
dökümünden **kalıcı olarak hatırlanmaya değer** bilgileri çıkarmak.

Kullanıcının adı: {ad}

## ZATEN BİLDİKLERİN
{mevcut}

## NEYİ YAZARSIN
Yalnızca kişi hakkında SÜREKLİLİĞİ olan şeyler:
- alışkanlık: "Sabahları kahve içmeden çalışmıyor."
- tercih:     "Uzun mesaj sevmiyor, kısa cevap istiyor."
- durum:      "Bu dönem üniversitede son sınıf." (geçiciyse gecerlilik yaz)
- ilişki:     "Zeynep nişanlısı."
- olgu:       "Elazığ'da yaşıyor."

## NEYİ ASLA YAZMAZSIN
- Tek seferlik olaylar: "dün 200 TL harcadı", "yarın dişçiye gidecek".
  Bunlar zaten veritabanında; hafızaya yazılırsa gün geçince yalan olur.
- Zaten bildiklerin listesindekiler ya da onların başka kelimelerle yazılmışı.
- Tahmin, yorum, çıkarım zinciri. Kişi söylemediyse yazma.
- Asistanın kendi cümleleri. Yalnız kullanıcının söyledikleri sayılır.

## GEÇİCİ BİLGİLER
Bir bilgi bir tarihten sonra geçerliliğini yitirecekse `gecerlilik` alanına
"YYYY-MM-DD" yaz. Süresiz ise null bırak. Bugünün tarihi: {today}

## ÇIKTI
Sadece JSON:
{{"bilgiler": [{{"icerik": "...", "tur": "alışkanlık|tercih|durum|ilişki|olgu", "gecerlilik": null}}]}}

Kayda değer hiçbir şey yoksa: {{"bilgiler": []}}
**Boş dönmek olağan ve doğru cevaptır.** Konuşmaların çoğu kalıcı bilgi
içermez. Bir şey yazmak için zorlama.
"""


# ── Okuma / yazma ────────────────────────────────────────────────────────────

def listele(conn, owner_id: int) -> List[Dict[str, Any]]:
    """Kişinin geçerli bilgileri (süresi dolmuşlar hariç), yeniden eskiye."""
    bugun = datetime.now(TZ).strftime("%Y-%m-%d")
    return [dict(r) for r in conn.execute(
        "SELECT * FROM hafiza WHERE owner_id = ? "
        "AND (gecerlilik IS NULL OR gecerlilik >= ?) "
        "ORDER BY id DESC",
        (owner_id, bugun),
    ).fetchall()]


def ekle(
    conn,
    owner_id: int,
    icerik: str,
    tur: str = "olgu",
    kaynak: str = "elle",
    gecerlilik: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Bilgi ekler. Birebir aynısı varsa None döner ve teyit damgası yenilenir.

    Teyit damgası budama sırasında işe yarıyor: aynı şeyin tekrar söylenmesi
    o bilginin hâlâ geçerli olduğunun işareti, o yüzden silinme sırasında
    en sona kalıyor.
    """
    icerik = (icerik or "").strip()
    if not icerik:
        return None

    simdi = datetime.now(TZ).isoformat()
    mevcut = conn.execute(
        "SELECT * FROM hafiza WHERE owner_id = ? AND icerik = ?", (owner_id, icerik)
    ).fetchone()
    if mevcut:
        conn.execute("UPDATE hafiza SET son_teyit_at = ? WHERE id = ?", (simdi, mevcut["id"]))
        return None

    cursor = conn.execute(
        "INSERT INTO hafiza (owner_id, icerik, tur, kaynak, gecerlilik, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (owner_id, icerik, tur if tur in TURLER else "olgu", kaynak, gecerlilik, simdi),
    )
    row = conn.execute("SELECT * FROM hafiza WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)


def unut(conn, hafiza_id: int) -> Optional[Dict[str, Any]]:
    """Bilgiyi siler ve silineni döner (yoksa None) — böylece ne silindiği yazdırılabiliyor."""
    row = conn.execute("SELECT * FROM hafiza WHERE id = ?", (hafiza_id,)).fetchone()
    if not row:
        return None
    conn.execute("DELETE FROM hafiza WHERE id = ?", (hafiza_id,))
    return dict(row)


def temizle(conn) -> int:
    """Süresi dolmuşları siler, sınırı aşan kişilerde en eskileri budar.

    Budamada önce `son_teyit_at`i boş olanlar gidiyor: bir kez söylenip bir
    daha teyit edilmemiş bilgi, tekrar tekrar doğrulanmış olandan daha az
    güvenilir.
    """
    bugun = datetime.now(TZ).strftime("%Y-%m-%d")
    silinen = conn.execute(
        "DELETE FROM hafiza WHERE gecerlilik IS NOT NULL AND gecerlilik < ?", (bugun,)
    ).rowcount

    for row in conn.execute("SELECT owner_id, COUNT(*) c FROM hafiza GROUP BY owner_id"):
        fazla = row["c"] - AZAMI_BILGI
        if fazla <= 0:
            continue
        silinen += conn.execute(
            "DELETE FROM hafiza WHERE id IN ("
            "  SELECT id FROM hafiza WHERE owner_id = ?"
            "  ORDER BY (son_teyit_at IS NOT NULL), COALESCE(son_teyit_at, created_at)"
            "  LIMIT ?"
            ")",
            (row["owner_id"], fazla),
        ).rowcount

    return silinen


def yonergeye(conn, owner_id: int) -> str:
    """Hafızayı system prompt'a girecek metne çevirir; bilgi yoksa boş string.

    Boş string dönmesi önemli: hiç bilgi yokken yönergeye "BİLDİKLERİN: (yok)"
    diye bir başlık koymak modele orayı doldurma baskısı yapıyor.
    """
    bilgiler = listele(conn, owner_id)[:YONERGE_SINIRI]
    if not bilgiler:
        return ""
    satirlar = "\n".join(f"- {b['icerik']}" for b in bilgiler)
    return (
        "\n## KULLANICI HAKKINDA BİLDİKLERİN\n"
        "Bunlar önceki konuşmalardan biriktirdiğin bilgiler. Yeri geldiğinde\n"
        "kullan, ama listelemeye kalkma ve her cümlede hatırlatma.\n"
        f"{satirlar}\n"
    )


# ── Çıkarım ──────────────────────────────────────────────────────────────────

async def cikar(owner_id: int) -> List[str]:
    """Yeni konuşmalardan bilgi çıkarır ve kaydeder; eklenen bilgileri döner.

    Damga (`gozlem_durum.son_hafiza_conv_id`) sayesinde her tur yalnız yeni
    satırlara bakıyor. Damga **model çağrısı başarılı olsun ya da olmasın**
    ilerletiliyor: başarısız bir turu sonsuza dek tekrar denemek, hatalı bir
    konuşmanın çıkarımı kalıcı olarak kilitlemesi demek olurdu.
    """
    from database import get_db
    from groq_client import complete_json
    from modules.gozlem import konusma

    with get_db() as conn:
        kullanici = conn.execute("SELECT ad FROM users WHERE id = ?", (owner_id,)).fetchone()
        if not kullanici:
            return []
        ad = kullanici["ad"]

        son_id = konusma.damga_oku(conn, owner_id, DAMGA)
        dokum, en_son = konusma.yeni_dokum(conn, owner_id, son_id, CIKARIM_SATIR_SINIRI)
        if en_son is None:
            return []
        mevcut = listele(conn, owner_id)

    if not dokum.strip():
        with get_db() as conn:
            konusma.damga_yaz(conn, owner_id, DAMGA, en_son)
        return []

    yonerge = CIKARIM_YONERGESI.format(
        ad=ad,
        mevcut="\n".join(f"- {b['icerik']}" for b in mevcut) or "(henüz hiçbir şey)",
        today=datetime.now(TZ).strftime("%Y-%m-%d"),
    )

    eklenen: List[str] = []
    try:
        sonuc = await complete_json(
            [{"role": "system", "content": yonerge},
             {"role": "user", "content": dokum}],
            max_tokens=900,          # akıl yürütme payı (bkz. groq_client)
            temperature=0.2,
        )
        adaylar = sonuc.get("bilgiler") or []
    except Exception:
        log.exception("Hafıza çıkarımı başarısız (owner=%s)", owner_id)
        adaylar = []

    with get_db() as conn:
        for aday in adaylar[:TUR_BASINA_AZAMI]:
            if not isinstance(aday, dict):
                continue
            yeni = ekle(
                conn, owner_id,
                aday.get("icerik", ""),
                aday.get("tur", "olgu"),
                kaynak="konuşma",
                gecerlilik=aday.get("gecerlilik") or None,
            )
            if yeni:
                eklenen.append(yeni["icerik"])
        konusma.damga_yaz(conn, owner_id, DAMGA, en_son)
        temizle(conn)

    if eklenen:
        log.info("Hafızaya %d bilgi eklendi (owner=%s)", len(eklenen), owner_id)
    return eklenen

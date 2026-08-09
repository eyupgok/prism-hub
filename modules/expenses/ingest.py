"""Banka bildirimlerinden otomatik harcama kaydı.

Telefondaki PRISM uygulaması, izin verilen bankacılık uygulamalarının bildirimlerini
yakalayıp buraya yollar. Metin Groq'a okutulur; harcama ise kaydedilir ve Telegram'dan
[Kategori] / [Sil] butonlarıyla haber verilir.

Gizlilik kararları (bilinçli):
- Ham bildirim metni veritabanına YAZILMAZ. Sadece tekrar tespiti için SHA-256 özeti saklanır.
- Tek kullanımlık şifre / doğrulama kodu içeren metinler Groq'a bile gönderilmez —
  telefonda elenir, burada ikinci kez elenir (iki kat savunma).
- Hata kayıtlarına metin basılmaz, sadece paket adı ve sonuç.
"""

import hashlib
import json
import os
import re
import secrets
import time
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, Optional

import pytz
from groq import AsyncGroq

from modules.expenses import service

TZ = pytz.timezone("Europe/Istanbul")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Aynı alışverişin ikinci bildirimi sayılacağı zaman aralığı (dakika).
# Çok geniş tutmak, aynı tutarlı iki ayrı alışverişi yanlışlıkla eler.
DUPLICATE_WINDOW_MINUTES = int(os.getenv("EXPENSE_DUPLICATE_WINDOW_MINUTES", "5"))

# Telegram callback verisi 64 bayt ile sınırlı; kategori adı yerine bu listedeki
# sırasını gönderiyoruz (expset_<id>_<index>).
CATEGORY_ORDER = ["yemek", "ulaşım", "eğlence", "fatura", "alışveriş", "diğer"]

# Tek kullanımlık şifre / doğrulama kodu içeren mesajlar hiçbir koşulda işlenmez.
_SECRET_PATTERN = re.compile(
    r"(tek\s*kullanım|otp|onay\s*kodu|doğrulama\s*kodu|güvenlik\s*kodu|işlem\s*şifre"
    r"|sms\s*şifre|aktivasyon\s*kodu|paylaşmayın|kimseyle\s*paylaş)",
    re.IGNORECASE,
)

_PARSE_PROMPT = """\
Sen bir banka bildirimi çözümleyicisisin. Verilen bildirim metnini incele ve SADECE JSON döndür.

HARCAMA sayılan durumlar: kart veya hesaptan yapılan ödeme, alışveriş, nakit çekme,
fatura ödemesi, otomatik ödeme talimatı, giden para transferi.

HARCAMA SAYILMAYAN durumlar: bakiye bildirimi, hesaba para yatması, gelen havale/EFT,
iade/iptal, kampanya ve reklam mesajları, giriş bildirimi, limit/puan bilgisi,
ekstre veya son ödeme hatırlatması, tek kullanımlık şifre.

Şu JSON şemasıyla yanıt ver:
{"is_expense": true/false, "amount": sayı veya null, "merchant": "metin",
 "category": "yemek|ulaşım|eğlence|fatura|alışveriş|diğer", "reason": "metin"}

Kurallar:
- amount: sadece sayı yaz, para birimi ekleme. Türkçe yazım (1.234,56) doğru çevrilmeli: 1234.56
- merchant: işyeri/kurum adı. Bulamazsan boş string
- category: işyerine göre seç. Market/giyim/teknoloji → alışveriş. Restoran/kafe/yemek siparişi → yemek.
  Akaryakıt/taksi/otobüs/metro/otopark → ulaşım. Sinema/oyun/abonelik/konser → eğlence.
  Elektrik/su/doğalgaz/telefon/internet/kira → fatura. Emin değilsen → diğer
- is_expense false ise amount null olabilir; reason'a tek cümlelik sebep yaz
- SADECE JSON döndür, açıklama veya kod bloğu işareti ekleme\
"""


def compute_hash(package_name: str, text: str, posted_at: Optional[str]) -> str:
    """Aynı bildirimin tekrar işlenmesini önleyen özet.

    Android aynı bildirimi güncellendiğinde tekrar gönderebiliyor; posted_at aynı
    kaldığı için özet de aynı çıkar ve ikinci kayıt açılmaz. Buna karşılık aynı
    tutarlı iki ayrı alışveriş farklı dakikalarda olacağından ayrı ayrı kaydedilir.
    """
    minute = (posted_at or "")[:16]  # YYYY-MM-DDTHH:MM
    raw = f"{package_name}|{text.strip()}|{minute}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def looks_like_secret(text: str) -> bool:
    """Tek kullanımlık şifre / doğrulama kodu mesajı mı?"""
    return bool(_SECRET_PATTERN.search(text))


def _extract_json(raw: str) -> Dict[str, Any]:
    """Model bazen JSON'u ``` bloğuna sarıyor veya öncesine metin ekliyor."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Yanıtta JSON bulunamadı")
    return json.loads(cleaned[start : end + 1])


async def parse_notification(title: str, text: str) -> Dict[str, Any]:
    """Bildirim metnini Groq'a okutup yapılandırılmış sonuç döner."""
    content = f"{title}\n{text}".strip() if title else text.strip()

    client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY", ""))
    response = await client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": _PARSE_PROMPT},
            {"role": "user", "content": content},
        ],
        temperature=0.1,
        max_tokens=300,
    )
    parsed = _extract_json(response.choices[0].message.content)

    amount = parsed.get("amount")
    try:
        amount = float(amount) if amount is not None else None
    except (TypeError, ValueError):
        amount = None

    category = parsed.get("category", "diğer")
    if category not in service.VALID_CATEGORIES:
        category = "diğer"

    return {
        "is_expense": bool(parsed.get("is_expense")) and amount is not None and amount > 0,
        "amount": amount,
        "merchant": (parsed.get("merchant") or "").strip()[:100],
        "category": category,
        "reason": (parsed.get("reason") or "").strip()[:200],
    }


# ── Elenen çift kayıtlar ─────────────────────────────────────────────────────
# Çift sanıp elediğimiz kayıt aslında ayrı bir alışveriş olabilir (aynı kafede iki
# kahve gibi). Sessizce yutmak yerine Telegram'a "yine de kaydet" butonu koyuyoruz.
# Bellekte tutuluyor: butonun ömrü kısa, servis yeniden başlarsa düşer — kalıcı
# saklamaya değmeyecek kadar geçici bir bilgi.
_PENDING_TTL_SECONDS = 3600
_PENDING_MAX = 50
_pending_duplicates: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

# Çift diye elediğimiz bildirimlerin özetleri. Telefon aynı bildirimi yeniden
# gönderirse (kuyruk yeniden denemesi, yanıtı alamadan kopan bağlantı) Telegram'a
# ikinci kez "çift kayıt" mesajı düşmesin diye tutuluyor.
_suppressed_hashes: "OrderedDict[str, float]" = OrderedDict()


def _prune_pending():
    cutoff = time.time() - _PENDING_TTL_SECONDS
    for token in [t for t, v in _pending_duplicates.items() if v["at"] < cutoff]:
        _pending_duplicates.pop(token, None)
    while len(_pending_duplicates) > _PENDING_MAX:
        _pending_duplicates.popitem(last=False)

    for h in [h for h, at in _suppressed_hashes.items() if at < cutoff]:
        _suppressed_hashes.pop(h, None)
    while len(_suppressed_hashes) > _PENDING_MAX * 4:
        _suppressed_hashes.popitem(last=False)


def remember_duplicate(candidate: Dict[str, Any]) -> str:
    """Elenen kaydı saklar, Telegram butonuna konacak kısa anahtarı döner."""
    _prune_pending()
    token = secrets.token_urlsafe(6)
    _pending_duplicates[token] = {"at": time.time(), "candidate": candidate}
    return token


def take_duplicate(token: str) -> Optional[Dict[str, Any]]:
    """Anahtarı tüketir (tek kullanımlık) — süresi dolmuşsa None."""
    _prune_pending()
    entry = _pending_duplicates.pop(token, None)
    return entry["candidate"] if entry else None


def save_remembered_duplicate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """'Yine de kaydet' butonunun karşılığı."""
    from database import get_db

    with get_db() as conn:
        return service.create_expense(
            conn,
            amount=candidate["amount"],
            category=candidate["category"],
            description=candidate["description"],
            expense_date=candidate["expense_date"],
            source=candidate["source"],
            source_hash=candidate["source_hash"],
            source_at=candidate["source_at"],
        )


def format_tl(amount: float) -> str:
    """1234.5 → '1.234,50' (Türkçe para yazımı)"""
    formatted = f"{amount:,.2f}"
    return formatted.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


async def ingest_notification(
    package_name: str,
    title: str,
    text: str,
    posted_at: Optional[str] = None,
    source: str = "notification",
) -> Dict[str, Any]:
    """Bildirimi işler. Harcamaysa kaydeder ve Telegram'dan haber verir.

    Dönüş: {"recorded": bool, "reason": str, "expense": {...} | None}
    """
    from database import get_db

    text = (text or "").strip()
    if not text:
        return {"recorded": False, "reason": "Boş bildirim", "expense": None}

    if looks_like_secret(text) or looks_like_secret(title or ""):
        # Şifre mesajı — Groq'a gönderilmez, hiçbir yere yazılmaz.
        return {"recorded": False, "reason": "Şifre/doğrulama mesajı, yok sayıldı", "expense": None}

    source_hash = compute_hash(package_name, text, posted_at)
    with get_db() as conn:
        existing = service.get_expense_by_source_hash(conn, source_hash)
    if existing:
        return {"recorded": False, "reason": "Bu bildirim zaten işlenmiş", "expense": existing}

    try:
        parsed = await parse_notification(title or "", text)
    except Exception as e:
        print(f"❌ Bildirim çözümlenemedi ({package_name}): {type(e).__name__}: {e}")
        return {"recorded": False, "reason": "Metin çözümlenemedi", "expense": None}

    if not parsed["is_expense"]:
        return {"recorded": False, "reason": parsed["reason"] or "Harcama değil", "expense": None}

    source_at = posted_at or datetime.now(TZ).isoformat()
    expense_date = (posted_at or "")[:10] or datetime.now(TZ).strftime("%Y-%m-%d")
    description = parsed["merchant"] or "Banka bildirimi"

    candidate = {
        "amount": parsed["amount"],
        "category": parsed["category"],
        "description": description,
        "expense_date": expense_date,
        "source": source,
        "source_hash": source_hash,
        "source_at": source_at,
    }

    # Aynı alışveriş hem banka uygulamasından hem SMS'ten gelmiş olabilir
    with get_db() as conn:
        twin = service.find_duplicate(
            conn, parsed["amount"], source_at, DUPLICATE_WINDOW_MINUTES
        )
    if twin:
        _prune_pending()
        already_told = source_hash in _suppressed_hashes
        _suppressed_hashes[source_hash] = time.time()
        if not already_told:
            await _notify_duplicate(candidate, twin)
        return {"recorded": False, "reason": "Aynı tutarlı kayıt zaten var", "expense": twin}

    with get_db() as conn:
        expense = service.create_expense(conn, **candidate)
        alert = service.check_budget_alert(conn, expense["category"])

    await _notify_telegram(expense, alert)
    return {"recorded": True, "reason": "Kaydedildi", "expense": expense}


def format_expense_message(expense: Dict[str, Any], alert: Optional[str] = None) -> str:
    """Telegram bildirim metni. Kategori değiştirilince aynı fonksiyonla yeniden kurulur."""
    import html

    lines = [
        f"💳 <b>{format_tl(expense['amount'])} TL</b> · {expense['category']}",
        f"🏪 {html.escape(expense['description'])}",
        "<i>Banka bildiriminden otomatik kaydedildi</i>",
    ]
    if alert:
        lines.append(f"\n{html.escape(alert)}")
    return "\n".join(lines)


def expense_keyboard(expense_id: int) -> Dict[str, Any]:
    return {"inline_keyboard": [[
        {"text": "🏷 Kategori", "callback_data": f"expcat_{expense_id}"},
        {"text": "🗑 Sil", "callback_data": f"expdel_{expense_id}"},
    ]]}


def category_keyboard(expense_id: int) -> Dict[str, Any]:
    """Kategori seçim butonları — 3'erli iki sıra."""
    buttons = [
        {"text": cat, "callback_data": f"expset_{expense_id}_{i}"}
        for i, cat in enumerate(CATEGORY_ORDER)
    ]
    return {"inline_keyboard": [buttons[i : i + 3] for i in range(0, len(buttons), 3)]}


async def _notify_duplicate(candidate: Dict[str, Any], existing: Dict[str, Any]):
    """Elenen çift kaydı haber verir — yanlış eleme olduysa geri alınabilsin."""
    import html

    from telegram_bot import send_message

    token = remember_duplicate(candidate)
    text = "\n".join([
        "🔁 <b>Aynı tutarlı ikinci bildirim yok sayıldı</b>",
        f"{format_tl(candidate['amount'])} TL · {html.escape(candidate['description'])}",
        f"<i>Zaten kayıtlı: #{existing['id']} — {html.escape(existing['description'])}</i>",
    ])
    keyboard = {"inline_keyboard": [[
        {"text": "➕ Yine de kaydet", "callback_data": f"dupadd_{token}"},
    ]]}

    try:
        await send_message(text, reply_markup=keyboard)
    except Exception as e:
        print(f"⚠️  Çift kayıt bildirimi gönderilemedi: {e}")


async def _notify_telegram(expense: Dict[str, Any], alert: Optional[str]):
    """Kaydedilen harcamayı Telegram'dan bildirir — düzeltme butonlarıyla."""
    from telegram_bot import send_message

    try:
        await send_message(
            format_expense_message(expense, alert),
            reply_markup=expense_keyboard(expense["id"]),
        )
    except Exception as e:
        # Bildirim gitmese bile harcama kaydı durur; sadece haber verilemez.
        print(f"⚠️  Harcama bildirimi gönderilemedi (id={expense['id']}): {e}")

import os
import json
import httpx
from fastapi import APIRouter, Request, HTTPException
from typing import Dict, Any, Optional

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def _api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"


router = APIRouter()


async def send_message(
    text: str,
    chat_id: Optional[str] = None,
    reply_markup: Optional[Dict] = None,
    parse_mode: str = "HTML",
) -> Dict:
    """Telegram'a mesaj gönderir, mesaj objesini döner"""
    target = chat_id or TELEGRAM_CHAT_ID
    payload: Dict[str, Any] = {
        "chat_id": target,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(_api_url("sendMessage"), json=payload)
        return resp.json()


async def edit_message(
    chat_id: str,
    message_id: int,
    text: str,
    reply_markup: Optional[Dict] = None,
):
    """Var olan mesajı düzenler; reply_markup=None → klavyeyi kaldır"""
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": json.dumps(reply_markup if reply_markup else {"inline_keyboard": []}),
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(_api_url("editMessageText"), json=payload)


async def answer_callback_query(callback_query_id: str, text: str = ""):
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(
            _api_url("answerCallbackQuery"),
            json={"callback_query_id": callback_query_id, "text": text},
        )


async def send_reminder_notification(reminder: Dict[str, Any]):
    """Hatırlatıcı bildirimini inline butonlarla gönderir"""
    from modules.reminders.service import format_reminder_notification

    text, keyboard = format_reminder_notification(reminder)
    await send_message(text, reply_markup={"inline_keyboard": keyboard})


async def set_webhook(webhook_url: str):
    """Railway'de kullanılacak webhook URL'sini Telegram'a bildirir"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            _api_url("setWebhook"),
            json={"url": webhook_url, "drop_pending_updates": True},
        )
        data = resp.json()

    if data.get("ok"):
        print(f"✅ Telegram webhook ayarlandı: {webhook_url}")
    else:
        print(f"❌ Webhook hatası: {data}")

    return data


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """Telegram'dan gelen her güncellemeyi karşılar"""
    try:
        update = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz JSON")

    if "message" in update:
        await _handle_message(update["message"])
    elif "callback_query" in update:
        await _handle_callback_query(update["callback_query"])

    return {"ok": True}


async def _handle_message(message: Dict[str, Any]):
    chat_id = str(message["chat"]["id"])
    text = message.get("text", "").strip()

    if not text:
        return

    # Güvenlik: yalnızca yetkili kullanıcı
    if TELEGRAM_CHAT_ID and chat_id != TELEGRAM_CHAT_ID:
        await send_message("⛔ Yetkisiz erişim.", chat_id=chat_id)
        return

    # /start komutu
    if text.startswith("/start"):
        await send_message(
            "👋 Merhaba! Ben <b>PRISM</b>, kişisel AI asistanınızım.\n\n"
            "Doğal dille konuşabilirsiniz. Örnekler:\n"
            "• <i>Yarın saat 10'da toplantı hatırlatıcısı ekle</i>\n"
            "• <i>Bugün 150 TL yemek harcadım</i>\n"
            "• <i>İş notlarıma bak</i>\n"
            "• <i>Hava nasıl?</i>\n"
            "• <i>Sabah özetini ver</i>",
            chat_id=chat_id,
        )
        return

    # İşleniyor mesajı gönder, ID'sini al
    processing = await send_message("⏳ İşleniyor...", chat_id=chat_id)
    processing_id: Optional[int] = None
    if processing.get("ok"):
        processing_id = processing["result"]["message_id"]

    from ai_router import route_message

    response_text = await route_message(text)

    # İşleniyor mesajını cevapla güncelle
    if processing_id:
        await edit_message(chat_id, processing_id, response_text)
    else:
        await send_message(response_text, chat_id=chat_id)


async def _handle_callback_query(callback_query: Dict[str, Any]):
    """Inline buton basımlarını işler: tamamla ve ertele"""
    cb_id = callback_query["id"]
    chat_id = str(callback_query["message"]["chat"]["id"])
    message_id = callback_query["message"]["message_id"]
    data = callback_query.get("data", "")

    from database import get_db
    from modules.reminders import service as svc

    try:
        if data.startswith("complete_"):
            reminder_id = int(data.split("_")[1])
            with get_db() as conn:
                r = svc.complete_reminder(conn, reminder_id)

            if r:
                await answer_callback_query(cb_id, "✅ Tamamlandı!")
                await edit_message(
                    chat_id, message_id,
                    f"✅ <s>{r['title']}</s>\n<i>Tamamlandı</i>",
                )
            else:
                await answer_callback_query(cb_id, "❌ Bulunamadı")

        elif data.startswith("snooze_"):
            _, minutes_str, reminder_id_str = data.split("_")
            minutes = int(minutes_str)
            reminder_id = int(reminder_id_str)

            with get_db() as conn:
                r = svc.snooze_reminder(conn, reminder_id, minutes)

            if r:
                due = svc.parse_dt(r["due_datetime"])
                label = f"{minutes} dakika" if minutes < 60 else f"{minutes // 60} saat"
                await answer_callback_query(cb_id, f"⏰ {label} ertelendi")
                await edit_message(
                    chat_id, message_id,
                    f"⏰ <b>{r['title']}</b> ertelendi\n📅 Yeni zaman: {svc.format_dt(due)}",
                )
            else:
                await answer_callback_query(cb_id, "❌ Bulunamadı")

    except Exception as e:
        await answer_callback_query(cb_id, f"❌ Hata: {e}")

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
    from modules.reminders.service import format_reminder_notification
    text, keyboard = format_reminder_notification(reminder)
    await send_message(text, reply_markup={"inline_keyboard": keyboard})


async def set_webhook(webhook_url: str):
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


async def _transcribe_voice(file_id: str) -> str:
    """Telegram ses dosyasını Groq Whisper ile metne çevirir"""
    from groq import AsyncGroq

    # Telegram'dan dosya yolunu al
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(_api_url("getFile"), params={"file_id": file_id})
        file_info = resp.json()

    file_path = file_info["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"

    # Ses dosyasını indir
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(file_url)
        audio_bytes = resp.content

    # Groq Whisper ile transkripsiyon
    groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY", ""))
    result = await groq_client.audio.transcriptions.create(
        file=("voice.ogg", audio_bytes, "audio/ogg"),
        model="whisper-large-v3-turbo",
        language="tr",
    )
    return result.text.strip()


@router.post("/webhook")
async def telegram_webhook(request: Request):
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

    # Güvenlik: yalnızca yetkili kullanıcı
    if TELEGRAM_CHAT_ID and chat_id != TELEGRAM_CHAT_ID:
        await send_message("⛔ Yetkisiz erişim.", chat_id=chat_id)
        return

    text = message.get("text", "").strip()
    voice = message.get("voice")

    if not text and not voice:
        return

    # ── Hızlı komutlar (AI parse gerektirmez) ────────────────────────────────
    if text.startswith("/start"):
        await send_message(
            "👋 Merhaba! Ben <b>PRISM</b>, kişisel AI asistanınızım.\n\n"
            "Doğal dille konuşabilirsiniz. Örnekler:\n"
            "• <i>Yarın saat 10'da toplantı hatırlatıcısı ekle</i>\n"
            "• <i>Her pazartesi standup hatırlat</i>\n"
            "• <i>Bugün 150 TL yemek harcadım</i>\n"
            "• <i>İş notlarıma bak</i>\n"
            "• <i>Hava nasıl?</i>\n"
            "• <i>Sabah özetini ver</i>\n\n"
            "Hızlı komutlar: /hava /ozet /liste /notlar /butce",
            chat_id=chat_id,
        )
        return

    if text == "/hava":
        from modules.weather import service as weather_svc
        try:
            weather = await weather_svc.get_weather()
            await send_message(weather_svc.format_weather_message(weather), chat_id=chat_id)
        except Exception as e:
            await send_message(f"❌ Hava durumu alınamadı: {e}", chat_id=chat_id)
        return

    if text == "/ozet":
        from modules.summary import service as summary_svc
        try:
            await send_message(await summary_svc.get_morning_summary(), chat_id=chat_id)
        except Exception as e:
            await send_message(f"❌ Özet alınamadı: {e}", chat_id=chat_id)
        return

    if text in ("/liste", "/hatirlaticilar"):
        from database import get_db
        from modules.reminders import service as svc
        with get_db() as conn:
            reminders = svc.list_reminders(conn, False)
        if not reminders:
            await send_message("📋 Aktif hatırlatıcı yok.", chat_id=chat_id)
        else:
            lines = ["📋 <b>Hatırlatıcılarınız:</b>\n"]
            for r in reminders:
                due = svc.parse_dt(r["due_datetime"])
                emoji = svc.PRIORITY_EMOJIS.get(r["priority"], "🟢")
                rec = " 🔁" if r.get("recurrence", "none") != "none" else ""
                lines.append(f"{emoji} [{r['id']}] {r['title']} — {svc.format_dt(due)}{rec}")
            await send_message("\n".join(lines), chat_id=chat_id)
        return

    if text == "/notlar":
        from database import get_db
        from modules.notes import service as svc
        with get_db() as conn:
            notes = svc.list_notes(conn)[:10]
        if not notes:
            await send_message("📝 Henüz not yok.", chat_id=chat_id)
        else:
            lines = ["📝 <b>Notlarınız:</b>\n"] + [
                f"• [{n['id']}] {n['title']} ({n['category']})" for n in notes
            ]
            await send_message("\n".join(lines), chat_id=chat_id)
        return

    if text == "/butce":
        from database import get_db
        from modules.expenses import service as svc
        from datetime import datetime
        import pytz
        with get_db() as conn:
            budgets = svc.get_all_budgets(conn)
            month = datetime.now(pytz.timezone("Europe/Istanbul")).strftime("%Y-%m")
            if not budgets:
                await send_message(
                    "📊 Henüz bütçe limiti ayarlanmamış.\n💡 Örnek: 'Yemek için aylık 3000 TL bütçe koy'",
                    chat_id=chat_id,
                )
            else:
                lines = ["📊 <b>Aylık Bütçe Limitleri:</b>\n"]
                for b in budgets:
                    alert = svc.check_budget_alert(conn, b["category"], month)
                    status = "🚨" if alert and "aşıldı" in alert else ("⚠️" if alert else "✅")
                    lines.append(f"{status} {b['category']}: {b['monthly_limit']:.0f} TL/ay")
                await send_message("\n".join(lines), chat_id=chat_id)
        return

    # ── Ses mesajı ────────────────────────────────────────────────────────────
    if voice:
        processing = await send_message("🎤 Ses işleniyor...", chat_id=chat_id)
        processing_id: Optional[int] = processing.get("result", {}).get("message_id")
        try:
            text = await _transcribe_voice(voice["file_id"])
            if processing_id:
                await edit_message(chat_id, processing_id, f"🎤 <i>{text}</i>\n⏳ İşleniyor...")
        except Exception as e:
            if processing_id:
                await edit_message(chat_id, processing_id, f"❌ Ses dosyası işlenemedi: {e}")
            return

    # ── AI ile işle ───────────────────────────────────────────────────────────
    if not voice:
        processing = await send_message("⏳ İşleniyor...", chat_id=chat_id)
        processing_id = processing.get("result", {}).get("message_id") if processing.get("ok") else None

    from ai_router import route_message
    response_text = await route_message(text, chat_id)

    if processing_id:
        await edit_message(chat_id, processing_id, response_text)
    else:
        await send_message(response_text, chat_id=chat_id)


async def _handle_callback_query(callback_query: Dict[str, Any]):
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

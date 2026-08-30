import html
import os
import json
import secrets
import httpx
from fastapi import APIRouter, BackgroundTasks, Request, HTTPException
from typing import Dict, Any, Optional

from logging_setup import get_logger

log = get_logger("prism.telegram")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")


def _api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"


def sahibin_chati(owner_id: int) -> Optional[str]:
    """Bir kaydın sahibinin Telegram sohbeti.

    Hatırlatıcı bildirimi, harcama haberi, özet — hepsi kaydın sahibine gider.
    Kişi henüz bota /start dememişse chat_id'si boş olur ve None döner;
    `send_message` o zaman TELEGRAM_CHAT_ID'e düşer, yani haber kaybolmaz.
    """
    from auth import kullanici_getir

    k = kullanici_getir(owner_id)
    return k["telegram_chat_id"] if k else None


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


async def edit_message_reply_markup(chat_id: str, message_id: int, reply_markup: Dict):
    """Sadece butonları değiştirir, mesaj metnine dokunmaz."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(
            _api_url("editMessageReplyMarkup"),
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "reply_markup": json.dumps(reply_markup),
            },
        )


async def answer_callback_query(callback_query_id: str, text: str = ""):
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(
            _api_url("answerCallbackQuery"),
            json={"callback_query_id": callback_query_id, "text": text},
        )


async def send_document(
    file_bytes: bytes,
    filename: str,
    caption: str = "",
    chat_id: Optional[str] = None,
) -> Dict:
    """Dosya gönderir (veritabanı yedeği için). Telegram sınırı: 50 MB."""
    target = chat_id or TELEGRAM_CHAT_ID
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            _api_url("sendDocument"),
            data={"chat_id": target, "caption": caption, "parse_mode": "HTML"},
            files={"document": (filename, file_bytes, "application/octet-stream")},
        )
        return resp.json()


async def ileti_gonder(ileti: Dict[str, Any]) -> bool:
    """Bir kullanıcının diğerine yolladığı sözü, asistanın ağzından iletir.

    Mesaj alıcının kendi hitabıyla ("efendim") açılıyor, gönderen ise adıyla
    anılıyor ("Eyüp Bey") — `ai_router.adiyla_hitap()` zaten bu ayrımı
    biliyor. Selamlama YOK: günde birkaç ileti gidince "Merhaba" her seferinde
    tekrarlanıp yapmacık duruyor.

    Metin `html.escape`'ten geçiyor: içerik doğrudan kullanıcıdan geliyor ve
    kaçırılmamış bir `<` mesajı 400 ile sessizce yutardı.
    """
    from ai_router import adiyla_hitap
    from auth import kullanici_getir

    gonderen = kullanici_getir(ileti["gonderen_id"]) or {}
    alici = kullanici_getir(ileti["alici_id"]) or {}
    if not alici.get("telegram_chat_id"):
        log.warning("İleti %s: alıcının chat_id'si yok, gönderilmedi", ileti["id"])
        return False

    if ileti["imzasiz"]:
        # İmzasız kip: kaynak görünmüyor, mesaj asistanın kendi cümlesi gibi
        # gidiyor. 🔹 işareti gözlem katmanınınkiyle aynı — alıcı açısından
        # "PRISM kendiliğinden bir şey söyledi" deneyimi tek biçimde kalsın.
        metin = f"🔹 {html.escape(ileti['mesaj'])}"
    else:
        kim = adiyla_hitap(gonderen.get("ad", "Bilinmeyen"), gonderen.get("hitap"))
        metin = (
            f"💬 {html.escape(kim)} şunu iletmemi istedi, efendim:\n\n"
            f"<i>{html.escape(ileti['mesaj'])}</i>"
        )

    sonuc = await send_message(metin, chat_id=str(alici["telegram_chat_id"]))
    if not sonuc.get("ok"):
        return False

    _ileti_baglama_yaz(str(alici["telegram_chat_id"]), metin, ileti["mesaj"])
    return True


def _ileti_baglama_yaz(chat_id: str, gorunen: str, mesaj: str):
    """Gönderilen iletiyi ALICININ konuşma bağlamına asistan satırı olarak yazar.

    Olmasaydı alıcı "neden böyle dedin?" diye cevap verdiğinde asistan neden
    bahsedildiğini bilemezdi — mesaj `conversations`'a hiç girmemiş olurdu.
    İmzasız kipte bu daha da belirgin: mesaj asistanın kendi cümlesi gibi
    duruyor ama arkasında hiçbir iz yok.

    `content` bilerek JSON: modele giden bağlamda asistan satırları hep o
    biçimde (bkz. `database.save_message`). Düz cümle koymak modeli JSON
    üretmekten caydırabilirdi.

    Yazamamak iletiyi düşürmez — mesaj zaten gitti, bu yalnız bağlam.
    """
    import json as _json

    from database import save_message

    try:
        save_message(
            chat_id,
            "assistant",
            _json.dumps(
                {"module": "chat", "action": "respond", "params": {"message": mesaj}},
                ensure_ascii=False,
            ),
            gorunen,
        )
    except Exception:
        log.warning("İleti konuşma bağlamına yazılamadı (chat=%s)", chat_id)


async def send_voice(
    ogg_bytes: bytes,
    caption: str = "",
    chat_id: Optional[str] = None,
) -> Dict:
    """Ses notu gönderir (dalgalı, tıklayınca çalan Telegram biçimi).

    OGG/Opus şart — `ses.seslendir_ogg()` bu yüzden ffmpeg'den geçiyor.
    Başarısızlık burada yutulmuyor ama çağıran taraf zaten metni ayrıca
    gönderdiği için ses kaybolsa da cevap kaybolmuyor.
    """
    target = chat_id or TELEGRAM_CHAT_ID
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            _api_url("sendVoice"),
            data={"chat_id": target, "caption": caption, "parse_mode": "HTML"},
            files={"voice": ("prism.ogg", ogg_bytes, "audio/ogg")},
        )
        return resp.json()


async def send_reminder_notification(reminder: Dict[str, Any]):
    """Hatırlatıcıyı SAHİBİNİN sohbetine yollar — herkes kendi görevini görür."""
    from modules.reminders.service import format_reminder_notification
    text, keyboard = format_reminder_notification(reminder)
    await send_message(
        text,
        chat_id=sahibin_chati(reminder["owner_id"]),
        reply_markup={"inline_keyboard": keyboard},
    )


async def set_webhook(webhook_url: str):
    payload: Dict[str, Any] = {"url": webhook_url, "drop_pending_updates": True}
    if TELEGRAM_WEBHOOK_SECRET:
        payload["secret_token"] = TELEGRAM_WEBHOOK_SECRET
    else:
        log.warning("⚠️  TELEGRAM_WEBHOOK_SECRET ayarlanmamış — webhook imza doğrulaması devre dışı")

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(_api_url("setWebhook"), json=payload)
        data = resp.json()

    if data.get("ok"):
        log.info(f"✅ Telegram webhook ayarlandı: {webhook_url}")
    else:
        log.error(f"❌ Webhook hatası: {data}")

    return data


async def _download_telegram_file(file_id: str) -> bytes:
    """Telegram sunucusundan dosyayı indirir (ses, fotoğraf vb.)"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(_api_url("getFile"), params={"file_id": file_id})
        file_info = resp.json()

    file_path = file_info["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(file_url)
        return resp.content


async def _transcribe_voice(file_id: str) -> str:
    """Telegram ses dosyasını indirir ve Groq Whisper ile metne çevirir"""
    from modules.chat.service import transcribe_audio

    audio_bytes = await _download_telegram_file(file_id)
    return await transcribe_audio(audio_bytes)


@router.post("/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    # Webhook imza doğrulaması (Telegram secret_token ile aynı değeri gönderir)
    if TELEGRAM_WEBHOOK_SECRET:
        received = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not secrets.compare_digest(received, TELEGRAM_WEBHOOK_SECRET):
            raise HTTPException(status_code=403, detail="Geçersiz webhook imzası")

    try:
        update = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz JSON")

    # Hemen 200 dön; Groq yavaş kalırsa Telegram update'i tekrar göndermesin
    background_tasks.add_task(_process_update, update)
    return {"ok": True}


async def _process_update(update: Dict[str, Any]):
    try:
        if "message" in update:
            await _handle_message(update["message"])
        elif "callback_query" in update:
            await _handle_callback_query(update["callback_query"])
    except Exception as e:
        log.error(f"❌ Telegram update işlenemedi: {e}")


async def _handle_message(message: Dict[str, Any]):
    from auth import kullanici_chat_id_ile

    chat_id = str(message["chat"]["id"])

    # Güvenlik: chat_id `users` tablosunda kayıtlı olmalı. Tek bir env değeri
    # yerine tablo bakılıyor — ikinci kişiyi eklemek `kullanici.py chat-id` ile
    # oluyor, kod ya da .env değişmiyor.
    kullanici = kullanici_chat_id_ile(chat_id)
    if not kullanici:
        # chat_id'yi loga basıyoruz: yeni birini eklerken numarasını buradan alıyorsun.
        log.warning("Yetkisiz chat: %s", chat_id)
        await send_message(
            "⛔ Üzgünüm, sizi tanıyamadım. Bu sohbet yetkili değil.", chat_id=chat_id
        )
        return

    owner_id = kullanici["id"]

    text = message.get("text", "").strip()
    voice = message.get("voice")
    photo = message.get("photo")
    caption = (message.get("caption") or "").strip()

    if not text and not voice and not photo:
        return

    # ── Hızlı komutlar (AI parse gerektirmez) ────────────────────────────────
    if text.startswith("/start"):
        await send_message(
            "<b>PRISM</b> hizmetinizde.\n\n"
            "Benimle olağan Türkçenizle konuşabilirsiniz. Örnekler:\n"
            "• <i>Yarın saat 10'da toplantı hatırlatıcısı ekle</i>\n"
            "• <i>Her pazartesi standup hatırlat</i>\n"
            "• <i>Bugün 150 TL yemek harcadım</i>\n"
            "• <i>İş notlarıma bak</i>\n"
            "• <i>Hava nasıl?</i>\n"
            "• <i>Sabah özetini ver</i>\n\n"
            "Hızlı komutlar: /site /hava /ozet /aksam /hafta /liste /notlar /butce /yedek",
            chat_id=chat_id,
        )
        return

    if text == "/site":
        # Doğal dille de sorulabiliyor ("site linkini ver") ama o yol Groq'tan
        # geçiyor. Adres, Groq çöktüğünde de lazım olan türden bir bilgi —
        # bu yüzden ayrıca sabit bir komut var.
        from ai_router import panel_adresi

        adres = panel_adresi()
        if adres == "(ayarlanmamış)":
            await send_message(
                "⚙️ Panel adresi sunucuda tanımlı değil (<code>PANEL_URL</code>).",
                chat_id=chat_id,
            )
        else:
            await send_message(
                f"🌐 <b>PRISM paneli</b>\n{adres}\n\n"
                "<i>iPhone'da Safari ile aç → Paylaş → Ana Ekrana Ekle</i>",
                chat_id=chat_id,
            )
        return

    if text == "/hava":
        from modules.weather import service as weather_svc
        try:
            weather = await weather_svc.get_weather(kullanici)
            await send_message(weather_svc.format_weather_message(weather), chat_id=chat_id)
        except Exception as e:
            await send_message(f"❌ Hava durumu alınamadı: {e}", chat_id=chat_id)
        return

    if text == "/ozet":
        from modules.summary import service as summary_svc
        try:
            await send_message(await summary_svc.get_morning_summary(owner_id), chat_id=chat_id)
        except Exception as e:
            await send_message(f"❌ Özet alınamadı: {e}", chat_id=chat_id)
        return

    if text in ("/liste", "/hatirlaticilar"):
        from database import get_db
        from modules.reminders import service as svc
        with get_db() as conn:
            reminders = svc.list_reminders(conn, owner_id, False)
        if not reminders:
            await send_message("📋 Aktif hatırlatıcı yok.", chat_id=chat_id)
        else:
            lines = ["📋 <b>Hatırlatıcılarınız:</b>\n"]
            for r in reminders:
                due = svc.parse_dt(r["due_datetime"])
                emoji = svc.PRIORITY_EMOJIS.get(r["priority"], "🟢")
                rec = " 🔁" if r.get("recurrence", "none") != "none" else ""
                lines.append(f"{emoji} [{r['id']}] {html.escape(r['title'])} — {svc.format_dt(due)}{rec}")
            await send_message("\n".join(lines), chat_id=chat_id)
        return

    if text == "/notlar":
        from database import get_db
        from modules.notes import service as svc
        with get_db() as conn:
            notes = svc.list_notes(conn, owner_id)[:10]
        if not notes:
            await send_message("📝 Henüz not yok.", chat_id=chat_id)
        else:
            lines = ["📝 <b>Notlarınız:</b>\n"] + [
                f"• [{n['id']}] {html.escape(n['title'])} ({n['category']})" for n in notes
            ]
            await send_message("\n".join(lines), chat_id=chat_id)
        return

    if text in ("/aksam", "/hafta"):
        from modules.summary import service as summary_svc
        try:
            builder = (
                summary_svc.get_evening_summary if text == "/aksam"
                else summary_svc.get_weekly_report
            )
            await send_message(await builder(owner_id), chat_id=chat_id)
        except Exception:
            log.exception("Özet oluşturulamadı (%s)", text)
            await send_message("❌ Özet oluşturulamadı, kayıtlara baktım.", chat_id=chat_id)
        return

    if text == "/yedek":
        from backup import send_backup

        await send_message("🗄 Yedek hazırlanıyor...", chat_id=chat_id)
        try:
            if not await send_backup():
                await send_message("❌ Yedek gönderilemedi, kayıtlara bak.", chat_id=chat_id)
        except Exception as e:
            await send_message(f"❌ Yedekleme hatası: {e}", chat_id=chat_id)
        return

    if text == "/butce":
        from database import get_db
        from modules.expenses import service as svc
        from datetime import datetime
        import pytz
        with get_db() as conn:
            budgets = svc.get_all_budgets(conn, owner_id)
            month = datetime.now(pytz.timezone("Europe/Istanbul")).strftime("%Y-%m")
            if not budgets:
                await send_message(
                    "📊 Henüz bütçe limiti ayarlanmamış.\n💡 Örnek: 'Yemek için aylık 3000 TL bütçe koy'",
                    chat_id=chat_id,
                )
            else:
                lines = ["📊 <b>Aylık Bütçe Limitleri:</b>\n"]
                for b in budgets:
                    alert = svc.check_budget_alert(conn, owner_id, b["category"], month)
                    status = "🚨" if alert and "aşıldı" in alert else ("⚠️" if alert else "✅")
                    lines.append(f"{status} {b['category']}: {b['monthly_limit']:.0f} TL/ay")
                await send_message("\n".join(lines), chat_id=chat_id)
        return

    # Konuşma geçmişine yazılacak okunur hâl; düz yazıda metnin kendisi yeter
    # (bkz. database.save_message).
    gorunen: Optional[str] = None

    # ── Ses mesajı ────────────────────────────────────────────────────────────
    if voice:
        processing = await send_message("🎤 Ses işleniyor...", chat_id=chat_id)
        processing_id: Optional[int] = processing.get("result", {}).get("message_id")
        try:
            text = await _transcribe_voice(voice["file_id"])
            gorunen = f"🎤 {text}"
            if processing_id:
                await edit_message(chat_id, processing_id, f"🎤 <i>{html.escape(text)}</i>\n⏳ İşleniyor...")
        except Exception as e:
            if processing_id:
                await edit_message(chat_id, processing_id, f"❌ Ses dosyası işlenemedi: {e}")
            return

    # ── Fotoğraf ─────────────────────────────────────────────────────────────
    elif photo:
        from modules.chat.service import describe_image

        processing = await send_message("🖼 Görsel inceleniyor...", chat_id=chat_id)
        processing_id = processing.get("result", {}).get("message_id")
        try:
            # Telegram fotoğrafı boyut sırasıyla gönderir; en büyüğünü al
            image_bytes = await _download_telegram_file(photo[-1]["file_id"])
            description = await describe_image(image_bytes, caption)
            text = f"{caption}\n\n[Görsel analizi]: {description}" if caption else f"[Görsel analizi]: {description}"
            gorunen = f"🖼 {caption}" if caption else "🖼 Görsel"
            if processing_id:
                await edit_message(chat_id, processing_id, "🖼 Görsel anlaşıldı\n⏳ İşleniyor...")
        except Exception as e:
            if processing_id:
                await edit_message(chat_id, processing_id, f"❌ Görsel işlenemedi: {e}")
            return

    # ── AI ile işle ───────────────────────────────────────────────────────────
    else:
        processing = await send_message("⏳ İşleniyor...", chat_id=chat_id)
        processing_id = processing.get("result", {}).get("message_id") if processing.get("ok") else None

    from ai_router import route_message
    response_text = await route_message(text, chat_id, owner_id, gorunen)

    if processing_id:
        await edit_message(chat_id, processing_id, response_text)
    else:
        await send_message(response_text, chat_id=chat_id)

    # Sesle sorana sesle cevap. Yazana yazıyla — "Kaydedildi." için ses notu
    # göndermek, dokunup dinlemeyi gerektirdiği için düz yazıdan daha yorucu
    # olurdu. Metin yukarıda zaten gönderildi; ses onun yerine değil YANINA
    # geliyor, çünkü sayı ve tarih okumak dinlemekten kolay.
    if voice:
        try:
            from ses import seslendir_ogg

            # Kişinin kendi ses tercihiyle okunuyor (users.ses_*)
            from auth import kullanici_getir

            konusma = await seslendir_ogg(response_text, kullanici_getir(owner_id))
            if konusma:
                await send_voice(konusma, chat_id=chat_id)
        except Exception:
            log.exception("Sesli cevap gönderilemedi")


async def _handle_callback_query(callback_query: Dict[str, Any]):
    cb_id = callback_query["id"]
    chat_id = str(callback_query["message"]["chat"]["id"])
    message_id = callback_query["message"]["message_id"]
    data = callback_query.get("data", "")

    # Güvenlik: mesajlarda olduğu gibi butonlarda da sadece kayıtlı kullanıcı.
    # Butonlar doğrudan silme/değiştirme yapıyor, bu kontrolün eksik olması
    # _handle_message ile asimetri yaratıyordu.
    from auth import kullanici_chat_id_ile

    kullanici = kullanici_chat_id_ile(chat_id)
    if not kullanici:
        await answer_callback_query(cb_id, "⛔ Yetkisiz")
        return

    owner_id = kullanici["id"]

    from database import get_db
    from modules.reminders import service as svc

    try:
        if data.startswith("complete_"):
            reminder_id = int(data.split("_")[1])
            with get_db() as conn:
                r = svc.complete_reminder(conn, owner_id, reminder_id)

            if r:
                await answer_callback_query(cb_id, "✅ Tamamlandı")
                if r.get("rescheduled"):
                    due = svc.parse_dt(r["due_datetime"])
                    await edit_message(
                        chat_id, message_id,
                        f"✅ <s>{html.escape(r['title'])}</s>\n"
                        f"<i>Tamamlandı</i> — 🔁 Sonraki tekrar: {svc.format_dt(due)}",
                    )
                else:
                    await edit_message(
                        chat_id, message_id,
                        f"✅ <s>{html.escape(r['title'])}</s>\n<i>Tamamlandı</i>",
                    )
            else:
                await answer_callback_query(cb_id, "❌ Bulunamadı")

        elif data.startswith("snooze_"):
            _, minutes_str, reminder_id_str = data.split("_")
            minutes = int(minutes_str)
            reminder_id = int(reminder_id_str)

            with get_db() as conn:
                r = svc.snooze_reminder(conn, owner_id, reminder_id, minutes)

            if r:
                due = svc.parse_dt(r["due_datetime"])
                label = f"{minutes} dakika" if minutes < 60 else f"{minutes // 60} saat"
                await answer_callback_query(cb_id, f"⏰ {label} ertelendi")
                await edit_message(
                    chat_id, message_id,
                    f"⏰ <b>{html.escape(r['title'])}</b> ertelendi\n📅 Yeni zaman: {svc.format_dt(due)}",
                )
            else:
                await answer_callback_query(cb_id, "❌ Bulunamadı")

        # ── AI ile istenen silmenin onayı ────────────────────────────────────
        elif data.startswith("delno_"):
            import confirm

            confirm.take(data.split("_", 1)[1])
            await answer_callback_query(cb_id, "Vazgeçildi")
            await edit_message(chat_id, message_id, "✅ <i>Vazgeçildi, hiçbir şey silinmedi.</i>")

        elif data.startswith("delok_"):
            import confirm
            from modules.expenses import service as exp_svc
            from modules.notes import service as note_svc

            pending = confirm.take(data.split("_", 1)[1])
            if pending is None:
                await answer_callback_query(cb_id, "⌛ Onay süresi doldu")
                await edit_message(
                    chat_id, message_id,
                    "⌛ <i>Onay süresi doldu, silme yapılmadı. Tekrar dener misiniz?</i>",
                )
            else:
                deleters = {
                    "reminder": (svc.delete_reminder, "Hatırlatıcı"),
                    "note": (note_svc.delete_note, "Not"),
                    "expense": (exp_svc.delete_expense, "Harcama"),
                }
                delete_fn, label = deleters[pending["kind"]]
                with get_db() as conn:
                    deleted = delete_fn(conn, owner_id, pending["id"])

                if deleted:
                    await answer_callback_query(cb_id, "🗑 Silindi")
                    await edit_message(chat_id, message_id, f"🗑 <i>{label} silindi.</i>")
                else:
                    await answer_callback_query(cb_id, "❌ Bulunamadı")
                    await edit_message(chat_id, message_id, f"❌ <i>{label} bulunamadı.</i>")

        # ── Banka bildiriminden kaydedilen harcamayı düzeltme ────────────────
        elif data.startswith("expdel_"):
            from modules.expenses import service as exp_svc

            expense_id = int(data.split("_")[1])
            with get_db() as conn:
                deleted = exp_svc.delete_expense(conn, owner_id, expense_id)

            if deleted:
                await answer_callback_query(cb_id, "🗑 Silindi")
                await edit_message(chat_id, message_id, "🗑 <i>Harcama silindi</i>")
            else:
                await answer_callback_query(cb_id, "❌ Bulunamadı")

        elif data.startswith("dupadd_"):
            from modules.expenses import service as exp_svc
            from modules.expenses.ingest import (
                expense_keyboard,
                format_expense_message,
                save_remembered_duplicate,
                take_duplicate,
            )

            candidate = take_duplicate(data.split("_", 1)[1])
            if candidate is None:
                await answer_callback_query(cb_id, "⌛ Bu düğmenin süresi doldu")
                await edit_message_reply_markup(chat_id, message_id, {"inline_keyboard": []})
            else:
                expense = save_remembered_duplicate(candidate)
                with get_db() as conn:
                    alert = exp_svc.check_budget_alert(conn, owner_id, expense["category"])
                await answer_callback_query(cb_id, "➕ Kaydedildi")
                await edit_message(
                    chat_id, message_id,
                    format_expense_message(expense, alert),
                    reply_markup=expense_keyboard(expense["id"]),
                )

        elif data.startswith("expcat_"):
            from modules.expenses.ingest import category_keyboard

            expense_id = int(data.split("_")[1])
            await answer_callback_query(cb_id, "Yeni kategoriyi seç")
            await edit_message_reply_markup(chat_id, message_id, category_keyboard(expense_id))

        elif data.startswith("expset_"):
            from modules.expenses import service as exp_svc
            from modules.expenses.ingest import (
                CATEGORY_ORDER,
                expense_keyboard,
                format_expense_message,
            )

            _, expense_id_str, index_str = data.split("_")
            expense_id = int(expense_id_str)
            category = CATEGORY_ORDER[int(index_str)]

            with get_db() as conn:
                expense = exp_svc.update_expense_category(conn, owner_id, expense_id, category)
                alert = exp_svc.check_budget_alert(conn, owner_id, category) if expense else None

            if expense:
                await answer_callback_query(cb_id, f"🏷 {category}")
                await edit_message(
                    chat_id, message_id,
                    format_expense_message(expense, alert),
                    reply_markup=expense_keyboard(expense_id),
                )
            else:
                await answer_callback_query(cb_id, "❌ Bulunamadı")

    except Exception as e:
        await answer_callback_query(cb_id, f"❌ Hata: {e}")

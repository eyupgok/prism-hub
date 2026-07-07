from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    message: str
    chat_id: str = "mobile"


@router.post("/")
async def chat(data: ChatMessage):
    """Doğal dil mesajını AI router'a iletir (mobil/web istemciler için).

    Yanıt metni Telegram ile aynı biçimde basit HTML etiketleri (<b>, <i>, <s>)
    içerebilir; Android tarafında HtmlCompat.fromHtml ile render edilebilir.
    """
    from ai_router import route_message

    text = data.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Mesaj boş olamaz")

    response = await route_message(text, data.chat_id)
    return {"response": response}


@router.post("/voice")
async def chat_voice(file: UploadFile = File(...), chat_id: str = Form("mobile")):
    """Ses dosyasını Whisper ile metne çevirip AI router'a iletir"""
    from ai_router import route_message
    from modules.chat.service import transcribe_audio

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Ses dosyası boş")

    try:
        text = await transcribe_audio(
            audio_bytes,
            file.filename or "voice.ogg",
            file.content_type or "audio/ogg",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Transkripsiyon başarısız: {e}")

    if not text:
        raise HTTPException(status_code=400, detail="Seste anlaşılır konuşma bulunamadı")

    response = await route_message(text, chat_id)
    return {"transcript": text, "response": response}

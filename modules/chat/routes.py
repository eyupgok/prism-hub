from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from auth import verify_api_key

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Sunucunun 1 GB RAM'i var ve dosya tamamen belleğe alınıyor. Sınır olmadan
# tek bir büyük yükleme servisi düşürebilir.
MAX_IMAGE_BYTES = 12 * 1024 * 1024   # 12 MB — telefon fotoğrafı için fazlasıyla yeterli
MAX_AUDIO_BYTES = 25 * 1024 * 1024   # 25 MB — birkaç dakikalık ses


async def _read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    """Dosyayı parça parça okur, sınırı aşınca okumayı bırakıp hata verir.

    `await upload.read()` tamamını belleğe alacağı için sınır kontrolünü sonradan
    yapmak işe yaramaz — bu yüzden okurken sayıyoruz.
    """
    chunks, total = [], 0
    while True:
        chunk = await upload.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Dosya çok büyük (sınır: {max_bytes // (1024 * 1024)} MB)",
            )
        chunks.append(chunk)
    return b"".join(chunks)


class ChatMessage(BaseModel):
    message: str


def sohbet_kovasi(user: dict) -> str:
    """Konuşma geçmişinin anahtarı — HER ZAMAN sunucuda, giriş yapan kişiden üretilir.

    Eskiden istemci `chat_id` gönderiyordu ve varsayılanı sabit "mobile" idi:
    Telegram dışı bütün istemciler tek bir kovaya yazıyordu. İki kullanıcıda bu,
    Groq'a karşıdakinin konuşma geçmişini bağlam diye vermek demekti. Artık
    istemcinin gönderdiği değere bakılmıyor.
    """
    return f"panel:{user['id']}"


@router.post("/")
async def chat(data: ChatMessage, user: dict = Depends(verify_api_key)):
    """Doğal dil mesajını AI router'a iletir (mobil/web istemciler için).

    Yanıt metni Telegram ile aynı biçimde basit HTML etiketleri (<b>, <i>, <s>)
    içerebilir; Android tarafında HtmlCompat.fromHtml ile render edilebilir.
    """
    from ai_router import route_message

    text = data.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Mesaj boş olamaz")

    response = await route_message(text, sohbet_kovasi(user), user["id"])
    return {"response": response}


@router.post("/voice")
async def chat_voice(
    file: UploadFile = File(...),
    user: dict = Depends(verify_api_key),
):
    """Ses dosyasını Whisper ile metne çevirip AI router'a iletir"""
    from ai_router import route_message
    from modules.chat.service import transcribe_audio

    audio_bytes = await _read_limited(file, MAX_AUDIO_BYTES)
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

    response = await route_message(text, sohbet_kovasi(user), user["id"])
    return {"transcript": text, "response": response}


@router.post("/image")
async def chat_image(
    file: UploadFile = File(...),
    message: str = Form(""),
    user: dict = Depends(verify_api_key),
):
    """Görseli vision modeliyle analiz edip AI router'a iletir.

    message: kullanıcının görselle birlikte yazdığı metin (opsiyonel).
    Dönen 'description' görsel analizi, 'response' PRISM'in nihai yanıtıdır.
    """
    from ai_router import route_message
    from modules.chat.service import describe_image

    image_bytes = await _read_limited(file, MAX_IMAGE_BYTES)
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Görsel dosyası boş")

    content_type = file.content_type or "image/jpeg"
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Dosya bir görsel değil")

    hint = message.strip()
    try:
        description = await describe_image(image_bytes, hint, content_type)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Görsel analizi başarısız: {e}")

    text = f"{hint}\n\n[Görsel analizi]: {description}" if hint else f"[Görsel analizi]: {description}"
    response = await route_message(text, sohbet_kovasi(user), user["id"])
    return {"description": description, "response": response}

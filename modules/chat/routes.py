from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
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


class SeslendirilecekMetin(BaseModel):
    metin: str
    # Önizleme için geçici üstünü yazma (kaydedilmez)
    ses_id: Optional[str] = None
    ses_sakinlik: Optional[float] = None
    ses_hiz: Optional[float] = None


class SesAyari(BaseModel):
    ses_id: Optional[str] = None
    ses_sakinlik: Optional[float] = None
    ses_hiz: Optional[float] = None


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


@router.post("/ses")
async def chat_ses(
    data: SeslendirilecekMetin,
    user: dict = Depends(verify_api_key),
):
    """Metni sese çevirip MP3 döner — panelin 🔊 düğmesi bunu çalıyor.

    Tarayıcının kendi `speechSynthesis`'i bedava ve anındaydı ama sesi her
    cihazda başkaydı. Asistanın sesi kimliğinin parçası; telefon değişince
    değişmemeli. Bu yüzden panel de Telegram'la AYNI motoru kullanıyor
    (`ses.seslendir`), tek fark biçim: burada MP3 yeter, tarayıcı onu
    doğrudan çalıyor; Telegram ise ses notu için OGG istiyor.

    Ses üretilemezse 503 — panel düğmeyi sessizce pasifleştirir, metin durur.
    """
    from ses import seslendir

    # Kişinin kayıtlı tercihiyle okunuyor; Ayarlar'daki "Önizle" düğmesi ise
    # HENÜZ KAYDEDİLMEMİŞ değerleri gövdede yolluyor. Kaydetmeden dinleyememek
    # ses ayarını kullanılmaz hâle getirirdi — her deneme için "kaydet, dinle,
    # beğenmedin, geri al" demek olurdu.
    deneme = data.model_dump(exclude_none=True)
    kisi = {**user, **{k: v for k, v in deneme.items() if k.startswith("ses_")}}

    mp3 = await seslendir(data.metin, kisi)
    if not mp3:
        raise HTTPException(status_code=503, detail="Seslendirme şu an kullanılamıyor")

    return Response(
        content=mp3,
        media_type="audio/mpeg",
        # Aynı metin iki kez çalınırsa ikinci sefer ağa çıkmasın
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get("/ses/secenekler")
async def ses_secenekleri(user: dict = Depends(verify_api_key)):
    """Panelin Ayarlar sayfasındaki ses bölümünü besleyen tek çağrı.

    Kota da burada: ücretsiz kademe ayda 10.000 karakter ve bu, ortalama bir
    yanıtta ~80 sesli cevap demek. Kullanıcı sesinin neden bir gün kesildiğini
    anlayabilmeli — rakamı görmezse arıza sanır.
    """
    import ses

    return {
        "sesler": await ses.sesler(),
        "kota": await ses.kota(),
        "ayar": ses.ayar_coz(user),
        "sinirlar": {
            "sakinlik": list(ses.SAKINLIK_ARALIGI),
            "hiz": list(ses.HIZ_ARALIGI),
        },
    }


@router.put("/ses/ayar")
async def ses_ayari_kaydet(data: SesAyari, user: dict = Depends(verify_api_key)):
    """Ses tercihini KENDİ satırına yazar.

    `?kisi=` burada geçerli değil: yazma her zaman giriş yapanın kendi
    verisine gider (bkz. CLAUDE.md "İki Kullanıcı"). Başkasının asistan
    sesini değiştirmek diye bir şey yok.
    """
    from database import get_db
    from ses import HIZ_ARALIGI, SAKINLIK_ARALIGI

    def sinirla(deger, aralik):
        return None if deger is None else min(max(float(deger), aralik[0]), aralik[1])

    with get_db() as conn:
        conn.execute(
            "UPDATE users SET ses_id = ?, ses_sakinlik = ?, ses_hiz = ? WHERE id = ?",
            (
                (data.ses_id or "").strip() or None,
                sinirla(data.ses_sakinlik, SAKINLIK_ARALIGI),
                sinirla(data.ses_hiz, HIZ_ARALIGI),
                user["id"],
            ),
        )
        guncel = dict(conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone())

    from ses import ayar_coz
    return {"ayar": ayar_coz(guncel)}


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

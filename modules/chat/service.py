import base64
import os

from groq import AsyncGroq

WHISPER_MODEL = "whisper-large-v3-turbo"
VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

VISION_PROMPT = """\
Sen bir görsel analiz asistanısın. Kullanıcının gönderdiği görseli Türkçe analiz et:
- Görselde ne olduğunu kısa ve net anlat.
- Fiş/fatura ise: toplam tutarı, işyeri adını, tarihi ve uygun harcama kategorisini \
(yemek|ulaşım|eğlence|fatura|alışveriş|diğer) belirt.
- Okunabilir metin içeriyorsa (el yazısı, tabela, belge, ekran görüntüsü) metni aynen aktar.
- Yorum ve tahmin ekleme, gördüğünü aktar."""


async def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "voice.ogg",
    content_type: str = "audio/ogg",
) -> str:
    """Ses verisini Groq Whisper ile Türkçe metne çevirir"""
    client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY", ""))
    result = await client.audio.transcriptions.create(
        file=(filename, audio_bytes, content_type),
        model=WHISPER_MODEL,
        language="tr",
    )
    return result.text.strip()


async def describe_image(
    image_bytes: bytes,
    user_hint: str = "",
    content_type: str = "image/jpeg",
) -> str:
    """Görseli Groq vision modeliyle analiz edip Türkçe açıklama döner.

    user_hint: kullanıcının fotoğrafla birlikte yazdığı metin (caption) —
    analizi kullanıcının niyetine odaklamak için modele iletilir.
    """
    b64 = base64.b64encode(image_bytes).decode("ascii")
    instruction = VISION_PROMPT
    if user_hint:
        instruction += f"\n\nKullanıcının bu görselle ilgili mesajı: {user_hint}"

    client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY", ""))
    response = await client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": instruction},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{content_type};base64,{b64}"},
                    },
                ],
            }
        ],
        temperature=0.2,
        max_tokens=600,
    )
    return response.choices[0].message.content.strip()

import os

from groq import AsyncGroq

WHISPER_MODEL = "whisper-large-v3-turbo"


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

"""Metni sese çevirme — Telegram ses notu ve panelin 🔊 düğmesi ortak kullanır.

## Neden sunucuda üretiliyor

Tarayıcının kendi seslendirme motoru (`speechSynthesis`) bedava ve anında,
ama sesi **her cihazda başka**: iPhone'da bir ses, Android'de başka, Windows'ta
üçüncü biri. Asistanın sesi kimliğinin parçası; telefonu değiştirince
değişmemeli. Bu yüzden ses tek yerden, sunucudan geliyor.

## Neden Groq değil

Groq'un seslendirme modeli yalnız İngilizce ve Arapça konuşuyor — Türkçe yok.
Whisper (ses → metin) Groq'ta, ama tersi başka bir kaynaktan gelmek zorunda.

## Neden edge-tts

Sunucunun 954 MB RAM'i var. Yerel bir model (Piper) teknik olarak sığardı ama
sentez sırasındaki 200-250 MB'lık sıçrama, bellek daralınca çekirdeğin en şişman
süreci öldürmesi demek — o da `prism`'in kendisi olurdu. Sesli cevap uğruna
asistanı kaybetmek kötü bir takas.

`edge-tts` ise bir ağ çağrısı: bellekte yalnız birkaç on kilobaytlık ses durur.
Anahtar da hesap da istemiyor.

⚠️ **Tek riski:** kullandığı uç Microsoft'un resmî olarak dışarıya açtığı bir
API değil, Edge'in "sesli oku" özelliğinin kendi ucu. Bir gün kapanabilir.
Bu yüzden buradaki her fonksiyon **hata yerine `None` döndürüyor**: ses
üretilemezse asistan eskisi gibi yazıyla cevap verir, hiçbir şey düşmez.
Seslendirme bir ikramdır, işin kendisi değil.
"""

import asyncio
import html as html_modulu
import os
import re
import unicodedata
from typing import Optional

from logging_setup import get_logger

log = get_logger("prism.ses")

# JARVIS erkek sesle konuşuyor; varsayılan ona göre. Emel'e geçmek için
# .env'de TTS_VOICE=tr-TR-EmelNeural yeter, kod değişmez.
VARSAYILAN_SES = os.getenv("TTS_VOICE", "tr-TR-AhmetNeural")

# Uzun metin uzun ses demek: 3 dakikalık bir sesli özet kimsenin dinlemediği
# bir şey olur, üstelik üretimi de bekletir. Sınırı aşan metin kesiliyor.
AZAMI_KARAKTER = int(os.getenv("TTS_MAX_CHARS", "1200"))

# Sesle okunduğunda saçma duran işaretlerin karşılıkları. Emoji ve etiketler
# aşağıda toptan eleniyor; bunlar ise elenirse ANLAM kaybediyor.
OKUNUSLAR = (
    ("°C", " derece"),
    ("₺", " lira"),
    ("&", " ve "),
    (" · ", ", "),
    ("·", ", "),
    ("→", ", "),
)

# Sesli okunmayacak karakterler.
#
#   So → emoji ve süs simgeleri (🔹 ☀ 🟢)
#   Sk → ten rengi değiştiricileri
#   Cf → sıfır genişlikli birleştirici (emoji dizilerini birbirine bağlayan)
#   Cs → vekil karakterler
#
# ⚠️ Kategori listesi tek başına YETMİYOR: "☀️"nin sonundaki görünmez
# varyasyon seçici (U+FE0F) "Mn" kategorisinde ve emojisi silinince ortada
# kalıp okunuşta bir boşluk bırakıyordu. Mn'in tamamını elemek Türkçe için
# gereksiz risk, o yüzden yalnız seçici aralığı ayrıca düşürülüyor.
ELENEN_KATEGORILER = ("So", "Sk", "Cf", "Cs")
VARYASYON_SECICILER = range(0xFE00, 0xFE10)


def _okunur(karakter: str) -> bool:
    if ord(karakter) in VARYASYON_SECICILER:
        return False
    return unicodedata.category(karakter) not in ELENEN_KATEGORILER


_ETIKET = re.compile(r"<[^>]+>")
_BOSLUK = re.compile(r"[ \t]+")
_COK_SATIR = re.compile(r"\n{2,}")

# ffmpeg yoksa her çağrıda log'a yazmasın diye: bir kez söyler, susar.
_ffmpeg_uyarildi = False


def temizle(metin: str) -> str:
    """Modelin ürettiği metni sesli okunabilir hâle getirir.

    Yanıtlar Telegram için HTML taşıyor (`<b>`, `&amp;`) ve emoji içeriyor
    (🔹 ☀️ 🟢). Ham hâliyle okutulursa asistan "küçüktür b büyüktür" der ya da
    emojiyi anlamsız bir sesle geçiştirir. Panelde de aynı metin kullanıldığı
    için temizlik burada, tek yerde yapılıyor.
    """
    if not metin:
        return ""

    metin = _ETIKET.sub(" ", metin)
    metin = html_modulu.unescape(metin)
    for eski, yeni in OKUNUSLAR:
        metin = metin.replace(eski, yeni)

    metin = "".join(k for k in metin if _okunur(k))

    metin = _BOSLUK.sub(" ", metin)
    metin = _COK_SATIR.sub("\n", metin).strip()

    return _kirp(metin)


def _kirp(metin: str) -> str:
    """Sınırı aşan metni mümkün olan en doğal yerden keser.

    Sırayla: cümle sonu → kelime sonu → çaresiz kalınca ham kesme. Kelime
    yedeği önemli, çünkü ilk yarıda hiç nokta olmayan bir metin (madde madde
    yazılmış bir özet gibi) yoksa kelimenin ortasında kesilip yarım bir hece
    okunuyordu.
    """
    if len(metin) <= AZAMI_KARAKTER:
        return metin

    kirpik = metin[:AZAMI_KARAKTER]
    asgari = AZAMI_KARAKTER // 2

    cumle = max(kirpik.rfind("."), kirpik.rfind("!"), kirpik.rfind("?"))
    if cumle >= asgari:
        return kirpik[: cumle + 1]

    kelime = kirpik.rfind(" ")
    return kirpik[:kelime] if kelime >= asgari else kirpik


async def seslendir(metin: str, ses: Optional[str] = None) -> Optional[bytes]:
    """Metni MP3'e çevirir. Üretilemezse `None` — çağıran taraf yazıyla devam eder.

    `edge_tts` içeriden import ediliyor: paket kurulmadan `git pull` yapılırsa
    (deploy sırası böyle) servis açılışta çökmesin diye. Eksikse yalnız ses
    kaybolur.
    """
    metin = temizle(metin)
    if not metin:
        return None

    try:
        import edge_tts
    except ImportError:
        log.warning("edge-tts kurulu değil — seslendirme atlandı (pip install -r requirements.txt)")
        return None

    try:
        konusma = edge_tts.Communicate(metin, ses or VARSAYILAN_SES)
        parcalar = [
            parca["data"] async for parca in konusma.stream()
            if parca["type"] == "audio"
        ]
    except Exception:
        log.exception("Seslendirme başarısız (%d karakter)", len(metin))
        return None

    if not parcalar:
        log.warning("Seslendirme boş döndü (%d karakter)", len(metin))
        return None
    return b"".join(parcalar)


async def seslendir_ogg(metin: str, ses: Optional[str] = None) -> Optional[bytes]:
    """Telegram ses notu için OGG/Opus. ffmpeg yoksa `None`.

    Telegram'ın dalgalı "ses notu" görünümü (`sendVoice`) OGG/Opus istiyor;
    edge-tts ise MP3 veriyor. Panel MP3'ü doğrudan çalabildiği için bu çevrim
    yalnız Telegram yolunda gerekiyor.
    """
    mp3 = await seslendir(metin, ses)
    if not mp3:
        return None
    return await _ogge_cevir(mp3)


async def _ogge_cevir(mp3: bytes) -> Optional[bytes]:
    global _ffmpeg_uyarildi
    try:
        surec = await asyncio.create_subprocess_exec(
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", "pipe:0",
            "-ac", "1",                 # ses notu tek kanal
            "-c:a", "libopus", "-b:a", "32k",
            "-f", "ogg", "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        if not _ffmpeg_uyarildi:
            _ffmpeg_uyarildi = True
            log.warning("ffmpeg yok — Telegram ses notu gönderilemeyecek (sudo apt install ffmpeg)")
        return None

    ogg, hata = await surec.communicate(mp3)
    if surec.returncode != 0 or not ogg:
        log.warning("ffmpeg çevrimi başarısız: %s", hata.decode("utf-8", "replace")[:200])
        return None
    return ogg

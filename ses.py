"""Metni sese çevirme — Telegram ses notu ve panelin 🔊 düğmesi ortak kullanır.

## Neden sunucuda üretiliyor

Tarayıcının kendi seslendirme motoru (`speechSynthesis`) bedava ve anında,
ama sesi **her cihazda başka**: iPhone'da bir ses, Android'de başka, Windows'ta
üçüncü biri. Asistanın sesi kimliğinin parçası; telefonu değiştirince
değişmemeli. Bu yüzden ses tek yerden, sunucudan geliyor.

## Neden Groq değil

Groq'un seslendirme modeli yalnız İngilizce ve Arapça konuşuyor — Türkçe yok.
Whisper (ses → metin) Groq'ta, ama tersi başka bir kaynaktan gelmek zorunda.

## Neden yerel model değil

Sunucunun 954 MB RAM'i var. Yerel bir model (Piper) teknik olarak sığardı ama
sentez sırasındaki 200-250 MB'lık sıçrama, bellek daralınca çekirdeğin en şişman
süreci öldürmesi demek — o da `prism`'in kendisi olurdu. Sesli cevap uğruna
asistanı kaybetmek kötü bir takas. Bir ağ çağrısında ise bellekte yalnız birkaç
on kilobaytlık ses durur.

## Neden ElevenLabs (edge-tts denendi ve elendi)

Önce `edge-tts` kullanıldı: bedava, anahtarsız. Ama Türkçede **yalnız iki sesi**
var (Ahmet, Emel) ve ikisi de "haber spikeri" karakterinde eğitilmiş. Perde ve
hız ayarı sesin rengini değiştiriyor, TAVRINI değiştirmiyor — JARVIS'i JARVIS
yapan şey ise tam olarak tavır: ölçülü tempo, vurgusuz ama ölü olmayan bir
mesafe. Bir spikere ayar çekerek elde edilmiyor.

ElevenLabs'in çok dilli modeli yüzlerce ses arasından seçim yaptırıyor ve
`stability` / `speed` ile tavır gerçekten ayarlanabiliyor.

⚠️ **Ücretsiz kademe ayda 10.000 karakter.** Ortalama bir yanıt ~120 karakter,
yani ayda ~80 sesli cevap. Kota bitince API hata döner, `seslendir()` `None`
verir ve asistan yazıyla devam eder — sessizce bozulmaz ama sesi de kesilir.
Kalan kota panelde görünüyor (`kota()`).

⚠️ **Yedek motor bilerek YOK.** Kota bitince edge-tts'e düşmek teknik olarak
kolaydı; yapılmadı, çünkü asistanın sesinin bir gün habersizce değişmesi
bozulmaktan daha kafa karıştırıcı. Ses kimliğin parçası: ya o ses, ya sessizlik.

⚠️ Buradaki her fonksiyon hata yerine **`None` döndürüyor**. Seslendirme bir
ikramdır, işin kendisi değil: üretilemezse cevap yazıyla gider.
"""

import asyncio
import html as html_modulu
import os
import re
import unicodedata
from typing import Optional

from logging_setup import get_logger

log = get_logger("prism.ses")

API_KOK = "https://api.elevenlabs.io/v1"

# Çok dilli model — Türkçeyi bu konuşuyor. Turbo/flash sürümleri yarı kredi
# yiyor ama telaffuz belirgin şekilde düşüyor; ayda 80 cevapta tasarrufun
# anlamı yok.
MODEL = os.getenv("TTS_MODEL", "eleven_multilingual_v2")

# Daniel — İngiliz, resmî, "steady broadcaster". Adaylar arasından seçildi.
VARSAYILAN_SES_ID = os.getenv("TTS_VOICE_ID", "onwK4e9ZLuTAKqWW03F9")

# stability: yükseldikçe okuma düzleşir, duygusal dalgalanma azalır. JARVIS'in
#            tavrı için istenen tam olarak bu; 0.5 altı fazla "oyunculuk" yapıyor.
# speed:     0.7–1.2 arası. Ölçülü tempo için 1'in biraz altı.
# style:     0 = abartma yok. JARVIS vurgu yapmaz.
VARSAYILAN_SAKINLIK = 0.6
VARSAYILAN_HIZ = 0.95
SAKINLIK_ARALIGI = (0.0, 1.0)
HIZ_ARALIGI = (0.7, 1.2)

# Uzun metin uzun ses demek: 3 dakikalık bir sesli özet kimsenin dinlemediği
# bir şey olur, üstelik kredi de yakar. Sınırı aşan metin kesiliyor.
AZAMI_KARAKTER = int(os.getenv("TTS_MAX_CHARS", "600"))

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


def ayar_coz(kullanici: Optional[dict] = None) -> dict:
    """Kişinin kayıtlı ses tercihini ElevenLabs'in beklediği biçime çevirir.

    Kişiye özel, çünkü asistanın sesi kimin dinlediğine bağlı: Eyüp Daniel'i
    seçebilir, Zeynep başkasını. Sütunlar boşsa varsayılanlara düşüyor —
    yani hiç ayar yapılmadan da çalışıyor.
    """
    k = kullanici or {}

    def sayi(deger, varsayilan, aralik):
        try:
            d = float(deger)
        except (TypeError, ValueError):
            return varsayilan
        # Panelden gelen değer kaydırıcıyla sınırlı ama API doğrudan da
        # çağrılabiliyor; aralık dışı bir değer 422 döndürürdü.
        return min(max(d, aralik[0]), aralik[1])

    return {
        "ses_id": (k.get("ses_id") or VARSAYILAN_SES_ID).strip(),
        "stability": sayi(k.get("ses_sakinlik"), VARSAYILAN_SAKINLIK, SAKINLIK_ARALIGI),
        "speed": sayi(k.get("ses_hiz"), VARSAYILAN_HIZ, HIZ_ARALIGI),
    }


def _istemci(zaman_asimi: float = 60.0):
    """Anahtarsızsa None — çağıran taraf sessizce sesten vazgeçer."""
    anahtar = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not anahtar:
        return None
    import httpx

    return httpx.AsyncClient(timeout=zaman_asimi, headers={"xi-api-key": anahtar})


async def seslendir(metin: str, kullanici: Optional[dict] = None) -> Optional[bytes]:
    """Metni MP3'e çevirir. Üretilemezse `None` — çağıran yazıyla devam eder."""
    metin = temizle(metin)
    if not metin:
        return None

    if not os.getenv("ELEVENLABS_API_KEY", "").strip():
        log.warning("ELEVENLABS_API_KEY yok — seslendirme atlandı")
        return None

    ayar = ayar_coz(kullanici)
    try:
        # İstemci kurulumu da try içinde: bu modülün sözleşmesi "asla hata
        # fırlatma", çağıran taraflar (Telegram döngüsü, gözlem turu) bir
        # istisnayı beklemiyor.
        async with _istemci() as c:
            cevap = await c.post(
                f"{API_KOK}/text-to-speech/{ayar['ses_id']}",
                json={
                    "text": metin,
                    "model_id": MODEL,
                    "voice_settings": {
                        "stability": ayar["stability"],
                        "similarity_boost": 0.75,
                        "style": 0.0,
                        "use_speaker_boost": True,
                        "speed": ayar["speed"],
                    },
                },
            )
    except Exception:
        log.exception("Seslendirme isteği başarısız (%d karakter)", len(metin))
        return None

    if cevap.status_code != 200:
        # 401 = anahtar bozuk · 422 = ses kimliği yanlış · 429 = kota bitti.
        # Üçü de "ses yok" demek ama sebebi log'da dursun, yoksa sessizliğin
        # neden başladığını anlamanın yolu olmaz.
        log.warning("Seslendirme reddedildi: %s %s",
                    cevap.status_code, cevap.text[:200])
        return None

    return cevap.content or None


async def sesler() -> list:
    """Hesaptaki sesler — panelin açılır listesi bunu çiziyor.

    Liste sabit yazılabilirdi ama ElevenLabs'te ses eklenip çıkarılabiliyor;
    sabit liste bir gün olmayan bir sesi gösterir ve seçilince 422 gelir.
    """
    istemci = _istemci(30.0)
    if istemci is None:
        return []
    try:
        async with istemci as c:
            cevap = await c.get(f"{API_KOK}/voices")
        if cevap.status_code != 200:
            log.warning("Ses listesi alınamadı: %s", cevap.status_code)
            return []
        return [
            {
                "id": v["voice_id"],
                "ad": (v.get("name") or "").split(" - ")[0].strip(),
                "tarif": (v.get("name") or "").partition(" - ")[2].strip(),
                "cinsiyet": (v.get("labels") or {}).get("gender", ""),
                "aksan": (v.get("labels") or {}).get("accent", ""),
            }
            for v in cevap.json().get("voices", [])
        ]
    except Exception:
        log.exception("Ses listesi alınamadı")
        return []


async def kota() -> Optional[dict]:
    """Kalan karakter hakkı. Ücretsiz kademe dar (10.000/ay), panelde gösteriliyor."""
    istemci = _istemci(30.0)
    if istemci is None:
        return None
    try:
        async with istemci as c:
            cevap = await c.get(f"{API_KOK}/user/subscription")
        if cevap.status_code != 200:
            return None
        d = cevap.json()
        kullanilan, sinir = d.get("character_count", 0), d.get("character_limit", 0)
        return {"kullanilan": kullanilan, "sinir": sinir,
                "kalan": max(sinir - kullanilan, 0), "kademe": d.get("tier", "")}
    except Exception:
        log.exception("Kota okunamadı")
        return None


async def seslendir_ogg(metin: str, kullanici: Optional[dict] = None) -> Optional[bytes]:
    """Telegram ses notu için OGG/Opus. ffmpeg yoksa `None`.

    Telegram'ın dalgalı "ses notu" görünümü (`sendVoice`) OGG/Opus istiyor;
    ElevenLabs ise MP3 veriyor. Panel MP3'ü doğrudan çalabildiği için bu
    çevrim yalnız Telegram yolunda gerekiyor.
    """
    mp3 = await seslendir(metin, kullanici)
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

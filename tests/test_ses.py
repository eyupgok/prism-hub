"""Seslendirme: metin temizliği ve hataya dayanıklılık.

İki şeyi kilitliyor:

1. **Temizlik.** Asistanın yanıtları Telegram için HTML taşıyor ve emoji
   içeriyor. Ham hâliyle okutulursa "küçüktür b büyüktür" duyulur.
2. **Sessiz düşme.** Seslendirme bir ikram, işin kendisi değil: motor
   erişilemezse `None` dönmeli ve asistan yazıyla devam etmeli. Bu testlerin
   yarısı "hata FIRLATMADIĞINI" doğruluyor.
"""

import asyncio

import pytest

import ses


class _SahteCevap:
    def __init__(self, kod, govde):
        self.status_code, self.content, self.text = kod, govde, ""


class _SahteIstemci:
    """`async with` ile kullanılan httpx istemcisinin yerine geçer."""

    def __init__(self, kod, govde):
        self._cevap = _SahteCevap(kod, govde)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, *a, **k):
        return self._cevap

    async def get(self, *a, **k):
        return self._cevap


class _KopukIstemci(_SahteIstemci):
    """Ağ kopması: istek sırasında patlar (gerçek dünyadaki hâli)."""

    async def post(self, *a, **k):
        raise RuntimeError("baglanti kesildi")


def _patlayan_istemci(*a, **k):
    return _KopukIstemci(0, b"")


# ── Temizlik ─────────────────────────────────────────────────────────────────

def test_html_etiketleri_okunmuyor():
    """Yanıtlar Telegram için <b>/<i> taşıyor; sesli okunursa saçmalık olur."""
    assert ses.temizle("<b>Üç</b> göreviniz var.") == "Üç göreviniz var."


def test_html_varliklari_cozuluyor():
    assert ses.temizle("Ali &amp; Veli") == "Ali ve Veli"
    assert ses.temizle("&quot;tamam&quot;") == '"tamam"'


def test_emoji_ve_gorunmez_seciciler_dusuyor():
    """⚠️ Asıl tuzak görünmez olan: "☀️"nin sonundaki varyasyon seçici (U+FE0F)
    "Mn" kategorisinde, yani emoji filtresine takılmıyor. Emojisi silinince
    ortada kalıp okunuşta bir boşluk bırakıyordu."""
    temiz = ses.temizle("\U0001F539 Yarın yağmur var. ☀️ Hazırlıklı olun.")

    assert temiz == "Yarın yağmur var. Hazırlıklı olun."
    assert "️" not in temiz


def test_isaretler_okunusuyla_degistiriliyor():
    """Elenirlerse ANLAM kaybolur — emoji gibi atılamazlar."""
    assert "37 derece" in ses.temizle("Sıcaklık 37°C")
    assert "250 lira" in ses.temizle("Tutar 250₺")
    assert ses.temizle("yemek · ulaşım") == "yemek, ulaşım"


def test_uzun_metin_cumle_sonundan_kesiliyor(monkeypatch):
    monkeypatch.setattr(ses, "AZAMI_KARAKTER", 40)

    temiz = ses.temizle("Birinci cümle burada. İkinci cümle de burada ve uzun.")

    assert temiz == "Birinci cümle burada."


def test_cumle_sonu_yoksa_kelime_ortasinda_kesilmiyor(monkeypatch):
    """Madde madde yazılmış bir özette ilk yarıda hiç nokta olmayabiliyor;
    yedek yol olmasaydı yarım bir hece okunurdu."""
    monkeypatch.setattr(ses, "AZAMI_KARAKTER", 30)

    liste = "yumurta ekmek peynir zeytin domates salatalık biber"
    temiz = ses.temizle(liste)

    assert len(temiz) <= 30
    assert liste.startswith(temiz)                 # uydurma yok, sadece kısaltma
    assert liste[len(temiz)] == " "                # tam kelimede bitti


def test_bos_metin_bos_doner():
    for bos in ("", None, "   ", "\U0001F539"):
        assert ses.temizle(bos) == ""


# ── Hataya dayanıklılık ──────────────────────────────────────────────────────

def test_bos_metin_seslendirilmiyor():
    """Boş metni motora göndermek gereksiz ağ çağrısı."""
    assert asyncio.run(ses.seslendir("   ")) is None
    assert asyncio.run(ses.seslendir("☀️")) is None


def test_anahtar_yoksa_seslendirme_atlanir(monkeypatch):
    """Anahtarsız kurulumda ses yok ama asistan çalışmaya devam eder."""
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    assert asyncio.run(ses.seslendir("Merhaba efendim.")) is None


def test_motor_cokerse_hata_firlatmiyor(monkeypatch):
    """Seslendirme başarısızlığı cevabı düşürmemeli — asistan yazıyla devam eder."""
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk_test")
    monkeypatch.setattr(ses, "_istemci", _patlayan_istemci)

    assert asyncio.run(ses.seslendir("Merhaba efendim.")) is None


def test_kota_bitince_ses_susar_asistan_susmaz(monkeypatch):
    """ElevenLabs kotası dolunca 429 döner. Ses kesilir, cevap kesilmez."""
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk_test")
    monkeypatch.setattr(ses, "_istemci", lambda *a, **k: _SahteIstemci(429, b""))

    assert asyncio.run(ses.seslendir("Merhaba efendim.")) is None


def test_kisiye_ozel_ayar_cozuluyor():
    """Asistanın sesi kimin dinlediğine bağlı; sütunlar boşsa varsayılan."""
    varsayilan = ses.ayar_coz({})
    assert varsayilan["ses_id"] == ses.VARSAYILAN_SES_ID
    assert varsayilan["stability"] == ses.VARSAYILAN_SAKINLIK

    kisi = ses.ayar_coz({"ses_id": "abc", "ses_sakinlik": 0.9, "ses_hiz": 0.8})
    assert (kisi["ses_id"], kisi["stability"], kisi["speed"]) == ("abc", 0.9, 0.8)


def test_aralik_disi_ayar_sinirlaniyor():
    """API aralık dışı değere 422 döner; panel kaydırıcıyla sınırlı ama uç
    doğrudan da çağrılabiliyor."""
    ucuk = ses.ayar_coz({"ses_sakinlik": 5.0, "ses_hiz": -3})

    assert ucuk["stability"] == ses.SAKINLIK_ARALIGI[1]
    assert ucuk["speed"] == ses.HIZ_ARALIGI[0]


def test_bozuk_ayar_varsayilana_duser():
    """Elle düzenlenmiş bir veritabanı satırı seslendirmeyi düşürmemeli."""
    bozuk = ses.ayar_coz({"ses_sakinlik": "abc", "ses_hiz": None})

    assert bozuk["stability"] == ses.VARSAYILAN_SAKINLIK
    assert bozuk["speed"] == ses.VARSAYILAN_HIZ


def test_ffmpeg_yoksa_ses_notu_yok_ama_cokme_yok(monkeypatch):
    """ffmpeg kurulu değilse Telegram ses notu gönderilemez; metin yine gider."""
    async def sahte_ses(metin, kullanici=None):
        return b"sahte-mp3"

    async def ffmpeg_yok(*a, **k):
        raise FileNotFoundError("ffmpeg")

    monkeypatch.setattr(ses, "seslendir", sahte_ses)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", ffmpeg_yok)

    assert asyncio.run(ses.seslendir_ogg("Merhaba.")) is None


def test_cok_dilli_model_kullaniliyor():
    """Turbo/flash yarı kredi yiyor ama telaffuzu düşük — ayda 80 cevapta
    tasarrufun anlamı yok."""
    assert "multilingual" in ses.MODEL

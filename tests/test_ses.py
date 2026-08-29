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


def test_motor_cokerse_hata_firlatmiyor(monkeypatch):
    """Seslendirme başarısızlığı cevabı düşürmemeli — asistan yazıyla devam eder."""
    class SahteCommunicate:
        def __init__(self, *a, **k):
            raise RuntimeError("uc kapali")

    sahte = type("edge_tts", (), {"Communicate": SahteCommunicate})
    monkeypatch.setitem(__import__("sys").modules, "edge_tts", sahte)

    assert asyncio.run(ses.seslendir("Merhaba efendim.")) is None


def test_ffmpeg_yoksa_ses_notu_yok_ama_cokme_yok(monkeypatch):
    """ffmpeg kurulu değilse Telegram ses notu gönderilemez; metin yine gider."""
    async def sahte_ses(metin, ses_adi=None):
        return b"sahte-mp3"

    async def ffmpeg_yok(*a, **k):
        raise FileNotFoundError("ffmpeg")

    monkeypatch.setattr(ses, "seslendir", sahte_ses)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", ffmpeg_yok)

    assert asyncio.run(ses.seslendir_ogg("Merhaba.")) is None


def test_varsayilan_ses_turkce():
    """Groq'un seslendirmesi Türkçe bilmiyordu; bu yüzden ayrı bir motor var."""
    assert ses.VARSAYILAN_SES.startswith("tr-TR-")

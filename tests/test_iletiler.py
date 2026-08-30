"""İletiler: bir kullanıcının diğerine, asistanın ağzından yolladığı sözler.

Buradaki testlerin ağırlığı **yanlış kişiye gitmeme** üzerinde. Sebebi şu:
ileti, asistanın kullanıcının adına BAŞKA BİR İNSANA mesaj gönderdiği tek
mekanizma. Bir hatırlatıcı yanlış kurulursa kullanıcı görür ve düzeltir;
yanlış iletilen bir mesaj geri alınamaz.
"""

from datetime import datetime, timedelta

import pytest
import pytz

from conftest import OTEKI, SAHIP
from modules.iletiler import service as svc
from modules.iletiler.models import AZAMI_BEKLEYEN, VAZGECME_DAKIKA

TZ = pytz.timezone("Europe/Istanbul")


def _an(saat=12, gun_farki=0):
    return TZ.localize(datetime(2026, 9, 15, saat, 0)) + timedelta(days=gun_farki)


def _ileti(db, mesaj="akşam geç kalacağım", saat_farki=None, alici="Öteki", now=None):
    now = now or _an()
    ne_zaman = None if saat_farki is None else (now + timedelta(hours=saat_farki)).isoformat()
    return svc.olustur(db, SAHIP, alici, mesaj, ne_zaman, now=now)


# ── Yanlış kişiye gitmeme ────────────────────────────────────────────────────

def test_telegrama_bagli_olmayana_iletilmiyor(db):
    """⚠️ En tehlikeli hata bu. chat_id yoksa `sahibin_chati()` mesajı
    TELEGRAM_CHAT_ID'e, yani GÖNDERENİN kendisine düşürürdü — kullanıcı
    iletildi sanır, karşı taraf hiçbir şey görmez."""
    db.execute("UPDATE users SET telegram_chat_id = NULL WHERE id = ?", (OTEKI,))

    with pytest.raises(svc.IletiHatasi, match="Telegram"):
        _ileti(db)


def test_taninmayan_kisiye_iletilmiyor(db):
    with pytest.raises(svc.IletiHatasi, match="bulamadım"):
        _ileti(db, alici="Kerem")


def test_kendine_ileti_gonderilemiyor(db):
    with pytest.raises(svc.IletiHatasi, match="Kendinize"):
        _ileti(db, alici="Test")


def test_kisi_bosluk_ve_buyuk_harf_farkindan_bulunuyor(db):
    """Model kullanıcının yazdığı adı olduğu gibi geçiriyor: "zeynep",
    "Zeynep", "ZEYNEP" — hepsi aynı kişi."""
    for yazim in ("Öteki", "öteki", " ÖTEKİ "):
        bulunan = svc.kisiyi_bul(db, yazim)
        assert bulunan and bulunan["id"] == OTEKI


def test_bos_mesaj_reddediliyor(db):
    with pytest.raises(svc.IletiHatasi):
        _ileti(db, mesaj="   ")


def test_cok_uzun_mesaj_reddediliyor(db):
    with pytest.raises(svc.IletiHatasi, match="uzun"):
        _ileti(db, mesaj="a" * (svc.AZAMI_UZUNLUK + 1))


# ── Zamanlama ────────────────────────────────────────────────────────────────

def test_vakit_verilmezse_hemen_gider(db):
    ileti = _ileti(db, saat_farki=None)

    assert ileti["hemen"] is True
    assert svc.vakti_gelenler(db, now=_an())


def test_gelecek_vakit_beklemede_kalir(db):
    _ileti(db, saat_farki=+3)

    assert svc.vakti_gelenler(db, now=_an()) == []
    assert len(svc.bekleyenler(db, SAHIP)) == 1


def test_gecmis_vakit_hemene_cevriliyor(db):
    """«saat 3'te söyle» derken 3'ü on dakika geçmişse kastedilen «hemen»dir;
    geçmişe mesaj göndermek diye bir şey yok."""
    ileti = _ileti(db, saat_farki=-2)

    assert ileti["hemen"] is True
    assert datetime.fromisoformat(ileti["iletilecek_at"]) == _an()


def test_bozuk_zaman_damgasi_iletiyi_dusurmuyor(db):
    """Modelin ürettiği bozuk bir tarih yüzünden mesaj kaybolmamalı."""
    ileti = svc.olustur(db, SAHIP, "Öteki", "merhaba", "yarın akşam", now=_an())

    assert ileti["hemen"] is True


def test_bayatlayan_ileti_gonderilmiyor(db):
    """Sunucu kapalı kaldıysa dört saat gecikmiş «akşam mesajı» iletmek,
    iletmemekten kötü — bağlamı çoktan geçmiş olur."""
    _ileti(db, saat_farki=-0.5)          # önce geçerli bir kayıt aç
    db.execute(
        "UPDATE iletiler SET iletilecek_at = ?",
        ((_an() - timedelta(minutes=VAZGECME_DAKIKA + 10)).isoformat(),),
    )

    assert svc.vakti_gelenler(db, now=_an()) == []


# ── İmzalı / imzasız kip ─────────────────────────────────────────────────────

def test_varsayilan_imzali(db):
    """⚠️ En önemli varsayılan: kaynağı gereksiz göstermek düzeltilebilir,
    göstermemek geri alınamaz. Belirtilmediyse imzalı gider."""
    assert _ileti(db)["imzasiz"] == 0


def test_imzasiz_istenirse_isaretleniyor(db):
    ileti = svc.olustur(db, SAHIP, "Öteki", "yağmur var", None, now=_an(), imzasiz=True)

    assert ileti["imzasiz"] == 1
    assert svc.vakti_gelenler(db, now=_an())[0]["imzasiz"] == 1


def test_kip_bekleyenler_listesinde_gorunuyor(db):
    """Kullanıcı bekleyen iletiye baktığında hangisinin kaynağı göstereceğini
    ayırt edebilmeli."""
    svc.olustur(db, SAHIP, "Öteki", "imzalı", (_an() + timedelta(hours=1)).isoformat(), now=_an())
    svc.olustur(db, SAHIP, "Öteki", "imzasız", (_an() + timedelta(hours=2)).isoformat(),
                now=_an(), imzasiz=True)

    assert [i["imzasiz"] for i in svc.bekleyenler(db, SAHIP)] == [0, 1]


def test_eski_kayitlar_imzali_sayiliyor(db):
    """Sütun sonradan eklendi (DEFAULT 0). Göç öncesi kayıtlar kaynağı
    GÖSTEREN biçimde gitmeli — sessizce imzasıza dönmemeli."""
    db.execute(
        "INSERT INTO iletiler (gonderen_id, alici_id, mesaj, iletilecek_at, created_at) "
        "VALUES (?, ?, 'eski', ?, ?)",
        (SAHIP, OTEKI, _an().isoformat(), _an().isoformat()),
    )

    assert svc.vakti_gelenler(db, now=_an())[0]["imzasiz"] == 0


# ── Gönderim ve iptal ────────────────────────────────────────────────────────

def test_iletilen_bir_daha_gonderilmiyor(db):
    ileti = _ileti(db)
    svc.iletildi(db, ileti["id"], now=_an())

    assert svc.vakti_gelenler(db, now=_an()) == []
    assert svc.bekleyenler(db, SAHIP) == []


def test_yalniz_gonderen_iptal_edebiliyor(db):
    """Alıcının bekleyen iletiden haberi bile yok; iptal hakkı gönderende."""
    ileti = _ileti(db, saat_farki=+3)

    assert svc.iptal(db, OTEKI, ileti["id"]) is None
    assert svc.iptal(db, SAHIP, ileti["id"]) is not None
    assert svc.bekleyenler(db, SAHIP) == []


def test_gonderilmis_ileti_iptal_edilemiyor(db):
    ileti = _ileti(db)
    svc.iletildi(db, ileti["id"], now=_an())

    assert svc.iptal(db, SAHIP, ileti["id"]) is None


def test_bekleyen_sinirini_asmaz(db):
    """Asistan, başkasına mesaj yağdırma aracına dönüşmemeli: alıcı bu
    mesajları istemedi."""
    for i in range(AZAMI_BEKLEYEN):
        _ileti(db, mesaj=f"mesaj {i}", saat_farki=+3)

    with pytest.raises(svc.IletiHatasi, match="sınır"):
        _ileti(db, mesaj="fazlalık", saat_farki=+3)


# ── Alıcının gerçekten gördüğü metin ─────────────────────────────────────────

def _gonder(db, monkeypatch, **kw):
    """`ileti_gonder`'i sahte Telegram ile çalıştırır, giden METNİ döner."""
    import asyncio

    import telegram_bot

    ileti = svc.olustur(db, SAHIP, "Öteki", kw.pop("mesaj", "merhaba"), None, now=_an(), **kw)
    db.commit()   # kullanici_getir kendi bağlantısını açıyor

    giden = []

    async def sahte_gonder(text, chat_id=None, **_):
        giden.append(text)
        return {"ok": True}

    monkeypatch.setattr(telegram_bot, "send_message", sahte_gonder)
    assert asyncio.run(telegram_bot.ileti_gonder(dict(ileti))) is True
    return giden[0]


def test_imzali_kaynagi_gosteriyor(db, monkeypatch):
    metin = _gonder(db, monkeypatch, mesaj="geç kalacağım")

    assert "Test" in metin                    # gönderenin adı
    assert "iletmemi istedi" in metin
    assert "geç kalacağım" in metin


def test_imzasiz_kaynagi_gostermiyor(db, monkeypatch):
    """İstenen özellik bu: mesaj asistanın kendi cümlesi gibi görünmeli."""
    metin = _gonder(db, monkeypatch, mesaj="şemsiyenizi alın", imzasiz=True)

    assert "Test" not in metin                # gönderenin adı GEÇMEMELİ
    assert "iletmemi istedi" not in metin
    assert "şemsiyenizi alın" in metin


def test_ileti_alicinin_baglamina_yaziliyor(db, monkeypatch):
    """Alıcı «neden böyle dedin?» diye cevap verirse asistan neden
    bahsedildiğini bilmeli — yoksa mesajın hiçbir izi kalmıyor."""
    from database import get_conversation

    _gonder(db, monkeypatch, mesaj="şemsiyenizi alın", imzasiz=True)

    gecmis = get_conversation("222")          # Öteki'nin chat_id'si
    assert gecmis and "şemsiyenizi alın" in gecmis[-1]["metin"]


def test_metin_kacisi_iki_kipte_de_yapiliyor(db, monkeypatch):
    """Kaçırılmamış bir `<` Telegram'da 400 döndürüp mesajı komple yutar."""
    for kw in ({}, {"imzasiz": True}):
        metin = _gonder(db, monkeypatch, mesaj="3 < 5 & doğru", **kw)
        assert "&lt;" in metin and "&amp;" in metin


def test_temizlik_gonderilmisi_ve_bayati_siliyor(db):
    gonderilmis = _ileti(db, mesaj="gitti")
    svc.iletildi(db, gonderilmis["id"], now=_an(gun_farki=-40))
    bekleyen = _ileti(db, mesaj="duruyor", saat_farki=+3)

    svc.temizle(db, now=_an())
    kalan = [r["id"] for r in db.execute("SELECT id FROM iletiler")]

    assert kalan == [bekleyen["id"]]

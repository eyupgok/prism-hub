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


def test_temizlik_gonderilmisi_ve_bayati_siliyor(db):
    gonderilmis = _ileti(db, mesaj="gitti")
    svc.iletildi(db, gonderilmis["id"], now=_an(gun_farki=-40))
    bekleyen = _ileti(db, mesaj="duruyor", saat_farki=+3)

    svc.temizle(db, now=_an())
    kalan = [r["id"] for r in db.execute("SELECT id FROM iletiler")]

    assert kalan == [bekleyen["id"]]

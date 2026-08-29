"""Asistanın üslubu: resmî hitap (siz) ve kişiye göre seslenme.

Üslup kolayca aşınan bir şey — yeni bir yanıt metni eklenirken "sen" kipine
kaymak çok kolay. Bu testler bunu yakalıyor.
"""

import ai_router
from modules.reminders import service as rem_svc
from conftest import SAHIP


# ── Hitap ────────────────────────────────────────────────────────────────────

def test_hitap_verilmisse_ad_ile_birlesir():
    assert ai_router.hitap_ifadesi("Eyüp", "Bey") == "Eyüp Bey"
    assert ai_router.hitap_ifadesi("Zeynep", "Hanım") == "Zeynep Hanım"


def test_hitap_yoksa_cinsiyetsiz_ifadeye_duser():
    """Addan cinsiyet çıkarmıyoruz: yanlış hitap gerçek bir kişiyi rahatsız
    eder, 'efendim' ise hiç kimseyi."""
    for bos in (None, "", "   "):
        assert ai_router.hitap_ifadesi("Eyüp", bos) == "efendim"


def test_hitap_yonergeye_giriyor():
    yonerge = ai_router.yonerge_metni("Zeynep", "Hanım")

    assert "Zeynep Hanım" in yonerge
    assert "SİZ diye hitap et" in yonerge


def test_hitap_kullanicidan_okunuyor(db):
    """Sütun sonradan eklendi; göç çalışmazsa hitap sessizce kaybolurdu."""
    db.execute("UPDATE users SET hitap = 'Bey' WHERE id = ?", (SAHIP,))
    db.commit()

    from auth import kullanici_getir

    assert kullanici_getir(SAHIP)["hitap"] == "Bey"


# ── Sabit metinler ───────────────────────────────────────────────────────────
# Kullanıcının gördüğü metinlerin çoğu modelden değil koddan geliyor. Yönerge
# resmîyken bu metinler "sen" kipinde kalırsa ton ortadan ikiye bölünür.

def test_yanit_metinleri_sen_kipinde_degil():
    import inspect
    import re

    kaynak = inspect.getsource(ai_router)
    # Kelime sınırıyla aranıyor: "ekleyebilirsiniz" içinde "ekleyebilirsin"
    # geçtiği için düz alt dize araması resmî hâli de yakalıyordu.
    yasak = ["dener misin", "yazar mısın", "eder misin", "ekleyebilirsin",
             "Onaylıyor musun", "Seni tanıyamadım"]

    bulunan = [y for y in yasak if re.search(rf"{re.escape(y)}\b", kaynak)]
    assert not bulunan, f"samimi kipte kalmış ifadeler: {bulunan}"


def test_onay_metni_resmi():
    """Silme onayı en sık görülen metinlerden biri."""
    import inspect

    assert "Onaylıyor musunuz?" in inspect.getsource(ai_router)


# ── Kendiliğinden gelen mesajlar ─────────────────────────────────────────────
# Üslup artık ÜÇ yerden geliyor (bkz. CLAUDE.md "Asistanın Üslubu"): yönerge,
# sabit metinler ve gözlem katmanının kendi yönergesi. Biri değişip diğeri
# kalırsa ton ortadan bölünür.

def test_gozlem_yonergesi_siz_kipini_koruyor():
    from modules.gozlem.service import YONERGE

    yonerge = YONERGE.format(ad="Eyüp", hitap="Eyüp Bey",
                             now="29.08.2026 09:15 (Cumartesi)",
                             hafiza="", sinyaller="- [DURUM] [x] y")

    assert "Eyüp Bey" in yonerge
    assert "**Daima SİZ**" in yonerge


def test_gozlem_yonergesi_memur_uslubunu_yasakliyor():
    """İlk gerçek turda model "arızası tespit edildi ... lütfen kontrol
    ediniz" yazdı — bilgi doğruydu ama bir bakanlık yazısı gibiydi. Soyut
    üslup tarifi yetmiyor, somut karşı örnek gerekiyor."""
    from modules.gozlem.service import YONERGE

    for kural in ("tespit edildi", "Lütfen", "İç adları kullanma"):
        assert kural in YONERGE, kural

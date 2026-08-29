"""Gözlem katmanı: hafıza, sinyaller, susma bütçesi, itiraz.

Bu testlerin çoğu asistanın **konuşmadığını** doğruluyor. Sebebi şu: gözlem
döngüsü, asistanın kullanıcının istemediği bir mesajı gönderebildiği tek
mekanizma. Çok konuşan asistan susturulur, susturulan asistan ölür — yani
buradaki asıl kırılganlık "bir şeyi kaçırmak" değil, "gereksiz konuşmak".

⚠️ `db` fikstürü işlemi test bitene kadar commit etmiyor. `service.tur()`
kendi bağlantısını açtığı için, ona görünmesi gereken her yazmadan sonra
`db.commit()` çağrılıyor.
"""

import json
from datetime import datetime, timedelta

import pytest
import pytz

import ai_router
from conftest import OTEKI, SAHIP
from modules.gozlem import hafiza, service, sinyaller, takip
from modules.gozlem.models import AZAMI_ACIK_TAKIP, AZAMI_BILGI, TAKIP_BAYATLAMA_GUNU
from modules.reminders import service as rem

TZ = pytz.timezone("Europe/Istanbul")


def _an(saat=12, gun_farki=0):
    """Deterministik bir an — testler günün saatine göre davranış değiştirmesin."""
    return TZ.localize(datetime(2026, 9, 15, saat, 0)) + timedelta(days=gun_farki)


def _harcama(db, owner, tutar, kategori="yemek", tarih=None, kaynak="manual", source_at=None):
    db.execute(
        "INSERT INTO expenses (owner_id, amount, category, description, expense_date, "
        "created_at, source, source_at) VALUES (?, ?, ?, '', ?, ?, ?, ?)",
        (owner, tutar, kategori, tarih or _an().strftime("%Y-%m-%d"),
         _an().isoformat(), kaynak, source_at),
    )


def _gunluk_kayit(db, owner, karar, anahtar=None, ne_zaman=None):
    db.execute(
        "INSERT INTO gozlem_gunlugu (owner_id, karar, anahtar, mesaj, sebep, sinyaller, created_at) "
        "VALUES (?, ?, ?, '', '', '[]', ?)",
        (owner, karar, anahtar, (ne_zaman or _an()).isoformat()),
    )


# ── Hafıza ───────────────────────────────────────────────────────────────────

def test_bilgi_eklenir_ve_listelenir(db):
    hafiza.ekle(db, SAHIP, "Elazığ'da yaşıyor.", "olgu")
    bilgiler = hafiza.listele(db, SAHIP)

    assert [b["icerik"] for b in bilgiler] == ["Elazığ'da yaşıyor."]


def test_ayni_bilgi_ikinci_kez_yazilmaz(db):
    """Tekrar yazmak yerine teyit damgası yenileniyor — aynı şeyin tekrar
    söylenmesi o bilginin hâlâ geçerli olduğunun işareti."""
    hafiza.ekle(db, SAHIP, "Kahveyi sever.", "tercih")

    assert hafiza.ekle(db, SAHIP, "Kahveyi sever.", "tercih") is None
    assert len(hafiza.listele(db, SAHIP)) == 1
    assert hafiza.listele(db, SAHIP)[0]["son_teyit_at"] is not None


def test_bilgi_kisiye_ozel(db):
    hafiza.ekle(db, SAHIP, "Elazığ'da yaşıyor.")
    hafiza.ekle(db, OTEKI, "İstanbul'da yaşıyor.")

    assert len(hafiza.listele(db, SAHIP)) == 1
    assert hafiza.listele(db, OTEKI)[0]["icerik"] == "İstanbul'da yaşıyor."


def test_suresi_dolan_bilgi_gorunmez_ve_silinir(db):
    """Geçici bilgiler tarihiyle giriyor. Olmasaydı asistan aylar sonra hâlâ
    'sınav haftanız' derdi."""
    dun = (datetime.now(TZ) - timedelta(days=1)).strftime("%Y-%m-%d")
    hafiza.ekle(db, SAHIP, "Bu hafta sınav haftası.", "durum", gecerlilik=dun)
    hafiza.ekle(db, SAHIP, "Elazığ'da yaşıyor.", "olgu")

    assert [b["icerik"] for b in hafiza.listele(db, SAHIP)] == ["Elazığ'da yaşıyor."]

    hafiza.temizle(db)
    kalan = db.execute("SELECT COUNT(*) c FROM hafiza WHERE owner_id = ?", (SAHIP,)).fetchone()
    assert kalan["c"] == 1


def test_sinir_asilinca_teyit_edilmemisler_once_dusuyor(db):
    for i in range(AZAMI_BILGI + 5):
        hafiza.ekle(db, SAHIP, f"Bilgi {i}.")
    # Bir tanesi tekrar söylendi → teyitli, budamada en sona kalmalı
    hafiza.ekle(db, SAHIP, "Bilgi 0.")

    hafiza.temizle(db)
    kalanlar = [b["icerik"] for b in hafiza.listele(db, SAHIP)]

    assert len(kalanlar) == AZAMI_BILGI
    assert "Bilgi 0." in kalanlar


def test_bos_hafiza_yonergeye_hicbir_sey_eklemez(db):
    """Boş bir başlık ('BİLDİKLERİN: yok') modele orayı doldurma baskısı yapıyor."""
    assert hafiza.yonergeye(db, SAHIP) == ""

    hafiza.ekle(db, SAHIP, "Elazığ'da yaşıyor.")
    assert "Elazığ'da yaşıyor." in hafiza.yonergeye(db, SAHIP)


def test_hafiza_yonergeye_giriyor(db):
    hafiza.ekle(db, SAHIP, "Uzun mesaj sevmiyor.")
    db.commit()

    yonerge = ai_router.yonerge_metni("Eyüp", "Bey", ai_router._hafiza(SAHIP))

    assert "Uzun mesaj sevmiyor." in yonerge


# ── Sinyaller ────────────────────────────────────────────────────────────────

def test_harcama_sessizligi_gecmis_yoksa_uyarmaz(db):
    """Hiç kurulmamış bir özellik 'bozuk' değildir — telefonda otomatik yakalama
    hiç çalışmamışsa sessizliği arıza sayma."""
    _harcama(db, SAHIP, 100, kaynak="manual")

    assert sinyaller.harcama_sessizligi(db, SAHIP, _an()) is None


def test_harcama_sessizligi_akis_kesilince_uyarir(db):
    """Telefondaki dinleyici sessizce ölebiliyor; kimse fark etmiyor."""
    eski = _an(gun_farki=-10)
    for _ in range(sinyaller.SESSIZLIK_ASGARI_GECMIS):
        _harcama(db, SAHIP, 50, kaynak="notification", source_at=eski.isoformat())

    s = sinyaller.harcama_sessizligi(db, SAHIP, _an())

    assert s and s["anahtar"] == "harcama_sessizligi"
    assert s["agirlik"] == 3
    assert "10 gün önce" in s["kanit"]


def test_harcama_sessizligi_ariza_olarak_isaretli(db):
    """İlk gerçek turda model bunu görüp 'kullanıcı zaten biliyor olabilir'
    diyerek sustu. Arızanın tanımı gereği kullanıcı bilmiyor — bilseydi
    düzeltmişti. Kategori, modelin susma eşiğini tersine çeviriyor."""
    eski = _an(gun_farki=-10)
    for _ in range(sinyaller.SESSIZLIK_ASGARI_GECMIS):
        _harcama(db, SAHIP, 50, kaynak="notification", source_at=eski.isoformat())

    assert sinyaller.harcama_sessizligi(db, SAHIP, _an())["kategori"] == sinyaller.ARIZA


def test_diger_sinyaller_durum(db):
    """Ağırlıkla karıştırılmamalı: butce_asildi da ağırlık 3 ama arıza değil —
    kullanıcı %80'de zaten uyarı almış oluyor."""
    from modules.expenses import service as exp

    exp.set_budget(db, SAHIP, "yemek", 1000)
    _harcama(db, SAHIP, 1200, "yemek")

    s = sinyaller.butce(db, SAHIP, _an())[0]
    assert s["agirlik"] == 3
    assert s["kategori"] == sinyaller.DURUM


def test_harcama_sessizligi_akis_surerken_susar(db):
    dun = _an(gun_farki=-1)
    for _ in range(sinyaller.SESSIZLIK_ASGARI_GECMIS):
        _harcama(db, SAHIP, 50, kaynak="notification", source_at=dun.isoformat())

    assert sinyaller.harcama_sessizligi(db, SAHIP, _an()) is None


def test_butce_hizi_ayin_basinda_hizli_harcamayi_yakalar(db):
    """Asıl değerli uyarı bu: 'aşıldı' bitmiş bir iş, 'bu hızla biter' önlenebilir."""
    from modules.expenses import service as exp

    exp.set_budget(db, SAHIP, "yemek", 3000)
    ayin_ucu = _an(saat=12).replace(day=3)
    _harcama(db, SAHIP, 2000, "yemek", tarih=ayin_ucu.strftime("%Y-%m-%d"))

    bulunan = sinyaller.butce(db, SAHIP, ayin_ucu)

    assert [s["anahtar"] for s in bulunan] == ["butce_hizi:yemek"]
    assert "%67" in bulunan[0]["kanit"]


def test_butce_normal_hizda_susar(db):
    from modules.expenses import service as exp

    exp.set_budget(db, SAHIP, "yemek", 3000)
    ayin_onbesi = _an(saat=12).replace(day=15)
    _harcama(db, SAHIP, 1400, "yemek", tarih=ayin_onbesi.strftime("%Y-%m-%d"))

    assert sinyaller.butce(db, SAHIP, ayin_onbesi) == []


def test_butce_asilinca_ayri_sinyal(db):
    from modules.expenses import service as exp

    exp.set_budget(db, SAHIP, "yemek", 1000)
    _harcama(db, SAHIP, 1200, "yemek")

    bulunan = sinyaller.butce(db, SAHIP, _an())

    assert bulunan[0]["anahtar"] == "butce_asildi:yemek"
    assert bulunan[0]["agirlik"] == 3


def test_gorev_yigilmasi_yogun_gunu_bulur(db):
    hedef = _an(gun_farki=2)
    for i in range(sinyaller.YIGILMA_ESIGI):
        rem.create_reminder(db, SAHIP, f"İş {i}", (hedef + timedelta(hours=i)).isoformat())

    bulunan = sinyaller.gorev_yigilmasi(db, SAHIP, _an())

    assert len(bulunan) == 1
    assert bulunan[0]["anahtar"] == f"gorev_yigilmasi:{hedef.strftime('%Y-%m-%d')}"


def test_gorev_yigilmasi_esigin_altinda_susar(db):
    hedef = _an(gun_farki=2)
    for i in range(sinyaller.YIGILMA_ESIGI - 1):
        rem.create_reminder(db, SAHIP, f"İş {i}", (hedef + timedelta(hours=i)).isoformat())

    assert sinyaller.gorev_yigilmasi(db, SAHIP, _an()) == []


def test_gecikmis_gorevler_anahtari_sayidan_bagimsiz(db):
    """Anahtar konu kimliği. Sayıya bağlasaydık her yeni gecikme 'yeni konu'
    sanılır, asistan aynı şeyi her gün söylerdi."""
    for i in range(sinyaller.GECIKME_ESIGI):
        rem.create_reminder(db, SAHIP, f"Eski {i}", _an(gun_farki=-5).isoformat())

    s = sinyaller.gecikmis_gorevler(db, SAHIP, _an())
    assert s["anahtar"] == "gecikmis_gorevler"

    rem.create_reminder(db, SAHIP, "Bir tane daha", _an(gun_farki=-5).isoformat())
    assert sinyaller.gecikmis_gorevler(db, SAHIP, _an())["anahtar"] == "gecikmis_gorevler"


def test_gecikmis_gorevler_tekrarlayanlari_saymaz(db):
    """Tekrarlayanlar zaten `reschedule_overdue_recurring` ile ötelenmiş oluyor."""
    for i in range(sinyaller.GECIKME_ESIGI + 2):
        rem.create_reminder(db, SAHIP, f"Günlük {i}", _an(gun_farki=-5).isoformat(),
                            recurrence="daily")

    assert sinyaller.gecikmis_gorevler(db, SAHIP, _an()) is None


def test_inatci_gorev_cok_ertelenmisi_bulur(db):
    r = rem.create_reminder(db, SAHIP, "Vergi ödemesi", _an(gun_farki=1).isoformat())
    db.execute("UPDATE reminders SET snooze_count = ? WHERE id = ?",
               (sinyaller.INAT_ERTELEME, r["id"]))

    bulunan = sinyaller.inatci_gorev(db, SAHIP, _an())

    assert bulunan[0]["anahtar"] == f"inatci_gorev:{r['id']}"
    assert "Vergi ödemesi" in bulunan[0]["kanit"]


def test_ev_halki_sadece_onemli_gorevleri_bildirir(db):
    rem.create_reminder(db, OTEKI, "Sınav", _an(saat=18).isoformat(), priority=1)
    rem.create_reminder(db, OTEKI, "Çamaşır", _an(saat=19).isoformat(), priority=4)

    bulunan = sinyaller.ev_halki(db, SAHIP, _an(saat=9))

    assert len(bulunan) == 1
    assert "Sınav" in bulunan[0]["kanit"]


def test_olagandisi_harcama_kucuk_tutarlarda_susar(db):
    """Kat hesabı küçük tutarlarda anlamsız: 20 TL'nin 3 katı da 60 TL."""
    for i in range(1, 15):
        _harcama(db, SAHIP, 10, tarih=_an(gun_farki=-i).strftime("%Y-%m-%d"))
    _harcama(db, SAHIP, 100)

    assert sinyaller.olagandisi_harcama(db, SAHIP, _an()) is None


def test_olagandisi_harcama_buyuk_sicramayi_yakalar(db):
    for i in range(1, 15):
        _harcama(db, SAHIP, 200, tarih=_an(gun_farki=-i).strftime("%Y-%m-%d"))
    _harcama(db, SAHIP, 3000)

    s = sinyaller.olagandisi_harcama(db, SAHIP, _an())

    assert s and s["anahtar"].startswith("olagandisi_harcama:")


# ── Takip ────────────────────────────────────────────────────────────────────
# Takip "yarın dişçiye gidiyorum" gibi hiçbir tabloya girmeyen bir cümleyi
# ertesi akşam sorulacak bir soruya çeviriyor.

def _takip(db, owner=SAHIP, konu="dişçi randevusu", saat_farki=0):
    an = datetime.now(TZ) + timedelta(hours=saat_farki)
    return takip.ekle(db, owner, konu, f"{konu} nasıl geçti?", an.isoformat())


def test_takip_vakti_gelmeden_sorulmaz(db):
    _takip(db, saat_farki=+5)

    assert takip.acik_takipler(db, SAHIP)          # kayıt duruyor
    assert takip.vakti_gelenler(db, SAHIP, datetime.now(TZ)) == []


def test_takip_vakti_gelince_sinyale_donuyor(db):
    t = _takip(db, saat_farki=-1)

    bulunan = sinyaller.bekleyen_takip(db, SAHIP, datetime.now(TZ))

    assert len(bulunan) == 1
    assert bulunan[0]["anahtar"] == f"takip:{t['id']}"
    assert bulunan[0]["kategori"] == sinyaller.TAKIP
    assert "nasıl geçti?" in bulunan[0]["kanit"]


def test_sorulmus_takip_tekrar_sorulmaz(db):
    t = _takip(db, saat_farki=-1)
    takip.soruldu(db, t["id"])

    assert takip.vakti_gelenler(db, SAHIP, datetime.now(TZ)) == []
    assert takip.acik_takipler(db, SAHIP) == []


def test_bayatlayan_takip_dusuyor(db):
    """Geç kalmış soru sorulmamış sorudan kötü: 'geçen hafta dişçi nasıl
    geçti?' ilgi değil dalgınlık gösterir."""
    _takip(db, saat_farki=-24 * (TAKIP_BAYATLAMA_GUNU + 1))

    assert takip.acik_takipler(db, SAHIP) == []
    assert takip.vakti_gelenler(db, SAHIP, datetime.now(TZ)) == []

    takip.temizle(db)
    assert db.execute("SELECT COUNT(*) c FROM takipler").fetchone()["c"] == 0


def test_ayni_konu_iki_kez_alinmaz(db):
    _takip(db, konu="dişçi randevusu")

    assert _takip(db, konu="dişçi randevusu") is None
    assert len(takip.acik_takipler(db, SAHIP)) == 1


def test_takip_sinirini_asmaz(db):
    """Her konuşmadan birkaç takip çıkarsa asistan sorgu hâkimi olur."""
    for i in range(AZAMI_ACIK_TAKIP + 3):
        _takip(db, konu=f"konu {i}", saat_farki=+1)

    assert len(takip.acik_takipler(db, SAHIP)) == AZAMI_ACIK_TAKIP


def test_bozuk_zaman_damgasi_kayit_acmaz(db):
    assert takip.ekle(db, SAHIP, "konu", "soru?", "yarın akşam") is None
    assert takip.ekle(db, SAHIP, "", "soru?", datetime.now(TZ).isoformat()) is None


def test_takip_kisiye_ozel(db):
    _takip(db, owner=SAHIP, konu="dişçi", saat_farki=-1)
    _takip(db, owner=OTEKI, konu="sınav", saat_farki=-1)

    bulunan = sinyaller.bekleyen_takip(db, SAHIP, datetime.now(TZ))

    assert len(bulunan) == 1
    assert "dişçi" in bulunan[0]["kanit"]


# ── Susma bütçesi ────────────────────────────────────────────────────────────

@pytest.fixture()
def sinyalli(monkeypatch):
    """Sinyal toplamayı sabitler — bütçe testleri sinyal üretimine bağlı kalmasın."""
    async def sahte(conn, owner_id, user, now=None):
        return [{"anahtar": "test_konu", "kanit": "bir şeyler oldu", "agirlik": 2}]

    monkeypatch.setattr(sinyaller, "topla", sahte)


@pytest.fixture()
def konusan_model(monkeypatch):
    """Groq'u sabitler: her zaman 'söyle' der. Gönderilen mesajlar listeye düşer."""
    gonderilen = []

    async def sahte_model(messages, **kw):
        return {"soyle": True, "anahtar": "test_konu",
                "mesaj": "Efendim, dikkatinizi çekmek istediğim bir şey var.",
                "sebep": "deneme"}

    async def sahte_gonder(text, chat_id=None, **kw):
        gonderilen.append((chat_id, text))
        return {}

    import groq_client
    import telegram_bot

    monkeypatch.setattr(groq_client, "complete_json", sahte_model)
    monkeypatch.setattr(telegram_bot, "send_message", sahte_gonder)
    return gonderilen


def _ac(db, owner=SAHIP, sinir=3):
    db.execute("UPDATE users SET gozlem_sinir = ? WHERE id = ?", (sinir, owner))
    db.commit()


@pytest.mark.asyncio
async def test_kapali_kullaniciya_asla_mesaj_gitmez(db, sinyalli, konusan_model):
    """En önemli güvenlik özelliği: sütun sıfır başlıyor, yani bu sürüm
    yayına alındığında kimseye sürpriz bildirim gitmiyor."""
    db.commit()          # gozlem_sinir varsayılan 0

    sonuc = await service.tur(SAHIP, now=_an())

    assert sonuc["karar"] == "sustu"
    assert "kapalı" in sonuc["sebep"]
    assert konusan_model == []


@pytest.mark.asyncio
async def test_sessiz_saatte_konusmaz(db, sinyalli, konusan_model):
    _ac(db)

    for saat in (23, 2, 7):
        sonuc = await service.tur(SAHIP, now=_an(saat=saat))
        assert sonuc["sebep"] == "sessiz saat", saat

    assert konusan_model == []


@pytest.mark.asyncio
async def test_gunluk_sinir_dolunca_susar(db, sinyalli, konusan_model):
    _ac(db, sinir=3)
    for _ in range(3):
        _gunluk_kayit(db, SAHIP, "konustu", ne_zaman=_an(saat=8))
    db.commit()

    sonuc = await service.tur(SAHIP, now=_an(saat=20))

    assert "günlük sınır dolu" in sonuc["sebep"]
    assert konusan_model == []


@pytest.mark.asyncio
async def test_asgari_ara_dolmadan_konusmaz(db, sinyalli, konusan_model):
    """Günlük sınır tek başına yetmiyor: üç mesajın üçü de arka arkaya gelirse
    sınır tutulmuş olur ama kullanıcı yine bombardımana uğrar."""
    _ac(db, sinir=3)
    _gunluk_kayit(db, SAHIP, "konustu", ne_zaman=_an(saat=12))
    db.commit()

    sonuc = await service.tur(SAHIP, now=_an(saat=13))

    assert "asgari" in sonuc["sebep"]
    assert konusan_model == []


@pytest.mark.asyncio
async def test_yakinda_konusulan_konu_tekrar_secilmez(db, sinyalli, konusan_model):
    _ac(db)
    _gunluk_kayit(db, SAHIP, "konustu", anahtar="test_konu", ne_zaman=_an(gun_farki=-1))
    db.commit()

    sonuc = await service.tur(SAHIP, now=_an())

    assert "konuşuldu" in sonuc["sebep"]
    assert konusan_model == []


@pytest.mark.asyncio
async def test_bekleme_suresi_gecince_konu_yeniden_acilabilir(db, sinyalli, konusan_model):
    _ac(db)
    eski = _an(gun_farki=-(service.KONU_BEKLEME_GUNU + 1))
    _gunluk_kayit(db, SAHIP, "konustu", anahtar="test_konu", ne_zaman=eski)
    db.commit()

    sonuc = await service.tur(SAHIP, now=_an())

    assert sonuc["karar"] == "konustu"


@pytest.mark.asyncio
async def test_sinyal_yoksa_model_hic_cagrilmaz(db, monkeypatch, konusan_model):
    """Turların çoğu burada bitiyor — maliyetin önemsiz olmasının sebebi bu."""
    cagrildi = []

    async def bos(conn, owner_id, user, now=None):
        return []

    async def sayan(messages, **kw):
        cagrildi.append(1)
        return {"soyle": False}

    import groq_client
    monkeypatch.setattr(sinyaller, "topla", bos)
    monkeypatch.setattr(groq_client, "complete_json", sayan)
    _ac(db)

    sonuc = await service.tur(SAHIP, now=_an())

    assert sonuc["sebep"] == "sinyal yok"
    assert cagrildi == []


@pytest.mark.asyncio
async def test_konusunca_gunluge_yazilir(db, sinyalli, konusan_model):
    _ac(db)

    sonuc = await service.tur(SAHIP, now=_an())

    assert sonuc["karar"] == "konustu"
    assert len(konusan_model) == 1

    satir = db.execute(
        "SELECT * FROM gozlem_gunlugu WHERE owner_id = ? ORDER BY id DESC LIMIT 1", (SAHIP,)
    ).fetchone()
    assert satir["karar"] == "konustu"
    assert satir["anahtar"] == "test_konu"
    assert json.loads(satir["sinyaller"]) == ["test_konu"]


@pytest.mark.asyncio
async def test_sustugu_turlar_da_gunluge_yazilir(db, sinyalli, konusan_model):
    """Bu satırlar olmadan eşikleri ayarlamanın hiçbir yolu yok."""
    _ac(db)
    _gunluk_kayit(db, SAHIP, "konustu", ne_zaman=_an(saat=12))
    db.commit()

    await service.tur(SAHIP, now=_an(saat=13))

    satir = db.execute(
        "SELECT * FROM gozlem_gunlugu WHERE owner_id = ? ORDER BY id DESC LIMIT 1", (SAHIP,)
    ).fetchone()
    assert satir["karar"] == "sustu"
    assert "asgari" in satir["sebep"]


@pytest.mark.asyncio
async def test_kuru_tur_gondermez_ve_gunluge_yazmaz(db, sinyalli, konusan_model):
    """Kuru turun bütçeyi harcaması ya da konu sayacını başlatması, denemeyi
    anlamsız kılardı."""
    _ac(db)

    sonuc = await service.tur(SAHIP, kuru=True, now=_an())

    assert sonuc["karar"] == "konustu"
    assert sonuc["gonderildi"] is False
    assert konusan_model == []

    adet = db.execute("SELECT COUNT(*) c FROM gozlem_gunlugu").fetchone()["c"]
    assert adet == 0


@pytest.mark.asyncio
async def test_kapali_kullanici_kuru_turda_denenebilir(db, sinyalli, konusan_model):
    """Açmadan önce ne olacağını görebilmek gerekiyor."""
    db.commit()          # gozlem_sinir = 0

    sonuc = await service.tur(SAHIP, kuru=True, now=_an())

    assert sonuc["karar"] == "konustu"
    assert konusan_model == []


@pytest.mark.asyncio
async def test_sinyal_turu_yonergeye_giriyor(db, monkeypatch):
    """Model, susma eşiğini ancak türü görürse ayarlayabilir."""
    gorulen_yonerge = []

    async def ariza_veren(conn, owner_id, user, now=None):
        return [{"anahtar": "bozuk_sey", "kanit": "bir şey durmuş",
                 "agirlik": 3, "kategori": sinyaller.ARIZA}]

    async def yakalayan(messages, **kw):
        gorulen_yonerge.append(messages[0]["content"])
        return {"soyle": False, "sebep": "deneme"}

    import groq_client
    monkeypatch.setattr(sinyaller, "topla", ariza_veren)
    monkeypatch.setattr(groq_client, "complete_json", yakalayan)
    _ac(db)

    await service.tur(SAHIP, now=_an())

    assert "[ARIZA] [bozuk_sey]" in gorulen_yonerge[0]
    assert "varsayılan\n  **söylemektir**" in gorulen_yonerge[0]


@pytest.mark.asyncio
async def test_kategorisiz_sinyal_durum_sayilir(db, sinyalli, monkeypatch):
    """`sinyalli` fikstürü kategori vermiyor — eski biçimli bir sinyal
    yönergeyi kırmamalı."""
    gorulen = []

    async def yakalayan(messages, **kw):
        gorulen.append(messages[0]["content"])
        return {"soyle": False, "sebep": "deneme"}

    import groq_client
    monkeypatch.setattr(groq_client, "complete_json", yakalayan)
    _ac(db)

    await service.tur(SAHIP, now=_an())

    assert "[DURUM] [test_konu]" in gorulen[0]


@pytest.mark.asyncio
async def test_takip_sorulunca_isaretleniyor(db, monkeypatch):
    """Uçtan uca: bekleyen takip → sinyal → mesaj → bir daha sorulmaz."""
    t = _takip(db, saat_farki=-1)
    _ac(db)

    async def soyleyen(messages, **kw):
        return {"soyle": True, "anahtar": f"takip:{t['id']}",
                "mesaj": "Dişçi nasıl geçti, efendim?", "sebep": "takip"}

    gonderilen = []

    async def sahte_gonder(text, chat_id=None, **kw):
        gonderilen.append(text)
        return {}

    import groq_client
    import telegram_bot
    monkeypatch.setattr(groq_client, "complete_json", soyleyen)
    monkeypatch.setattr(telegram_bot, "send_message", sahte_gonder)

    sonuc = await service.tur(SAHIP, now=_an())

    assert sonuc["karar"] == "konustu"
    assert "Dişçi nasıl geçti" in gonderilen[0]

    satir = db.execute("SELECT soruldu_at FROM takipler WHERE id = ?", (t["id"],)).fetchone()
    assert satir["soruldu_at"] is not None


@pytest.mark.asyncio
async def test_takip_gonderilemezse_sorulmus_sayilmaz(db, monkeypatch):
    """Telegram'a ulaşamadıysak soru sorulmamıştır; bir sonraki turda
    yeniden denenmeli."""
    t = _takip(db, saat_farki=-1)
    _ac(db)

    async def soyleyen(messages, **kw):
        return {"soyle": True, "anahtar": f"takip:{t['id']}", "mesaj": "Soru?", "sebep": ""}

    async def patlayan(text, chat_id=None, **kw):
        raise RuntimeError("Telegram ulaşılamıyor")

    import groq_client
    import telegram_bot
    monkeypatch.setattr(groq_client, "complete_json", soyleyen)
    monkeypatch.setattr(telegram_bot, "send_message", patlayan)

    with pytest.raises(RuntimeError):
        await service.tur(SAHIP, now=_an())

    satir = db.execute("SELECT soruldu_at FROM takipler WHERE id = ?", (t["id"],)).fetchone()
    assert satir["soruldu_at"] is None


@pytest.mark.asyncio
async def test_uydurma_anahtar_gecerliye_dusuyor(db, sinyalli, monkeypatch):
    """Model olmayan bir anahtar döndürürse konu bekleme sayacı yanlış yere
    işler ve aynı şey ertesi gün tekrar söylenir."""
    async def uyduran(messages, **kw):
        return {"soyle": True, "anahtar": "olmayan_konu", "mesaj": "Bir şey.", "sebep": ""}

    async def yut(text, chat_id=None, **kw):
        return {}

    import groq_client
    import telegram_bot
    monkeypatch.setattr(groq_client, "complete_json", uyduran)
    monkeypatch.setattr(telegram_bot, "send_message", yut)
    _ac(db)

    sonuc = await service.tur(SAHIP, now=_an())

    assert sonuc["anahtar"] == "test_konu"


@pytest.mark.asyncio
async def test_bos_mesaj_gonderilmez(db, sinyalli, monkeypatch):
    async def bos_donen(messages, **kw):
        return {"soyle": True, "anahtar": "test_konu", "mesaj": "   ", "sebep": ""}

    gonderilen = []

    async def sahte_gonder(text, chat_id=None, **kw):
        gonderilen.append(text)
        return {}

    import groq_client
    import telegram_bot
    monkeypatch.setattr(groq_client, "complete_json", bos_donen)
    monkeypatch.setattr(telegram_bot, "send_message", sahte_gonder)
    _ac(db)

    sonuc = await service.tur(SAHIP, now=_an())

    assert sonuc["karar"] == "sustu"
    assert gonderilen == []


@pytest.mark.asyncio
async def test_mesaj_kacisla_gonderiliyor(db, sinyalli, monkeypatch):
    """Kaçırılmış bir '<' Telegram'da 400 döndürüp mesajı sessizce yutar."""
    async def html_donen(messages, **kw):
        return {"soyle": True, "anahtar": "test_konu",
                "mesaj": "5 < 10 & bu <b>kalın</b> değil", "sebep": ""}

    gonderilen = []

    async def sahte_gonder(text, chat_id=None, **kw):
        gonderilen.append(text)
        return {}

    import groq_client
    import telegram_bot
    monkeypatch.setattr(groq_client, "complete_json", html_donen)
    monkeypatch.setattr(telegram_bot, "send_message", sahte_gonder)
    _ac(db)

    await service.tur(SAHIP, now=_an())

    assert "&lt;" in gonderilen[0]
    assert "<b>" not in gonderilen[0]


@pytest.mark.asyncio
async def test_mesaj_sahibinin_sohbetine_gidiyor(db, sinyalli, konusan_model):
    _ac(db, owner=OTEKI)

    await service.tur(OTEKI, now=_an())

    assert konusan_model[0][0] == "222"       # conftest: OTEKI'nin chat_id'si


# ── İtiraz ───────────────────────────────────────────────────────────────────

def test_cakisan_saatte_itiraz_eder(db):
    rem.create_reminder(db, SAHIP, "Sınav", _an(saat=14).isoformat())
    yeni = rem.create_reminder(db, SAHIP, "Toplantı", _an(saat=14).isoformat())

    itiraz = ai_router._itiraz(db, SAHIP, yeni)

    assert "Sınav" in itiraz
    assert "14:00" in itiraz


def test_uzak_saatte_itiraz_yok(db):
    rem.create_reminder(db, SAHIP, "Sınav", _an(saat=9).isoformat())
    yeni = rem.create_reminder(db, SAHIP, "Toplantı", _an(saat=18).isoformat())

    assert ai_router._itiraz(db, SAHIP, yeni) == ""


def test_gun_yigilinca_uyarir(db):
    """Saatler çakışmıyor ama gün doldu."""
    for i in range(ai_router.GUN_YIGILMA_ESIGI - 1):
        rem.create_reminder(db, SAHIP, f"İş {i}", _an(saat=8 + i * 2).isoformat())
    yeni = rem.create_reminder(db, SAHIP, "Bir daha", _an(saat=20).isoformat())

    itiraz = ai_router._itiraz(db, SAHIP, yeni)

    assert f"{ai_router.GUN_YIGILMA_ESIGI}. göreviniz" in itiraz


def test_baskasinin_gorevi_itiraza_sayilmaz(db):
    """Sahiplik kuralı burada da geçerli: karşı tarafın takvimi seni bağlamaz."""
    rem.create_reminder(db, OTEKI, "Onun sınavı", _an(saat=14).isoformat())
    yeni = rem.create_reminder(db, SAHIP, "Toplantı", _an(saat=14).isoformat())

    assert ai_router._itiraz(db, SAHIP, yeni) == ""
